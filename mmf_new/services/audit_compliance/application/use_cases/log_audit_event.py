"""Log audit event use case."""

from dataclasses import dataclass
from typing import Any

from mmf_new.core.application.base import Command, CommandRequest
from mmf_new.core.domain import AuditLevel, SecurityEventType

from ...domain.models import SecurityAuditEvent
from ..ports_out import AuditEventRepositoryPort, AuditorPort, SIEMAdapterPort


@dataclass(kw_only=True)
class LogAuditEventRequest(CommandRequest):
    """Request to log a security audit event."""

    event_type: SecurityEventType
    principal_id: str | None = None
    resource: str | None = None
    action: str | None = None
    result: str | None = None
    details: dict[str, Any] | None = None
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    service_name: str | None = None
    level: AuditLevel = AuditLevel.INFO


@dataclass
class LogAuditEventResponse:
    """Response from logging an audit event."""

    event_id: str
    success: bool
    error_message: str | None = None
    siem_sent: bool = False


class LogAuditEventUseCase(Command[LogAuditEventRequest, LogAuditEventResponse]):
    """Use case for logging security audit events."""

    def __init__(
        self,
        repository: AuditEventRepositoryPort,
        auditor: AuditorPort,
        siem_adapter: SIEMAdapterPort,
    ):
        self.repository = repository
        self.auditor = auditor
        self.siem_adapter = siem_adapter

    async def execute(self, request: LogAuditEventRequest) -> LogAuditEventResponse:
        """Execute the log audit event use case."""
        try:
            # Create domain entity
            audit_event = SecurityAuditEvent(
                event_type=request.event_type,
                principal_id=request.principal_id,
                resource=request.resource,
                action=request.action,
                result=request.result,
                details=request.details or {},
                session_id=request.session_id,
                ip_address=request.ip_address,
                user_agent=request.user_agent,
                correlation_id=request.correlation_id or request.correlation_id,
                service_name=request.service_name,
                level=request.level,
            )

            # Save to repository
            saved_event = await self.repository.save(audit_event)

            # Log via auditor
            await self.auditor.audit_event(saved_event)

            # Send to SIEM if critical or high priority
            siem_sent = False
            if saved_event.is_critical() or saved_event.requires_immediate_attention():
                try:
                    siem_sent = await self.siem_adapter.send_event(saved_event)
                except Exception:
                    # SIEM failure shouldn't fail the entire operation
                    siem_sent = False

            return LogAuditEventResponse(
                event_id=str(saved_event.id),
                success=True,
                siem_sent=siem_sent,
            )

        except Exception as e:
            return LogAuditEventResponse(
                event_id="",
                success=False,
                error_message=str(e),
                siem_sent=False,
            )
