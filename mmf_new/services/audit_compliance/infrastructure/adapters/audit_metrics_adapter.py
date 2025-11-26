"""Audit compliance metrics adapter extending framework metrics."""

from datetime import datetime
from typing import Any, Optional

from mmf_new.framework.observability.framework_metrics import FrameworkMetrics

from ...domain.contracts import IMetricsAdapter


class AuditComplianceMetricsAdapter(IMetricsAdapter):
    """Prometheus metrics adapter for audit compliance extending framework metrics."""

    def __init__(self, service_name: str = "audit_compliance"):
        self.framework_metrics = FrameworkMetrics(service_name)
        self.service_name = service_name

        # Initialize audit-specific metrics
        self._initialize_audit_metrics()

    def _initialize_audit_metrics(self) -> None:
        """Initialize audit compliance specific metrics."""

        # Security Event Metrics
        self.security_events_total = self.framework_metrics.create_counter(
            "security_events_total",
            "Total number of security events collected",
            ["event_type", "severity", "source_system"],
        )

        self.audit_events_total = self.framework_metrics.create_counter(
            "audit_events_total",
            "Total number of audit events logged",
            ["principal_id", "resource", "action", "level"],
        )

        self.critical_events_total = self.framework_metrics.create_counter(
            "critical_events_total",
            "Total number of critical security events",
            ["event_type", "resource"],
        )

        # Compliance Metrics
        self.compliance_scans_total = self.framework_metrics.create_counter(
            "compliance_scans_total",
            "Total number of compliance scans performed",
            ["framework", "target_type", "result"],
        )

        self.compliance_violations_total = self.framework_metrics.create_counter(
            "compliance_violations_total",
            "Total number of compliance violations detected",
            ["framework", "severity", "resource"],
        )

        self.compliance_score = self.framework_metrics.create_gauge(
            "compliance_score", "Current compliance score by framework", ["framework"]
        )

        # Threat Analysis Metrics
        self.threat_patterns_detected = self.framework_metrics.create_counter(
            "threat_patterns_detected_total",
            "Total number of threat patterns detected",
            ["pattern_name", "threat_level", "resource"],
        )

        self.threat_level_gauge = self.framework_metrics.create_gauge(
            "current_threat_level",
            "Current threat level (0=low, 1=medium, 2=high, 3=critical)",
            ["resource"],
        )

        self.threat_analysis_duration = self.framework_metrics.create_histogram(
            "threat_analysis_duration_seconds",
            "Time spent analyzing threat patterns",
            ["analysis_type"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        )

        # SIEM Integration Metrics
        self.siem_events_sent = self.framework_metrics.create_counter(
            "siem_events_sent_total",
            "Total number of events sent to SIEM",
            ["siem_type", "success"],
        )

        self.siem_connection_status = self.framework_metrics.create_gauge(
            "siem_connection_status",
            "SIEM connection status (1=connected, 0=disconnected)",
            ["siem_type"],
        )

        # Cache Metrics
        self.cache_operations_total = self.framework_metrics.create_counter(
            "cache_operations_total",
            "Total number of cache operations",
            ["operation", "key_pattern", "success"],
        )

        self.cached_events_count = self.framework_metrics.create_gauge(
            "cached_events_count", "Number of events currently in cache", ["cache_key_type"]
        )

        self.cache_hit_ratio = self.framework_metrics.create_gauge(
            "cache_hit_ratio", "Cache hit ratio for audit events", ["cache_key_type"]
        )

        # Repository Metrics
        self.repository_operations_total = self.framework_metrics.create_counter(
            "repository_operations_total",
            "Total number of repository operations",
            ["operation", "entity_type", "success"],
        )

        self.repository_query_duration = self.framework_metrics.create_histogram(
            "repository_query_duration_seconds",
            "Time spent on repository queries",
            ["operation", "entity_type"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        )

        # Security Report Metrics
        self.security_reports_generated = self.framework_metrics.create_counter(
            "security_reports_generated_total",
            "Total number of security reports generated",
            ["report_type", "format", "success"],
        )

        self.report_generation_duration = self.framework_metrics.create_histogram(
            "report_generation_duration_seconds",
            "Time spent generating security reports",
            ["report_type"],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0],
        )

        # System Health Metrics
        self.audit_system_health = self.framework_metrics.create_gauge(
            "audit_system_health", "Overall audit system health score (0-100)", []
        )

        self.active_security_alerts = self.framework_metrics.create_gauge(
            "active_security_alerts", "Number of active security alerts", ["severity"]
        )

    # Security Event Methods
    def record_security_event(
        self,
        event_type: str,
        severity: str,
        source_system: str,
        success: bool = True,
    ) -> None:
        """Record a security event."""
        if self.security_events_total and success:
            self.security_events_total.labels(
                event_type=event_type, severity=severity, source_system=source_system
            ).inc()

    def record_audit_event(
        self,
        principal_id: str,
        resource: str,
        action: str,
        level: str,
        success: bool = True,
    ) -> None:
        """Record an audit event."""
        if self.audit_events_total and success:
            self.audit_events_total.labels(
                principal_id=principal_id, resource=resource, action=action, level=level
            ).inc()

    def record_critical_event(self, event_type: str, resource: str) -> None:
        """Record a critical security event."""
        if self.critical_events_total:
            self.critical_events_total.labels(event_type=event_type, resource=resource).inc()

    # Compliance Methods
    def record_compliance_scan(
        self,
        framework: str,
        target_type: str,
        result: str,
        score: float | None = None,
    ) -> None:
        """Record a compliance scan."""
        if self.compliance_scans_total:
            self.compliance_scans_total.labels(
                framework=framework, target_type=target_type, result=result
            ).inc()

        if self.compliance_score and score is not None:
            self.compliance_score.labels(framework=framework).set(score)

    def record_compliance_violation(
        self,
        framework: str,
        severity: str,
        resource: str,
    ) -> None:
        """Record a compliance violation."""
        if self.compliance_violations_total:
            self.compliance_violations_total.labels(
                framework=framework, severity=severity, resource=resource
            ).inc()

    def update_compliance_score(self, framework: str, score: float) -> None:
        """Update compliance score for a framework."""
        if self.compliance_score:
            self.compliance_score.labels(framework=framework).set(score)

    # Threat Analysis Methods
    def record_threat_pattern(
        self,
        pattern_name: str,
        threat_level: str,
        resource: str,
    ) -> None:
        """Record a detected threat pattern."""
        if self.threat_patterns_detected:
            self.threat_patterns_detected.labels(
                pattern_name=pattern_name, threat_level=threat_level, resource=resource
            ).inc()

    def update_threat_level(self, resource: str, level: int) -> None:
        """Update current threat level for a resource."""
        if self.threat_level_gauge:
            self.threat_level_gauge.labels(resource=resource).set(level)

    def record_threat_analysis_duration(self, analysis_type: str, duration: float) -> None:
        """Record time spent on threat analysis."""
        if self.threat_analysis_duration:
            self.threat_analysis_duration.labels(analysis_type=analysis_type).observe(duration)

    # SIEM Integration Methods
    def record_siem_event(self, siem_type: str, success: bool) -> None:
        """Record SIEM event transmission."""
        if self.siem_events_sent:
            self.siem_events_sent.labels(
                siem_type=siem_type, success="success" if success else "failure"
            ).inc()

    def update_siem_connection_status(self, siem_type: str, connected: bool) -> None:
        """Update SIEM connection status."""
        if self.siem_connection_status:
            self.siem_connection_status.labels(siem_type=siem_type).set(1 if connected else 0)

    # Cache Methods
    def record_cache_operation(
        self,
        operation: str,
        key_pattern: str,
        success: bool,
    ) -> None:
        """Record cache operation."""
        if self.cache_operations_total:
            self.cache_operations_total.labels(
                operation=operation,
                key_pattern=key_pattern,
                success="success" if success else "failure",
            ).inc()

    def update_cached_events_count(self, cache_key_type: str, count: int) -> None:
        """Update count of cached events."""
        if self.cached_events_count:
            self.cached_events_count.labels(cache_key_type=cache_key_type).set(count)

    def update_cache_hit_ratio(self, cache_key_type: str, ratio: float) -> None:
        """Update cache hit ratio."""
        if self.cache_hit_ratio:
            self.cache_hit_ratio.labels(cache_key_type=cache_key_type).set(ratio)

    # Repository Methods
    def record_repository_operation(
        self,
        operation: str,
        entity_type: str,
        success: bool,
        duration: float | None = None,
    ) -> None:
        """Record repository operation."""
        if self.repository_operations_total:
            self.repository_operations_total.labels(
                operation=operation,
                entity_type=entity_type,
                success="success" if success else "failure",
            ).inc()

        if self.repository_query_duration and duration is not None:
            self.repository_query_duration.labels(
                operation=operation, entity_type=entity_type
            ).observe(duration)

    # Security Report Methods
    def record_security_report(
        self,
        report_type: str,
        format: str,
        success: bool,
        duration: float | None = None,
    ) -> None:
        """Record security report generation."""
        if self.security_reports_generated:
            self.security_reports_generated.labels(
                report_type=report_type, format=format, success="success" if success else "failure"
            ).inc()

        if self.report_generation_duration and duration is not None:
            self.report_generation_duration.labels(report_type=report_type).observe(duration)

    # System Health Methods
    def update_audit_system_health(self, health_score: float) -> None:
        """Update overall audit system health score."""
        if self.audit_system_health:
            self.audit_system_health.set(health_score)

    def update_active_security_alerts(self, severity: str, count: int) -> None:
        """Update count of active security alerts by severity."""
        if self.active_security_alerts:
            self.active_security_alerts.labels(severity=severity).set(count)

    # Convenience Methods
    def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of current metrics values."""
        summary = {
            "service_name": self.service_name,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {},
        }

        # This would typically pull actual values from Prometheus
        # For now, we provide the structure
        summary["metrics"] = {
            "security_events": "Available via security_events_total",
            "compliance_scans": "Available via compliance_scans_total",
            "threat_patterns": "Available via threat_patterns_detected_total",
            "siem_integrations": "Available via siem_events_sent_total",
            "cache_operations": "Available via cache_operations_total",
            "repository_operations": "Available via repository_operations_total",
        }

        return summary

    def reset_metrics(self) -> None:
        """Reset metrics (mainly for testing)."""
        # In a real implementation, this would clear metric values
        # Prometheus client doesn't support direct resets of all metrics
        pass

    # Integration with existing monitoring.py metrics
    def update_security_score(self, score: float) -> None:
        """Update security score (compatible with existing monitoring)."""
        if hasattr(self.framework_metrics, "security_score"):
            self.framework_metrics.security_score.set(score)

    def increment_processed_events(self, event_type: str = "security") -> None:
        """Increment processed events counter."""
        self.framework_metrics.record_document_processed(event_type, "success")
