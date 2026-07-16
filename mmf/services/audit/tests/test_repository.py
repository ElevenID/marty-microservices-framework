from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from mmf.core.domain.audit_types import AuditEventType, AuditOutcome, AuditSeverity
from mmf.services.audit.domain.entities import RequestAuditEvent
from mmf.services.audit.domain.value_objects import (
    ActorInfo,
    RequestContext,
    ResourceInfo,
    ServiceContext,
)

# Define a test-specific model compatible with SQLite
TestBase = declarative_base()


class TestAuditLogRecord(TestBase):
    """Test database model for audit log records."""

    __tablename__ = "audit_logs"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Core event information
    event_id = Column(String(36), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    outcome = Column(String(20), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    message = Column(Text)

    # Actor information
    user_id = Column(String(255), index=True)
    username = Column(String(255))
    session_id = Column(String(255), index=True)
    api_key_id = Column(String(255))
    client_id = Column(String(255))

    # Request information
    source_ip = Column(String(50))  # Changed from INET
    user_agent = Column(Text)
    request_id = Column(String(255), index=True)
    method = Column(String(10))
    endpoint = Column(String(500))

    # Resource and action
    resource_type = Column(String(100), index=True)
    resource_id = Column(String(255))
    action = Column(String(255))

    # Context
    service_name = Column(String(100), index=True)
    environment = Column(String(50), index=True)
    correlation_id = Column(String(255), index=True)
    trace_id = Column(String(255), index=True)

    # Performance metrics
    duration_ms = Column(Float)
    response_size = Column(Integer)
    status_code = Column(Integer)

    # Error information
    error_code = Column(String(100))
    error_message = Column(Text)

    # Additional data
    details = Column(JSON)  # Changed from JSONB
    encrypted_fields = Column(JSON)  # Changed from JSONB

    # Security correlation
    security_event_id = Column(String(36), index=True)

    # Metadata
    event_hash = Column(String(64))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@pytest.fixture
def repository(db_session):
    # Mock session factory to return the fixture session
    class MockSessionFactory:
        def __call__(self):
            return db_session

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Patch the AuditLogRecord in the repository module with our TestAuditLogRecord
    with patch(
        "mmf.services.audit.infrastructure.repositories.audit_repository.AuditLogRecord",
        TestAuditLogRecord,
    ):
        from mmf.services.audit.infrastructure.repositories.audit_repository import (
            AuditRepository,
        )

        repo = AuditRepository(MockSessionFactory())
        yield repo


@pytest.mark.asyncio
async def test_save_and_find_audit_event(repository):
    event_id = uuid4()
    event = RequestAuditEvent(
        event_id=event_id,
        event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
        severity=AuditSeverity.INFO,
        outcome=AuditOutcome.SUCCESS,
        timestamp=datetime.now(timezone.utc),
        message="Test login",
        actor_info=ActorInfo(user_id="user123", username="testuser"),
        request_context=RequestContext(
            method="POST", endpoint="/auth/login", request_id="req123", source_ip="127.0.0.1"
        ),
        resource_info=ResourceInfo(resource_type="auth", action="login"),
        service_context=ServiceContext(
            service_name="auth-service", environment="test", version="1.0.0", instance_id="inst-1"
        ),
    )

    # Save
    saved_event = await repository.save(event)
    assert saved_event.id == event_id

    # Find by ID
    found_event = await repository.find_by_id(event_id)
    assert found_event is not None
    assert found_event.id == event_id
    assert found_event.message == "Test login"
    assert found_event.actor_info.user_id == "user123"


@pytest.mark.asyncio
async def test_find_by_criteria(repository):
    # Create events
    event1 = RequestAuditEvent(
        event_id=uuid4(),
        event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
        severity=AuditSeverity.INFO,
        outcome=AuditOutcome.SUCCESS,
        timestamp=datetime.now(timezone.utc),
        message="Login success",
        service_context=ServiceContext(
            service_name="auth-service", environment="test", version="1.0.0", instance_id="inst-1"
        ),
    )

    event2 = RequestAuditEvent(
        event_id=uuid4(),
        event_type=AuditEventType.AUTH_LOGIN_FAILURE,
        severity=AuditSeverity.HIGH,
        outcome=AuditOutcome.FAILURE,
        timestamp=datetime.now(timezone.utc),
        message="Login failed",
        service_context=ServiceContext(
            service_name="auth-service", environment="test", version="1.0.0", instance_id="inst-1"
        ),
    )

    await repository.save(event1)
    await repository.save(event2)

    # Search by severity
    high_severity_events = await repository.find_by_criteria(severity=AuditSeverity.HIGH)
    assert len(high_severity_events) == 1
    assert high_severity_events[0].id == event2.id

    # Search by event type
    login_success_events = await repository.find_by_criteria(
        event_type=AuditEventType.AUTH_LOGIN_SUCCESS
    )
    assert len(login_success_events) == 1
    assert login_success_events[0].id == event1.id
