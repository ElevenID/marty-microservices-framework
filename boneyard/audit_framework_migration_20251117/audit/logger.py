"""
Main audit logging manager for the enterprise audit framework.
This module provides the central audit logger that manages multiple destinations,
handles event routing, and provides compliance and retention features.
"""

import asyncio
import builtins
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .destinations import (
    ConsoleAuditDestination,
    DatabaseAuditDestination,
    FileAuditDestination,
    SIEMAuditDestination,
)
from .events import (
    AuditContext,
    AuditDestination,
    AuditEvent,
    AuditEventBuilder,
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
)

logger = logging.getLogger(__name__)


class AuditConfig:
    """Configuration for audit logging."""

    def __init__(self):
        # Destinations
        self.enable_file_logging: bool = True
        self.enable_database_logging: bool = True
        self.enable_console_logging: bool = False
        self.enable_siem_logging: bool = False
        # File configuration
        self.log_file_path: Path = Path("logs/audit.log")
        self.max_file_size: int = 100 * 1024 * 1024  # 100MB
        self.max_files: int = 10
        # Database configuration
        self.batch_size: int = 100
        # SIEM configuration
        self.siem_endpoint: str = ""
        self.siem_api_key: str = ""
        # Security
        self.encrypt_sensitive_data: bool = True
        # Performance
        self.async_logging: bool = True
        self.flush_interval_seconds: int = 30
        # Retention
        self.retention_days: int = 365
        self.auto_cleanup: bool = True
        self.cleanup_interval_hours: int = 24
        # Filtering
        self.min_severity: AuditSeverity = AuditSeverity.INFO
        self.excluded_event_types: builtins.list[AuditEventType] = []
        # Compliance
        self.compliance_mode: bool = False
        self.immutable_logging: bool = False


