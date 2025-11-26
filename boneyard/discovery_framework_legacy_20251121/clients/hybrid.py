from __future__ import annotations

"""
Hybrid discovery client that composes client-side and server-side strategies.
"""

import logging

from ..config import DiscoveryConfig, ServiceQuery
from ..results import DiscoveryResult
from .base import ServiceDiscoveryClient
from .client_side import ClientSideDiscovery
from .server_side import ServerSideDiscovery

logger = logging.getLogger(__name__)


class HybridDiscovery(ServiceDiscoveryClient):
    """Hybrid discovery combining client-side and server-side approaches."""

    def __init__(
        self,
        client_side: ClientSideDiscovery,
        server_side: ServerSideDiscovery,
        config: DiscoveryConfig,
    ):
        super().__init__(config)
        self.client_side = client_side
        self.server_side = server_side
        self.prefer_client_side = True

    async def discover_instances(self, query: ServiceQuery) -> DiscoveryResult:
        """Discover instances using the configured preference with fallback."""
        primary = self.client_side if self.prefer_client_side else self.server_side
        fallback = self.server_side if self.prefer_client_side else self.client_side

        try:
            return await primary.discover_instances(query)

        except Exception as error:
            logger.warning("Primary discovery failed, trying fallback: %s", error)

            try:
                result = await fallback.discover_instances(query)
                result.metadata["fallback_used"] = True
                return result

            except Exception as fallback_error:
                logger.error("Both discovery methods failed: %s", fallback_error)
                raise
