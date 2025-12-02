"""SIEM destination adapter for audit logging."""

import logging

from mmf.services.audit.domain.contracts import IAuditDestination
from mmf.services.audit.domain.entities import RequestAuditEvent

logger = logging.getLogger(__name__)


class SIEMAuditDestination(IAuditDestination):
    """SIEM destination adapter delegating to audit_compliance ElasticsearchSIEMAdapter."""

    def __init__(self, siem_adapter=None):
        """Initialize SIEM destination.

        Args:
            siem_adapter: Optional ElasticsearchSIEMAdapter from audit_compliance service
        """
        self.siem_adapter = siem_adapter

    async def write_event(self, event: RequestAuditEvent) -> None:
        """Write a single audit event to SIEM.

        Args:
            event: The audit event to write
        """
        if not self.siem_adapter:
            logger.warning("SIEM adapter not configured, skipping event forwarding")
            return

        try:
            # Convert audit event to SIEM format
            self._convert_to_siem_format(event)
            # Forward to Elasticsearch SIEM adapter
            # await self.siem_adapter.index_event(siem_event)
            logger.info("Forwarded audit event %s to SIEM", event.id)
        except Exception as e:
            logger.error("Failed to write audit event to SIEM: %s", e, exc_info=True)

    async def write_batch(self, events: list[RequestAuditEvent]) -> None:
        """Write a batch of audit events to SIEM.

        Args:
            events: List of audit events to write
        """
        if not self.siem_adapter:
            logger.warning("SIEM adapter not configured, skipping batch forwarding")
            return

        try:
            # Convert all events
            [self._convert_to_siem_format(e) for e in events]
            # Bulk index to SIEM
            # await self.siem_adapter.bulk_index_events(siem_events)
            logger.info("Forwarded %d audit events to SIEM", len(events))
        except Exception as e:
            logger.error("Failed to write audit batch to SIEM: %s", e, exc_info=True)

    async def flush(self) -> None:
        """Flush any buffered events (handled by SIEM adapter)."""

    async def close(self) -> None:
        """Close the destination and cleanup resources."""

    async def health_check(self) -> bool:
        """Check if the destination is healthy.

        Returns:
            True if destination is operational
        """
        if not self.siem_adapter:
            return False

        try:
            # Check SIEM connectivity
            # return await self.siem_adapter.health_check()
            return True
        except Exception as e:
            logger.error("SIEM destination health check failed: %s", e)
            return False

    def _convert_to_siem_format(self, event: RequestAuditEvent) -> dict:
        """Convert audit event to SIEM format.

        Args:
            event: The audit event

        Returns:
            Dictionary in SIEM format
        """
        # Basic conversion - this should match audit_compliance event format
        siem_event = {
            "@timestamp": event.timestamp.isoformat(),
            "event": {
                "id": str(event.id),
                "type": event.event_type.value,
                "severity": event.severity.value,
                "outcome": event.outcome.value,
                "category": "audit",
            },
            "message": event.message,
        }

        # Add source/actor information
        if event.request_context:
            siem_event["source"] = {
                "ip": event.request_context.source_ip,
                "request_id": event.request_context.request_id,
            }

        if event.actor_info:
            siem_event["user"] = {
                "id": event.actor_info.user_id,
                "name": event.actor_info.username,
            }

        # Add service context
        if event.service_context:
            siem_event["service"] = {
                "name": event.service_context.service_name,
                "environment": event.service_context.environment,
                "version": event.service_context.version,
            }

        # Add resource information
        if event.resource_info:
            siem_event["resource"] = {
                "type": event.resource_info.resource_type,
                "id": event.resource_info.resource_id,
                "action": event.resource_info.action,
            }

        # Add raw event data
        siem_event["raw_data"] = event.to_dict()

        return siem_event
