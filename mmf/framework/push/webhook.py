"""
Webhook Push Adapter.

HTTP webhook adapter for delivering notifications to external endpoints.
Supports HMAC signing, circuit breaker pattern, and configurable retries.

Features:
- HMAC-SHA256 payload signing
- Circuit breaker pattern for endpoint protection
- Exponential backoff retry
- Event type filtering
- Configurable timeouts
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mmf.core.push import IPushAdapter, PushChannel, PushMessage, PushResult, PushStatus

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class WebhookEndpointConfig:
    """Configuration for a single webhook endpoint."""

    url: str
    secret: str = ""  # Empty = no signature
    event_types: list[str] = field(default_factory=list)  # Empty = all events
    enabled: bool = True
    custom_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class WebhookConfig:
    """Webhook adapter configuration."""

    # Timeout settings
    connect_timeout: float = 5.0
    read_timeout: float = 30.0

    # Retry settings
    max_retries: int = 3
    initial_backoff: float = 1.0
    max_backoff: float = 60.0

    # Circuit breaker settings
    failure_threshold: int = 5
    recovery_timeout: int = 300  # 5 minutes

    # Signature settings
    signature_header: str = "X-MMF-Signature"
    event_header: str = "X-MMF-Event"
    delivery_id_header: str = "X-MMF-Delivery-Id"
    timestamp_header: str = "X-MMF-Timestamp"


# =============================================================================
# Circuit Breaker
# =============================================================================


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for an endpoint."""

    failures: int = 0
    last_failure: datetime | None = None
    is_open: bool = False

    def record_failure(self, threshold: int) -> None:
        """Record a failure and potentially open the circuit."""
        self.failures += 1
        self.last_failure = datetime.now(timezone.utc)
        if self.failures >= threshold:
            self.is_open = True
            logger.warning(f"Circuit breaker opened after {self.failures} failures")

    def record_success(self) -> None:
        """Record a success and reset the circuit."""
        if self.is_open:
            logger.info("Circuit breaker closed after successful request")
        self.failures = 0
        self.is_open = False

    def should_allow(self, recovery_timeout: int) -> bool:
        """Check if a request should be allowed."""
        if not self.is_open:
            return True

        # Check if recovery timeout has elapsed
        if self.last_failure:
            elapsed = (datetime.now(timezone.utc) - self.last_failure).total_seconds()
            if elapsed >= recovery_timeout:
                return True  # Allow one attempt (half-open)

        return False


# =============================================================================
# Webhook Adapter
# =============================================================================


