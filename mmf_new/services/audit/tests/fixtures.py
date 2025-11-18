"""
Integration Test Fixtures for Audit Service

This module provides comprehensive test fixtures for testing the audit service
in various scenarios including database, encryption, and middleware integration.
"""

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Optional, dict
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionMaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Import audit service components
from mmf_new.core.domain.audit_types import AuditEventType, AuditOutcome, AuditSeverity
from mmf_new.services.audit.application.commands import LogRequestCommand
from mmf_new.services.audit.di_config import AuditDIContainer
from mmf_new.services.audit.domain.entities import RequestAuditEvent
from mmf_new.services.audit.domain.value_objects import (
    RequestInfo,
    ResponseInfo,
    SystemInfo,
    UserInfo,
)
from mmf_new.services.audit.infrastructure.adapters.audit_encryption_adapter import (
    AuditEncryptionAdapter,
)
from mmf_new.services.audit.infrastructure.adapters.database_audit_destination import (
    DatabaseAuditDestination,
)
from mmf_new.services.audit.infrastructure.adapters.file_audit_destination import (
    FileAuditDestination,
)
from mmf_new.services.audit.infrastructure.models import AuditLogRecord
from mmf_new.services.audit.infrastructure.repository import AuditRepository
from mmf_new.services.audit.service_factory import AuditServiceFactory


class TestDatabaseConfig:
    """Test database configuration."""

    def __init__(self):
        self.database_url = "sqlite+aiosqlite:///:memory:"
        self.echo = False
        self.pool_class = StaticPool
        self.connect_args = {"check_same_thread": False}


