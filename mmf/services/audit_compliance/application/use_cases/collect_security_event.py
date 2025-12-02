"""Collect security event use case."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mmf.core.application.base import Command, CommandRequest
from mmf.core.domain import AuditLevel, SecurityEventSeverity, SecurityEventType

from ...domain.models import SecurityAuditEvent
from ..ports_out import AuditEventRepositoryPort, SIEMAdapterPort, ThreatAnalyzerPort


@dataclass(kw_only=True)
class CollectSecurityEventRequest(CommandRequest):
    """Request to collect and process a security event."""

    event_type: SecurityEventType
    source_system: str
    event_data: dict[str, Any]
    severity: SecurityEventSeverity = SecurityEventSeverity.MEDIUM
    resource: str | None = None
    principal_id: str | None = None
    auto_analyze: bool = True
    send_to_siem: bool = True


@dataclass
class CollectSecurityEventResponse:
    """Response from security event collection."""

    audit_event: SecurityAuditEvent
    analysis_results: dict[str, Any] | None = None
    threat_patterns_detected: list[str] | None = None
    siem_sent: bool = False
    success: bool = True
    error_message: str | None = None
    warnings: list[str] | None = None


class CollectSecurityEventUseCase(
    Command[CollectSecurityEventRequest, CollectSecurityEventResponse]
):
    """Use case for collecting and processing security events."""

    def __init__(
        self,
        repository: AuditEventRepositoryPort,
        siem_adapter: SIEMAdapterPort | None = None,
        threat_analyzer: ThreatAnalyzerPort | None = None,
    ):
        self.repository = repository
        self.siem_adapter = siem_adapter
        self.threat_analyzer = threat_analyzer

    async def execute(self, request: CollectSecurityEventRequest) -> CollectSecurityEventResponse:
        """Execute the security event collection use case."""
        warnings = []

        try:
            # Parse and enrich the event data
            enriched_data = await self._enrich_event_data(request)

            # Create the security audit event
            audit_event = SecurityAuditEvent(
                event_type=request.event_type,
                principal_id=request.principal_id or enriched_data.get("principal_id", "system"),
                resource=request.resource or enriched_data.get("resource", request.source_system),
                action=enriched_data.get("action", "security_event"),
                result=enriched_data.get("result", "collected"),
                details={
                    "source_system": request.source_system,
                    "severity": request.severity.value,
                    "original_event": request.event_data,
                    "enriched_data": enriched_data.get("enrichment", {}),
                    "collection_timestamp": enriched_data.get("collection_timestamp"),
                },
                correlation_id=request.correlation_id,
                level=self._map_severity_to_audit_level(request.severity),
            )

            # Save the audit event
            await self.repository.save(audit_event)

            # Analyze for threat patterns if requested
            analysis_results = None
            threat_patterns_detected = []

            if request.auto_analyze and self.threat_analyzer:
                try:
                    analysis_results = await self._analyze_for_threats(audit_event, request)
                    if analysis_results and analysis_results.get("patterns_detected"):
                        threat_patterns_detected = analysis_results["patterns_detected"]
                except Exception as e:
                    warnings.append(f"Threat analysis failed: {str(e)}")

            # Send to SIEM if requested and criteria met
            siem_sent = False
            if (
                request.send_to_siem
                and self.siem_adapter
                and self._should_send_to_siem(audit_event, request)
            ):
                try:
                    siem_event = self._prepare_siem_event(audit_event, analysis_results)
                    await self.siem_adapter.send_event(siem_event)
                    siem_sent = True
                except Exception as e:
                    warnings.append(f"SIEM transmission failed: {str(e)}")

            return CollectSecurityEventResponse(
                audit_event=audit_event,
                analysis_results=analysis_results,
                threat_patterns_detected=threat_patterns_detected,
                siem_sent=siem_sent,
                success=True,
                warnings=warnings if warnings else None,
            )

        except Exception as e:
            return CollectSecurityEventResponse(
                audit_event=None,  # type: ignore
                success=False,
                error_message=str(e),
                warnings=warnings if warnings else None,
            )

    async def _enrich_event_data(self, request: CollectSecurityEventRequest) -> dict[str, Any]:
        """Enrich the raw event data with additional context."""

        enriched = {
            "collection_timestamp": datetime.utcnow().isoformat(),
            "enrichment": {},
        }

        # Extract common fields from event data
        event_data = request.event_data

        # Try to extract principal information
        for field in ["user_id", "username", "principal", "actor", "subject"]:
            if field in event_data:
                enriched["principal_id"] = str(event_data[field])
                break

        # Try to extract resource information
        for field in ["resource", "target", "object", "url", "endpoint"]:
            if field in event_data:
                enriched["resource"] = str(event_data[field])
                break

        # Try to extract action information
        for field in ["action", "method", "operation", "event", "activity"]:
            if field in event_data:
                enriched["action"] = str(event_data[field])
                break

        # Try to extract result information
        for field in ["result", "status", "outcome", "success", "response_code"]:
            if field in event_data:
                enriched["result"] = str(event_data[field])
                break

        # Add IP address if available
        for field in ["ip_address", "client_ip", "remote_addr", "source_ip"]:
            if field in event_data:
                enriched["enrichment"]["ip_address"] = str(event_data[field])
                break

        # Add user agent if available
        for field in ["user_agent", "ua", "browser"]:
            if field in event_data:
                enriched["enrichment"]["user_agent"] = str(event_data[field])
                break

        # Add timestamp if available (prefer original event timestamp)
        for field in ["timestamp", "time", "event_time", "occurred_at"]:
            if field in event_data:
                enriched["enrichment"]["original_timestamp"] = str(event_data[field])
                break

        # Add any additional metadata
        metadata_fields = ["session_id", "trace_id", "request_id", "transaction_id"]
        for field in metadata_fields:
            if field in event_data:
                enriched["enrichment"][field] = str(event_data[field])

        return enriched

    async def _analyze_for_threats(
        self,
        audit_event: SecurityAuditEvent,
        request: CollectSecurityEventRequest,
    ) -> dict[str, Any] | None:
        """Analyze the event for threat patterns."""
        if not self.threat_analyzer:
            return None

        try:
            # Convert audit event to analysis format
            analysis_data = {
                "event_type": audit_event.event_type.value,
                "resource": audit_event.resource,
                "principal_id": audit_event.principal_id,
                "timestamp": audit_event.timestamp,
                "severity": request.severity.value,
                "source_system": request.source_system,
                "event_data": request.event_data,
            }

            # Perform threat analysis
            analysis_result = await self.threat_analyzer.analyze_event(analysis_data)

            # Check for existing patterns that this event might trigger
            patterns_triggered = []
            if analysis_result.get("pattern_matches"):
                for pattern_match in analysis_result["pattern_matches"]:
                    pattern_id = pattern_match.get("pattern_id")
                    if pattern_id:
                        patterns_triggered.append(pattern_id)

                        # Update the pattern with the trigger
                        try:
                            pattern = await self.threat_analyzer.get_pattern(pattern_id)
                            if pattern:
                                pattern.record_trigger(audit_event.to_dict())
                                await self.threat_analyzer.update_pattern(pattern)
                        except Exception:
                            # Don't fail the analysis if pattern update fails
                            continue

            return {
                "analysis_timestamp": analysis_result.get("timestamp"),
                "risk_score": analysis_result.get("risk_score", 0.0),
                "confidence": analysis_result.get("confidence", 0.0),
                "patterns_detected": patterns_triggered,
                "anomalies": analysis_result.get("anomalies", []),
                "recommendations": analysis_result.get("recommendations", []),
            }

        except Exception as e:
            # Return basic analysis info even if full analysis fails
            return {
                "analysis_error": str(e),
                "risk_score": self._calculate_basic_risk_score(request),
                "patterns_detected": [],
            }

    def _should_send_to_siem(
        self,
        audit_event: SecurityAuditEvent,
        request: CollectSecurityEventRequest,
    ) -> bool:
        """Determine if the event should be sent to SIEM."""
        # Send critical and high severity events
        if request.severity in [SecurityEventSeverity.CRITICAL, SecurityEventSeverity.HIGH]:
            return True

        # Send security-specific event types
        critical_event_types = [
            SecurityEventType.AUTHENTICATION_FAILURE,
            SecurityEventType.AUTHORIZATION_FAILURE,
            SecurityEventType.PRIVILEGE_ESCALATION,
            SecurityEventType.SUSPICIOUS_ACTIVITY,
            SecurityEventType.SECURITY_VIOLATION,
            SecurityEventType.COMPLIANCE_VIOLATION,
        ]

        if audit_event.event_type in critical_event_types:
            return True

        # Send events from critical systems
        critical_systems = ["authentication", "authorization", "security", "compliance"]
        if any(system in request.source_system.lower() for system in critical_systems):
            return True

        return False

    def _prepare_siem_event(
        self,
        audit_event: SecurityAuditEvent,
        analysis_results: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Prepare the event data for SIEM transmission."""
        siem_event = {
            "event_id": audit_event.id,
            "timestamp": audit_event.timestamp.isoformat(),
            "event_type": audit_event.event_type.value,
            "severity": audit_event.details.get("severity", "MEDIUM"),
            "source_system": audit_event.details.get("source_system", "unknown"),
            "principal_id": audit_event.principal_id,
            "resource": audit_event.resource,
            "action": audit_event.action,
            "result": audit_event.result,
            "level": audit_event.level.value,
            "details": audit_event.details,
        }

        # Add analysis results if available
        if analysis_results:
            siem_event["analysis"] = {
                "risk_score": analysis_results.get("risk_score", 0.0),
                "confidence": analysis_results.get("confidence", 0.0),
                "patterns_detected": analysis_results.get("patterns_detected", []),
                "anomalies": analysis_results.get("anomalies", []),
            }

        # Add correlation information
        if audit_event.correlation_id:
            siem_event["correlation_id"] = audit_event.correlation_id

        return siem_event

    def _map_severity_to_audit_level(self, severity: SecurityEventSeverity) -> AuditLevel:
        """Map security event severity to audit level."""
        mapping = {
            SecurityEventSeverity.CRITICAL: AuditLevel.CRITICAL,
            SecurityEventSeverity.HIGH: AuditLevel.ERROR,
            SecurityEventSeverity.MEDIUM: AuditLevel.WARNING,
            SecurityEventSeverity.LOW: AuditLevel.INFO,
        }
        return mapping.get(severity, AuditLevel.INFO)

    def _calculate_basic_risk_score(self, request: CollectSecurityEventRequest) -> float:
        """Calculate a basic risk score when full analysis isn't available."""
        base_score = 0.0

        # Severity contribution
        severity_scores = {
            SecurityEventSeverity.CRITICAL: 0.8,
            SecurityEventSeverity.HIGH: 0.6,
            SecurityEventSeverity.MEDIUM: 0.4,
            SecurityEventSeverity.LOW: 0.2,
        }
        base_score += severity_scores.get(request.severity, 0.2)

        # Event type contribution
        high_risk_events = [
            SecurityEventType.AUTHENTICATION_FAILURE,
            SecurityEventType.AUTHORIZATION_FAILURE,
            SecurityEventType.PRIVILEGE_ESCALATION,
            SecurityEventType.SUSPICIOUS_ACTIVITY,
        ]

        if request.event_type in high_risk_events:
            base_score += 0.2

        return min(base_score, 1.0)
