"""Compliance scanner port interface for the domain layer."""

from abc import ABC, abstractmethod
from typing import Any

from mmf_new.core.domain import ComplianceFramework

from ..models.compliance_scan_result import ComplianceScanResult


class IComplianceScanner(ABC):
    """Port interface for compliance scanning operations."""

    @abstractmethod
    async def scan(
        self,
        framework: ComplianceFramework,
        target_resource: str,
        target_type: str,
        scan_configuration: dict[str, Any] | None = None,
    ) -> ComplianceScanResult:
        """Perform a compliance scan.

        Args:
            framework: The compliance framework to scan against
            target_resource: The resource to scan (e.g., service name, database name)
            target_type: Type of resource being scanned
            scan_configuration: Optional configuration for the scan

        Returns:
            ComplianceScanResult with findings and recommendations
        """
        pass

    @abstractmethod
    async def get_supported_frameworks(self) -> list[ComplianceFramework]:
        """Get list of supported compliance frameworks.

        Returns:
            List of supported compliance frameworks
        """
        pass

    @abstractmethod
    async def validate_configuration(
        self,
        framework: ComplianceFramework,
        configuration: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate scan configuration for a framework.

        Args:
            framework: The compliance framework
            configuration: Configuration to validate

        Returns:
            Dictionary with validation results and any errors
        """
        pass

    @abstractmethod
    def is_framework_supported(self, framework: ComplianceFramework) -> bool:
        """Check if a compliance framework is supported.

        Args:
            framework: The compliance framework to check

        Returns:
            True if framework is supported, False otherwise
        """
        pass

    @abstractmethod
    async def get_framework_rules(self, framework: ComplianceFramework) -> list[dict[str, Any]]:
        """Get the rules for a specific compliance framework.

        Args:
            framework: The compliance framework

        Returns:
            List of rules with their metadata
        """
        pass
