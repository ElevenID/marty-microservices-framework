"""
Storage Adapter for Gateway
"""

from mmf.core.gateway import IRateLimitStorage


class InMemoryRateLimitAdapter(IRateLimitStorage):
    """In-memory implementation of RateLimitStoragePort."""

    def __init__(self):
        self._storage: dict[str, int] = {}

    async def get_usage(self, key: str) -> int:
        return self._storage.get(key, 0)

    async def increment_usage(self, key: str, amount: int = 1, ttl: int = 60) -> int:
        # Simple implementation without TTL cleanup for now
        current = self._storage.get(key, 0)
        self._storage[key] = current + amount
        return self._storage[key]
