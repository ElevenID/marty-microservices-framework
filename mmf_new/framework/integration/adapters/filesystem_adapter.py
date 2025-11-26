"""
Filesystem Adapter
"""

import logging
import time
import aiofiles
import os
from pathlib import Path
from typing import Any

from mmf_new.framework.integration.ports.connector import ExternalSystemPort
from mmf_new.framework.integration.domain.models import (
    ConnectionConfig,
    IntegrationRequest,
    IntegrationResponse,
)
from mmf_new.framework.integration.domain.exceptions import ConnectionFailedError

class FileSystemAdapter(ExternalSystemPort):
    """Filesystem connector implementation using aiofiles."""

    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.base_path = Path(config.endpoint_url or "/tmp")
        self.connected = False

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
            raise ConnectionFailedError(f"Failed to connect: {e}")

    async def disconnect(self) -> bool:
        """Disconnect from file system."""
        self.connected = False
        return True

    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute file system request."""
        start_time = time.time()
        
        try:
            operation = request.operation.lower()
            file_path = request.data.get("file_path", "test.txt") if isinstance(request.data, dict) else "test.txt"
            full_path = self.base_path / file_path
            
            # Prevent directory traversal
            if not str(full_path.resolve()).startswith(str(self.base_path.resolve())):
                raise ValueError("Invalid file path: Access denied")

            result_data = None
            
            if operation == "read":
                if full_path.exists():
                    async with aiofiles.open(full_path) as f:
                        content = await f.read()
                    result_data = {"content": content, "size": len(content), "path": str(file_path)}
                else:
                    raise FileNotFoundError(f"File not found: {file_path}")
                    
            elif operation == "write":
                content = request.data.get("content", "") if isinstance(request.data, dict) else str(request.data)
                full_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(full_path, mode='w') as f:
                    await f.write(content)
                result_data = {"bytes_written": len(content), "path": str(file_path)}
                
            elif operation == "append":
                content = request.data.get("content", "") if isinstance(request.data, dict) else str(request.data)
                full_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(full_path, mode='a') as f:
                    await f.write(content)
                result_data = {"bytes_appended": len(content), "path": str(file_path)}
                
            elif operation == "delete":
                if full_path.exists():
                    if full_path.is_file():
                        os.remove(full_path)
                        result_data = {"deleted": True, "path": str(file_path)}
                    else:
                        raise ValueError(f"Path is not a file: {file_path}")
                else:
                    raise FileNotFoundError(f"File not found: {file_path}")
            
            else:
                raise ValueError(f"Unsupported operation: {operation}")

            latency = (time.time() - start_time) * 1000
            return IntegrationResponse(
                request_id=request.request_id,
                success=True,
                data=result_data,
                latency_ms=latency
            )
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                latency_ms=latency
            )

    async def health_check(self) -> bool:
        """Check health of file system."""
        try:
            return self.base_path.exists() and os.access(self.base_path, os.R_OK | os.W_OK)
        except Exception:
            return False