@pytest_asyncio.fixture
async def test_database_engine():
    """Create test database engine."""
    config = TestDatabaseConfig()
    engine = create_async_engine(
        config.database_url,
        echo=config.echo,
        poolclass=config.pool_class,
        connect_args=config.connect_args,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(AuditLogRecord.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def test_database_session(test_database_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = AsyncSessionMaker(
        test_database_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def test_encryption_adapter() -> AsyncGenerator[AuditEncryptionAdapter, None]:
    """Create test encryption adapter."""
    # Use a test encryption key
    test_key = b"test_key_32_bytes_long_for_testing"
    adapter = AuditEncryptionAdapter(encryption_key=test_key)
    yield adapter


@pytest_asyncio.fixture
async def test_temp_directory() -> AsyncGenerator[Path, None]:
    """Create temporary directory for file tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest_asyncio.fixture
async def test_file_audit_destination(
    test_temp_directory, test_encryption_adapter
) -> AsyncGenerator[FileAuditDestination, None]:
    """Create test file audit destination."""
    destination = FileAuditDestination(
        base_directory=test_temp_directory,
        max_file_size_mb=1,  # Small for testing
        encryption_adapter=test_encryption_adapter,
    )
    yield destination


@pytest_asyncio.fixture
async def test_database_audit_destination(
    test_database_session, test_encryption_adapter
) -> AsyncGenerator[DatabaseAuditDestination, None]:
    """Create test database audit destination."""
    destination = DatabaseAuditDestination(
        session_factory=lambda: test_database_session,
        encryption_adapter=test_encryption_adapter,
        batch_size=5,  # Small batch for testing
        batch_timeout_seconds=1.0,  # Quick timeout for testing
    )
    yield destination

    # Cleanup any pending batches
    await destination.flush()


@pytest_asyncio.fixture
async def test_audit_repository(
    test_database_session, test_encryption_adapter
) -> AsyncGenerator[AuditRepository, None]:
    """Create test audit repository."""
    repository = AuditRepository(
        session_factory=lambda: test_database_session, encryption_adapter=test_encryption_adapter
    )
    yield repository


@pytest_asyncio.fixture
def mock_audit_compliance_service():
    """Create mock audit compliance service."""
    mock_service = AsyncMock()
    mock_service.forward_audit_event = AsyncMock(return_value=True)
    return mock_service


@pytest_asyncio.fixture
async def test_audit_di_container(
    test_database_session,
    test_encryption_adapter,
    test_temp_directory,
    mock_audit_compliance_service,
) -> AsyncGenerator[AuditDIContainer, None]:
    """Create test DI container with all dependencies."""

    # Create destinations
    database_destination = DatabaseAuditDestination(
        session_factory=lambda: test_database_session,
        encryption_adapter=test_encryption_adapter,
        batch_size=5,
        batch_timeout_seconds=1.0,
    )

    file_destination = FileAuditDestination(
        base_directory=test_temp_directory,
        max_file_size_mb=1,
        encryption_adapter=test_encryption_adapter,
    )

    console_destination = AsyncMock()  # Mock console for testing

    destinations = [database_destination, file_destination, console_destination]

    # Create repository
    repository = AuditRepository(
        session_factory=lambda: test_database_session, encryption_adapter=test_encryption_adapter
    )

    # Create container
    container = AuditDIContainer(
        destinations=destinations,
        repository=repository,
        audit_compliance_service=mock_audit_compliance_service,
        encryption_adapter=test_encryption_adapter,
    )

    yield container

    # Cleanup
    await database_destination.flush()


@pytest_asyncio.fixture
async def test_audit_service_factory(
    test_audit_di_container,
) -> AsyncGenerator[AuditServiceFactory, None]:
    """Create test audit service factory."""
    factory = AuditServiceFactory(test_audit_di_container)
    yield factory


# Sample test data fixtures
@pytest.fixture
def sample_user_info() -> UserInfo:
    """Create sample user info."""
    return UserInfo(
        user_id="test-user-123",
        user_role="admin",
        session_id="session-456",
        ip_address="192.168.1.100",
        user_agent="TestAgent/1.0",
    )


@pytest.fixture
def sample_request_info() -> RequestInfo:
    """Create sample request info."""
    return RequestInfo(
        method="POST",
        path="/api/v1/users",
        query_params={"include": "profile"},
        headers={"Content-Type": "application/json"},
        body_size=256,
    )


@pytest.fixture
def sample_response_info() -> ResponseInfo:
    """Create sample response info."""
    return ResponseInfo(
        status_code=201,
        headers={"Location": "/api/v1/users/123"},
        body_size=128,
        execution_time_ms=150,
    )


@pytest.fixture
def sample_system_info() -> SystemInfo:
    """Create sample system info."""
    return SystemInfo(
        service_name="user-service",
        service_version="1.2.3",
        environment="test",
        hostname="test-host",
        correlation_id="corr-789",
    )


@pytest.fixture
def sample_audit_event(
    sample_user_info, sample_request_info, sample_response_info, sample_system_info
) -> RequestAuditEvent:
    """Create sample audit event."""
    return RequestAuditEvent(
        event_type=AuditEventType.API_REQUEST,
        severity=AuditSeverity.MEDIUM,
        outcome=AuditOutcome.SUCCESS,
        user_info=sample_user_info,
        request_info=sample_request_info,
        response_info=sample_response_info,
        system_info=sample_system_info,
        additional_context={"test": "data"},
    )


@pytest.fixture
def sample_log_request_command(
    sample_user_info, sample_request_info, sample_response_info, sample_system_info
) -> LogRequestCommand:
    """Create sample log request command."""
    return LogRequestCommand(
        event_type=AuditEventType.API_REQUEST,
        severity=AuditSeverity.MEDIUM,
        service_name="user-service",
        endpoint="/api/v1/users",
        method="POST",
        user_id="test-user-123",
        user_role="admin",
        user_session_id="session-456",
        client_ip="192.168.1.100",
        user_agent="TestAgent/1.0",
        request_data={"name": "John Doe", "email": "john@example.com"},
        response_data={"id": 123, "name": "John Doe"},
        status_code=201,
        execution_time_seconds=0.15,
        correlation_id="corr-789",
        additional_context={"test": "data"},
    )


# Test scenario fixtures
@pytest.fixture
def high_severity_events() -> list[LogRequestCommand]:
    """Create list of high severity events for compliance forwarding testing."""
    return [
        LogRequestCommand(
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.HIGH,
            service_name="auth-service",
            endpoint="/auth/login",
            method="POST",
            user_id="attacker-user",
            status_code=401,
            additional_context={"failed_attempts": 5},
        ),
        LogRequestCommand(
            event_type=AuditEventType.DATA_BREACH,
            severity=AuditSeverity.CRITICAL,
            service_name="user-service",
            endpoint="/api/v1/users/sensitive",
            method="GET",
            user_id="unauthorized-user",
            status_code=403,
            additional_context={"attempted_access": "sensitive_data"},
        ),
    ]


@pytest.fixture
def batch_test_events() -> list[LogRequestCommand]:
    """Create list of events for batch processing testing."""
    events = []
    for i in range(10):
        events.append(
            LogRequestCommand(
                event_type=AuditEventType.API_REQUEST,
                severity=AuditSeverity.LOW,
                service_name=f"service-{i % 3}",
                endpoint=f"/api/v1/resource/{i}",
                method="GET",
                user_id=f"user-{i % 5}",
                status_code=200,
                execution_time_seconds=0.1 + (i * 0.01),
                additional_context={"batch_test": True, "index": i},
            )
        )
    return events


@pytest.fixture
def encryption_test_data() -> dict[str, any]:
    """Create test data for encryption testing."""
    return {
        "sensitive_data": {
            "password": "super_secret_password",  # pragma: allowlist secret
            "ssn": "123-45-6789",
            "credit_card": "4111-1111-1111-1111",
            "api_key": "sk_test_123456789",  # pragma: allowlist secret
        },
        "non_sensitive_data": {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
            "status": "active",
        },
    }


# Performance testing fixtures
@pytest.fixture
def performance_test_config():
    """Configuration for performance testing."""
    return {
        "concurrent_requests": 100,
        "total_requests": 1000,
        "request_rate_per_second": 50,
        "max_response_time": 1.0,  # seconds
        "success_rate_threshold": 0.95,  # 95%
    }


# Error simulation fixtures
@pytest.fixture
def error_scenarios():
    """Different error scenarios for testing."""
    return {
        "database_connection_error": Exception("Database connection failed"),
        "encryption_error": Exception("Encryption key invalid"),
        "file_write_error": OSError("No space left on device"),
        "network_timeout": asyncio.TimeoutError("Network timeout"),
        "serialization_error": ValueError("Cannot serialize data"),
    }


# Middleware testing fixtures
@pytest.fixture
def mock_fastapi_request():
    """Create mock FastAPI request."""
    mock_request = MagicMock()
    mock_request.method = "POST"
    mock_request.url.path = "/api/v1/users"
    mock_request.url.query = "include=profile"
    mock_request.headers = {"Content-Type": "application/json", "User-Agent": "TestAgent/1.0"}
    mock_request.client.host = "192.168.1.100"
    mock_request.state.user_id = "test-user-123"
    mock_request.state.user_role = "admin"
    return mock_request


@pytest.fixture
def mock_fastapi_response():
    """Create mock FastAPI response."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.headers = {"Location": "/api/v1/users/123"}
    return mock_response


@pytest.fixture
def mock_grpc_context():
    """Create mock gRPC context."""
    mock_context = AsyncMock()
    mock_context.peer.return_value = "ipv4:192.168.1.100:54321"
    mock_context.invocation_metadata.return_value = [
        ("user-id", "test-user-123"),
        ("user-role", "admin"),
        ("content-type", "application/grpc"),
    ]
    mock_context.code.return_value = 0  # OK status
    return mock_context


# Integration test scenarios
@pytest.fixture
def integration_test_scenarios():
    """Different integration test scenarios."""
    return {
        "success_flow": {
            "description": "Complete successful audit flow",
            "steps": [
                "create_audit_event",
                "encrypt_sensitive_data",
                "store_in_database",
                "write_to_file",
                "forward_to_compliance",
                "verify_storage",
            ],
        },
        "partial_failure": {
            "description": "Some destinations fail, others succeed",
            "steps": [
                "create_audit_event",
                "fail_database_storage",
                "succeed_file_storage",
                "verify_independent_failures",
            ],
        },
        "compliance_forwarding": {
            "description": "High severity events forwarded to compliance",
            "steps": [
                "create_high_severity_event",
                "verify_compliance_forwarding",
                "verify_normal_storage",
            ],
        },
    }
