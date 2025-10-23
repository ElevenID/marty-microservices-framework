"""
Security Audit Module

This module contains concrete implementations of audit logging for security operations.
It depends only on the security.api layer, following the level contract principle.

Key Features:
- Structured audit event logging
- Multiple audit backends (file, database, remote)
- Configurable event filtering and formatting
- Async and sync logging support
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .api import AuditEvent, IAuditor

logger = logging.getLogger(__name__)


class FileAuditor:
    """
    File-based audit logger.

    This auditor writes security events to a structured log file,
    making it suitable for local deployments and development.
    """

    def __init__(self, log_file_path: str | Path, max_file_size: int = 10 * 1024 * 1024):
        """
        Initialize the file auditor.

        Args:
            log_file_path: Path to the audit log file
            max_file_size: Maximum file size before rotation (in bytes)
        """
        self.log_file_path = Path(log_file_path)
        self.max_file_size = max_file_size

        # Ensure directory exists
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)

    def audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """
        Log a security event to file.

        Args:
            event_type: Type of security event
            details: Event details and metadata
        """
        try:
            # Create audit event
            event = AuditEvent(
                event_type=event_type,
                principal_id=details.get("principal_id"),
                resource=details.get("resource"),
                action=details.get("action"),
                result=details.get("result", "unknown"),
                details=details,
                session_id=details.get("session_id")
            )

            # Convert to JSON
            event_data = {
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "principal_id": event.principal_id,
                "resource": event.resource,
                "action": event.action,
                "result": event.result,
                "session_id": event.session_id,
                "details": event.details
            }

            # Write to file
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                json.dump(event_data, f, separators=(",", ":"))
                f.write("\n")

            # Check for rotation
            self._maybe_rotate_log()

        except Exception as e:
            logger.error("Failed to write audit event: %s", e)

    def _maybe_rotate_log(self) -> None:
        """Rotate log file if it exceeds maximum size."""
        try:
            if self.log_file_path.exists() and self.log_file_path.stat().st_size > self.max_file_size:
                # Simple rotation - just rename with timestamp
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                rotated_path = self.log_file_path.with_name(f"{self.log_file_path.stem}_{timestamp}.log")
                self.log_file_path.rename(rotated_path)
                logger.info("Rotated audit log to: %s", rotated_path)
        except Exception as e:
            logger.error("Failed to rotate audit log: %s", e)


class StructuredAuditor:
    """
    Structured logger-based auditor.

    This auditor uses Python's logging system with structured formatting,
    making it compatible with log aggregation systems.
    """

    def __init__(self, logger_name: str = "security.audit", log_level: int = logging.INFO):
        """
        Initialize the structured auditor.

        Args:
            logger_name: Name of the logger to use
            log_level: Minimum log level for audit events
        """
        self.audit_logger = logging.getLogger(logger_name)
        self.log_level = log_level

    def audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """
        Log a security event using structured logging.

        Args:
            event_type: Type of security event
            details: Event details and metadata
        """
        try:
            # Create audit event
            event = AuditEvent(
                event_type=event_type,
                principal_id=details.get("principal_id"),
                resource=details.get("resource"),
                action=details.get("action"),
                result=details.get("result", "unknown"),
                details=details,
                session_id=details.get("session_id")
            )

            # Create structured log message
            log_data = {
                "event_type": event.event_type,
                "principal_id": event.principal_id,
                "resource": event.resource,
                "action": event.action,
                "result": event.result,
                "session_id": event.session_id,
                "timestamp": event.timestamp.isoformat(),
                **event.details
            }

            # Log with appropriate level based on result
            if event.result == "failure" or event.result == "error":
                log_level = logging.WARNING
            else:
                log_level = self.log_level

            self.audit_logger.log(
                log_level,
                "Security audit event: %s",
                event_type,
                extra={"audit_data": log_data}
            )

        except Exception as e:
            logger.error("Failed to write structured audit event: %s", e)


class CompositeAuditor:
    """
    Composite auditor that forwards events to multiple audit backends.

    This allows writing audit events to multiple destinations simultaneously,
    providing redundancy and flexibility.
    """

    def __init__(self, auditors: list[IAuditor]):
        """
        Initialize the composite auditor.

        Args:
            auditors: List of auditor instances to forward events to
        """
        self.auditors = auditors

    def audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """
        Forward the audit event to all configured auditors.

        Args:
            event_type: Type of security event
            details: Event details and metadata
        """
        for auditor in self.auditors:
            try:
                auditor.audit_event(event_type, details)
            except Exception as e:
                logger.error("Auditor %s failed to log event: %s", type(auditor).__name__, e)


class FilteringAuditor:
    """
    Filtering auditor that applies event filtering before forwarding.

    This allows selective audit logging based on event types, principals,
    resources, or other criteria.
    """

    def __init__(self, base_auditor: IAuditor, event_filter: dict[str, Any] | None = None):
        """
        Initialize the filtering auditor.

        Args:
            base_auditor: Underlying auditor to forward events to
            event_filter: Filter criteria for events
        """
        self.base_auditor = base_auditor
        self.event_filter = event_filter or {}

    def audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """
        Filter and forward the audit event if it matches criteria.

        Args:
            event_type: Type of security event
            details: Event details and metadata
        """
        if self._should_audit_event(event_type, details):
            self.base_auditor.audit_event(event_type, details)

    def _should_audit_event(self, event_type: str, details: dict[str, Any]) -> bool:
        """
        Check if the event should be audited based on filter criteria.

        Args:
            event_type: Type of security event
            details: Event details and metadata

        Returns:
            True if the event should be audited
        """
        # Check event type filter
        if "event_types" in self.event_filter:
            allowed_types = self.event_filter["event_types"]
            if event_type not in allowed_types:
                return False

        # Check result filter
        if "results" in self.event_filter:
            allowed_results = self.event_filter["results"]
            event_result = details.get("result", "unknown")
            if event_result not in allowed_results:
                return False

        # Check principal filter
        if "principals" in self.event_filter:
            allowed_principals = self.event_filter["principals"]
            principal_id = details.get("principal_id")
            if principal_id and principal_id not in allowed_principals:
                return False

        # Check resource filter
        if "resources" in self.event_filter:
            allowed_resources = self.event_filter["resources"]
            resource = details.get("resource")
            if resource and not any(resource.startswith(pattern) for pattern in allowed_resources):
                return False

        return True


class NoOpAuditor:
    """
    No-operation auditor for testing and development.

    This auditor discards all events, useful for performance testing
    or when audit logging is not needed.
    """

    def audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """
        Discard the audit event (no-op).

        Args:
            event_type: Type of security event (ignored)
            details: Event details and metadata (ignored)
        """
        pass


def create_default_auditor(config: dict[str, Any]) -> IAuditor:
    """
    Create a default auditor based on configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Configured auditor instance
    """
    audit_config = config.get("audit", {})
    audit_type = audit_config.get("type", "structured")

    if audit_type == "file":
        log_file = audit_config.get("log_file", "security_audit.log")
        max_size = audit_config.get("max_file_size", 10 * 1024 * 1024)
        return FileAuditor(log_file, max_size)

    elif audit_type == "structured":
        logger_name = audit_config.get("logger_name", "security.audit")
        log_level = getattr(logging, audit_config.get("log_level", "INFO").upper())
        return StructuredAuditor(logger_name, log_level)

    elif audit_type == "composite":
        auditors = []
        for auditor_config in audit_config.get("auditors", []):
            auditor = create_default_auditor({"audit": auditor_config})
            auditors.append(auditor)
        return CompositeAuditor(auditors)

    elif audit_type == "noop":
        return NoOpAuditor()

    else:
        # Default to structured logging
        return StructuredAuditor()
