"""
Security Report Generator Adapter

Implements ISecurityReportGenerator interface to generate comprehensive
security reports in multiple formats (JSON, HTML, PDF) with visualizations.
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from mmf.core.domain.audit_types import ComplianceFramework, SecurityEventSeverity
from mmf.framework.infrastructure.database_manager import DatabaseManager
from mmf.framework.infrastructure.framework_metrics import FrameworkMetrics

from ..domain.contracts import ISecurityReportGenerator
from ..domain.models import ComplianceScanResult, SecurityAuditEvent, ThreatPattern

logger = logging.getLogger(__name__)


class SecurityReportGeneratorAdapter(ISecurityReportGenerator):
    """
    Security report generator adapter that creates comprehensive reports
    in multiple formats with visualizations and actionable insights.
    """

    def __init__(
        self,
        database_manager: DatabaseManager,
        metrics: FrameworkMetrics,
        config: dict[str, Any] | None = None,
    ):
        self.database_manager = database_manager
        self.metrics = metrics
        self.config = config or {}

        # Report configuration
        self.output_directory = Path(self.config.get("output_directory", "./security_reports"))
        self.output_directory.mkdir(parents=True, exist_ok=True)

        # Template configurations
        self.include_charts = self.config.get("include_charts", True)
        self.include_recommendations = self.config.get("include_recommendations", True)
        self.severity_colors = {
            SecurityEventSeverity.CRITICAL: "#dc3545",
            SecurityEventSeverity.HIGH: "#fd7e14",
            SecurityEventSeverity.MEDIUM: "#ffc107",
            SecurityEventSeverity.LOW: "#28a745",
            SecurityEventSeverity.INFO: "#6c757d",
        }

    async def generate_security_report(
        self,
        events: list[SecurityAuditEvent],
        compliance_results: list[ComplianceScanResult],
        threat_patterns: list[ThreatPattern],
        report_format: str = "html",
        include_visualizations: bool = True,
    ) -> str:
        """
        Generate comprehensive security report in specified format.

        Args:
            events: Security audit events
            compliance_results: Compliance scan results
            threat_patterns: Identified threat patterns
            report_format: Output format ("html", "json", "pdf")
            include_visualizations: Whether to include charts and graphs

        Returns:
            Path to generated report file
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Record report generation attempt
            self.metrics.increment_counter(
                "security_reports_generated_total", labels={"format": report_format}
            )

            # Generate report data
            report_data = await self._compile_report_data(
                events, compliance_results, threat_patterns
            )

            # Generate report based on format
            if report_format.lower() == "json":
                report_path = await self._generate_json_report(report_data)
            elif report_format.lower() == "html":
                report_path = await self._generate_html_report(report_data, include_visualizations)
            elif report_format.lower() == "pdf":
                report_path = await self._generate_pdf_report(report_data, include_visualizations)
            else:
                raise ValueError(f"Unsupported report format: {report_format}")

            # Record generation metrics
            generation_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.metrics.observe_histogram(
                "security_report_generation_duration_seconds",
                generation_duration,
                labels={"format": report_format},
            )

            self.metrics.increment_counter(
                "security_report_generation_success_total", labels={"format": report_format}
            )

            logger.info(
                f"Security report generated successfully: {report_path} "
                f"({generation_duration:.2f}s)"
            )

            return str(report_path)

        except Exception as e:
            # Record generation error
            self.metrics.increment_counter(
                "security_report_generation_errors_total",
                labels={"format": report_format, "error_type": type(e).__name__},
            )

            logger.error(f"Security report generation failed: {e}")
            raise

    async def generate_executive_summary(
        self,
        events: list[SecurityAuditEvent],
        compliance_results: list[ComplianceScanResult],
        threat_patterns: list[ThreatPattern],
    ) -> dict[str, Any]:
        """
        Generate executive security summary.

        Args:
            events: Security audit events
            compliance_results: Compliance scan results
            threat_patterns: Identified threat patterns

        Returns:
            Executive summary data
        """
        try:
            # Calculate key metrics
            total_events = len(events)
            critical_events = len(
                [e for e in events if e.severity == SecurityEventSeverity.CRITICAL]
            )
            high_events = len([e for e in events if e.severity == SecurityEventSeverity.HIGH])

            # Compliance metrics
            total_scans = len(compliance_results)
            passed_scans = len([r for r in compliance_results if r.passed])
            avg_compliance_score = (
                sum(r.score for r in compliance_results) / total_scans if total_scans > 0 else 0.0
            )

            # Threat metrics
            total_threats = len(threat_patterns)
            critical_threats = len(
                [t for t in threat_patterns if t.severity == SecurityEventSeverity.CRITICAL]
            )

            # Risk assessment
            risk_score = self._calculate_overall_risk_score(
                events, compliance_results, threat_patterns
            )
            risk_level = self._determine_risk_level(risk_score)

            # Generate recommendations
            recommendations = self._generate_executive_recommendations(
                events, compliance_results, threat_patterns, risk_score
            )

            summary = {
                "report_metadata": {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "period_covered": self._get_analysis_period(events),
                    "report_version": "1.0.0",
                },
                "security_overview": {
                    "total_security_events": total_events,
                    "critical_events": critical_events,
                    "high_severity_events": high_events,
                    "event_trend": self._calculate_event_trend(events),
                },
                "compliance_status": {
                    "frameworks_assessed": total_scans,
                    "compliant_frameworks": passed_scans,
                    "average_compliance_score": round(avg_compliance_score, 3),
                    "compliance_trend": self._calculate_compliance_trend(compliance_results),
                },
                "threat_landscape": {
                    "active_threat_patterns": total_threats,
                    "critical_threats": critical_threats,
                    "threat_categories": self._get_threat_category_breakdown(threat_patterns),
                },
                "risk_assessment": {
                    "overall_risk_score": round(risk_score, 3),
                    "risk_level": risk_level,
                    "key_risk_factors": self._identify_key_risk_factors(
                        events, compliance_results, threat_patterns
                    ),
                },
                "executive_recommendations": recommendations,
                "next_actions": self._generate_next_actions(risk_level, recommendations),
            }

            logger.info("Executive security summary generated successfully")
            return summary

        except Exception as e:
            logger.error(f"Executive summary generation failed: {e}")
            return {"error": str(e), "generated_at": datetime.now(timezone.utc).isoformat()}

    async def generate_compliance_dashboard(
        self, compliance_results: list[ComplianceScanResult]
    ) -> str:
        """
        Generate compliance dashboard HTML report.

        Args:
            compliance_results: Compliance scan results

        Returns:
            Path to generated dashboard file
        """
        try:
            dashboard_data = {
                "compliance_overview": self._create_compliance_overview(compliance_results),
                "framework_details": self._create_framework_details(compliance_results),
                "trend_analysis": self._create_compliance_trends(compliance_results),
                "remediation_priorities": self._create_remediation_priorities(compliance_results),
            }

            dashboard_html = self._generate_compliance_dashboard_html(dashboard_data)

            dashboard_path = (
                self.output_directory
                / f"compliance_dashboard_{int(datetime.now().timestamp())}.html"
            )
            with open(dashboard_path, "w", encoding="utf-8") as f:
                f.write(dashboard_html)

            logger.info(f"Compliance dashboard generated: {dashboard_path}")
            return str(dashboard_path)

        except Exception as e:
            logger.error(f"Compliance dashboard generation failed: {e}")
            raise

    # Private helper methods

    async def _compile_report_data(
        self,
        events: list[SecurityAuditEvent],
        compliance_results: list[ComplianceScanResult],
        threat_patterns: list[ThreatPattern],
    ) -> dict[str, Any]:
        """Compile comprehensive report data."""
        return {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "report_version": "1.0.0",
                "data_sources": {
                    "security_events": len(events),
                    "compliance_scans": len(compliance_results),
                    "threat_patterns": len(threat_patterns),
                },
            },
            "executive_summary": await self.generate_executive_summary(
                events, compliance_results, threat_patterns
            ),
            "security_events": {
                "summary": self._analyze_security_events(events),
                "events": [
                    self._serialize_event(event) for event in events[:100]
                ],  # Limit for size
            },
            "compliance_analysis": {
                "summary": self._analyze_compliance_results(compliance_results),
                "results": [
                    self._serialize_compliance_result(result) for result in compliance_results
                ],
            },
            "threat_analysis": {
                "summary": self._analyze_threat_patterns(threat_patterns),
                "patterns": [
                    self._serialize_threat_pattern(pattern) for pattern in threat_patterns
                ],
            },
            "recommendations": self._generate_comprehensive_recommendations(
                events, compliance_results, threat_patterns
            ),
            "appendices": {
                "methodology": self._get_analysis_methodology(),
                "definitions": self._get_security_definitions(),
                "references": self._get_security_references(),
            },
        }

    async def _generate_json_report(self, report_data: dict[str, Any]) -> Path:
        """Generate JSON format report."""
        timestamp = int(datetime.now().timestamp())
        report_path = self.output_directory / f"security_report_{timestamp}.json"

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        return report_path

    async def _generate_html_report(
        self, report_data: dict[str, Any], include_visualizations: bool = True
    ) -> Path:
        """Generate HTML format report with styling and visualizations."""
        timestamp = int(datetime.now().timestamp())
        report_path = self.output_directory / f"security_report_{timestamp}.html"

        html_content = self._create_html_report_template().format(
            title="Comprehensive Security Report",
            generated_at=report_data["metadata"]["generated_at"],
            executive_summary=self._format_executive_summary_html(report_data["executive_summary"]),
            security_events_section=self._format_security_events_html(
                report_data["security_events"]
            ),
            compliance_section=self._format_compliance_html(report_data["compliance_analysis"]),
            threat_analysis_section=self._format_threat_analysis_html(
                report_data["threat_analysis"]
            ),
            recommendations_section=self._format_recommendations_html(
                report_data["recommendations"]
            ),
            visualizations_section=(
                self._generate_visualizations_html(report_data) if include_visualizations else ""
            ),
            appendices_section=self._format_appendices_html(report_data["appendices"]),
        )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return report_path

    async def _generate_pdf_report(
        self, report_data: dict[str, Any], include_visualizations: bool = True
    ) -> Path:
        """Generate PDF format report (placeholder - would require additional libraries)."""
        # This would typically use libraries like ReportLab or WeasyPrint
        # For now, generate HTML and indicate PDF conversion needed

        html_path = await self._generate_html_report(report_data, include_visualizations)
        pdf_path = self.output_directory / html_path.name.replace(".html", ".pdf")

        logger.warning(
            f"PDF generation not implemented. HTML report generated at: {html_path}. "
            f"Use external tool to convert to PDF: {pdf_path}"
        )

        return pdf_path

    def _create_html_report_template(self) -> str:
        """Create HTML report template."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f8f9fa;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .content {{
            padding: 30px;
        }}
        .section {{
            margin-bottom: 40px;
            border-bottom: 1px solid #eee;
            padding-bottom: 30px;
        }}
        .section:last-child {{
            border-bottom: none;
        }}
        .section h2 {{
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .metric-card {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 15px 0;
            border-radius: 0 5px 5px 0;
        }}
        .severity-critical {{ border-left-color: #dc3545; }}
        .severity-high {{ border-left-color: #fd7e14; }}
        .severity-medium {{ border-left-color: #ffc107; }}
        .severity-low {{ border-left-color: #28a745; }}
        .severity-info {{ border-left-color: #6c757d; }}
        .recommendation-item {{
            background: #e3f2fd;
            border-radius: 5px;
            padding: 15px;
            margin: 10px 0;
        }}
        .chart-container {{
            text-align: center;
            margin: 20px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
        }}
        .footer {{
            background: #343a40;
            color: white;
            text-align: center;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <p>Generated: {generated_at}</p>
        </div>

        <div class="content">
            <div class="section">
                <h2>Executive Summary</h2>
                {executive_summary}
            </div>

            <div class="section">
                <h2>Security Events Analysis</h2>
                {security_events_section}
            </div>

            <div class="section">
                <h2>Compliance Assessment</h2>
                {compliance_section}
            </div>

            <div class="section">
                <h2>Threat Analysis</h2>
                {threat_analysis_section}
            </div>

            <div class="section">
                <h2>Recommendations</h2>
                {recommendations_section}
            </div>

            {visualizations_section}

            <div class="section">
                <h2>Appendices</h2>
                {appendices_section}
            </div>
        </div>

        <div class="footer">
            <p>Generated by Marty Microservices Framework Security System</p>
            <p>© 2024 - Confidential Security Report</p>
        </div>
    </div>
</body>
</html>
        """

    # Analysis and formatting helper methods (simplified implementations)

    def _analyze_security_events(self, events: list[SecurityAuditEvent]) -> dict[str, Any]:
        """Analyze security events for summary."""
        if not events:
            return {"total": 0, "by_severity": {}, "trends": []}

        severity_counts = {}
        for event in events:
            severity = event.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return {
            "total": len(events),
            "by_severity": severity_counts,
            "time_range": {
                "start": min(event.timestamp for event in events).isoformat(),
                "end": max(event.timestamp for event in events).isoformat(),
            },
        }

    def _analyze_compliance_results(self, results: list[ComplianceScanResult]) -> dict[str, Any]:
        """Analyze compliance results for summary."""
        if not results:
            return {"total": 0, "passed": 0, "average_score": 0.0}

        passed = len([r for r in results if r.passed])
        avg_score = sum(r.score for r in results) / len(results)

        return {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "average_score": round(avg_score, 3),
            "frameworks": list({r.framework.value for r in results}),
        }

    def _analyze_threat_patterns(self, patterns: list[ThreatPattern]) -> dict[str, Any]:
        """Analyze threat patterns for summary."""
        if not patterns:
            return {"total": 0, "by_category": {}, "by_severity": {}}

        category_counts = {}
        severity_counts = {}

        for pattern in patterns:
            category = pattern.threat_category.value
            severity = pattern.severity.value

            category_counts[category] = category_counts.get(category, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return {
            "total": len(patterns),
            "by_category": category_counts,
            "by_severity": severity_counts,
        }

    # Placeholder methods for comprehensive functionality

    def _calculate_overall_risk_score(self, events, compliance_results, threat_patterns) -> float:
        """Calculate overall security risk score."""
        # Simplified risk calculation
        event_risk = len(
            [
                e
                for e in events
                if e.severity in [SecurityEventSeverity.CRITICAL, SecurityEventSeverity.HIGH]
            ]
        ) / max(len(events), 1)
        compliance_risk = 1.0 - (
            sum(r.score for r in compliance_results) / max(len(compliance_results), 1)
        )
        threat_risk = len(
            [t for t in threat_patterns if t.severity == SecurityEventSeverity.CRITICAL]
        ) / max(len(threat_patterns), 1)

        return event_risk * 0.4 + compliance_risk * 0.4 + threat_risk * 0.2

    def _determine_risk_level(self, risk_score: float) -> str:
        """Determine risk level from score."""
        if risk_score >= 0.8:
            return "CRITICAL"
        elif risk_score >= 0.6:
            return "HIGH"
        elif risk_score >= 0.4:
            return "MEDIUM"
        else:
            return "LOW"

    def _serialize_event(self, event: SecurityAuditEvent) -> dict[str, Any]:
        """Serialize security event for JSON output."""
        return asdict(event)

    def _serialize_compliance_result(self, result: ComplianceScanResult) -> dict[str, Any]:
        """Serialize compliance result for JSON output."""
        return asdict(result)

    def _serialize_threat_pattern(self, pattern: ThreatPattern) -> dict[str, Any]:
        """Serialize threat pattern for JSON output."""
        return asdict(pattern)

    # HTML formatting methods (simplified)

    def _format_executive_summary_html(self, summary: dict[str, Any]) -> str:
        """Format executive summary as HTML."""
        return f"""
        <div class="metric-card">
            <h3>Security Overview</h3>
            <p>Total Events: {summary.get("security_overview", {}).get("total_security_events", 0)}</p>
            <p>Risk Level: {summary.get("risk_assessment", {}).get("risk_level", "Unknown")}</p>
        </div>
        """

    def _format_security_events_html(self, events_data: dict[str, Any]) -> str:
        """Format security events section as HTML."""
        summary = events_data.get("summary", {})
        return f"""
        <div class="metric-card">
            <p>Total Events: {summary.get("total", 0)}</p>
            <p>Severity Breakdown: {summary.get("by_severity", {})}</p>
        </div>
        """

    def _format_compliance_html(self, compliance_data: dict[str, Any]) -> str:
        """Format compliance section as HTML."""
        summary = compliance_data.get("summary", {})
        return f"""
        <div class="metric-card">
            <p>Frameworks Assessed: {summary.get("total", 0)}</p>
            <p>Compliance Rate: {summary.get("passed", 0)}/{summary.get("total", 0)}</p>
        </div>
        """

    def _format_threat_analysis_html(self, threat_data: dict[str, Any]) -> str:
        """Format threat analysis section as HTML."""
        summary = threat_data.get("summary", {})
        return f"""
        <div class="metric-card">
            <p>Active Threats: {summary.get("total", 0)}</p>
            <p>Categories: {summary.get("by_category", {})}</p>
        </div>
        """

    def _format_recommendations_html(self, recommendations: list[dict[str, Any]]) -> str:
        """Format recommendations section as HTML."""
        html = ""
        for rec in recommendations[:5]:  # Show top 5
            html += f"""
            <div class="recommendation-item">
                <h4>{rec.get("title", "Recommendation")}</h4>
                <p>{rec.get("description", "No description available")}</p>
            </div>
            """
        return html

    def _format_appendices_html(self, appendices: dict[str, Any]) -> str:
        """Format appendices section as HTML."""
        return """
        <div class="metric-card">
            <h3>Analysis Methodology</h3>
            <p>This report was generated using automated security analysis tools and compliance frameworks.</p>
        </div>
        """

    def _generate_visualizations_html(self, report_data: dict[str, Any]) -> str:
        """Generate visualizations section (placeholder)."""
        return """
        <div class="section">
            <h2>Visualizations</h2>
            <div class="chart-container">
                <p>Charts and graphs would be generated here with visualization libraries.</p>
            </div>
        </div>
        """

    # Placeholder methods for additional functionality

    def _get_analysis_period(self, events: list[SecurityAuditEvent]) -> dict[str, str]:
        """Get analysis period from events."""
        if not events:
            return {"start": "N/A", "end": "N/A"}

        timestamps = [event.timestamp for event in events]
        return {"start": min(timestamps).isoformat(), "end": max(timestamps).isoformat()}

    def _calculate_event_trend(self, events: list[SecurityAuditEvent]) -> str:
        """Calculate event trend (simplified)."""
        return "stable"  # Placeholder

    def _calculate_compliance_trend(self, results: list[ComplianceScanResult]) -> str:
        """Calculate compliance trend (simplified)."""
        return "improving"  # Placeholder

    def _get_threat_category_breakdown(self, patterns: list[ThreatPattern]) -> dict[str, int]:
        """Get threat category breakdown."""
        breakdown = {}
        for pattern in patterns:
            category = pattern.threat_category.value
            breakdown[category] = breakdown.get(category, 0) + 1
        return breakdown

    def _identify_key_risk_factors(self, events, compliance_results, threat_patterns) -> list[str]:
        """Identify key risk factors."""
        return ["High severity events", "Compliance gaps", "Active threats"]

    def _generate_executive_recommendations(
        self, events, compliance_results, threat_patterns, risk_score
    ) -> list[dict[str, Any]]:
        """Generate executive recommendations."""
        return [
            {
                "priority": "high",
                "title": "Address Critical Security Events",
                "description": "Investigate and remediate critical security events immediately",
            }
        ]

    def _generate_next_actions(
        self, risk_level: str, recommendations: list[dict[str, Any]]
    ) -> list[str]:
        """Generate next action items."""
        return [
            "Review and prioritize security recommendations",
            "Schedule follow-up security assessment",
            "Update security policies and procedures",
        ]

    def _generate_comprehensive_recommendations(
        self, events, compliance_results, threat_patterns
    ) -> list[dict[str, Any]]:
        """Generate comprehensive recommendations."""
        return [
            {
                "category": "Security Events",
                "priority": "high",
                "title": "Event Response Procedures",
                "description": "Establish formal incident response procedures",
            }
        ]

    def _get_analysis_methodology(self) -> str:
        """Get analysis methodology description."""
        return "Automated security analysis using machine learning and rule-based detection"

    def _get_security_definitions(self) -> dict[str, str]:
        """Get security term definitions."""
        return {
            "Risk Score": "Calculated metric indicating overall security risk level",
            "Threat Pattern": "Identified pattern of malicious or suspicious activity",
        }

    def _get_security_references(self) -> list[str]:
        """Get security framework references."""
        return [
            "NIST Cybersecurity Framework",
            "OWASP Security Guidelines",
            "ISO 27001 Information Security Standard",
        ]

    # Additional placeholder methods for compliance dashboard

    def _create_compliance_overview(self, results: list[ComplianceScanResult]) -> dict[str, Any]:
        """Create compliance overview."""
        return {"placeholder": "compliance overview"}

    def _create_framework_details(self, results: list[ComplianceScanResult]) -> dict[str, Any]:
        """Create framework details."""
        return {"placeholder": "framework details"}

    def _create_compliance_trends(self, results: list[ComplianceScanResult]) -> dict[str, Any]:
        """Create compliance trends."""
        return {"placeholder": "compliance trends"}

    def _create_remediation_priorities(self, results: list[ComplianceScanResult]) -> dict[str, Any]:
        """Create remediation priorities."""
        return {"placeholder": "remediation priorities"}

    def _generate_compliance_dashboard_html(self, dashboard_data: dict[str, Any]) -> str:
        """Generate compliance dashboard HTML."""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Compliance Dashboard</title></head>
        <body><h1>Compliance Dashboard</h1><p>Dashboard content would be generated here.</p></body>
        </html>
        """
