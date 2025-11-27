"""Analyze threat pattern use case."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from mmf_new.core.application.base import Command, CommandRequest
from mmf_new.core.domain import AuditLevel, SecurityEventType, SecurityThreatLevel

from ...domain.models import SecurityAuditEvent, ThreatPattern
from ..ports_out import AuditEventRepositoryPort, SIEMAdapterPort, ThreatAnalyzerPort


@dataclass
class AnalyzeThreatPatternRequest(CommandRequest):
    """Request to analyze threat patterns."""

    pattern_id: str | None = None  # Analyze specific pattern
    resource: str | None = None  # Analyze patterns for specific resource
    time_window_hours: int = 24  # Analysis window
    threat_threshold: SecurityThreatLevel = SecurityThreatLevel.MEDIUM
    include_recent_only: bool = True
    save_analysis: bool = True


@dataclass
class AnalyzeThreatPatternResponse:
    """Response from threat pattern analysis."""

    threat_patterns: list[ThreatPattern]
    analysis_summary: dict[str, Any]
    high_risk_patterns: list[ThreatPattern]
    recommendations: list[str]
    success: bool
    error_message: str | None = None


class AnalyzeThreatPatternUseCase(
    Command[AnalyzeThreatPatternRequest, AnalyzeThreatPatternResponse]
):
    """Use case for analyzing threat patterns."""

    def __init__(
        self,
        analyzer: ThreatAnalyzerPort,
        repository: AuditEventRepositoryPort | None = None,
        siem_adapter: SIEMAdapterPort | None = None,
    ):
        self.analyzer = analyzer
        self.repository = repository
        self.siem_adapter = siem_adapter

    async def execute(self, request: AnalyzeThreatPatternRequest) -> AnalyzeThreatPatternResponse:
        """Execute the threat pattern analysis use case."""
        try:
            # Calculate time window for analysis
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=request.time_window_hours)

            # Get threat patterns to analyze
            if request.pattern_id:
                # Analyze specific pattern
                pattern = await self.analyzer.get_pattern(request.pattern_id)
                if not pattern:
                    return AnalyzeThreatPatternResponse(
                        threat_patterns=[],
                        analysis_summary={},
                        high_risk_patterns=[],
                        recommendations=[],
                        success=False,
                        error_message=f"Threat pattern {request.pattern_id} not found",
                    )
                patterns = [pattern]
            else:
                # Get patterns for resource or all patterns
                patterns = await self.analyzer.get_patterns(
                    resource=request.resource,
                    start_time=start_time,
                    end_time=end_time,
                    include_recent_only=request.include_recent_only,
                )

            # Analyze each pattern
            analyzed_patterns = []
            high_risk_patterns = []
            total_triggers = 0
            critical_count = 0

            for pattern in patterns:
                # Update pattern with recent analysis
                analysis_result = await self.analyzer.analyze_pattern(
                    pattern=pattern,
                    start_time=start_time,
                    end_time=end_time,
                )

                # Update the pattern with analysis results
                pattern.confidence_score = analysis_result.get(
                    "confidence_score", pattern.confidence_score
                )
                pattern.last_updated = datetime.utcnow()

                analyzed_patterns.append(pattern)
                total_triggers += pattern.trigger_count

                # Check if pattern meets high-risk criteria
                if (
                    pattern.threat_level.value >= request.threat_threshold.value
                    and pattern.is_active()
                    and pattern.confidence_score >= 0.7
                ):
                    high_risk_patterns.append(pattern)

                if pattern.threat_level == SecurityThreatLevel.CRITICAL:
                    critical_count += 1

            # Generate analysis summary
            analysis_summary = {
                "total_patterns": len(analyzed_patterns),
                "high_risk_patterns": len(high_risk_patterns),
                "critical_patterns": critical_count,
                "total_triggers": total_triggers,
                "analysis_window_hours": request.time_window_hours,
                "analysis_timestamp": end_time.isoformat(),
                "resource_analyzed": request.resource,
                "threat_threshold": request.threat_threshold.value,
            }

            # Generate recommendations
            recommendations = self._generate_recommendations(
                analyzed_patterns,
                high_risk_patterns,
                analysis_summary,
            )

            # Save analysis results if requested
            if self.repository and request.save_analysis:
                try:
                    # Create audit event for the analysis

                    audit_event = SecurityAuditEvent(
                        event_type=SecurityEventType.SECURITY_ANALYSIS,
                        principal_id=request.user_id,
                        resource=request.resource or "system",
                        action="threat_pattern_analysis",
                        result="completed",
                        details={
                            "patterns_analyzed": len(analyzed_patterns),
                            "high_risk_found": len(high_risk_patterns),
                            "critical_found": critical_count,
                            "analysis_window_hours": request.time_window_hours,
                        },
                        correlation_id=request.correlation_id,
                        level=AuditLevel.CRITICAL
                        if critical_count > 0
                        else AuditLevel.WARNING
                        if high_risk_patterns
                        else AuditLevel.INFO,
                    )

                    await self.repository.save(audit_event)
                except Exception:
                    # Don't fail the analysis if audit logging fails
                    pass

            # Send critical patterns to SIEM if available
            if self.siem_adapter and high_risk_patterns:
                try:
                    critical_patterns = [
                        p
                        for p in high_risk_patterns
                        if p.threat_level == SecurityThreatLevel.CRITICAL
                    ]
                    if critical_patterns:
                        siem_events = []
                        for pattern in critical_patterns:
                            siem_event = {
                                "event_type": "threat_pattern_detected",
                                "pattern_id": pattern.pattern_id,
                                "pattern_name": pattern.pattern_name,
                                "threat_level": pattern.threat_level.value,
                                "confidence": pattern.confidence_score,
                                "resource": pattern.resource,
                                "triggers": pattern.trigger_count,
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                            siem_events.append(siem_event)

                        await self.siem_adapter.send_events(siem_events)
                except Exception:
                    # Don't fail the analysis if SIEM sending fails
                    pass

            return AnalyzeThreatPatternResponse(
                threat_patterns=analyzed_patterns,
                analysis_summary=analysis_summary,
                high_risk_patterns=high_risk_patterns,
                recommendations=recommendations,
                success=True,
            )

        except Exception as e:
            return AnalyzeThreatPatternResponse(
                threat_patterns=[],
                analysis_summary={},
                high_risk_patterns=[],
                recommendations=[],
                success=False,
                error_message=str(e),
            )

    def _generate_recommendations(
        self,
        patterns: list[ThreatPattern],
        high_risk_patterns: list[ThreatPattern],
        summary: dict[str, Any],
    ) -> list[str]:
        """Generate security recommendations based on analysis."""
        recommendations = []

        if not patterns:
            recommendations.append("No threat patterns detected in the analysis window.")
            return recommendations

        # Critical threat recommendations
        critical_patterns = [
            p for p in high_risk_patterns if p.threat_level == SecurityThreatLevel.CRITICAL
        ]
        if critical_patterns:
            recommendations.append(
                f"URGENT: {len(critical_patterns)} critical threat patterns detected. "
                "Immediate security response required."
            )
            for pattern in critical_patterns[:3]:  # Top 3 critical
                recommendations.append(
                    f"Critical pattern '{pattern.pattern_name}' on {pattern.resource} "
                    f"with {pattern.trigger_count} triggers."
                )

        # High-risk pattern recommendations
        if high_risk_patterns:
            recommendations.append(
                f"{len(high_risk_patterns)} high-risk threat patterns require attention."
            )

            # Check for patterns with high trigger counts
            high_trigger_patterns = [p for p in high_risk_patterns if p.trigger_count > 10]
            if high_trigger_patterns:
                recommendations.append(
                    "Multiple high-frequency threat patterns detected. "
                    "Consider implementing automated blocking rules."
                )

        # Pattern diversity recommendations
        unique_resources = len({p.resource for p in patterns if p.resource})
        if unique_resources > 5:
            recommendations.append(
                f"Threat patterns detected across {unique_resources} resources. "
                "Consider implementing centralized security monitoring."
            )

        # Confidence-based recommendations
        low_confidence_patterns = [p for p in patterns if p.confidence_score < 0.5]
        if low_confidence_patterns:
            recommendations.append(
                f"{len(low_confidence_patterns)} patterns have low confidence scores. "
                "Review and refine pattern detection rules."
            )

        # General security posture
        if not high_risk_patterns and patterns:
            recommendations.append(
                "Current threat level is manageable. Continue monitoring for pattern evolution."
            )

        return recommendations
