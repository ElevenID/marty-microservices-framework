"""Application layer commands and responses for audit service."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from mmf_new.core.domain.audit_types import AuditEventType, AuditOutcome, AuditSeverity


@dataclass
class LogRequestCommand:
    """Command to log an audit request."""

    event_type: AuditEventType
    severity: AuditSeverity
    outcome: AuditOutcome
    message: str
    # Request context
    method: str | None = None
    endpoint: str | None = None
    source_ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None
    # Actor info
    user_id: str | None = None
    username: str | None = None
    session_id: str | None = None
    api_key_id: str | None = None
    # Resource info
    resource_type: str | None = None
    resource_id: str | None = None
    action: str = ""
    # Service context
    service_name: str | None = None
    environment: str | None = None
    version: str | None = None
    instance_id: str | None = None
    # Response metadata
    status_code: int | None = None
    response_size: int | None = None
    # Performance
    duration_ms: float | None = None
    # Additional details
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LogRequestResponse:
    """Response from logging a request."""

    event_id: UUID
    timestamp: datetime
    security_event_id: str | None = None  # Set if forwarded to audit_compliance


@dataclass
class LogApiCallCommand:
    """Command to log an API call."""

    target_service: str
    target_endpoint: str
    severity: AuditSeverity
    outcome: AuditOutcome
    message: str
    # Request context
    method: str | None = None
    source_ip: str | None = None
    correlation_id: str | None = None
    # Actor info
    user_id: str | None = None
    username: str | None = None
    # Performance
    duration_ms: float | None = None
    status_code: int | None = None
    # Additional details
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LogApiCallResponse:
    """Response from logging an API call."""

    event_id: UUID
    timestamp: datetime
    security_event_id: str | None = None


@dataclass
class QueryAuditEventsCommand:
    """Command to query audit events."""

    event_type: AuditEventType | None = None
    severity: AuditSeverity | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    user_id: str | None = None
    service_name: str | None = None
    correlation_id: str | None = None
    skip: int = 0
    limit: int = 100


@dataclass
class QueryAuditEventsResponse:
    """Response from querying audit events."""

    events: list[dict[str, Any]]
    total_count: int
    skip: int
    limit: int


@dataclass
class GenerateAuditReportCommand:
    """Command to generate an audit report."""

    start_time: datetime
    end_time: datetime
    event_types: list[AuditEventType] | None = None
    severity_threshold: AuditSeverity | None = None
    service_name: str | None = None
    format: str = "json"  # json, csv, pdf


@dataclass
class GenerateAuditReportResponse:
    """Response from generating an audit report."""

    report_id: str
    report_path: str | None = None
    report_data: dict[str, Any] | None = None
    generated_at: datetime = field(default_factory=datetime.utcnow)
