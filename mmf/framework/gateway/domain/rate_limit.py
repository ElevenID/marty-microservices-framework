"""
Gateway Rate Limiting Domain Service
"""

from ..ports.output import RateLimitStoragePort
from .exceptions import RateLimitExceededError
from .models import GatewayRequest, RouteConfig


class GatewayRateLimiter:
    """
    Handles rate limiting for gateway requests.
    """

    def __init__(self, storage: RateLimitStoragePort | None = None):
        self.storage = storage

    async def check_rate_limit(self, route: RouteConfig, request: GatewayRequest) -> None:
        """
        Check if the request exceeds the rate limit for the route.

        Args:
            route: The matched route configuration.
            request: The incoming gateway request.

        Raises:
            RateLimitExceededError: If the rate limit is exceeded.
        """
        # Simple implementation
        if not route.rate_limit or not self.storage:
            return

        key = f"rl:{route.name}:{request.client_ip}"
        usage = await self.storage.increment_usage(key)
        if usage > route.rate_limit.requests_per_window:
            raise RateLimitExceededError()
