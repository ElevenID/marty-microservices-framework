from typing import Optional

import pytest

from mmf.core.domain.ports.cache import CachePort


class ConcreteCache(CachePort[str]):
    """Concrete implementation of CachePort for testing."""

    async def get(self, key: str) -> str | None:
        return "value"

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        return True

    async def delete(self, key: str) -> bool:
        return True

    async def exists(self, key: str) -> bool:
        return True


class TestCachePort:
    def test_cannot_instantiate_abstract_cache(self):
        """Test that the abstract CachePort class cannot be instantiated."""
        with pytest.raises(TypeError):
            CachePort()

    @pytest.mark.asyncio
    async def test_concrete_cache_implementation(self):
        """Test that a concrete implementation works as expected."""
        cache = ConcreteCache()

        # Test get
        val = await cache.get("key")
        assert val == "value"

        # Test set
        success = await cache.set("key", "value")
        assert success is True

        # Test delete
        deleted = await cache.delete("key")
        assert deleted is True

        # Test exists
        exists = await cache.exists("key")
        assert exists is True
