import asyncio

import pytest

from marty_msf.framework.discovery.cache import ServiceCache
from marty_msf.framework.discovery.config import (
    CacheStrategy,
    DiscoveryConfig,
    ServiceQuery,
)
from marty_msf.framework.discovery.core import (
    HealthStatus,
    ServiceEndpoint,
    ServiceInstance,
    ServiceInstanceType,
    ServiceMetadata,
)


def _make_instance(
    service_name: str = "orders", instance_id: str = "instance-1"
) -> ServiceInstance:
    endpoint = ServiceEndpoint(
        host="localhost",
        port=8080,
        protocol=ServiceInstanceType.HTTP,
    )
    metadata = ServiceMetadata(
        version="1.0.0",
        environment="test",
        region="us-east-1",
        availability_zone="us-east-1a",
    )
    instance = ServiceInstance(
        service_name=service_name,
        instance_id=instance_id,
        endpoint=endpoint,
        metadata=metadata,
    )
    instance.update_health_status(HealthStatus.HEALTHY)
    return instance


@pytest.mark.asyncio
async def test_cache_returns_and_expires_entries() -> None:
    config = DiscoveryConfig(cache_strategy=CacheStrategy.TTL, cache_ttl=0.05)
    cache = ServiceCache(config)
    query = ServiceQuery(service_name="orders")
    instance = _make_instance()

    await cache.put(query, [instance])
    cached = await cache.get(query)
    assert cached == [instance]

    # Age the entry beyond TTL without sleeping the test.
    entry = cache._cache[cache._generate_cache_key(query)]
    entry.created_at -= 0.1

    stale = await cache.get(query)
    assert stale is None
    assert cache.get_stats()["misses"] >= 1


@pytest.mark.asyncio
async def test_cache_refresh_ahead(monkeypatch: pytest.MonkeyPatch) -> None:
    config = DiscoveryConfig(
        cache_strategy=CacheStrategy.REFRESH_AHEAD,
        cache_ttl=0.1,
        refresh_ahead_factor=0.5,
    )
    cache = ServiceCache(config)
    query = ServiceQuery(service_name="orders")
    instance = _make_instance()

    await cache.put(query, [instance])
    cache_entry = cache._cache[cache._generate_cache_key(query)]
    cache_entry.created_at -= config.cache_ttl * config.refresh_ahead_factor * 1.2

    refresh_called = asyncio.Event()

    async def fake_refresh(self, cache_key, entry, refresh_callback):
        refresh_called.set()
        return []

    monkeypatch.setattr(ServiceCache, "_refresh_entry", fake_refresh, raising=False)

    async def refresh_callback():
        return [instance]

    await cache.get(query, refresh_callback=refresh_callback)
    await asyncio.wait_for(refresh_called.wait(), timeout=0.2)


@pytest.mark.asyncio
async def test_cache_invalidate_by_service() -> None:
    config = DiscoveryConfig(cache_strategy=CacheStrategy.TTL, cache_ttl=1.0)
    cache = ServiceCache(config)
    instance = _make_instance()
    query = ServiceQuery(service_name="billing")

    await cache.put(query, [instance])
    assert await cache.get(query) == [instance]

    await cache.invalidate(query.service_name)
    assert await cache.get(query) is None
