"""
Integration test configuration for audit compliance service.

This module provides fixtures and configuration for integration tests
that verify the complete hexagonal architecture works end-to-end.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any

import pytest
import redis
from sqlalchemy.exc import OperationalError

from mmf.core.domain.audit_types import (
    AuditLevel,
    ComplianceFramework,
    SecurityEventSeverity,
    SecurityEventType,
)
from mmf.services.audit_compliance.di_config import (
    AuditComplianceConfig,
    AuditComplianceDIContainer,
    create_test_config,
)
from mmf.services.audit_compliance.service_factory import (
    AuditComplianceService,
    create_audit_compliance_service,
)

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config() -> AuditComplianceConfig:
    """Create test configuration."""
    return create_test_config()


@pytest.fixture
async def di_container(
    test_config: AuditComplianceConfig,
) -> AsyncGenerator[AuditComplianceDIContainer, None]:
    """Create and initialize DI container for tests."""
    container = AuditComplianceDIContainer(test_config)
    await container.initialize()

    try:
        yield container
    finally:
        await container.shutdown()


@pytest.fixture
async def audit_service(
    test_config: AuditComplianceConfig,
) -> AsyncGenerator[AuditComplianceService, None]:
    """Create audit compliance service for tests."""
    service = await create_audit_compliance_service(test_config, "test")

    try:
        yield service
    finally:
        await service.shutdown()


@pytest.fixture
def sample_audit_events() -> list[dict[str, Any]]:
    """Sample audit events for testing."""
    return [
        {
            "event_type": SecurityEventType.AUTHENTICATION_SUCCESS,
            "severity": SecurityEventSeverity.INFO,
            "source": "auth_service",
            "description": "User logged in successfully",
            "user_id": "user123",
            "metadata": {"ip_address": "192.168.1.100", "user_agent": "Mozilla/5.0"},
        },
        {
            "event_type": SecurityEventType.AUTHENTICATION_FAILURE,
            "severity": SecurityEventSeverity.WARNING,
            "source": "auth_service",
            "description": "Failed login attempt",
            "user_id": "user456",
            "metadata": {"ip_address": "10.0.0.50", "reason": "invalid_password"},
        },
        {
            "event_type": SecurityEventType.PERMISSION_DENIED,
            "severity": SecurityEventSeverity.HIGH,
            "source": "api_gateway",
            "description": "Unauthorized access attempt",
            "resource_id": "sensitive_endpoint",
            "metadata": {"endpoint": "/admin/users", "method": "DELETE"},
        },
        {
            "event_type": SecurityEventType.DATA_ACCESS,
            "severity": SecurityEventSeverity.MEDIUM,
            "source": "database_service",
            "description": "Sensitive data accessed",
            "user_id": "admin_user",
            "resource_id": "customer_pii",
            "metadata": {"table": "customers", "records_accessed": 150},
        },
    ]


@pytest.fixture
def compliance_frameworks() -> list[ComplianceFramework]:
    """Sample compliance frameworks for testing."""
    return [
        ComplianceFramework.GDPR,
        ComplianceFramework.HIPAA,
        ComplianceFramework.SOX,
        ComplianceFramework.PCI_DSS,
    ]


@pytest.fixture
def threat_patterns_data() -> list[dict[str, Any]]:
    """Sample threat pattern data for testing."""
    return [
        {
            "pattern_type": "brute_force",
            "indicators": ["multiple_failed_logins", "short_time_interval", "same_source_ip"],
            "confidence": 0.85,
            "severity": "high",
        },
        {
            "pattern_type": "privilege_escalation",
            "indicators": ["admin_access_pattern", "unusual_permissions", "system_modification"],
            "confidence": 0.75,
            "severity": "critical",
        },
        {
            "pattern_type": "data_exfiltration",
            "indicators": ["large_data_transfer", "off_hours_access", "external_destination"],
            "confidence": 0.90,
            "severity": "critical",
        },
    ]


@pytest.fixture
def mock_siem_events() -> list[dict[str, Any]]:
    """Mock SIEM events for testing collection."""
    return [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "security_alert",
            "severity": "high",
            "source": "firewall",
            "message": "Suspicious network traffic detected",
            "metadata": {
                "source_ip": "192.168.1.50",
                "destination_ip": "10.0.0.100",
                "port": 443,
                "protocol": "TCP",
            },
        },
        {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "malware_detection",
            "severity": "critical",
            "source": "endpoint_protection",
            "message": "Malware signature detected",
            "metadata": {
                "file_path": "/tmp/suspicious_file.exe",  # nosec B108
                "hash": "abc123def456",  # pragma: allowlist secret
                "user": "test_user",
            },
        },
    ]


# Helper functions for tests


def assert_audit_event_valid(event, expected_data: dict[str, Any]):
    """Assert that audit event matches expected data."""
    assert event.event_type == expected_data["event_type"]
    assert event.severity == expected_data["severity"]
    assert event.source == expected_data["source"]
    assert event.description == expected_data["description"]

    if "user_id" in expected_data:
        assert event.user_id == expected_data["user_id"]
    if "resource_id" in expected_data:
        assert event.resource_id == expected_data["resource_id"]


def assert_compliance_scan_valid(scan_result, expected_frameworks: list):
    """Assert that compliance scan result is valid."""
    assert scan_result is not None
    assert scan_result.scan_id is not None
    assert scan_result.frameworks == expected_frameworks
    assert scan_result.overall_score is not None
    assert 0 <= scan_result.overall_score <= 1
    assert len(scan_result.framework_results) > 0


def assert_threat_pattern_valid(threat_pattern):
    """Assert that threat pattern is valid."""
    assert threat_pattern is not None
    assert threat_pattern.pattern_id is not None
    assert threat_pattern.pattern_type is not None
    assert threat_pattern.confidence is not None
    assert 0 <= threat_pattern.confidence <= 1
    assert threat_pattern.severity is not None
    assert len(threat_pattern.indicators) > 0


def assert_security_report_valid(report_data: dict[str, Any]):
    """Assert that security report is valid."""
    assert "report_id" in report_data
    assert "report_path" in report_data
    assert "metadata" in report_data
    assert report_data["report_id"] is not None
    assert report_data["report_path"] is not None


# Mock implementations for external services


class MockElasticsearchClient:
    """Mock Elasticsearch client for testing."""

    def __init__(self):
        self.indexed_documents = []
        self.search_results = []

    async def index(self, index: str, document: dict[str, Any]):
        """Mock document indexing."""
        self.indexed_documents.append(
            {"index": index, "document": document, "timestamp": datetime.utcnow()}
        )
        return {"_id": f"mock_id_{len(self.indexed_documents)}"}

    async def search(self, index: str, query: dict[str, Any]):
        """Mock document search."""
        return {
            "hits": {
                "total": {"value": len(self.search_results)},
                "hits": [
                    {"_source": result, "_id": f"id_{i}"}
                    for i, result in enumerate(self.search_results)
                ],
            }
        }

    def set_search_results(self, results: list[dict[str, Any]]):
        """Set mock search results."""
        self.search_results = results


# Performance testing utilities


class PerformanceTimer:
    """Simple performance timer for testing."""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        self.start_time = datetime.utcnow()

    def stop(self):
        self.end_time = datetime.utcnow()

    @property
    def duration_ms(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0


@pytest.fixture
def perf_timer() -> PerformanceTimer:
    """Performance timer fixture."""
    return PerformanceTimer()


# Test data generators


def generate_audit_events(count: int) -> list[dict[str, Any]]:
    """Generate test audit events."""
    event_types = [
        SecurityEventType.AUTHENTICATION_SUCCESS,
        SecurityEventType.AUTHENTICATION_FAILURE,
        SecurityEventType.PERMISSION_DENIED,
        SecurityEventType.DATA_ACCESS,
        SecurityEventType.CONFIGURATION_CHANGE,
    ]

    severities = [
        SecurityEventSeverity.INFO,
        SecurityEventSeverity.LOW,
        SecurityEventSeverity.MEDIUM,
        SecurityEventSeverity.HIGH,
        SecurityEventSeverity.CRITICAL,
    ]

    events = []
    for i in range(count):
        events.append(
            {
                "event_type": event_types[i % len(event_types)],
                "severity": severities[i % len(severities)],
                "source": f"test_service_{i % 5}",
                "description": f"Test event {i}",
                "user_id": f"user_{i % 10}",
                "resource_id": f"resource_{i % 20}",
                "metadata": {"test_data": True, "event_number": i},
            }
        )

    return events


# Error simulation utilities


class ErrorSimulator:
    """Utility to simulate various error conditions."""

    @staticmethod
    def simulate_database_error():
        """Simulate database connection error."""

        raise OperationalError("Database connection failed", None, None)

    @staticmethod
    def simulate_cache_error():
        """Simulate Redis cache error."""

        raise redis.ConnectionError("Redis connection failed")

    @staticmethod
    def simulate_elasticsearch_error():
        """Simulate Elasticsearch error."""
        raise ConnectionError("Elasticsearch connection failed")


# Test configuration validation


def validate_test_environment():
    """Validate that test environment is properly configured."""
    try:
        # Check that we can create test config
        config = create_test_config()
        assert config.database_url == "sqlite:///:memory:"
        assert config.redis_url == "redis://localhost:6379/2"
        assert config.cache_max_events == 1000

        logger.info("Test environment validation passed")
        return True

    except Exception as e:
        logger.error(f"Test environment validation failed: {e}")
        return False
