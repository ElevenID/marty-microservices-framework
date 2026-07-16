"""HTTP Adapter for Delivery Service.

This adapter implements the DeliveryServicePort using HTTP requests.
"""

import logging
import os
from typing import Optional

import httpx

from examples.petstore_domain.services.store_service.application.ports.delivery_service import (
    DeliveryRequest,
    DeliveryServicePort,
)
from mmf.framework.resilience.domain.config import (
    CircuitBreakerConfig,
    RetryConfig,
    RetryStrategy,
)
from mmf.framework.resilience.infrastructure.adapters.circuit_breaker import (
    CircuitBreaker,
)
from mmf.framework.resilience.infrastructure.adapters.retry import RetryManager

logger = logging.getLogger(__name__)


class HttpDeliveryServiceAdapter(DeliveryServicePort):
    """HTTP implementation of the Delivery Service Port."""

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize the adapter.

        Args:
            base_url: Base URL of the delivery service. If None, reads from DELIVERY_BOARD_URL env var.
        """
        self.base_url = base_url or os.getenv("DELIVERY_BOARD_URL", "http://localhost:8002")

        # Initialize Circuit Breaker
        cb_config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=30,
            failure_exceptions=(httpx.RequestError, httpx.HTTPStatusError),
        )
        self.circuit_breaker = CircuitBreaker(name="delivery-service-cb", config=cb_config)

        # Initialize Retry Manager
        retry_config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            retryable_exceptions=(httpx.ConnectError, httpx.TimeoutException),
        )
        self.retry_manager = RetryManager(config=retry_config)

    async def _make_request(self, url: str, payload: dict) -> dict:
        """Make HTTP request."""
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=5.0)
            response.raise_for_status()
            return response.json()

    async def create_delivery(self, request: DeliveryRequest) -> Optional[str]:
        """Create a delivery via HTTP."""
        url = f"{self.base_url}/deliveries"
        payload = {
            "order_id": request.order_id,
            "address": request.address,
            "items": request.items,
            "priority": request.priority,
        }

        try:
            # Wrap request with retry logic
            async def retriable_request():
                return await self._make_request(url, payload)

            # Execute through circuit breaker and retry manager
            async def execute_with_resilience():
                return await self.retry_manager.execute_async(retriable_request)

            data = await self.circuit_breaker.call(execute_with_resilience)
            return data.get("id")

        except Exception as e:
            logger.error(f"Failed to create delivery: {e}")
            return None
