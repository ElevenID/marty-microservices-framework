"""
REST API Connector

HTTP/HTTPS REST API connector implementation with authentication,
circuit breaker, and health checking capabilities.
"""

import base64
import builtins
import logging
import time
from urllib.parse import urljoin

import aiohttp

from ..base import ExternalSystemConnector
from ..config import IntegrationRequest, IntegrationResponse


class RESTAPIConnector(ExternalSystemConnector):
    """REST API connector implementation."""

    def __init__(self, config):
        """Initialize REST API connector."""
        super().__init__(config)
        self.session: aiohttp.ClientSession | None = None

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
            return False

    async def disconnect(self) -> bool:
        """Close HTTP session."""
        try:
            if self.session:
                await self.session.close()

            self.connected = False
            logging.info(f"Disconnected from REST API: {self.config.endpoint_url}")
            return True

        except Exception as e:
            logging.exception(f"Failed to disconnect from REST API: {e}")
            return False

    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute REST API request."""
        start_time = time.time()

        try:
            # Check circuit breaker
            if self.is_circuit_breaker_open():
                raise Exception("Circuit breaker is open")

            if not self.session:
                raise Exception("Not connected to REST API")

            # Prepare request
            url = urljoin(self.config.endpoint_url, request.operation)
            headers = self._prepare_headers(request.headers)

            # Execute HTTP request
            method = request.data.get("method", "GET").upper()
            request_data = request.data.get("body")
            params = request.data.get("params")

            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=request_data if isinstance(request_data, dict) else None,
                data=request_data if isinstance(request_data, str | bytes) else None,
                params=params,
            ) as response:
                response_data = await response.text()

                # Try to parse as JSON
                try:
                    if response.content_type == "application/json":
                        response_data = await response.json()
                except Exception as parse_error:
                    logging.debug(
                        "REST API response from %s was not JSON: %s",
                        url,
                        parse_error,
                        exc_info=True,
                    )

                latency = (time.time() - start_time) * 1000

                # Record metrics
                self.metrics["total_requests"] += 1
                self.metrics["total_latency"] += latency

                if 200 <= response.status < 300:
                    self.record_success()

                    return IntegrationResponse(
                        request_id=request.request_id,
                        success=True,
                        data=response_data,
                        status_code=response.status,
                        headers=dict(response.headers),
                        latency_ms=latency,
                    )
                self.record_failure()

                return IntegrationResponse(
                    request_id=request.request_id,
                    success=False,
                    data=response_data,
                    status_code=response.status,
                    error_code=str(response.status),
                    error_message=f"HTTP {response.status}: {response.reason}",
                    latency_ms=latency,
                )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            self.record_failure()

            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                latency_ms=latency,
            )

    def _prepare_headers(self, request_headers: builtins.dict[str, str]) -> builtins.dict[str, str]:
        """Prepare HTTP headers with authentication."""
        headers = request_headers.copy()

        # Add authentication headers
        auth_type = self.config.auth_type
        credentials = self.config.credentials

        if auth_type == "bearer":
            token = credentials.get("token")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        elif auth_type == "api_key":
            api_key = credentials.get("api_key")
            key_header = credentials.get("key_header", "X-API-Key")
            if api_key:
                headers[key_header] = api_key

        elif auth_type == "basic":
            username = credentials.get("username")
            password = credentials.get("password")
            if username and password:
                auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {auth_string}"

        # Set default content type
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        return headers

    async def health_check(self) -> bool:
        """Check REST API health."""
        try:
            if not self.session:
                return False

            health_endpoint = self.config.health_check_endpoint or "/health"
            url = urljoin(self.config.endpoint_url, health_endpoint)

            async with self.session.get(url) as response:
                return 200 <= response.status < 300

        except Exception as e:
            logging.exception(f"REST API health check failed: {e}")
            return False
