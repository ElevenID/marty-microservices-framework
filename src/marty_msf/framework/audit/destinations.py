"""
Audit logging destinations for the enterprise audit framework.
This module provides various destinations for audit events:
- File-based logging with rotation
- Database logging with structured storage
- SIEM integration
- Console logging for development
"""

import asyncio
import builtins
import gzip
import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiofiles
import aiohttp
from colorama import Fore, Style, init
from sqlalchemy import Column, DateTime, Integer, String, Text, and_, select
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

from .events import (
    AuditContext,
    AuditDestination,
    AuditEncryption,
    AuditEvent,
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
)

logger = logging.getLogger(__name__)
Base = declarative_base()


class AuditLogRecord(Base):
    """Database model for audit log records."""

    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    outcome = Column(String(20), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    # Actor information
    user_id = Column(String(255), index=True)
    username = Column(String(255))
    session_id = Column(String(255), index=True)
    api_key_id = Column(String(255))
    client_id = Column(String(255))
    # Request information
    source_ip = Column(INET)
    user_agent = Column(Text)
    request_id = Column(String(255), index=True)
    method = Column(String(10))
    endpoint = Column(String(500))
    # Resource and action
    resource_type = Column(String(100), index=True)
    resource_id = Column(String(255))
    action = Column(String(255), nullable=False)
    # Event details
    message = Column(Text)
    details = Column(JSONB)
    # Context
    service_name = Column(String(100), index=True)
    environment = Column(String(50), index=True)
    correlation_id = Column(String(255), index=True)
    trace_id = Column(String(255), index=True)
    # Performance
    duration_ms = Column(Integer)
    response_size = Column(Integer)
    # Error information
    error_code = Column(String(100))
    error_message = Column(Text)
    # Integrity and metadata
    event_hash = Column(String(64))
    encrypted_fields = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class FileAuditDestination(AuditDestination):
    """File-based audit logging with rotation and compression."""

    def __init__(
        self,
        log_file_path: Path,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        max_files: int = 10,
        encrypt_sensitive: bool = True,
    ):
        self.log_file_path = Path(log_file_path)
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.encrypt_sensitive = encrypt_sensitive
        if encrypt_sensitive:
            self.encryption = AuditEncryption()
        # Ensure directory exists
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def log_event(self, event: AuditEvent) -> None:
        """Log audit event to file."""
        try:
            async with self._lock:
                # Check if rotation is needed
                await self._rotate_if_needed()
                # Prepare event data
                event_data = event.to_dict()
                # Encrypt sensitive data if enabled
                if self.encrypt_sensitive:
                    event_data["details"] = self.encryption.encrypt_sensitive_data(
                        event_data.get("details", {})
                    )
                # Add integrity hash
                event_data["event_hash"] = event.get_hash()
                # Write to file
                async with aiofiles.open(self.log_file_path, "a", encoding="utf-8") as f:
                    await f.write(json.dumps(event_data, default=str) + "\n")
                logger.debug(f"Logged audit event {event.event_id} to file")
        except Exception as e:
            logger.error(f"Failed to log audit event to file: {e}")

    async def search_events(
        self, criteria: builtins.dict[str, Any], limit: int = 100
    ) -> AsyncGenerator[AuditEvent, None]:
        """Search audit events in file (simple implementation)."""
        try:
            if not self.log_file_path.exists():
                return
            count = 0
            async with aiofiles.open(self.log_file_path, encoding="utf-8") as f:
                async for line in f:
                    if count >= limit:
                        break
                    try:
                        event_data = json.loads(line.strip())
                        # Simple filtering
                        if self._matches_criteria(event_data, criteria):
                            # Convert back to AuditEvent (simplified)
                            yield self._dict_to_event(event_data)
                            count += 1
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to search audit events in file: {e}")

    async def close(self) -> None:
        """Close file destination."""
        # No persistent connections to close

    async def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds size limit."""
        if not self.log_file_path.exists():
            return
        if self.log_file_path.stat().st_size > self.max_file_size:
            await self._rotate_files()

    async def _rotate_files(self) -> None:
        """Rotate log files."""
        try:
            # Remove oldest file if we have too many
            oldest_file = self.log_file_path.with_suffix(f".{self.max_files - 1}.log")
            if oldest_file.exists():
                oldest_file.unlink()
            # Shift existing files
            for i in range(self.max_files - 2, 0, -1):
                current_file = self.log_file_path.with_suffix(f".{i}.log")
                next_file = self.log_file_path.with_suffix(f".{i + 1}.log")
                if current_file.exists():
                    current_file.rename(next_file)
            # Move current file to .1
            if self.log_file_path.exists():
                rotated_file = self.log_file_path.with_suffix(".1.log")
                self.log_file_path.rename(rotated_file)
                # Optionally compress rotated file
                await self._compress_file(rotated_file)
            logger.info(f"Rotated audit log file: {self.log_file_path}")
        except Exception as e:
            logger.error(f"Failed to rotate audit log files: {e}")

    async def _compress_file(self, file_path: Path) -> None:
        """Compress rotated log file."""
        try:

            compressed_path = file_path.with_suffix(file_path.suffix + ".gz")
            with open(file_path, "rb") as f_in:
                with gzip.open(compressed_path, "wb") as f_out:
                    f_out.writelines(f_in)
            # Remove original file
            file_path.unlink()
            logger.debug(f"Compressed audit log file: {compressed_path}")
        except Exception as e:
            logger.error(f"Failed to compress audit log file: {e}")

    def _matches_criteria(
        self, event_data: builtins.dict[str, Any], criteria: builtins.dict[str, Any]
    ) -> bool:
        """Check if event matches search criteria."""
        for key, value in criteria.items():
            if key not in event_data:
                return False
            if isinstance(value, list):
                if event_data[key] not in value:
                    return False
            elif event_data[key] != value:
                return False
        return True

    def _dict_to_event(self, event_data: builtins.dict[str, Any]) -> AuditEvent:
        """Convert dictionary back to AuditEvent (simplified)."""
        # This is a simplified conversion - in production you might want more robust handling

        return AuditEvent(
            event_id=event_data.get("event_id", ""),
            event_type=AuditEventType(event_data.get("event_type", "api_request")),
            severity=AuditSeverity(event_data.get("severity", "info")),
            outcome=AuditOutcome(event_data.get("outcome", "success")),
            timestamp=datetime.fromisoformat(
                event_data.get("timestamp", datetime.now().isoformat())
            ),
            user_id=event_data.get("user_id"),
            action=event_data.get("action", ""),
            message=event_data.get("message", ""),
            details=event_data.get("details", {}),
        )


class DatabaseAuditDestination(AuditDestination):
    """Database-based audit logging with structured queries."""

    def __init__(
        self,
        db_session: AsyncSession,
        encrypt_sensitive: bool = True,
        batch_size: int = 100,
    ):
        self.db_session = db_session
        self.encrypt_sensitive = encrypt_sensitive
        self.batch_size = batch_size
        self._batch: builtins.list[AuditEvent] = []
        self._batch_lock = asyncio.Lock()
        if encrypt_sensitive:
            self.encryption = AuditEncryption()

    async def log_event(self, event: AuditEvent) -> None:
        """Log audit event to database."""
        try:
            async with self._batch_lock:
                self._batch.append(event)
                if len(self._batch) >= self.batch_size:
                    await self._flush_batch()
        except Exception as e:
            logger.error(f"Failed to add audit event to batch: {e}")

    async def search_events(
        self, criteria: builtins.dict[str, Any], limit: int = 100
    ) -> AsyncGenerator[AuditEvent, None]:
        """Search audit events in database."""
        try:
            query = select(AuditLogRecord)
            # Apply filters
            conditions = []
            if "event_type" in criteria:
                conditions.append(AuditLogRecord.event_type == criteria["event_type"])
            if "user_id" in criteria:
                conditions.append(AuditLogRecord.user_id == criteria["user_id"])
            if "source_ip" in criteria:
                conditions.append(AuditLogRecord.source_ip == criteria["source_ip"])
            if "start_time" in criteria:
                conditions.append(AuditLogRecord.timestamp >= criteria["start_time"])
            if "end_time" in criteria:
                conditions.append(AuditLogRecord.timestamp <= criteria["end_time"])
            if "service_name" in criteria:
                conditions.append(AuditLogRecord.service_name == criteria["service_name"])
            if conditions:
                query = query.where(and_(*conditions))
            query = query.order_by(AuditLogRecord.timestamp.desc()).limit(limit)
            result = await self.db_session.execute(query)
            for record in result.scalars():
                yield self._record_to_event(record)
        except Exception as e:
            logger.error(f"Failed to search audit events in database: {e}")

    async def close(self) -> None:
        """Close database destination and flush remaining events."""
        try:
            async with self._batch_lock:
                if self._batch:
                    await self._flush_batch()
        except Exception as e:
            logger.error(f"Failed to flush final batch: {e}")

    async def _flush_batch(self) -> None:
        """Flush batched events to database."""
        if not self._batch:
            return
        try:
            for event in self._batch:
                # Prepare event data
                details = event.details or {}
                encrypted_fields = []
                if self.encrypt_sensitive:
                    original_details = details.copy()
                    details = self.encryption.encrypt_sensitive_data(details)
                    # Track which fields were encrypted
                    for key in original_details:
                        if f"{key}_encrypted" in details:
                            encrypted_fields.append(key)
                # Create database record
                record = AuditLogRecord(
                    event_id=event.event_id,
                    event_type=event.event_type.value,
                    severity=event.severity.value,
                    outcome=event.outcome.value,
                    timestamp=event.timestamp,
                    user_id=event.user_id,
                    username=event.username,
                    session_id=event.session_id,
                    api_key_id=event.api_key_id,
                    client_id=event.client_id,
                    source_ip=event.source_ip,
                    user_agent=event.user_agent,
                    request_id=event.request_id,
                    method=event.method,
                    endpoint=event.endpoint,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    action=event.action,
                    message=event.message,
                    details=details,
                    service_name=event.context.service_name if event.context else None,
                    environment=event.context.environment if event.context else None,
                    correlation_id=event.context.correlation_id if event.context else None,
                    trace_id=event.context.trace_id if event.context else None,
                    duration_ms=int(event.duration_ms) if event.duration_ms else None,
                    response_size=event.response_size,
                    error_code=event.error_code,
                    error_message=event.error_message,
                    event_hash=event.get_hash(),
                    encrypted_fields=encrypted_fields if encrypted_fields else None,
                )
                self.db_session.add(record)
            await self.db_session.commit()
            logger.debug(f"Flushed {len(self._batch)} audit events to database")
            self._batch.clear()
        except Exception as e:
            logger.error(f"Failed to flush audit events to database: {e}")
            await self.db_session.rollback()

    def _record_to_event(self, record: AuditLogRecord) -> AuditEvent:
        """Convert database record to AuditEvent."""

        # Decrypt sensitive fields if needed
        details = record.details or {}
        if self.encrypt_sensitive and record.encrypted_fields:
            details = self.encryption.decrypt_sensitive_data(details)
        # Create context if available
        context = None
        if record.service_name:
            context = AuditContext(
                service_name=record.service_name,
                environment=record.environment or "",
                version="",  # Not stored in this example
                instance_id="",  # Not stored in this example
                correlation_id=record.correlation_id,
                trace_id=record.trace_id,
            )
        return AuditEvent(
            event_id=record.event_id,
            event_type=AuditEventType(record.event_type),
            severity=AuditSeverity(record.severity),
            outcome=AuditOutcome(record.outcome),
            timestamp=record.timestamp,
            user_id=record.user_id,
            username=record.username,
            session_id=record.session_id,
            api_key_id=record.api_key_id,
            client_id=record.client_id,
            source_ip=str(record.source_ip) if record.source_ip else None,
            user_agent=record.user_agent,
            request_id=record.request_id,
            method=record.method,
            endpoint=record.endpoint,
            resource_type=record.resource_type,
            resource_id=record.resource_id,
            action=record.action,
            message=record.message,
            details=details,
            context=context,
            duration_ms=float(record.duration_ms) if record.duration_ms else None,
            response_size=record.response_size,
            error_code=record.error_code,
            error_message=record.error_message,
        )


class ConsoleAuditDestination(AuditDestination):
    """Console-based audit logging for development."""

    def __init__(self, format_json: bool = False, include_details: bool = True):
        self.format_json = format_json
        self.include_details = include_details
        # Setup colored output if available
        try:

            init()
            self.colors = {
                "INFO": Fore.WHITE,
                "LOW": Fore.GREEN,
                "MEDIUM": Fore.YELLOW,
                "HIGH": Fore.RED,
                "CRITICAL": Fore.RED + Style.BRIGHT,
            }
            self.reset_color = Style.RESET_ALL
        except ImportError:
            self.colors = {}
            self.reset_color = ""

    async def log_event(self, event: AuditEvent) -> None:
        """Log audit event to console."""
        try:
            if self.format_json:
                print(event.to_json())
            else:
                color = self.colors.get(event.severity.value.upper(), "")
                reset = self.reset_color
                output = (
                    f"{color}[{event.timestamp.isoformat()}] "
                    f"{event.severity.value.upper()}: "
                    f"{event.event_type.value} - "
                    f"{event.action} "
                    f"({event.outcome.value})"
                    f"{reset}"
                )
                if event.user_id:
                    output += f" | User: {event.user_id}"
                if event.source_ip:
                    output += f" | IP: {event.source_ip}"
                if event.message:
                    output += f" | {event.message}"
                if self.include_details and event.details:
                    output += f" | Details: {json.dumps(event.details, default=str)}"
                print(output)
        except Exception as e:
            logger.error(f"Failed to log audit event to console: {e}")

    async def search_events(
        self, criteria: builtins.dict[str, Any], limit: int = 100
    ) -> AsyncGenerator[AuditEvent, None]:
        """Console destination doesn't support searching."""
        return
        yield  # This is unreachable but makes the function a generator

    async def close(self) -> None:
        """Close console destination."""


class SIEMAuditDestination(AuditDestination):
    """SIEM integration for audit events."""

    def __init__(self, siem_endpoint: str, api_key: str, batch_size: int = 50):
        self.siem_endpoint = siem_endpoint
        self.api_key = api_key
        self.batch_size = batch_size
        self._batch: builtins.list[AuditEvent] = []
        self._batch_lock = asyncio.Lock()

    async def log_event(self, event: AuditEvent) -> None:
        """Log audit event to SIEM."""
        try:
            async with self._batch_lock:
                self._batch.append(event)
                if len(self._batch) >= self.batch_size:
                    await self._send_batch()
        except Exception as e:
            logger.error(f"Failed to add audit event to SIEM batch: {e}")

    async def search_events(
        self, criteria: builtins.dict[str, Any], limit: int = 100
    ) -> AsyncGenerator[AuditEvent, None]:
        """SIEM destination typically doesn't support searching from application."""
        return
        yield  # This is unreachable but makes the function a generator

    async def close(self) -> None:
        """Close SIEM destination and send remaining events."""
        try:
            async with self._batch_lock:
                if self._batch:
                    await self._send_batch()
        except Exception as e:
            logger.error(f"Failed to send final SIEM batch: {e}")

    async def _send_batch(self) -> None:
        """Send batched events to SIEM."""
        if not self._batch:
            return
        try:

            # Prepare payload
            events_data = [event.to_dict() for event in self._batch]
            payload = {
                "events": events_data,
                "source": "audit-framework",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.siem_endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        logger.debug(f"Sent {len(self._batch)} audit events to SIEM")
                    else:
                        logger.error(f"SIEM responded with status {response.status}")
            self._batch.clear()
        except Exception as e:
            logger.error(f"Failed to send audit events to SIEM: {e}")
            # Don't clear batch on error - will retry on next batch or close
