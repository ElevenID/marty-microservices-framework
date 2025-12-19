from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from mmf.core.domain import ComplianceFramework
from mmf.services.audit_compliance.application.use_cases.generate_security_report import (
    GenerateSecurityReportRequest,
    GenerateSecurityReportUseCase,
)
from mmf.services.audit_compliance.application.use_cases.scan_compliance import (
    ScanComplianceRequest,
    ScanComplianceUseCase,
)
from mmf.services.audit_compliance.domain.models import ComplianceScanResult


@pytest.mark.unit
class TestGenerateSecurityReportUseCase:
    @pytest.fixture
    def mock_report_generator(self):
        return AsyncMock()

    @pytest.fixture
    def mock_audit_repository(self):
        return AsyncMock()

    @pytest.fixture
    def mock_compliance_scanner(self):
        return AsyncMock()

    @pytest.fixture
    def mock_threat_analyzer(self):
        return AsyncMock()

    @pytest.fixture
    def use_case(
        self,
        mock_report_generator,
        mock_audit_repository,
        mock_compliance_scanner,
        mock_threat_analyzer,
    ):
        return GenerateSecurityReportUseCase(
            report_generator=mock_report_generator,
            audit_repository=mock_audit_repository,
            compliance_scanner=mock_compliance_scanner,
            threat_analyzer=mock_threat_analyzer,
        )

    @pytest.mark.asyncio
    async def test_execute_basic_report(self, use_case, mock_audit_repository):
        # Setup
        request = GenerateSecurityReportRequest(
            report_type="security",
            user_id="user123",
            include_audit_events=True,
            include_compliance_scans=False,
            include_threat_analysis=False,
        )

        mock_audit_repository.find_by_criteria.return_value = []

        # Execute
        response = await use_case.execute(request)

        # Verify
        assert response.success
        assert response.report_data["report_metadata"]["report_type"] == "security"
        mock_audit_repository.find_by_criteria.assert_called_once()


@pytest.mark.unit
class TestScanComplianceUseCase:
    @pytest.fixture
    def mock_scanner(self):
        scanner = AsyncMock()
        # is_framework_supported is synchronous
        scanner.is_framework_supported = Mock()
        return scanner

    @pytest.fixture
    def mock_repository(self):
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_scanner, mock_repository):
        return ScanComplianceUseCase(scanner=mock_scanner, repository=mock_repository)

    @pytest.mark.asyncio
    async def test_execute_successful_scan(self, use_case, mock_scanner):
        # Setup
        request = ScanComplianceRequest(
            framework=ComplianceFramework.GDPR,
            target_resource="db-prod-01",
            target_type="database",
            user_id="user123",
        )

        mock_scanner.is_framework_supported.return_value = True

        mock_scan_result = Mock(spec=ComplianceScanResult)
        mock_scan_result.is_compliant.return_value = True
        mock_scan_result.score = 100
        mock_scan_result.findings = []

        mock_scanner.scan.return_value = mock_scan_result

        # Execute
        response = await use_case.execute(request)

        # Verify
        assert response.success
        assert response.scan_result == mock_scan_result
        mock_scanner.scan.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_unsupported_framework(self, use_case, mock_scanner):
        # Setup
        request = ScanComplianceRequest(
            framework=ComplianceFramework.GDPR,
            target_resource="db-prod-01",
            target_type="database",
            user_id="user123",
        )

        mock_scanner.is_framework_supported.return_value = False

        # Execute
        response = await use_case.execute(request)

        # Verify
        assert not response.success
        assert "not supported" in response.error_message
        mock_scanner.scan.assert_not_called()