class AuditLogger:
    """Central audit logging manager."""

    def __init__(
        self,
        config: AuditConfig,
        context: AuditContext,
        db_session: Any | None = None,
    ):
        self.config = config
        self.context = context
        self.db_session = db_session
        self.destinations: builtins.list[AuditDestination] = []
        self._initialized = False
        self._background_tasks: builtins.list[asyncio.Task] = []
        self._shutdown = False
        # Event queue for async logging
        if config.async_logging:
            self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        logger.info(f"Audit logger initialized for service: {context.service_name}")

    async def initialize(self) -> None:
        """Initialize audit logger and destinations."""
        if self._initialized:
            return
        try:
            # Setup destinations
            await self._setup_destinations()
            # Start background tasks
            if self.config.async_logging:
                task = asyncio.create_task(self._process_event_queue())
                self._background_tasks.append(task)
            if self.config.auto_cleanup:
                task = asyncio.create_task(self._cleanup_task())
                self._background_tasks.append(task)
            # Periodic flush task
            task = asyncio.create_task(self._flush_task())
            self._background_tasks.append(task)
            self._initialized = True
            # Log initialization
            await self.log_system_event(
                AuditEventType.SYSTEM_STARTUP,
                "Audit logging system initialized",
                severity=AuditSeverity.INFO,
            )
            logger.info("Audit logger initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize audit logger: {e}")
            raise

    async def close(self) -> None:
        """Close audit logger and all destinations."""
        try:
            # Log shutdown
            if self._initialized:
                await self.log_system_event(
                    AuditEventType.SYSTEM_SHUTDOWN,
                    "Audit logging system shutting down",
                    severity=AuditSeverity.INFO,
                )
            # Set shutdown flag
            self._shutdown = True
            # Process remaining events
            if self.config.async_logging and hasattr(self, "_event_queue"):
                while not self._event_queue.empty():
                    try:
                        event = self._event_queue.get_nowait()
                        await self._log_to_destinations(event)
                    except asyncio.QueueEmpty:
                        break
            # Cancel background tasks
            for task in self._background_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            # Close destinations
            for destination in self.destinations:
                await destination.close()
            logger.info("Audit logger closed successfully")
        except Exception as e:
            logger.error(f"Error closing audit logger: {e}")

    async def log_event(self, event: AuditEvent) -> None:
        """Log an audit event."""
        if not self._should_log_event(event):
            return
        # Set context if not already set
        if not event.context:
            event.context = self.context
        try:
            if self.config.async_logging:
                await self._event_queue.put(event)
            else:
                await self._log_to_destinations(event)
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")

    def create_event_builder(self) -> AuditEventBuilder:
        """Create an audit event builder with context."""
        return AuditEventBuilder(self.context)

    async def log_auth_event(
        self,
        event_type: AuditEventType,
        user_id: str,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        source_ip: str | None = None,
        details: builtins.dict[str, Any] | None = None,
    ) -> None:
        """Log authentication event."""
        builder = (
            self.create_event_builder()
            .event_type(event_type)
            .user(user_id)
            .outcome(outcome)
            .action("authenticate")
            .severity(
                AuditSeverity.MEDIUM if outcome == AuditOutcome.SUCCESS else AuditSeverity.HIGH
            )
        )
        if source_ip:
            builder.request(source_ip=source_ip)
        if details:
            builder.details(details)
        await self.log_event(builder.build())

    async def log_api_event(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        user_id: str | None = None,
        source_ip: str | None = None,
        duration_ms: float | None = None,
        request_size: int | None = None,
        response_size: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Log API request/response event."""
        outcome = AuditOutcome.SUCCESS if 200 <= status_code < 400 else AuditOutcome.FAILURE
        severity = AuditSeverity.INFO if outcome == AuditOutcome.SUCCESS else AuditSeverity.MEDIUM
        builder = (
            self.create_event_builder()
            .event_type(AuditEventType.API_REQUEST)
            .outcome(outcome)
            .severity(severity)
            .action(f"{method} {endpoint}")
            .request(source_ip=source_ip, method=method, endpoint=endpoint)
            .detail("status_code", status_code)
            .detail("request_size", request_size)
            .detail("response_size", response_size)
        )
        if user_id:
            builder.user(user_id)
        if duration_ms:
            builder.performance(duration_ms, response_size)
        if error_message:
            builder.error(error_message=error_message)
        await self.log_event(builder.build())

    async def log_data_event(
        self,
        event_type: AuditEventType,
        resource_type: str,
        resource_id: str,
        action: str,
        user_id: str | None = None,
        changes: builtins.dict[str, Any] | None = None,
    ) -> None:
        """Log data operation event."""
        builder = (
            self.create_event_builder()
            .event_type(event_type)
            .resource(resource_type, resource_id)
            .action(action)
            .outcome(AuditOutcome.SUCCESS)
            .severity(AuditSeverity.MEDIUM)
        )
        if user_id:
            builder.user(user_id)
        if changes:
            builder.detail("changes", changes)
        await self.log_event(builder.build())

    async def log_security_event(
        self,
        event_type: AuditEventType,
        message: str,
        severity: AuditSeverity = AuditSeverity.HIGH,
        source_ip: str | None = None,
        user_id: str | None = None,
        details: builtins.dict[str, Any] | None = None,
    ) -> None:
        """Log security event."""
        builder = (
            self.create_event_builder()
            .event_type(event_type)
            .message(message)
            .severity(severity)
            .outcome(AuditOutcome.FAILURE)
            .action("security_violation")
        )
        if source_ip:
            builder.request(source_ip=source_ip)
        if user_id:
            builder.user(user_id)
        if details:
            builder.details(details)
        await self.log_event(builder.build())

    async def log_system_event(
        self,
        event_type: AuditEventType,
        message: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        details: builtins.dict[str, Any] | None = None,
    ) -> None:
        """Log system event."""
        builder = (
            self.create_event_builder()
            .event_type(event_type)
            .message(message)
            .severity(severity)
            .outcome(AuditOutcome.SUCCESS)
            .action("system_operation")
        )
        if details:
            builder.details(details)
        await self.log_event(builder.build())

    async def search_events(
        self,
        event_type: AuditEventType | None = None,
        user_id: str | None = None,
        source_ip: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> AsyncGenerator[AuditEvent, None]:
        """Search audit events across all destinations that support it."""
        criteria = {}
        if event_type:
            criteria["event_type"] = event_type.value
        if user_id:
            criteria["user_id"] = user_id
        if source_ip:
            criteria["source_ip"] = source_ip
        if start_time:
            criteria["start_time"] = start_time
        if end_time:
            criteria["end_time"] = end_time
        # Search in database destination first (most efficient)
        for destination in self.destinations:
            if isinstance(destination, DatabaseAuditDestination):
                async for event in destination.search_events(criteria, limit):
                    yield event
                return
        # Fallback to file destination
        for destination in self.destinations:
            if isinstance(destination, FileAuditDestination):
                async for event in destination.search_events(criteria, limit):
                    yield event
                return

    async def get_audit_statistics(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> builtins.dict[str, Any]:
        """Get audit logging statistics."""
        if not start_time:
            start_time = datetime.now(timezone.utc) - timedelta(days=7)
        if not end_time:
            end_time = datetime.now(timezone.utc)
        stats = {
            "period": {"start": start_time.isoformat(), "end": end_time.isoformat()},
            "event_counts": {},
            "user_activity": {},
            "security_events": 0,
            "error_events": 0,
            "total_events": 0,
        }
        try:
            async for event in self.search_events(
                start_time=start_time, end_time=end_time, limit=10000
            ):
                stats["total_events"] += 1
                # Count by event type
                event_type = event.event_type.value
                stats["event_counts"][event_type] = stats["event_counts"].get(event_type, 0) + 1
                # Count by user
                if event.user_id:
                    stats["user_activity"][event.user_id] = (
                        stats["user_activity"].get(event.user_id, 0) + 1
                    )
                # Count security events
                if "security" in event_type.lower() or event.severity in [
                    AuditSeverity.HIGH,
                    AuditSeverity.CRITICAL,
                ]:
                    stats["security_events"] += 1
                # Count error events
                if event.outcome in [AuditOutcome.FAILURE, AuditOutcome.ERROR]:
                    stats["error_events"] += 1
        except Exception as e:
            logger.error(f"Error generating audit statistics: {e}")
            stats["error"] = str(e)
        return stats

    async def cleanup_old_events(self, older_than_days: int = None) -> int:
        """Clean up old audit events based on retention policy."""
        if older_than_days is None:
            older_than_days = self.config.retention_days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        logger.info(
            f"Cleaning up audit events older than {older_than_days} days (before {cutoff_date})"
        )
        # This would typically be implemented in the database destination
        # For now, return 0 as a placeholder
        return 0

    async def _setup_destinations(self) -> None:
        """Setup audit logging destinations."""
        # File destination
        if self.config.enable_file_logging:
            file_destination = FileAuditDestination(
                log_file_path=self.config.log_file_path,
                max_file_size=self.config.max_file_size,
                max_files=self.config.max_files,
                encrypt_sensitive=self.config.encrypt_sensitive_data,
            )
            self.destinations.append(file_destination)
            logger.info(f"Added file audit destination: {self.config.log_file_path}")
        # Database destination
        if self.config.enable_database_logging and self.db_session:
            db_destination = DatabaseAuditDestination(
                db_session=self.db_session,
                encrypt_sensitive=self.config.encrypt_sensitive_data,
                batch_size=self.config.batch_size,
            )
            self.destinations.append(db_destination)
            logger.info("Added database audit destination")
        # Console destination
        if self.config.enable_console_logging:
            console_destination = ConsoleAuditDestination(format_json=False, include_details=True)
            self.destinations.append(console_destination)
            logger.info("Added console audit destination")
        # SIEM destination
        if self.config.enable_siem_logging and self.config.siem_endpoint:
            siem_destination = SIEMAuditDestination(
                siem_endpoint=self.config.siem_endpoint,
                api_key=self.config.siem_api_key,
                batch_size=self.config.batch_size,
            )
            self.destinations.append(siem_destination)
            logger.info(f"Added SIEM audit destination: {self.config.siem_endpoint}")

    def _should_log_event(self, event: AuditEvent) -> bool:
        """Check if event should be logged based on configuration."""
        # Check minimum severity
        severity_levels = {
            AuditSeverity.INFO: 0,
            AuditSeverity.LOW: 1,
            AuditSeverity.MEDIUM: 2,
            AuditSeverity.HIGH: 3,
            AuditSeverity.CRITICAL: 4,
        }
        if severity_levels[event.severity] < severity_levels[self.config.min_severity]:
            return False
        # Check excluded event types
        if event.event_type in self.config.excluded_event_types:
            return False
        return True

    async def _log_to_destinations(self, event: AuditEvent) -> None:
        """Log event to all configured destinations."""
        for destination in self.destinations:
            try:
                await destination.log_event(event)
            except Exception as e:
                logger.error(f"Failed to log to destination {type(destination).__name__}: {e}")

    async def _process_event_queue(self) -> None:
        """Process events from the async queue."""
        while not self._shutdown:
            try:
                # Wait for events with timeout
                try:
                    event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                    await self._log_to_destinations(event)
                except asyncio.TimeoutError:
                    continue
            except Exception as e:
                logger.error(f"Error processing audit event queue: {e}")
                await asyncio.sleep(1)

    async def _flush_task(self) -> None:
        """Periodic flush task for destinations."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.flush_interval_seconds)
                # Trigger flush on destinations that support it
                for destination in self.destinations:
                    if hasattr(destination, "_flush_batch"):
                        try:
                            await destination._flush_batch()
                        except Exception as e:
                            logger.error(
                                f"Error flushing destination {type(destination).__name__}: {e}"
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush task: {e}")

    async def _cleanup_task(self) -> None:
        """Periodic cleanup task for old audit events."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.cleanup_interval_hours * 3600)
                if self.config.auto_cleanup:
                    cleaned_count = await self.cleanup_old_events()
                    logger.info(f"Cleaned up {cleaned_count} old audit events")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger | None:
    """Get the global audit logger instance."""
    return _audit_logger


def set_audit_logger(audit_logger: AuditLogger) -> None:
    """Set the global audit logger instance."""
    global _audit_logger
    _audit_logger = audit_logger


@asynccontextmanager
async def audit_context(config: AuditConfig, context: AuditContext, db_session: Any | None = None):
    """Context manager for audit logging."""
    audit_logger = AuditLogger(config, context, db_session)
    try:
        await audit_logger.initialize()
        set_audit_logger(audit_logger)
        yield audit_logger
    finally:
        await audit_logger.close()
        set_audit_logger(None)
