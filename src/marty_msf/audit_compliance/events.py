"""
Enhanced Security Event Management System

Provides comprehensive security event collection, analysis, and response
capabilities for the Marty Microservices Framework.
"""

import uuid
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from ..security_core.models import SecurityThreatLevel
from .monitoring import SecurityEvent, SecurityEventSeverity, SecurityEventType


class SecurityEventManager:
    """
    Enhanced security event management with real-time analysis and response.
    """

    def __init__(self, max_events: int = 10000):
        """Initialize the security event manager."""
        self.max_events = max_events
        self.events: deque[SecurityEvent] = deque(maxlen=max_events)
        self.event_handlers: dict[SecurityEventType, list[Callable]] = {}
        self.threat_patterns: dict[str, dict] = {}

        # Metrics tracking
        self.metrics = {
            "total_events": 0,
            "events_by_type": {},
            "events_by_severity": {},
            "threats_detected": 0,
            "handlers_executed": 0,
            "patterns_matched": 0,
        }

        # Real-time analysis
        self.analysis_enabled = True
        self.correlation_window = timedelta(minutes=5)
        self.threat_threshold = 3  # Number of related events to trigger threat detection

    def log_event(
        self,
        event_type: SecurityEventType,
        severity: SecurityEventSeverity,
        user_id: str | None = None,
        source_ip: str | None = None,
        resource: str | None = None,
        action: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> SecurityEvent:
        """Log a security event and trigger analysis."""
        event = SecurityEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            source_ip=source_ip,
            resource=resource,
            action=action,
            raw_data=details or {},
        )

        # Store the event
        self.events.append(event)

        # Update metrics
        self._update_metrics(event)

        # Trigger real-time analysis
        if self.analysis_enabled:
            self._analyze_event(event)

        # Execute registered handlers
        self._execute_handlers(event)

        return event

    def log_authentication_event(
        self,
        success: bool,
        user_id: str,
        source_ip: str | None = None,
        method: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> SecurityEvent:
        """Log an authentication event."""
        event_type = (
            SecurityEventType.AUTHENTICATION_SUCCESS
            if success
            else SecurityEventType.AUTHENTICATION_FAILURE
        )
        severity = SecurityEventSeverity.INFO if success else SecurityEventSeverity.MEDIUM

        event_details = {"method": method or "unknown", **(details or {})}

        return self.log_event(
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            source_ip=source_ip,
            action="authenticate",
            details=event_details,
        )

    def log_authorization_event(
        self,
        allowed: bool,
        user_id: str,
        resource: str,
        action: str,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> SecurityEvent:
        """Log an authorization event."""
        event_type = (
            SecurityEventType.AUTHORIZATION_FAILURE
            if not allowed
            else SecurityEventType.DATA_ACCESS
        )
        severity = SecurityEventSeverity.MEDIUM if not allowed else SecurityEventSeverity.INFO

        event_details = {"reason": reason or "unknown", "allowed": allowed, **(details or {})}

        return self.log_event(
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            resource=resource,
            action=action,
            details=event_details,
        )

    def log_threat_event(
        self,
        threat_type: str,
        severity: SecurityEventSeverity,
        source_ip: str | None = None,
        user_id: str | None = None,
        indicators: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> SecurityEvent:
        """Log a threat detection event."""
        event_details = {
            "threat_type": threat_type,
            "indicators": indicators or [],
            **(details or {}),
        }

        return self.log_event(
            event_type=SecurityEventType.THREAT_DETECTED,
            severity=severity,
            user_id=user_id,
            source_ip=source_ip,
            action="threat_detection",
            details=event_details,
        )

    def register_event_handler(
        self, event_type: SecurityEventType, handler: Callable[[SecurityEvent], None]
    ) -> None:
        """Register an event handler for specific event types."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def unregister_event_handler(
        self, event_type: SecurityEventType, handler: Callable[[SecurityEvent], None]
    ) -> bool:
        """Unregister an event handler."""
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
                return True
            except ValueError:
                pass
        return False

    def define_threat_pattern(
        self,
        pattern_name: str,
        event_types: list[SecurityEventType],
        time_window: timedelta,
        min_occurrences: int,
        severity_threshold: SecurityEventSeverity = SecurityEventSeverity.MEDIUM,
    ) -> None:
        """Define a threat detection pattern."""
        self.threat_patterns[pattern_name] = {
            "event_types": event_types,
            "time_window": time_window,
            "min_occurrences": min_occurrences,
            "severity_threshold": severity_threshold,
        }

    def get_events(
        self,
        event_type: SecurityEventType | None = None,
        severity: SecurityEventSeverity | None = None,
        user_id: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[SecurityEvent]:
        """Get events with optional filtering."""
        events = list(self.events)

        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if severity:
            events = [e for e in events if e.severity == severity]

        if user_id:
            events = [e for e in events if e.user_id == user_id]

        if since:
            events = [e for e in events if e.timestamp >= since]

        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply limit
        if limit:
            events = events[:limit]

        return events

    def get_event_summary(self, time_window: timedelta = timedelta(hours=24)) -> dict[str, Any]:
        """Get a summary of events within a time window."""
        cutoff = datetime.now(timezone.utc) - time_window
        recent_events = [e for e in self.events if e.timestamp >= cutoff]

        summary = {
            "time_window": str(time_window),
            "total_events": len(recent_events),
            "by_type": {},
            "by_severity": {},
            "by_hour": {},
            "top_users": {},
            "top_source_ips": {},
            "threat_indicators": [],
        }

        # Analyze by type
        for event in recent_events:
            event_type = event.event_type.value
            summary["by_type"][event_type] = summary["by_type"].get(event_type, 0) + 1

        # Analyze by severity
        for event in recent_events:
            severity = event.severity.value
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1

        # Analyze by hour
        for event in recent_events:
            hour = event.timestamp.strftime("%Y-%m-%d %H:00")
            summary["by_hour"][hour] = summary["by_hour"].get(hour, 0) + 1

        # Top users
        user_counts = {}
        for event in recent_events:
            if event.user_id:
                user_counts[event.user_id] = user_counts.get(event.user_id, 0) + 1
        summary["top_users"] = dict(
            sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        # Top source IPs
        ip_counts = {}
        for event in recent_events:
            if event.source_ip:
                ip_counts[event.source_ip] = ip_counts.get(event.source_ip, 0) + 1
        summary["top_source_ips"] = dict(
            sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        # Threat indicators
        high_severity_events = [
            e
            for e in recent_events
            if e.severity in (SecurityEventSeverity.HIGH, SecurityEventSeverity.CRITICAL)
        ]
        if high_severity_events:
            summary["threat_indicators"].append(
                f"{len(high_severity_events)} high/critical severity events"
            )

        failed_auth_events = [
            e for e in recent_events if e.event_type == SecurityEventType.AUTHENTICATION_FAILURE
        ]
        if len(failed_auth_events) > 10:
            summary["threat_indicators"].append(
                f"{len(failed_auth_events)} authentication failures"
            )

        return summary

    def clear_events(self, before: datetime | None = None) -> int:
        """Clear events, optionally before a specific timestamp."""
        if before:
            original_count = len(self.events)
            self.events = deque(
                [e for e in self.events if e.timestamp >= before], maxlen=self.events.maxlen
            )
            cleared_count = original_count - len(self.events)
        else:
            cleared_count = len(self.events)
            self.events.clear()

        return cleared_count

    def get_metrics(self) -> dict[str, Any]:
        """Get event management metrics."""
        return {
            **self.metrics,
            "current_events_count": len(self.events),
            "max_events": self.max_events,
            "analysis_enabled": self.analysis_enabled,
            "registered_handlers": sum(len(handlers) for handlers in self.event_handlers.values()),
            "defined_patterns": len(self.threat_patterns),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _update_metrics(self, event: SecurityEvent) -> None:
        """Update internal metrics."""
        self.metrics["total_events"] += 1

        # Update by type
        event_type = event.event_type.value
        if event_type not in self.metrics["events_by_type"]:
            self.metrics["events_by_type"][event_type] = 0
        self.metrics["events_by_type"][event_type] += 1

        # Update by severity
        severity = event.severity.value
        if severity not in self.metrics["events_by_severity"]:
            self.metrics["events_by_severity"][severity] = 0
        self.metrics["events_by_severity"][severity] += 1

        # Count threats
        if event.event_type == SecurityEventType.THREAT_DETECTED:
            self.metrics["threats_detected"] += 1

    def _analyze_event(self, event: SecurityEvent) -> None:
        """Perform real-time analysis on the event."""
        # Check for threat patterns
        for pattern_name, pattern_config in self.threat_patterns.items():
            if self._check_threat_pattern(event, pattern_name, pattern_config):
                self.metrics["patterns_matched"] += 1
                self._trigger_threat_response(pattern_name, event)

    def _check_threat_pattern(
        self, event: SecurityEvent, pattern_name: str, pattern_config: dict
    ) -> bool:
        """Check if an event matches a threat pattern."""
        # Check if event type is relevant to this pattern
        if event.event_type not in pattern_config["event_types"]:
            return False

        # Check severity threshold
        severity_levels = {
            SecurityEventSeverity.INFO: 1,
            SecurityEventSeverity.LOW: 2,
            SecurityEventSeverity.MEDIUM: 3,
            SecurityEventSeverity.HIGH: 4,
            SecurityEventSeverity.CRITICAL: 5,
        }

        event_severity_level = severity_levels.get(event.severity, 0)
        threshold_level = severity_levels.get(pattern_config["severity_threshold"], 3)

        if event_severity_level < threshold_level:
            return False

        # Check time window and occurrence count
        time_window = pattern_config["time_window"]
        min_occurrences = pattern_config["min_occurrences"]
        cutoff = event.timestamp - time_window

        # Count related events in the time window
        related_events = [
            e
            for e in self.events
            if (
                e.timestamp >= cutoff
                and e.event_type in pattern_config["event_types"]
                and severity_levels.get(e.severity, 0) >= threshold_level
            )
        ]

        return len(related_events) >= min_occurrences

    def _trigger_threat_response(self, pattern_name: str, event: SecurityEvent) -> None:
        """Trigger a threat response for a matched pattern."""
        # Log a threat detection event
        threat_event = self.log_event(
            event_type=SecurityEventType.THREAT_DETECTED,
            severity=SecurityEventSeverity.HIGH,
            user_id=event.user_id,
            source_ip=event.source_ip,
            details={
                "pattern_matched": pattern_name,
                "trigger_event_id": event.event_id,
                "pattern_type": "correlation",
                "response_triggered": True,
            },
        )

        # Execute threat-specific handlers if any
        threat_handlers = self.event_handlers.get(SecurityEventType.THREAT_DETECTED, [])
        for handler in threat_handlers:
            try:
                handler(threat_event)
                self.metrics["handlers_executed"] += 1
            except Exception:
                # Don't let handler failures break the system
                pass

    def _execute_handlers(self, event: SecurityEvent) -> None:
        """Execute registered handlers for an event."""
        handlers = self.event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
                self.metrics["handlers_executed"] += 1
            except Exception:
                # Don't let handler failures break the system
                pass


def create_event_manager(max_events: int = 10000) -> SecurityEventManager:
    """
    Create a security event manager instance.

    Args:
        max_events: Maximum number of events to keep in memory

    Returns:
        Configured SecurityEventManager instance
    """
    manager = SecurityEventManager(max_events)

    # Define some common threat patterns
    manager.define_threat_pattern(
        "brute_force_authentication",
        [SecurityEventType.AUTHENTICATION_FAILURE],
        timedelta(minutes=5),
        5,
        SecurityEventSeverity.MEDIUM,
    )

    manager.define_threat_pattern(
        "privilege_escalation_attempts",
        [SecurityEventType.AUTHORIZATION_FAILURE, SecurityEventType.PRIVILEGE_ESCALATION],
        timedelta(minutes=10),
        3,
        SecurityEventSeverity.MEDIUM,
    )

    manager.define_threat_pattern(
        "suspicious_data_access",
        [SecurityEventType.DATA_ACCESS, SecurityEventType.DATA_MODIFICATION],
        timedelta(minutes=15),
        10,
        SecurityEventSeverity.LOW,
    )

    return manager
