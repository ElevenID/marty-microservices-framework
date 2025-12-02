"""Security report generator contract."""

from typing import Any, Protocol


class ISecurityReportGenerator(Protocol):
    """Interface for security report generation."""

    async def generate_report(
        self,
        data: dict[str, Any],
        format: str,
        report_type: str,
    ) -> str:
        """
        Generate a security report.

        Args:
            data: Report data
            format: Output format (json, html, pdf)
            report_type: Type of report

        Returns:
            Path to the generated report file
        """
        ...