class WebhookAdapter:
    """
    Webhook push adapter.

    Implements IPushAdapter for HTTP webhook delivery. Sends push
    messages as JSON payloads to configured endpoints.

    Usage:
        config = WebhookConfig(max_retries=5)
        adapter = WebhookAdapter(config)
        await adapter.start()

        # Send with endpoints in target
        message = PushMessage(
            target=PushTarget(webhook_urls=["https://example.com/webhook"]),
            data={"event": "notification"},
        )
        result = await adapter.send(message)

        # Or with explicit endpoint configs
        result = await adapter.send_to_endpoints(
            message,
            endpoints=[
                WebhookEndpointConfig(
                    url="https://example.com/webhook",
                    secret="my-secret",  # pragma: allowlist secret
                )
            ],
        )
    """

    def __init__(self, config: WebhookConfig | None = None):
        """
        Initialize the webhook adapter.

        Args:
            config: Webhook configuration (uses defaults if not provided)
        """
        self.config = config or WebhookConfig()
        self._client: Any = None  # httpx.AsyncClient
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}

    @property
    def channel(self) -> PushChannel:
        """The channel this adapter handles."""
        return PushChannel.WEBHOOK

    async def start(self) -> None:
        """Start the webhook adapter."""
        try:
            import httpx

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=self.config.connect_timeout,
                    read=self.config.read_timeout,
                    write=self.config.read_timeout,
                    pool=self.config.connect_timeout,
                ),
            )
            logger.info("Webhook adapter started")
        except ImportError:
            raise RuntimeError("httpx is required for webhook adapter: pip install httpx")

    async def stop(self) -> None:
        """Stop the webhook adapter and cleanup resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.info("Webhook adapter stopped")

    def _get_circuit_breaker(self, url: str) -> CircuitBreakerState:
        """Get or create circuit breaker for an endpoint."""
        if url not in self._circuit_breakers:
            self._circuit_breakers[url] = CircuitBreakerState()
        return self._circuit_breakers[url]

    async def send(self, message: PushMessage) -> PushResult:
        """
        Send a push message to webhook endpoints.

        Uses URLs from message.target.webhook_urls.

        Args:
            message: The push message

        Returns:
            PushResult with delivery status
        """
        if not message.target.webhook_urls:
            return PushResult(
                message_id=message.id,
                channel=PushChannel.WEBHOOK,
                status=PushStatus.FAILED,
                success=False,
                error_code="NO_ENDPOINTS",
                error_message="No webhook URLs provided",
            )

        # Convert URLs to endpoint configs
        endpoints = [WebhookEndpointConfig(url=url) for url in message.target.webhook_urls]

        return await self.send_to_endpoints(message, endpoints)

    async def send_to_endpoints(
        self,
        message: PushMessage,
        endpoints: list[WebhookEndpointConfig],
    ) -> PushResult:
        """
        Send a push message to specific webhook endpoints.

        Args:
            message: The push message
            endpoints: List of endpoint configurations

        Returns:
            PushResult with delivery status
        """
        if not endpoints:
            return PushResult(
                message_id=message.id,
                channel=PushChannel.WEBHOOK,
                status=PushStatus.FAILED,
                success=False,
                error_code="NO_ENDPOINTS",
                error_message="No webhook endpoints provided",
            )

        # Filter by enabled and event type
        event_type = message.data.get("event_type", "")
        filtered = [
            ep
            for ep in endpoints
            if ep.enabled and (not ep.event_types or event_type in ep.event_types)
        ]

        if not filtered:
            return PushResult(
                message_id=message.id,
                channel=PushChannel.WEBHOOK,
                status=PushStatus.DELIVERED,
                success=True,
                metadata={"skipped": "No matching endpoints for event type"},
            )

        # Send to all endpoints in parallel
        tasks = [self._deliver_to_endpoint(message, ep) for ep in filtered]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        success_count = sum(1 for r in results if isinstance(r, PushResult) and r.success)
        total = len(filtered)

        return PushResult(
            message_id=message.id,
            channel=PushChannel.WEBHOOK,
            status=PushStatus.DELIVERED if success_count > 0 else PushStatus.FAILED,
            success=success_count > 0,
            delivered_at=datetime.now(timezone.utc) if success_count > 0 else None,
            metadata={
                "total_endpoints": total,
                "success_count": success_count,
                "failure_count": total - success_count,
            },
        )

    async def send_batch(self, messages: list[PushMessage]) -> list[PushResult]:
        """Send multiple messages."""
        results = []
        for message in messages:
            result = await self.send(message)
            results.append(result)
        return results

    async def _deliver_to_endpoint(
        self,
        message: PushMessage,
        endpoint: WebhookEndpointConfig,
    ) -> PushResult:
        """Deliver to a single endpoint with retries."""
        # Check circuit breaker
        circuit = self._get_circuit_breaker(endpoint.url)
        if not circuit.should_allow(self.config.recovery_timeout):
            return PushResult(
                message_id=message.id,
                channel=PushChannel.WEBHOOK,
                status=PushStatus.FAILED,
                success=False,
                error_code="CIRCUIT_OPEN",
                error_message="Circuit breaker is open for this endpoint",
            )

        # Build request body
        body = json.dumps(message.to_dict()).encode()

        # Generate signature
        signature = self._sign_payload(body, endpoint.secret)

        # Build headers
        headers = {
            "Content-Type": "application/json",
            self.config.event_header: message.data.get("event_type", "push"),
            self.config.delivery_id_header: message.id,
            self.config.timestamp_header: datetime.now(timezone.utc).isoformat(),
            **endpoint.custom_headers,
        }

        if signature:
            headers[self.config.signature_header] = signature

        if message.correlation_id:
            headers["X-MMF-Correlation-Id"] = message.correlation_id

        # Attempt delivery with retries
        for attempt in range(self.config.max_retries):
            try:
                if self._client is None:
                    await self.start()

                response = await self._client.post(
                    endpoint.url,
                    content=body,
                    headers=headers,
                )

                if response.status_code < 400:
                    circuit.record_success()
                    return PushResult(
                        message_id=message.id,
                        channel=PushChannel.WEBHOOK,
                        status=PushStatus.DELIVERED,
                        success=True,
                        delivered_at=datetime.now(timezone.utc),
                        attempt_number=attempt + 1,
                        metadata={
                            "status_code": response.status_code,
                            "endpoint": endpoint.url,
                        },
                    )

                # Server error - retry
                if response.status_code >= 500:
                    circuit.record_failure(self.config.failure_threshold)
                    backoff = min(
                        self.config.initial_backoff * (2**attempt),
                        self.config.max_backoff,
                    )
                    logger.warning(
                        f"Webhook {endpoint.url} returned {response.status_code}, "
                        f"retry {attempt + 1}, backing off {backoff}s"
                    )
                    await asyncio.sleep(backoff)
                    continue

                # Client error - don't retry
                return PushResult(
                    message_id=message.id,
                    channel=PushChannel.WEBHOOK,
                    status=PushStatus.REJECTED,
                    success=False,
                    error_code=str(response.status_code),
                    error_message=response.text[:200] if response.text else None,
                    attempt_number=attempt + 1,
                )

            except Exception as e:
                circuit.record_failure(self.config.failure_threshold)
                logger.error(f"Webhook error for {endpoint.url}: {e}")

                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.initial_backoff * (2**attempt))
                    continue

                return PushResult(
                    message_id=message.id,
                    channel=PushChannel.WEBHOOK,
                    status=PushStatus.FAILED,
                    success=False,
                    error_code="EXCEPTION",
                    error_message=str(e),
                    should_retry=True,
                )

        return PushResult(
            message_id=message.id,
            channel=PushChannel.WEBHOOK,
            status=PushStatus.FAILED,
            success=False,
            error_code="MAX_RETRIES",
            error_message="Max retries exceeded",
        )

    def _sign_payload(self, body: bytes, secret: str) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        if not secret:
            return ""

        signature = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        return f"sha256={signature}"

    @staticmethod
    def verify_signature(body: bytes, secret: str, signature: str) -> bool:
        """
        Verify webhook signature.

        Args:
            body: Raw request body bytes
            secret: Webhook secret
            signature: Signature header value

        Returns:
            True if signature is valid
        """
        if not signature.startswith("sha256="):
            return False

        expected = f"sha256={hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}"
        return hmac.compare_digest(expected, signature)

    def get_circuit_breaker_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics for all endpoints."""
        return {
            url: {
                "failures": cb.failures,
                "is_open": cb.is_open,
                "last_failure": cb.last_failure.isoformat() if cb.last_failure else None,
            }
            for url, cb in self._circuit_breakers.items()
        }
