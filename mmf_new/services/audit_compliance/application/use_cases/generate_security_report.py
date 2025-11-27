"""Generate security report use case."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from mmf_new.core.application.base import Command, CommandRequest
from mmf_new.core.domain import AuditLevel, ComplianceFramework, SecurityEventType

from ...domain.models import SecurityAuditEvent
from ..ports_out import (
    AuditEventRepositoryPort,
    ComplianceScannerPort,
    SecurityReportGeneratorPort,
    ThreatAnalyzerPort,
)


@dataclass(kw_only=True)
class GenerateSecurityReportRequest(CommandRequest):
    """Request to generate a security report."""

    report_type: str  # "compliance", "security", "threat_analysis", "comprehensive"
    time_period_hours: int = 24
    include_compliance_scans: bool = True
    include_threat_analysis: bool = True
    include_audit_events: bool = True
    frameworks: list[ComplianceFramework] | None = None
    resource_filter: str | None = None
    format: str = "json"  # "json", "html", "pdf"
    save_report: bool = True


@dataclass
class GenerateSecurityReportResponse:
    """Response from security report generation."""

    report_data: dict[str, Any]
    summary: dict[str, Any]
    report_file_path: str | None = None
    success: bool = True
    error_message: str | None = None
    warnings: list[str] | None = None


class GenerateSecurityReportUseCase(
    Command[GenerateSecurityReportRequest, GenerateSecurityReportResponse]
):
    """Use case for generating comprehensive security reports."""

    def __init__(
        self,
        report_generator: SecurityReportGeneratorPort,
        audit_repository: AuditEventRepositoryPort,
        compliance_scanner: ComplianceScannerPort | None = None,
        threat_analyzer: ThreatAnalyzerPort | None = None,
    ):
        self.report_generator = report_generator
        self.audit_repository = audit_repository
        self.compliance_scanner = compliance_scanner
        self.threat_analyzer = threat_analyzer

    async def execute(
        self, request: GenerateSecurityReportRequest
    ) -> GenerateSecurityReportResponse:
        """Execute the security report generation use case."""
        warnings = []

        try:
            # Calculate time window
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=request.time_period_hours)

            # Initialize report data structure
            report_data = {
                "report_metadata": {
                    "report_type": request.report_type,
                    "generated_at": end_time.isoformat(),
                    "time_period": {
                        "start": start_time.isoformat(),
                        "end": end_time.isoformat(),
                        "hours": request.time_period_hours,
                    },
                    "resource_filter": request.resource_filter,
                    "generated_by": request.user_id,
                },
                "sections": {},
            }

            # Collect audit events if requested
            if request.include_audit_events:
                try:
                    audit_events = await self._collect_audit_events(
                        start_time, end_time, request.resource_filter
                    )
                    report_data["sections"]["audit_events"] = {
                        "total_events": len(audit_events),
                        "events_by_type": self._group_events_by_type(audit_events),
                        "events_by_level": self._group_events_by_level(audit_events),
                        "timeline": self._create_event_timeline(audit_events),
                        "top_resources": self._get_top_resources(audit_events),
                    }
                    if request.format == "json":
                        report_data["sections"]["audit_events"]["raw_events"] = [
                            event.to_dict() for event in audit_events
                        ]
                except Exception as e:
                    warnings.append(f"Failed to collect audit events: {str(e)}")

            # Collect compliance scan results if requested
            if request.include_compliance_scans and self.compliance_scanner:
                try:
                    compliance_data = await self._collect_compliance_data(
                        start_time, end_time, request.frameworks, request.resource_filter
                    )
                    report_data["sections"]["compliance"] = compliance_data
                except Exception as e:
                    warnings.append(f"Failed to collect compliance data: {str(e)}")

            # Collect threat analysis if requested
            if request.include_threat_analysis and self.threat_analyzer:
                try:
                    threat_data = await self._collect_threat_analysis(
                        start_time, end_time, request.resource_filter
                    )
                    report_data["sections"]["threat_analysis"] = threat_data
                except Exception as e:
                    warnings.append(f"Failed to collect threat analysis: {str(e)}")

            # Generate executive summary
            summary = self._generate_executive_summary(report_data)
            report_data["executive_summary"] = summary

            # Generate the formatted report
            report_file_path = None
            if request.save_report:
                try:
                    report_file_path = await self.report_generator.generate_report(
                        report_data=report_data,
                        format=request.format,
                        report_type=request.report_type,
                    )
                except Exception as e:
                    warnings.append(f"Failed to save report file: {str(e)}")

            # Log report generation
            try:
                audit_event = SecurityAuditEvent(
                    event_type=SecurityEventType.DATA_ACCESS,
                    principal_id=request.user_id,
                    resource="security_reports",
                    action="generate_report",
                    result="success",
                    details={
                        "report_type": request.report_type,
                        "time_period_hours": request.time_period_hours,
                        "sections_included": list(report_data["sections"].keys()),
                        "total_events": report_data.get("sections", {})
                        .get("audit_events", {})
                        .get("total_events", 0),
                    },
                    correlation_id=request.correlation_id,
                    level=AuditLevel.INFO,
                )

                await self.audit_repository.save(audit_event)
            except Exception as e:
                warnings.append(f"Failed to log report generation: {str(e)}")

            return GenerateSecurityReportResponse(
                report_data=report_data,
                report_file_path=report_file_path,
                summary=summary,
                success=True,
                warnings=warnings if warnings else None,
            )

        except Exception as e:
            return GenerateSecurityReportResponse(
                report_data={},
                summary={},
                success=False,
                error_message=str(e),
                warnings=warnings if warnings else None,
            )

    async def _collect_audit_events(
        self,
        start_time: datetime,
        end_time: datetime,
        resource_filter: str | None,
    ) -> list:
        """Collect audit events for the report."""
        query_filters = {
            "start_time": start_time,
            "end_time": end_time,
        }
        if resource_filter:
            query_filters["resource"] = resource_filter

        return await self.audit_repository.find_by_criteria(query_filters)

    async def _collect_compliance_data(
        self,
        start_time: datetime,
        end_time: datetime,
        frameworks: list[ComplianceFramework] | None,
        resource_filter: str | None,
    ) -> dict[str, Any]:
        """Collect compliance scan data for the report."""
        if not self.compliance_scanner:
            return {}

        compliance_data = {
            "frameworks_scanned": [],
            "overall_compliance": {"compliant": 0, "non_compliant": 0},
            "findings_by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "resources_scanned": set(),
        }

        # Get recent compliance results
        frameworks_to_scan = frameworks or [ComplianceFramework.SOC2, ComplianceFramework.PCI_DSS]

        for framework in frameworks_to_scan:
            try:
                # This would typically query stored compliance results
                # For now, we'll simulate the data structure
                compliance_data["frameworks_scanned"].append(
                    {
                        "framework": framework.value,
                        "scan_timestamp": end_time.isoformat(),
                        "status": "completed",
                    }
                )
            except Exception:
                continue

        return compliance_data

    async def _collect_threat_analysis(
        self,
        start_time: datetime,
        end_time: datetime,
        resource_filter: str | None,
    ) -> dict[str, Any]:
        """Collect threat analysis data for the report."""
        if not self.threat_analyzer:
            return {}

        try:
            patterns = await self.threat_analyzer.get_patterns(
                resource=resource_filter,
                start_time=start_time,
                end_time=end_time,
            )

            threat_data = {
                "total_patterns": len(patterns),
                "active_patterns": len([p for p in patterns if p.is_active()]),
                "critical_patterns": len([p for p in patterns if p.threat_level.value >= 4]),
                "pattern_summary": [
                    {
                        "pattern_id": p.pattern_id,
                        "pattern_name": p.pattern_name,
                        "threat_level": p.threat_level.value,
                        "trigger_count": p.trigger_count,
                        "confidence": p.confidence_score,
                        "resource": p.resource,
                    }
                    for p in patterns[:10]  # Top 10 patterns
                ],
            }

            return threat_data
        except Exception:
            return {}

    def _group_events_by_type(self, events: list) -> dict[str, int]:
        """Group events by type for summary."""
        type_counts = {}
        for event in events:
            event_type = (
                event.event_type.value
                if hasattr(event.event_type, "value")
                else str(event.event_type)
            )
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
        return type_counts

    def _group_events_by_level(self, events: list) -> dict[str, int]:
        """Group events by severity level."""
        level_counts = {}
        for event in events:
            level = event.level.value if hasattr(event.level, "value") else str(event.level)
            level_counts[level] = level_counts.get(level, 0) + 1
        return level_counts

    def _create_event_timeline(self, events: list) -> list[dict[str, Any]]:
        """Create a timeline of events."""
        timeline = []
        for event in sorted(events, key=lambda e: e.timestamp, reverse=True)[:20]:
            timeline.append(
                {
                    "timestamp": event.timestamp.isoformat(),
                    "type": event.event_type.value
                    if hasattr(event.event_type, "value")
                    else str(event.event_type),
                    "level": event.level.value
                    if hasattr(event.level, "value")
                    else str(event.level),
                    "resource": event.resource,
                    "action": event.action,
                }
            )
        return timeline

    def _get_top_resources(self, events: list) -> list[dict[str, Any]]:
        """Get the most active resources."""
        resource_counts = {}
        for event in events:
            if event.resource:
                resource_counts[event.resource] = resource_counts.get(event.resource, 0) + 1

        top_resources = sorted(resource_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        return [{"resource": resource, "event_count": count} for resource, count in top_resources]

    def _generate_executive_summary(self, report_data: dict[str, Any]) -> dict[str, Any]:
        """Generate an executive summary of the report."""
        summary = {
            "report_period": report_data["report_metadata"]["time_period"],
            "key_metrics": {},
            "risk_assessment": "LOW",
            "recommendations": [],
        }

        # Analyze audit events
        if "audit_events" in report_data["sections"]:
            audit_section = report_data["sections"]["audit_events"]
            summary["key_metrics"]["total_security_events"] = audit_section["total_events"]

            # Determine risk level based on critical events
            events_by_level = audit_section.get("events_by_level", {})
            critical_count = events_by_level.get("CRITICAL", 0)
            warning_count = events_by_level.get("WARNING", 0)

            if critical_count > 0:
                summary["risk_assessment"] = "CRITICAL"
                summary["recommendations"].append(
                    f"Immediate attention required: {critical_count} critical security events detected"
                )
            elif warning_count > 10:
                summary["risk_assessment"] = "HIGH"
                summary["recommendations"].append(
                    f"High warning activity: {warning_count} warning events require review"
                )
            elif warning_count > 0:
                summary["risk_assessment"] = "MEDIUM"

        # Analyze threat patterns
        if "threat_analysis" in report_data["sections"]:
            threat_section = report_data["sections"]["threat_analysis"]
            critical_patterns = threat_section.get("critical_patterns", 0)

            if critical_patterns > 0:
                summary["risk_assessment"] = "CRITICAL"
                summary["recommendations"].append(
                    f"Critical threat patterns active: {critical_patterns} patterns require immediate response"
                )

        # Analyze compliance
        if "compliance" in report_data["sections"]:
            report_data["sections"]["compliance"]
            # Add compliance-specific recommendations based on findings
            pass

        if not summary["recommendations"]:
            summary["recommendations"].append(
                "Security posture appears stable. Continue monitoring."
            )

        return summary
