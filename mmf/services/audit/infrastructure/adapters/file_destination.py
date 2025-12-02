"""File destination adapter for audit logging."""

import asyncio
import gzip
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from mmf.services.audit.domain.contracts import IAuditDestination
from mmf.services.audit.domain.entities import RequestAuditEvent

logger = logging.getLogger(__name__)


class FileAuditDestination(IAuditDestination):
    """File destination adapter with rotation and compression."""

    def __init__(
        self,
        log_directory: str,
        max_file_size_mb: int = 100,
        max_files: int = 10,
        compress_rotated: bool = True,
        file_prefix: str = "audit",
    ):
        """Initialize file destination.

        Args:
            log_directory: Directory to store log files
            max_file_size_mb: Maximum file size before rotation (MB)
            max_files: Maximum number of log files to retain
            compress_rotated: Whether to compress rotated files
            file_prefix: Prefix for log filenames
        """
        self.log_directory = Path(log_directory)
        self.max_file_size = max_file_size_mb * 1024 * 1024  # Convert to bytes
        self.max_files = max_files
        self.compress_rotated = compress_rotated
        self.file_prefix = file_prefix
        self.current_file: Path | None = None
        self._write_lock = asyncio.Lock()

        # Create log directory if it doesn't exist
        self.log_directory.mkdir(parents=True, exist_ok=True)

    async def write_event(self, event: RequestAuditEvent) -> None:
        """Write a single audit event to file.

        Args:
            event: The audit event to write
        """
        async with self._write_lock:
            await self._ensure_current_file()
            await self._write_to_file(event)
            await self._check_rotation()

    async def write_batch(self, events: list[RequestAuditEvent]) -> None:
        """Write a batch of audit events to file.

        Args:
            events: List of audit events to write
        """
        async with self._write_lock:
            await self._ensure_current_file()
            for event in events:
                await self._write_to_file(event)
            await self._check_rotation()

    async def flush(self) -> None:
        """Flush any buffered events."""
        # aiofiles handles flushing automatically

    async def close(self) -> None:
        """Close the destination and cleanup resources."""
        self.current_file = None

    async def health_check(self) -> bool:
        """Check if the destination is healthy.

        Returns:
            True if destination is operational
        """
        try:
            return self.log_directory.exists() and os.access(self.log_directory, os.W_OK)
        except Exception as e:
            logger.error("File destination health check failed: %s", e)
            return False

    async def _ensure_current_file(self) -> None:
        """Ensure current log file exists."""
        if self.current_file is None or not self.current_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_file = self.log_directory / f"{self.file_prefix}_{timestamp}.log"
            logger.info("Created new audit log file: %s", self.current_file)

    async def _write_to_file(self, event: RequestAuditEvent) -> None:
        """Write event to current file.

        Args:
            event: The audit event to write
        """
        if self.current_file is None:
            await self._ensure_current_file()

        try:
            event_json = json.dumps(event.to_dict(), default=str)
            async with aiofiles.open(self.current_file, mode="a") as f:
                await f.write(event_json + "\n")
        except Exception as e:
            logger.error("Failed to write audit event to file: %s", e, exc_info=True)

    async def _check_rotation(self) -> None:
        """Check if log file needs rotation."""
        if self.current_file is None or not self.current_file.exists():
            return

        file_size = self.current_file.stat().st_size
        if file_size >= self.max_file_size:
            await self._rotate_file()

    async def _rotate_file(self) -> None:
        """Rotate the current log file."""
        if self.current_file is None:
            return

        logger.info("Rotating audit log file: %s", self.current_file)

        # Compress old file if enabled
        if self.compress_rotated:
            await self._compress_file(self.current_file)

        # Create new file
        self.current_file = None
        await self._ensure_current_file()

        # Clean up old files
        await self._cleanup_old_files()

    async def _compress_file(self, file_path: Path) -> None:
        """Compress a log file.

        Args:
            file_path: Path to the file to compress
        """
        try:
            compressed_path = file_path.with_suffix(file_path.suffix + ".gz")

            async with aiofiles.open(file_path, "rb") as f_in:
                content = await f_in.read()

            # Run gzip compression in executor to avoid blocking
            loop = asyncio.get_event_loop()
            compressed_content = await loop.run_in_executor(None, gzip.compress, content)

            async with aiofiles.open(compressed_path, "wb") as f_out:
                await f_out.write(compressed_content)

            # Remove original file
            file_path.unlink()
            logger.info("Compressed audit log: %s", compressed_path)
        except Exception as e:
            logger.error("Failed to compress audit log: %s", e, exc_info=True)

    async def _cleanup_old_files(self) -> None:
        """Remove old log files exceeding max_files limit."""
        try:
            # Get all audit log files (including compressed)
            log_files = sorted(
                self.log_directory.glob(f"{self.file_prefix}_*.log*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            # Remove files beyond max_files limit
            for old_file in log_files[self.max_files :]:
                old_file.unlink()
                logger.info("Removed old audit log: %s", old_file)
        except Exception as e:
            logger.error("Failed to cleanup old audit logs: %s", e, exc_info=True)
