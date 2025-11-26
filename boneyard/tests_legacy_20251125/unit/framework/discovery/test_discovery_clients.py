from unittest.mock import AsyncMock

import pytest

from marty_msf.framework.discovery.clients.hybrid import HybridDiscovery
from marty_msf.framework.discovery.clients.server_side import ServerSideDiscovery
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
from marty_msf.framework.discovery.results import DiscoveryResult


def _make_instance(
    service_name: str = "orders", instance_id: str = "instance-1"
) -> ServiceInstance:
    endpoint = ServiceEndpoint(
        host="localhost",
        port=9000,
        protocol=ServiceInstanceType.HTTP,
    )
    metadata = ServiceMetadata(
        version="1.0.0",
        environment="test",
        region="us-west-2",
        availability_zone="us-west-2a",
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
async def test_server_side_discovery_caches_results() -> None:
    config = DiscoveryConfig(cache_strategy=CacheStrategy.TTL, cache_ttl=5.0)
    server = ServerSideDiscovery("http://discovery", config)
    query = ServiceQuery(service_name="orders")
    instance = _make_instance()

    query_mock = AsyncMock(return_value=[instance])
    server._query_discovery_service = query_mock

    first = await server.discover_instances(query)
    assert first.source == "discovery_service"
    assert first.cached is False

    second = await server.discover_instances(query)
    assert second.source == "cache"
    assert second.cached is True

    assert query_mock.await_count == 1
    assert server._stats["cache_hits"] == 1
    assert server._stats["cache_misses"] == 1


@pytest.mark.asyncio
async def test_hybrid_discovery_fallback_on_primary_failure() -> None:
    config = DiscoveryConfig(cache_strategy=CacheStrategy.NONE)
    query = ServiceQuery(service_name="billing")
    instance = _make_instance(service_name="billing", instance_id="billing-1")

    client_side = type("StubClientSide", (), {})()
    client_side.discover_instances = AsyncMock(side_effect=RuntimeError("registry offline"))

    fallback_result = DiscoveryResult(
        instances=[instance],
        query=query,
        source="server",
        cached=False,
        resolution_time=0.01,
    )

    server_side = type("StubServerSide", (), {})()
    server_side.discover_instances = AsyncMock(return_value=fallback_result)

    hybrid = HybridDiscovery(client_side, server_side, config)

    result = await hybrid.discover_instances(query)
    assert result.instances == [instance]
    assert result.metadata["fallback_used"] is True

    client_side.discover_instances.assert_awaited_once()
    server_side.discover_instances.assert_awaited_once()
