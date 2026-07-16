"""Tests for audit service use cases."""

from datetime import datetime, timezone
from unittest.mock import ANY, AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from mmf.core.domain.audit_types import (
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
    SecurityEventSeverity,
    SecurityEventType,
)
from mmf.services.audit.application.commands import (
    GenerateAuditReportCommand,
    LogRequestCommand,
    QueryAuditEventsCommand,
)
from mmf.services.audit.application.use_cases import (
    GenerateAuditReportUseCase,
    LogRequestUseCase,
    QueryAuditEventsUseCase,
)
from mmf.services.audit.domain.contracts import IAuditDestination, IAuditRepository
from mmf.services.audit.domain.entities import RequestAuditEvent


@pytest.fixture
def mock_repository():
    repo = Mock(spec=IAuditRepository)
    repo.save = AsyncMock()
    repo.find_by_criteria = AsyncMock()
    repo.count = AsyncMock()
    return repo


@pytest.fixture
def mock_destination():
    dest = Mock(spec=IAuditDestination)
    dest.write_event = AsyncMock()
    return dest


@pytest.fixture
def mock_compliance_logger():
    logger = AsyncMock()
    logger.log_audit_event = AsyncMock()
    return logger


@pytest.mark.asyncio
async def test_log_request_success(mock_repository, mock_destination):
    """Test successful logging of a request."""
    # Setup
    use_case = LogRequestUseCase(
        repository=mock_repository,
        destinations=[mock_destination],
    )

    command = LogRequestCommand(
        event_type=AuditEventType.ACCESS_CONTROL,
        severity=AuditSeverity.INFO,
        outcome=AuditOutcome.SUCCESS,
        message="User login successful",
        user_id="user-123",
        username="testuser",
        method="POST",
        endpoint="/api/login",
        source_ip="127.0.0.1",
        status_code=200,
        duration_ms=150.5,
    )

    # Mock repository save to return the event with an ID
    async def save_side_effect(event):
        if not event.id:
            event.id = uuid4()
        return event

    mock_repository.save.side_effect = save_side_effect

    # Execute
    response = await use_case.execute(command)

    # Verify
    assert response.event_id is not None
    assert isinstance(response.event_id, UUID)

    # Verify repository call
    mock_repository.save.assert_called_once()
    saved_event = mock_repository.save.call_args[0][0]
    assert isinstance(saved_event, RequestAuditEvent)
    assert saved_event.event_type == AuditEventType.ACCESS_CONTROL
    assert saved_event.severity == AuditSeverity.INFO
    assert saved_event.actor_info.user_id == "user-123"
    assert saved_event.request_context.method == "POST"
    assert saved_event.performance_metrics.duration_ms == 150.5

    # Verify destination call
    mock_destination.write_event.assert_called_once()


@pytest.mark.asyncio
async def test_log_request_high_severity_forwarding(
    mock_repository, mock_destination, mock_compliance_logger
):
    """Test that high severity events are forwarded to compliance logger."""
    # Setup
    use_case = LogRequestUseCase(
        repository=mock_repository,
        destinations=[mock_destination],
        auto_forward_threshold=AuditSeverity.HIGH,
        compliance_logger=mock_compliance_logger,
    )

    command = LogRequestCommand(
        event_type=AuditEventType.SECURITY,
        severity=AuditSeverity.CRITICAL,
        outcome=AuditOutcome.FAILURE,
        message="Potential SQL Injection detected",
        user_id="attacker",
        method="POST",
        endpoint="/api/users",
        details={"query": "' OR 1=1 --"},
    )

    # Mock repository save
    async def save_side_effect(event):
        if not event.id:
            event.id = uuid4()
        return event

    mock_repository.save.side_effect = save_side_effect

    # Mock compliance logger response
    compliance_response = Mock()
    compliance_response.event_id = "sec-event-123"
    mock_compliance_logger.log_audit_event.return_value = compliance_response

    # Execute
    response = await use_case.execute(command)

    # Verify
    assert response.security_event_id == "sec-event-123"

    # Verify compliance logger called
    mock_compliance_logger.log_audit_event.assert_called_once()
    call_kwargs = mock_compliance_logger.log_audit_event.call_args[1]
    assert call_kwargs["event_type"] == SecurityEventType.SECURITY_VIOLATION
    assert call_kwargs["severity"] == SecurityEventSeverity.CRITICAL
    assert call_kwargs["user_id"] == "attacker"


@pytest.mark.asyncio
async def test_query_audit_events(mock_repository):
    """Test querying audit events."""
    # Setup
    use_case = QueryAuditEventsUseCase(repository=mock_repository)

    command = QueryAuditEventsCommand(
        event_type=AuditEventType.ACCESS_CONTROL,
        user_id="user-123",
        limit=10,
    )

    # Mock repository response
    mock_events = [
        RequestAuditEvent(
            event_type=AuditEventType.ACCESS_CONTROL,
            severity=AuditSeverity.INFO,
            outcome=AuditOutcome.SUCCESS,
            message="Test event 1",
            timestamp=datetime.now(timezone.utc),
        ),
        RequestAuditEvent(
            event_type=AuditEventType.ACCESS_CONTROL,
            severity=AuditSeverity.INFO,
            outcome=AuditOutcome.SUCCESS,
            message="Test event 2",
            timestamp=datetime.now(timezone.utc),
        ),
    ]
    mock_repository.find_by_criteria.return_value = mock_events
    mock_repository.count.return_value = 2

    # Execute
    response = await use_case.execute(command)

    # Verify
    assert len(response.events) == 2
    assert response.total_count == 2

    # Verify repository calls
    mock_repository.find_by_criteria.assert_called_once_with(
        event_type=AuditEventType.ACCESS_CONTROL,
        severity=None,
        start_time=None,
        end_time=None,
        user_id="user-123",
        service_name=None,
        correlation_id=None,
        skip=0,
        limit=10,
    )

    mock_repository.count.assert_called_once_with(
        event_type=AuditEventType.ACCESS_CONTROL,
        severity=None,
        start_time=None,
        end_time=None,
    )


@pytest.mark.asyncio
async def test_generate_audit_report(mock_repository):
    """Test generating audit report."""
    # Setup
    use_case = GenerateAuditReportUseCase(repository=mock_repository)

    start_time = datetime.now(timezone.utc)
    end_time = datetime.now(timezone.utc)

    command = GenerateAuditReportCommand(
        start_time=start_time,
        end_time=end_time,
        service_name="auth-service",
        severity_threshold=AuditSeverity.HIGH,
    )

    # Mock repository response with mixed severity events
    mock_events = [
        RequestAuditEvent(
            event_type=AuditEventType.SECURITY,
            severity=AuditSeverity.CRITICAL,
            outcome=AuditOutcome.FAILURE,
            message="Critical failure",
            timestamp=datetime.now(timezone.utc),
        ),
        RequestAuditEvent(
            event_type=AuditEventType.ACCESS_CONTROL,
            severity=AuditSeverity.INFO,
            outcome=AuditOutcome.SUCCESS,
            message="Info event",
            timestamp=datetime.now(timezone.utc),
        ),
    ]
    mock_repository.find_by_criteria.return_value = mock_events

    # Execute
    response = await use_case.execute(command)

    # Verify
    # Should only include the CRITICAL event because threshold is HIGH
    assert response.report_data["summary"]["total_events"] == 1
    assert response.report_data["summary"]["by_severity"][AuditSeverity.CRITICAL.value] == 1
    assert AuditSeverity.INFO.value not in response.report_data["summary"]["by_severity"]

    # Verify repository call
    mock_repository.find_by_criteria.assert_called_once()
