"""Scan compliance use case."""

from dataclasses import dataclass
from typing import Any

from mmf.core.application.base import Command, CommandRequest
from mmf.core.domain import AuditLevel, ComplianceFramework, SecurityEventType

from ...domain.models import ComplianceScanResult, SecurityAuditEvent
from ..ports_out import AuditEventRepositoryPort, ComplianceScannerPort


@dataclass(kw_only=True)
class ScanComplianceRequest(CommandRequest):
    """Request to scan for compliance."""

    framework: ComplianceFramework
    target_resource: str
    target_type: str  # "service", "database", "api", etc.
    scan_configuration: dict[str, Any] | None = None
    save_results: bool = True


@dataclass
class ScanComplianceResponse:
    """Response from compliance scan."""

    scan_result: ComplianceScanResult
    success: bool
    error_message: str | None = None
    warnings: list[str] | None = None


class ScanComplianceUseCase(Command[ScanComplianceRequest, ScanComplianceResponse]):
    """Use case for performing compliance scans."""

    def __init__(
        self,
        scanner: ComplianceScannerPort,
        repository: AuditEventRepositoryPort | None = None,
    ):
        self.scanner = scanner
        self.repository = repository

    async def execute(self, request: ScanComplianceRequest) -> ScanComplianceResponse:
        """Execute the compliance scan use case."""
        warnings = []

        try:
            # Validate framework support
            if not self.scanner.is_framework_supported(request.framework):
                return ScanComplianceResponse(
                    scan_result=None,  # type: ignore
                    success=False,
                    error_message=f"Framework {request.framework.value} is not supported",
                )

            # Validate configuration if provided
            if request.scan_configuration:
                validation_result = await self.scanner.validate_configuration(
                    request.framework,
                    request.scan_configuration,
                )
                if not validation_result.get("valid", True):
                    return ScanComplianceResponse(
                        scan_result=None,  # type: ignore
                        success=False,
                        error_message=f"Invalid configuration: {validation_result.get('errors', [])}",
                    )

                # Add any validation warnings
                if validation_result.get("warnings"):
                    warnings.extend(validation_result["warnings"])

            # Perform the scan
            scan_result = await self.scanner.scan(
                framework=request.framework,
                target_resource=request.target_resource,
                target_type=request.target_type,
                scan_configuration=request.scan_configuration,
            )

            # Log the scan event if repository is available
            if self.repository and request.save_results:
                try:
                    # Create an audit event for the compliance scan

                    audit_event = SecurityAuditEvent(
                        event_type=SecurityEventType.COMPLIANCE_VIOLATION
                        if not scan_result.is_compliant()
                        else SecurityEventType.DATA_ACCESS,
                        principal_id=request.user_id,
                        resource=request.target_resource,
                        action="compliance_scan",
                        result="compliant" if scan_result.is_compliant() else "non_compliant",
                        details={
                            "framework": request.framework.value,
                            "target_type": request.target_type,
                            "score": scan_result.score,
                            "findings_count": len(scan_result.findings),
                            "critical_findings": len(scan_result.get_critical_findings()),
                        },
                        correlation_id=request.correlation_id,
                        level=AuditLevel.WARNING
                        if not scan_result.is_compliant()
                        else AuditLevel.INFO,
                    )

                    await self.repository.save(audit_event)
                except Exception as e:
                    warnings.append(f"Failed to log compliance scan audit event: {str(e)}")

            return ScanComplianceResponse(
                scan_result=scan_result,
                success=True,
                warnings=warnings if warnings else None,
            )

        except Exception as e:
            return ScanComplianceResponse(
                scan_result=None,  # type: ignore
                success=False,
                error_message=str(e),
                warnings=warnings if warnings else None,
            )
