"""
Security Audit Logging System

Comprehensive audit logging for all security events including authentication,
authorization decisions, policy evaluations, and administrative actions.
"""

import asyncio
import json
import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union

from ...core.di_container import (
    configure_service,
    get_container,
    get_service,
    get_service_optional,
)
from ..exceptions import SecurityError, SecurityErrorType

# Import moved to avoid circular import

logger = logging.getLogger(__name__)


class SecurityEventType(Enum):
    """Types of security events for audit logging."""

    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_GRANTED = "authorization_granted"
    AUTHORIZATION_DENIED = "authorization_denied"
    TOKEN_ISSUED = "token_issued"
    TOKEN_VALIDATED = "token_validated"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_REVOKED = "token_revoked"
    PERMISSION_CHECK = "permission_check"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    POLICY_EVALUATION = "policy_evaluation"
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_DELETED = "policy_deleted"
    ADMIN_ACTION = "admin_action"
    SECURITY_VIOLATION = "security_violation"
    RATE_LIMIT_HIT = "rate_limit_hit"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    CONFIGURATION_CHANGED = "configuration_changed"
    SYSTEM_ERROR = "system_error"


class AuditLevel(Enum):
    """Audit logging levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SecurityAuditEvent:
    """Represents a security audit event."""

    event_type: SecurityEventType
    timestamp: datetime
    principal_id: str | None = None
    resource: str | None = None
    action: str | None = None
    result: str | None = None  # "success", "failure", "denied", etc.
    details: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    service_name: str | None = None
    level: AuditLevel = AuditLevel.INFO

    def __post_init__(self):
        """Set default timestamp if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to strings
        data["event_type"] = self.event_type.value
        data["level"] = self.level.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditSink:
    """Base class for audit log sinks."""

    def __init__(self, name: str):
        self.name = name
        self.is_active = True

    async def write_event(self, event: SecurityAuditEvent) -> bool:
        """Write audit event to sink."""
        raise NotImplementedError

    async def close(self):
        """Close sink and cleanup resources."""
        pass


class FileAuditSink(AuditSink):
    """File-based audit sink."""

    def __init__(self, name: str, file_path: str, rotate_size_mb: int = 100):
        super().__init__(name)
        self.file_path = Path(file_path)
        self.rotate_size_mb = rotate_size_mb
        self.lock = threading.Lock()

        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    async def write_event(self, event: SecurityAuditEvent) -> bool:
        """Write event to file."""
        try:
            with self.lock:
                # Check file size and rotate if needed
                if self._should_rotate():
                    self._rotate_file()

                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write(event.to_json() + "\n")

                return True

        except Exception as e:
            logger.error("Failed to write audit event to file %s: %s", self.file_path, e)
            return False

    def _should_rotate(self) -> bool:
        """Check if file should be rotated."""
        if not self.file_path.exists():
            return False

        size_mb = self.file_path.stat().st_size / (1024 * 1024)
        return size_mb > self.rotate_size_mb

    def _rotate_file(self):
        """Rotate log file."""
        if not self.file_path.exists():
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_path = self.file_path.with_suffix(f".{timestamp}.log")
        self.file_path.rename(rotated_path)


class DatabaseAuditSink(AuditSink):
    """Database audit sink (placeholder for actual implementation)."""

    def __init__(self, name: str, connection_string: str):
        super().__init__(name)
        self.connection_string = connection_string
        # In real implementation, initialize database connection

    async def write_event(self, event: SecurityAuditEvent) -> bool:
        """Write event to database."""
        # Placeholder - implement actual database write
        logger.debug("Would write audit event to database: %s", event.event_type.value)
        return True


class SyslogAuditSink(AuditSink):
    """Syslog audit sink."""

    def __init__(self, name: str, facility: str = "auth", server: str | None = None):
        super().__init__(name)
        self.facility = facility
        self.server = server
        # In real implementation, setup syslog connection

    async def write_event(self, event: SecurityAuditEvent) -> bool:
        """Write event to syslog."""
        # Placeholder - implement actual syslog write
        logger.debug("Would write audit event to syslog: %s", event.event_type.value)
        return True


