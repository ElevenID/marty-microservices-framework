"""
Enterprise Audit Logging Framework

This module provides comprehensive audit logging capabilities for microservices,
including event tracking, multiple destinations, encryption, and compliance features.

Key Features:
- Structured audit events with encryption support
- Multiple destinations (file, database, console, SIEM)
- Automatic middleware integration for FastAPI and gRPC
- Event correlation and search capabilities
- Retention and compliance management
- Performance monitoring and anomaly detection

Usage:
from marty_msf.framework.audit import (
        AuditLogger, AuditConfig, AuditContext,
        AuditEventType, AuditSeverity, AuditOutcome,
        setup_fastapi_audit_middleware,
        audit_context
    )

    # Basic setup
    config = AuditConfig()
    context = AuditContext(
        service_name="my-service",
        service_version="1.0.0",
        environment="production"
    )

    # Using context manager
    async with audit_context(config, context) as audit_logger:
        await audit_logger.log_auth_event(
            AuditEventType.USER_LOGIN,
            user_id="user123",
            source_ip="192.168.1.100"
        )

    # FastAPI integration
    app = FastAPI()
    setup_fastapi_audit_middleware(app)
"""

from .destinations import (
    AuditLogRecord,
    ConsoleAuditDestination,
    DatabaseAuditDestination,
    FileAuditDestination,
    SIEMAuditDestination,
)
from .events import (
    AuditContext,
    AuditDestination,
    AuditEncryption,
    AuditEvent,
    AuditEventBuilder,
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
)
from .logger import (
    AuditConfig,
    AuditLogger,
    audit_context,
    get_audit_logger,
    set_audit_logger,
)
from .middleware import (
    AuditMiddlewareConfig,
    setup_fastapi_audit_middleware,
    setup_grpc_audit_interceptor,
)

__all__ = [
    "AuditConfig",
    "AuditContext",
    "AuditDestination",
    "AuditEncryption",
    # Events
    "AuditEvent",
    "AuditEventBuilder",
    "AuditEventType",
    "AuditLogRecord",
    # Logger
    "AuditLogger",
    # Middleware
    "AuditMiddlewareConfig",
    "AuditOutcome",
    "AuditSeverity",
    "ConsoleAuditDestination",
    "DatabaseAuditDestination",
    # Destinations
    "FileAuditDestination",
    "SIEMAuditDestination",
    "audit_context",
    "get_audit_logger",
    "set_audit_logger",
    "setup_fastapi_audit_middleware",
    "setup_grpc_audit_interceptor",
]

__version__ = "1.0.0"
