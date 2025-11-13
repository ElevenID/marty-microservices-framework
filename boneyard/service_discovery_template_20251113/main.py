"""
Service Discovery Template

A comprehensive service discovery implementation that provides:
- Dynamic service registration and discovery
- Health monitoring and automatic deregistration
- Load balancing with multiple strategies
- Service metadata and tagging
- Integration with Consul, etcd, and Kubernetes
- Failover and clustering support
"""

import asyncio
import builtins
import signal
import sys
from contextlib import asynccontextmanager
from typing import Any, list

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from marty_msf.framework.config_factory import create_service_config
from marty_msf.framework.discovery import (
    DiscoveryManagerConfig,
    LoadBalancingConfig,
    LoadBalancingStrategy,
    ServiceDiscoveryManager,
    ServiceInstance,
    ServiceQuery,
)
from marty_msf.framework.discovery.monitoring import MetricsCollector
from marty_msf.framework.health import HealthChecker
from marty_msf.framework.logging import UnifiedServiceLogger

logger = UnifiedServiceLogger(__name__)

# Global discovery manager
discovery_manager: ServiceDiscoveryManager | None = None
metrics_collector: MetricsCollector | None = None
health_checker: HealthChecker | None = None


class ServiceDiscoveryService:
    """Service Discovery Service implementation."""

    def __init__(self):
        self.discovery_manager: ServiceDiscoveryManager | None = None
        self.metrics: MetricsCollector | None = None
        self.health_checker: HealthChecker | None = None
        self.registry_type = "consul"  # Default

    async def initialize(self, config: builtins.dict[str, Any]):
        """Initialize the service discovery service."""
        try:
            # Create discovery manager configuration
            discovery_config = DiscoveryManagerConfig(
                service_name="service-discovery",
                registry_type=config.get("registry_type", "consul"),
                consul_config={
                    "host": config.get("consul_host", "localhost"),
                    "port": config.get("consul_port", 8500),
                    "token": config.get("consul_token"),
                },
                etcd_config={
                    "host": config.get("etcd_host", "localhost"),
                    "port": config.get("etcd_port", 2379),
                },
                kubernetes_config={
                    "namespace": config.get("k8s_namespace", "default"),
                },
                load_balancing_enabled=True,
                load_balancing_config=LoadBalancingConfig(
                    strategy=LoadBalancingStrategy.ROUND_ROBIN,
                    health_check_enabled=True,
                ),
                health_check_enabled=True,
                health_check_interval=config.get("health_check_interval", 30),
                registry_refresh_interval=config.get("registry_refresh_interval", 60),
            )

            # Initialize discovery manager
            self.discovery_manager = ServiceDiscoveryManager(discovery_config)
            await self.discovery_manager.start()

            # Initialize metrics
            self.metrics = MetricsCollector("service_discovery")

            # Initialize health checker
            self.health_checker = HealthChecker()

            # Register self as a service
            self_instance = ServiceInstance(
                service_name="service-discovery",
                instance_id="discovery-001",
                endpoint=f"http://localhost:{config.get('port', 8090)}",
                metadata={
                    "version": "1.0.0",
                    "registry_type": self.registry_type,
                    "capabilities": ["registration", "discovery", "health_checks"],
                },
            )

            await self.discovery_manager.register_service(self_instance)

            logger.info("Service Discovery service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Service Discovery service: {e}")
            raise

    async def shutdown(self):
        """Shutdown the service discovery service."""
        try:
            if self.discovery_manager:
                await self.discovery_manager.stop()
            logger.info("Service Discovery service shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def register_service(self, service_data: builtins.dict[str, Any]) -> bool:
        """Register a service instance."""
        try:
            if not self.discovery_manager:
                raise RuntimeError("Discovery manager not initialized")

            # Create service instance from data
            service_instance = ServiceInstance(
                service_name=service_data["service_name"],
                instance_id=service_data.get(
                    "instance_id", f"{service_data['service_name']}-001"
                ),
                endpoint=service_data["endpoint"],
                metadata=service_data.get("metadata", {}),
                health_check_url=service_data.get("health_check_url"),
                tags=set(service_data.get("tags", [])),
            )

            # Register with discovery manager
            success = await self.discovery_manager.register_service(service_instance)

            if success:
                self.metrics.increment("services_registered") if self.metrics else None
                logger.info(
                    f"Registered service: {service_instance.service_name}[{service_instance.instance_id}]"
                )

            return success

        except Exception as e:
            logger.error(f"Failed to register service: {e}")
            self.metrics.increment("registration_errors") if self.metrics else None
            return False

    async def deregister_service(self, service_name: str, instance_id: str) -> bool:
        """Deregister a service instance."""
        try:
            if not self.discovery_manager:
                raise RuntimeError("Discovery manager not initialized")

            success = await self.discovery_manager.deregister_service(
                service_name, instance_id
            )

            if success:
                self.metrics.increment(
                    "services_deregistered"
                ) if self.metrics else None
                logger.info(f"Deregistered service: {service_name}[{instance_id}]")

            return success

        except Exception as e:
            logger.error(f"Failed to deregister service: {e}")
            self.metrics.increment("deregistration_errors") if self.metrics else None
            return False

    async def discover_services(
        self, service_name: str, tags: builtins.list[str] | None = None
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Discover service instances."""
        try:
            if not self.discovery_manager:
                raise RuntimeError("Discovery manager not initialized")

            # Create service query
            query = ServiceQuery(
                service_name=service_name,
                tags=set(tags) if tags else None,
                healthy_only=True,
            )

            # Discover services
            instances = await self.discovery_manager.discover_service_instances(query)

            # Convert to dictionary format
            result = []
            for instance in instances:
                result.append(
                    {
                        "service_name": instance.service_name,
                        "instance_id": instance.instance_id,
                        "endpoint": instance.endpoint,
                        "metadata": instance.metadata.to_dict()
                        if instance.metadata
                        else {},
                        "health_status": instance.health_status.value
                        if instance.health_status
                        else "unknown",
                        "tags": list(instance.tags) if instance.tags else [],
                    }
                )

            self.metrics.increment("discovery_requests") if self.metrics else None
            return result

        except Exception as e:
            logger.error(f"Failed to discover services: {e}")
            self.metrics.increment("discovery_errors") if self.metrics else None
            return []

    async def get_service_health(
        self, service_name: str, instance_id: str
    ) -> builtins.dict[str, Any]:
        """Get health status of a specific service instance."""
        try:
            if not self.discovery_manager:
                raise RuntimeError("Discovery manager not initialized")

            instance = await self.discovery_manager.get_service_instance(
                service_name, instance_id
            )

            if not instance:
                return {"status": "not_found"}

            # Perform health check if health checker is available
            health_status = "unknown"
            if self.health_checker and instance.health_check_url:
                is_healthy = await self.health_checker.check_health(
                    instance.health_check_url
                )
                health_status = "healthy" if is_healthy else "unhealthy"

            return {
                "service_name": instance.service_name,
                "instance_id": instance.instance_id,
                "endpoint": instance.endpoint,
                "health_status": health_status,
                "last_seen": instance.metadata.last_seen.isoformat()
                if instance.metadata and instance.metadata.last_seen
                else None,
            }

        except Exception as e:
            logger.error(f"Failed to get service health: {e}")
            return {"status": "error", "message": str(e)}

    async def get_all_services(self) -> builtins.dict[str, Any]:
        """Get all registered services."""
        try:
            if not self.discovery_manager:
                raise RuntimeError("Discovery manager not initialized")

            services = await self.discovery_manager.get_all_services()

            result = {}
            for service_name, instances in services.items():
                result[service_name] = []
                for instance in instances:
                    result[service_name].append(
                        {
                            "instance_id": instance.instance_id,
                            "endpoint": instance.endpoint,
                            "metadata": instance.metadata.to_dict()
                            if instance.metadata
                            else {},
                            "health_status": instance.health_status.value
                            if instance.health_status
                            else "unknown",
                            "tags": list(instance.tags) if instance.tags else [],
                        }
                    )

            return result

        except Exception as e:
            logger.error(f"Failed to get all services: {e}")
            return {}

    def get_metrics(self) -> builtins.dict[str, Any]:
        """Get service discovery metrics."""
        metrics = {}

        if self.metrics:
            metrics.update(self.metrics.get_all_metrics())

        if self.discovery_manager:
            discovery_stats = self.discovery_manager.get_stats()
            metrics.update(discovery_stats)

        return metrics

    def get_health_status(self) -> builtins.dict[str, Any]:
        """Get health status of the discovery service."""
        try:
            healthy = self.discovery_manager and self.discovery_manager.is_healthy()

            return {
                "status": "healthy" if healthy else "unhealthy",
                "discovery_manager": "healthy" if healthy else "unhealthy",
                "registry_type": self.registry_type,
                "timestamp": self.metrics.get_timestamp() if self.metrics else None,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Global service instance
service_discovery_service = ServiceDiscoveryService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global discovery_manager, metrics_collector, health_checker

    try:
        # Load configuration
        config = create_service_config()

        # Service discovery specific configuration
        sd_config = {
            "registry_type": config.discovery.registry_type
            if hasattr(config, "discovery")
            else "consul",
            "consul_host": "localhost",
            "consul_port": 8500,
            "etcd_host": "localhost",
            "etcd_port": 2379,
            "k8s_namespace": "default",
            "health_check_interval": 30,
            "registry_refresh_interval": 60,
            "port": 8090,
        }

        # Initialize service
        await service_discovery_service.initialize(sd_config)

        # Set global references
        discovery_manager = service_discovery_service.discovery_manager
        metrics_collector = service_discovery_service.metrics
        health_checker = service_discovery_service.health_checker

        logger.info("Service Discovery API started successfully")
        yield

    except Exception as e:
        logger.error(f"Failed to start Service Discovery API: {e}")
        raise
    finally:
        # Cleanup
        await service_discovery_service.shutdown()
        logger.info("Service Discovery API stopped")


# FastAPI app
app = FastAPI(
    title="Service Discovery API",
    description="Comprehensive service discovery with health monitoring and load balancing",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/services/register")
async def register_service(
    service_data: builtins.dict[str, Any], background_tasks: BackgroundTasks
):
    """Register a new service instance."""
    try:
        # Validate required fields
        required_fields = ["service_name", "endpoint"]
        for field in required_fields:
            if field not in service_data:
                raise HTTPException(
                    status_code=400, detail=f"Missing required field: {field}"
                )

        success = await service_discovery_service.register_service(service_data)

        if success:
            # Schedule health check in background
            if service_data.get("health_check_url"):
                background_tasks.add_task(
                    schedule_health_check,
                    service_data["service_name"],
                    service_data.get(
                        "instance_id", f"{service_data['service_name']}-001"
                    ),
                )

            return {"status": "success", "message": "Service registered successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to register service")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/services/{service_name}/{instance_id}")
async def deregister_service(service_name: str, instance_id: str):
    """Deregister a service instance."""
    try:
        success = await service_discovery_service.deregister_service(
            service_name, instance_id
        )

        if success:
            return {"status": "success", "message": "Service deregistered successfully"}
        else:
            raise HTTPException(status_code=404, detail="Service instance not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deregistration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/services")
async def get_all_services():
    """Get all registered services."""
    try:
        services = await service_discovery_service.get_all_services()
        return {"services": services, "total_services": len(services)}
    except Exception as e:
        logger.error(f"Error getting all services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/services/{service_name}")
async def discover_service(service_name: str, tags: str | None = None):
    """Discover instances of a specific service."""
    try:
        tag_list = tags.split(",") if tags else None
        instances = await service_discovery_service.discover_services(
            service_name, tag_list
        )

        return {
            "service_name": service_name,
            "instances": instances,
            "instance_count": len(instances),
        }
    except Exception as e:
        logger.error(f"Discovery error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/services/{service_name}/{instance_id}/health")
async def get_service_health(service_name: str, instance_id: str):
    """Get health status of a specific service instance."""
    try:
        health_status = await service_discovery_service.get_service_health(
            service_name, instance_id
        )

        if health_status.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Service instance not found")

        return health_status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/services/{service_name}/{instance_id}/health")
async def update_service_health(
    service_name: str, instance_id: str, health_data: builtins.dict[str, Any]
):
    """Update health status of a service instance."""
    try:
        # This would update the health status in the registry
        # Implementation depends on the specific registry backend
        return {"status": "success", "message": "Health status updated"}
    except Exception as e:
        logger.error(f"Health update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Service discovery health check."""
    health_status = service_discovery_service.get_health_status()

    if health_status["status"] == "healthy":
        return health_status
    else:
        return JSONResponse(status_code=503, content=health_status)


@app.get("/metrics")
async def get_metrics():
    """Get service discovery metrics."""
    try:
        metrics = service_discovery_service.get_metrics()
        return metrics
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get detailed statistics about the discovery service."""
    try:
        return {
            "metrics": service_discovery_service.get_metrics(),
            "health": service_discovery_service.get_health_status(),
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def schedule_health_check(service_name: str, instance_id: str):
    """Schedule a health check for a service instance."""
    try:
        await asyncio.sleep(5)  # Initial delay
        health_status = await service_discovery_service.get_service_health(
            service_name, instance_id
        )
        logger.info(
            f"Health check completed for {service_name}[{instance_id}]: {health_status}"
        )
    except Exception as e:
        logger.error(f"Health check failed for {service_name}[{instance_id}]: {e}")


def handle_shutdown(signum, frame):
    """Handle shutdown signals."""
    logger.info("Received shutdown signal, stopping service discovery...")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Run the service
    uvicorn.run("main:app", host="0.0.0.0", port=8090, reload=False, log_level="info")
