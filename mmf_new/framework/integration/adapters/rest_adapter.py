"""
REST API Adapter
"""

import logging
import time
from typing import Any, Optional

import aiohttp

from mmf_new.framework.integration.domain.exceptions import (
    ConnectionFailedError,
    RequestTimeoutError,
)
from mmf_new.framework.integration.domain.models import (
    ConnectionConfig,
    IntegrationRequest,
    IntegrationResponse,
)
from mmf_new.framework.integration.ports.connector import ExternalSystemPort


class RESTAPIAdapter(ExternalSystemPort):
    """REST API connector implementation using aiohttp."""

    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.session: aiohttp.ClientSession | None = None
        self.connected = False

    async def connect(self) -> bool:
        """Establish HTTP session."""
        try:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
            self.connected = True
            logging.info(f"Connected to REST API: {self.config.endpoint_url}")
            return True
        except Exception as e:
            logging.exception(f"Failed to connect to REST API: {e}")
            raise ConnectionFailedError(f"Failed to connect: {e}")

    async def disconnect(self) -> bool:
        """Close HTTP session."""
        try:
            if self.session:
                await self.session.close()
                self.session = None
            self.connected = False
            logging.info(f"Disconnected from REST API: {self.config.endpoint_url}")
            return True
        except Exception as e:
            logging.exception(f"Failed to disconnect from REST API: {e}")
            return False

    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute HTTP request."""
        if not self.session:
            await self.connect()

        start_time = time.time()
        method = request.operation.upper()
        url = f"{self.config.endpoint_url}"

        # Handle path parameters if present in data
        if isinstance(request.data, dict) and "path" in request.data:
            url = f"{url}/{request.data['path'].lstrip('/')}"

        try:
            async with self.session.request(
                method=method,
                url=url,
                json=request.data if method in ["POST", "PUT", "PATCH"] else None,
                params=request.data if method == "GET" else None,
                headers=request.headers,
                timeout=request.timeout or self.config.timeout,
            ) as response:
                content = (
                    await response.json()
                    if response.content_type == "application/json"
                    else await response.text()
                )

                latency = (time.time() - start_time) * 1000

                return IntegrationResponse(
                    request_id=request.request_id,
                    success=response.status < 400,
                    data=content,
                    status_code=response.status,
                    headers=dict(response.headers),
                    latency_ms=latency,
                )
        except aiohttp.ClientError as e:
            latency = (time.time() - start_time) * 1000
            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logging.exception(f"Request failed: {e}")
            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                latency_ms=latency,
            )

    async def health_check(self) -> bool:
        """Check health of external system."""
        if not self.session:
            return False

        try:
            # Use configured health check endpoint or default to root
            url = self.config.endpoint_url
            if (
                hasattr(self.config, "protocol_settings")
                and "health_check_path" in self.config.protocol_settings
            ):
                url = f"{url}/{self.config.protocol_settings['health_check_path'].lstrip('/')}"

            async with self.session.get(url, timeout=5) as response:
                return response.status < 400
        except Exception:
            return False
