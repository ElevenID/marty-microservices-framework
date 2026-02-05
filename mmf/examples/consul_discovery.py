"""
Example: Using ConsulAdapter for Service Discovery

This example shows how to use ConsulAdapter instead of MemoryRegistry
for production service discovery with HashCorp Consul.
"""

import asyncio
import os

from mmf.discovery.adapters import ConsulAdapter
from mmf.discovery.domain.models import ServiceInstance, ServiceRegistryConfig


async def main():
    # Configuration
    config = ServiceRegistryConfig(
        enable_health_checks=True,
        health_check_interval=10,
        health_check_timeout=5,
        service_ttl=30,
    )

    # Create Consul adapter
    consul = ConsulAdapter(
        config=config,
        consul_host=os.getenv("CONSUL_HOST", "localhost"),
        consul_port=int(os.getenv("CONSUL_PORT", "8500")),
        consul_token=os.getenv("CONSUL_TOKEN"),
        consul_datacenter=os.getenv("CONSUL_DC", "dc1"),
    )

    await consul.start()

    try:
        # Register a service instance
        instance = ServiceInstance(
            service_name="my-api-service",
            instance_id="api-1",
            host="10.0.1.10",
            port=8080,
            version="1.2.0",
            region="us-west-2",
            zone="us-west-2a",
            tags={"environment", "production"},
            metadata={"team": "platform"},
            health_check_url="http://10.0.1.10:8080/health",
        )

        success = await consul.register(instance)
        print(f"Registration: {'Success' if success else 'Failed'}")

        # Discover service instances
        instances = await consul.discover("my-api-service")
        print(f"Found {len(instances)} instances")
        for inst in instances:
            print(f"  - {inst.instance_id}: {inst.host}:{inst.port} ({inst.health_status})")

        # Get only healthy instances
        healthy = await consul.get_healthy_instances("my-api-service")
        print(f"Healthy instances: {len(healthy)}")

        # List all services
        services = await consul.list_services()
        print(f"All services: {services}")

        # Cleanup
        await consul.deregister("my-api-service", "api-1")

        # Statistics
        stats = consul.get_stats()
        print(f"Stats: {stats}")

    finally:
        await consul.stop()


if __name__ == "__main__":
    asyncio.run(main())
