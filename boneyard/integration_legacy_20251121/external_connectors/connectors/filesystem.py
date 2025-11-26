"""Filesystem connector implementation for external systems."""

import logging
import os
import time
from pathlib import Path

from ..base import ExternalSystemConnector
from ..config import ExternalSystemConfig, IntegrationRequest, IntegrationResponse


class FileSystemConnector(ExternalSystemConnector):
    """Filesystem connector implementation.

    PRODUCTION READY: This implementation provides functional local filesystem
    operations with circuit breaker patterns and proper error handling.

    For production deployment with remote filesystems (S3, Azure Blob, etc.):
    1. Install appropriate SDK (boto3, azure-storage-blob, etc.)
    2. Add authentication handling (credentials, IAM roles, etc.)
    3. Implement retry logic for network operations
    4. Add streaming support for large files
    5. Configure proper timeouts and connection limits
    """

    def __init__(self, config: ExternalSystemConfig):
        """Initialize file system connector."""
        super().__init__(config)
        self.base_path = Path(config.endpoint_url or "/tmp")

    async def connect(self) -> bool:
        """Connect to file system."""
        try:
            # Ensure the base path exists and is accessible
            self.base_path.mkdir(parents=True, exist_ok=True)
            if not os.access(self.base_path, os.R_OK | os.W_OK):
                raise PermissionError(f"No read/write access to {self.base_path}")

            logging.info(f"Connected to file system: {self.base_path}")
            self.connected = True
            return True
        except Exception as e:
            logging.exception(f"Failed to connect to file system: {e}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from file system."""
        try:
            # No actual disconnect needed for local filesystem
            self.connected = False
            logging.info(f"Disconnected from file system: {self.base_path}")
            return True
        except Exception as e:
            logging.exception(f"Failed to disconnect from file system: {e}")
            return False

    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute file system request."""
        start_time = time.time()

        try:
            # Check circuit breaker
            if self.is_circuit_breaker_open():
                raise ConnectionError("Circuit breaker is open")

            # Implement file system operations based on request
            operation = request.data.get("operation", "read") if request.data else "read"
            file_path = request.data.get("file_path", "test.txt") if request.data else "test.txt"

            full_path = self.base_path / file_path

            if operation == "read":
                if full_path.exists():
                    content = full_path.read_text(encoding="utf-8")
                    result_data = {"content": content, "size": len(content), "path": str(file_path)}
                else:
                    raise FileNotFoundError(f"File not found: {file_path}")
            elif operation == "write":
                content = request.data.get("content", "") if request.data else ""
                # Ensure parent directories exist
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")
                result_data = {"bytes_written": len(content), "path": str(file_path)}
            elif operation == "append":
                content = request.data.get("content", "") if request.data else ""
                # Ensure parent directories exist
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, "a", encoding="utf-8") as f:
                    f.write(content)
                result_data = {"bytes_appended": len(content), "path": str(file_path)}
            elif operation == "delete":
                if full_path.exists():
                    if full_path.is_file():
                        full_path.unlink()
                        result_data = {"deleted": True, "path": str(file_path)}
                    else:
                        raise ValueError(f"Path is not a file: {file_path}")
                else:
                    raise FileNotFoundError(f"File not found: {file_path}")
            elif operation == "list":
                if full_path.is_dir():
                    files = [f.name for f in full_path.iterdir() if f.is_file()]
                    dirs = [d.name for d in full_path.iterdir() if d.is_dir()]
                    result_data = {
                        "files": files,
                        "directories": dirs,
                        "total_files": len(files),
                        "path": str(file_path),
                    }
                else:
                    files = [f.name for f in self.base_path.iterdir() if f.is_file()]
                    result_data = {"files": files, "count": len(files), "path": str(self.base_path)}
            elif operation == "exists":
                result_data = {
                    "exists": full_path.exists(),
                    "is_file": full_path.is_file(),
                    "path": str(file_path),
                }
            elif operation == "info":
                if full_path.exists():
                    stat = full_path.stat()
                    result_data = {
                        "path": str(file_path),
                        "size": stat.st_size,
                        "modified_time": stat.st_mtime,
                        "is_file": full_path.is_file(),
                        "is_directory": full_path.is_dir(),
                    }
                else:
                    raise FileNotFoundError(f"File not found: {file_path}")
            else:
                raise ValueError(f"Unsupported operation: {operation}")

            latency = (time.time() - start_time) * 1000
            self.record_success()

            return IntegrationResponse(
                request_id=request.request_id,
                success=True,
                data=result_data,
                latency_ms=latency,
            )

        except (FileNotFoundError, ValueError, ConnectionError) as e:
            latency = (time.time() - start_time) * 1000
            self.record_failure()

            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.record_failure()

            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=f"File system operation error: {e}",
                latency_ms=latency,
            )

    async def health_check(self) -> bool:
        """Check file system health."""
        try:
            # Check if base path is accessible
            return (
                self.connected
                and self.base_path.exists()
                and os.access(self.base_path, os.R_OK | os.W_OK)
            )
        except Exception as e:
            logging.exception("File system health check failed: %s", e)
            return False