class SecurityAuditor:
    """Main security audit logging system."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.sinks: dict[str, AuditSink] = {}
        self.event_queue: queue.Queue = queue.Queue()
        self.is_running = False
        self.worker_task: asyncio.Task | None = None
        self.correlation_context: dict[int, str] = {}
        self.default_context: dict[str, Any] = {}
        self.event_filters: list[Callable[[SecurityAuditEvent], bool]] = []

        # Statistics
        self.events_processed = 0
        self.events_failed = 0
        self.events_filtered = 0

        # Initialize default file sink
        self._initialize_default_sinks()

    def _initialize_default_sinks(self):
        """Initialize default audit sinks."""
        # File sink for security events
        file_sink = FileAuditSink(
            name="security_audit_file", file_path=f"/tmp/security_audit_{self.service_name}.log"
        )
        self.add_sink(file_sink)

        logger.info("Initialized default audit sinks for service: %s", self.service_name)

    def add_sink(self, sink: AuditSink):
        """Add an audit sink."""
        self.sinks[sink.name] = sink
        logger.info("Added audit sink: %s", sink.name)

    def remove_sink(self, sink_name: str) -> bool:
        """Remove an audit sink."""
        if sink_name in self.sinks:
            del self.sinks[sink_name]
            logger.info("Removed audit sink: %s", sink_name)
            return True
        return False

    def add_event_filter(self, filter_func: Callable[[SecurityAuditEvent], bool]):
        """Add event filter function."""
        self.event_filters.append(filter_func)

    def set_correlation_context(self, correlation_id: str, session_id: str | None = None):
        """Set correlation context for current thread."""
        thread_id = threading.current_thread().ident
        if thread_id is not None:
            self.correlation_context[thread_id] = correlation_id
        if session_id:
            self.default_context["session_id"] = session_id

    def clear_correlation_context(self):
        """Clear correlation context for current thread."""
        thread_id = threading.current_thread().ident
        if thread_id is not None:
            self.correlation_context.pop(thread_id, None)

    async def start(self):
        """Start audit processing."""
        if self.is_running:
            return

        self.is_running = True
        self.worker_task = asyncio.create_task(self._process_events())
        logger.info("Started security auditor")

    async def stop(self):
        """Stop audit processing."""
        if not self.is_running:
            return

        self.is_running = False

        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        # Close all sinks
        for sink in self.sinks.values():
            await sink.close()

        logger.info("Stopped security auditor")

    async def _process_events(self):
        """Process audit events from queue."""
        while self.is_running:
            try:
                # Get event from queue with timeout
                try:
                    event = self.event_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Apply filters
                if self._should_filter_event(event):
                    self.events_filtered += 1
                    continue

                # Write to all active sinks
                success = True
                for sink in self.sinks.values():
                    if sink.is_active:
                        try:
                            if not await sink.write_event(event):
                                success = False
                        except Exception as e:
                            logger.error("Sink %s failed to write event: %s", sink.name, e)
                            success = False

                if success:
                    self.events_processed += 1
                else:
                    self.events_failed += 1

                self.event_queue.task_done()

            except Exception as e:
                logger.error("Error processing audit event: %s", e)
                await asyncio.sleep(0.1)

    def _should_filter_event(self, event: SecurityAuditEvent) -> bool:
        """Check if event should be filtered out."""
        for filter_func in self.event_filters:
            try:
                if not filter_func(event):
                    return True
            except Exception as e:
                logger.error("Event filter error: %s", e)

        return False

    def audit(
        self,
        event_type: SecurityEventType,
        principal_id: str | None = None,
        resource: str | None = None,
        action: str | None = None,
        result: str | None = None,
        level: AuditLevel = AuditLevel.INFO,
        **details,
    ):
        """Log a security audit event."""
        try:
            # Get correlation ID from context
            thread_id = threading.current_thread().ident
            correlation_id = (
                self.correlation_context.get(thread_id) if thread_id is not None else None
            )

            # Create audit event
            event = SecurityAuditEvent(
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                principal_id=principal_id,
                resource=resource,
                action=action,
                result=result,
                level=level,
                correlation_id=correlation_id,
                service_name=self.service_name,
                details=details,
            )

            # Add default context
            for key, value in self.default_context.items():
                if not hasattr(event, key) or getattr(event, key) is None:
                    setattr(event, key, value)

            # Queue event for processing
            if self.is_running:
                self.event_queue.put(event)
            else:
                # If not running, log directly
                logger.info("Security audit: %s", event.to_json())

        except Exception as e:
            logger.error("Failed to create audit event: %s", e)

    def audit_authentication_success(
        self, principal_id: str, auth_method: str, session_id: str | None = None, **details
    ):
        """Audit successful authentication."""
        self.audit(
            event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
            principal_id=principal_id,
            result="success",
            session_id=session_id,
            auth_method=auth_method,
            **details,
        )

    def audit_authentication_failure(
        self, principal_id: str | None, auth_method: str, reason: str, **details
    ):
        """Audit failed authentication."""
        self.audit(
            event_type=SecurityEventType.AUTHENTICATION_FAILURE,
            principal_id=principal_id,
            result="failure",
            level=AuditLevel.WARNING,
            auth_method=auth_method,
            reason=reason,
            **details,
        )

    def audit_authorization_granted(
        self, principal_id: str, resource: str, action: str, policy_id: str | None = None, **details
    ):
        """Audit successful authorization."""
        self.audit(
            event_type=SecurityEventType.AUTHORIZATION_GRANTED,
            principal_id=principal_id,
            resource=resource,
            action=action,
            result="granted",
            policy_id=policy_id,
            **details,
        )

    def audit_authorization_denied(
        self, principal_id: str, resource: str, action: str, reason: str, **details
    ):
        """Audit denied authorization."""
        self.audit(
            event_type=SecurityEventType.AUTHORIZATION_DENIED,
            principal_id=principal_id,
            resource=resource,
            action=action,
            result="denied",
            level=AuditLevel.WARNING,
            reason=reason,
            **details,
        )

    def audit_policy_evaluation(
        self,
        policy_id: str,
        principal_id: str,
        resource: str,
        action: str,
        decision: str,
        evaluation_time_ms: float,
        **details,
    ):
        """Audit policy evaluation."""
        self.audit(
            event_type=SecurityEventType.POLICY_EVALUATION,
            principal_id=principal_id,
            resource=resource,
            action=action,
            result=decision,
            policy_id=policy_id,
            evaluation_time_ms=evaluation_time_ms,
            **details,
        )

    def audit_admin_action(self, principal_id: str, action: str, target: str, **details):
        """Audit administrative action."""
        self.audit(
            event_type=SecurityEventType.ADMIN_ACTION,
            principal_id=principal_id,
            action=action,
            resource=target,
            level=AuditLevel.WARNING,
            **details,
        )

    def audit_security_violation(
        self, principal_id: str | None, violation_type: str, description: str, **details
    ):
        """Audit security violation."""
        self.audit(
            event_type=SecurityEventType.SECURITY_VIOLATION,
            principal_id=principal_id,
            result="violation",
            level=AuditLevel.ERROR,
            violation_type=violation_type,
            description=description,
            **details,
        )

    def audit_error(self, error: SecurityError):
        """Audit security error."""
        self.audit(
            event_type=SecurityEventType.SYSTEM_ERROR,
            result="error",
            level=AuditLevel.ERROR,
            error_type=error.error_type.value,
            error_message=error.message,
            **error.context,
        )

    def get_statistics(self) -> dict[str, Any]:
        """Get audit statistics."""
        return {
            "service_name": self.service_name,
            "is_running": self.is_running,
            "events_processed": self.events_processed,
            "events_failed": self.events_failed,
            "events_filtered": self.events_filtered,
            "queue_size": self.event_queue.qsize(),
            "active_sinks": len([s for s in self.sinks.values() if s.is_active]),
            "total_sinks": len(self.sinks),
        }


def get_security_auditor(service_name: str | None = None) -> SecurityAuditor:
    """
    Get security auditor instance using dependency injection.

    Args:
        service_name: Optional service name for the auditor

    Returns:
        SecurityAuditor instance
    """

    # Try to get existing auditor
    auditor = get_service_optional(SecurityAuditor)
    if auditor is not None:
        return auditor

    # Configure with service name if provided
    if service_name:
        configure_service(SecurityAuditor, {"service_name": service_name})

    return get_service(SecurityAuditor)


def reset_security_auditor() -> None:
    """Reset security auditor (for testing)."""
    get_container().remove(SecurityAuditor)


# Convenience audit functions
def audit_auth_success(principal_id: str, auth_method: str, **details):
    """Convenience function for authentication success audit."""
    get_security_auditor().audit_authentication_success(principal_id, auth_method, **details)


def audit_auth_failure(principal_id: str | None, auth_method: str, reason: str, **details):
    """Convenience function for authentication failure audit."""
    get_security_auditor().audit_authentication_failure(
        principal_id, auth_method, reason, **details
    )


def audit_authz_granted(principal_id: str, resource: str, action: str, **details):
    """Convenience function for authorization granted audit."""
    get_security_auditor().audit_authorization_granted(principal_id, resource, action, **details)


def audit_authz_denied(principal_id: str, resource: str, action: str, reason: str, **details):
    """Convenience function for authorization denied audit."""
    get_security_auditor().audit_authorization_denied(
        principal_id, resource, action, reason, **details
    )


__all__ = [
    "SecurityAuditEvent",
    "SecurityEventType",
    "AuditLevel",
    "SecurityAuditor",
    "AuditSink",
    "FileAuditSink",
    "DatabaseAuditSink",
    "SyslogAuditSink",
    "get_security_auditor",
    "reset_security_auditor",
    "audit_auth_success",
    "audit_auth_failure",
    "audit_authz_granted",
    "audit_authz_denied",
]
