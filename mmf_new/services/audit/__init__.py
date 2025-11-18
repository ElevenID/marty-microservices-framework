"""Audit service public API."""

from .application import (
    GenerateAuditReportCommand,
    GenerateAuditReportResponse,
    LogApiCallCommand,
    LogApiCallResponse,
    LogRequestCommand,
    LogRequestResponse,
    QueryAuditEventsCommand,
    QueryAuditEventsResponse,
)
from .di_config import AuditConfig, AuditDIContainer
from .domain import (
    ApiCallEvent,
    IAuditDestination,
    IAuditEncryption,
    IAuditLogger,
    IAuditRepository,
    IMiddlewareAuditor,
    MiddlewareAuditEvent,
    RequestAuditEvent,
)
from .service_factory import (
    AuditService,
    audit_context,
    create_audit_service,
    create_default_audit_config,
)

__all__ = [
    # Domain
    "RequestAuditEvent",
    "ApiCallEvent",
    "MiddlewareAuditEvent",
    "IAuditDestination",
    "IAuditEncryption",
    "IAuditRepository",
    "IAuditLogger",
    "IMiddlewareAuditor",
    # Application
    "LogRequestCommand",
    "LogRequestResponse",
    "LogApiCallCommand",
    "LogApiCallResponse",
    "QueryAuditEventsCommand",
    "QueryAuditEventsResponse",
    "GenerateAuditReportCommand",
    "GenerateAuditReportResponse",
    # Service
    "AuditService",
    "AuditConfig",
    "AuditDIContainer",
    "create_audit_service",
    "audit_context",
    "create_default_audit_config",
]
