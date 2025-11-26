"""
Service Discovery Manager

Main orchestrator for service discovery components including registry management,
load balancing, health monitoring, circuit breakers, and metrics collection.
"""

import asyncio
import builtins
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .circuit_breaker import CircuitBreakerConfig, CircuitBreakerManager
from .clients.base import ServiceDiscoveryClient
from .clients.client_side import ClientSideDiscovery
from .config import DiscoveryConfig, ServiceQuery
from .core import ServiceInstance, ServiceRegistry, ServiceWatcher
from .health import HealthCheckConfig, HealthMonitor, create_health_checker
from .load_balancing import (
    LoadBalancer,
    LoadBalancingConfig,
    LoadBalancingContext,
    create_load_balancer,
)
from .mesh import ServiceMeshConfig, ServiceMeshManager, create_service_mesh_client
from .monitoring import DiscoveryMetrics, MetricsAggregator, MetricsCollector
from .registry import (
    ConsulServiceRegistry,
    EtcdServiceRegistry,
    InMemoryServiceRegistry,
    KubernetesServiceRegistry,
)

logger = logging.getLogger(__name__)


class DiscoveryManagerState(Enum):
    """Discovery manager states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class DiscoveryManagerConfig:
    """Configuration for service discovery manager."""

    # Core settings
    service_name: str = "discovery-manager"
    environment: str = "development"

    # Registry configuration
    primary_registry_type: str = "memory"  # memory, consul, etcd, kubernetes
    backup_registry_types: builtins.list[str] = field(default_factory=list)
    registry_failover_enabled: bool = True

    # Load balancing
    load_balancing_enabled: bool = True
    load_balancing_config: LoadBalancingConfig | None = None

    # Health monitoring
    health_monitoring_enabled: bool = True
    default_health_check_config: HealthCheckConfig | None = None

    # Circuit breakers
    circuit_breaker_enabled: bool = True
    circuit_breaker_config: CircuitBreakerConfig | None = None

    # Service mesh integration
    service_mesh_enabled: bool = False
    service_mesh_configs: builtins.list[ServiceMeshConfig] = field(default_factory=list)

    # Discovery settings
    discovery_config: DiscoveryConfig | None = None
    auto_registration: bool = True

    # Monitoring and metrics
    metrics_enabled: bool = True
    metrics_export_interval: float = 60.0

    # Background tasks
    cleanup_interval: float = 300.0  # 5 minutes
    health_check_interval: float = 30.0
    metrics_collection_interval: float = 60.0

    # Startup and shutdown
    startup_timeout: float = 30.0
    shutdown_timeout: float = 30.0
    graceful_shutdown: bool = True


class ServiceDiscoveryManager:
    """Main service discovery manager orchestrating all components."""

    def __init__(self, config: DiscoveryManagerConfig):
        self.config = config
        self.state = DiscoveryManagerState.STOPPED

        # Core components
        self._primary_registry: ServiceRegistry | None = None
        self._backup_registries: builtins.list[ServiceRegistry] = []
        self._load_balancer: LoadBalancer | None = None
        self._discovery_client: ServiceDiscoveryClient | None = None
        self._health_monitor = HealthMonitor()
        self._circuit_breaker_manager = CircuitBreakerManager()
        self._service_mesh_manager = ServiceMeshManager()

        # Monitoring
        self._metrics_collector = MetricsCollector()
        self._discovery_metrics = DiscoveryMetrics(self._metrics_collector)
        self._metrics_aggregator = MetricsAggregator()

        # State management
        self._registered_services: builtins.set[str] = set()
        self._watched_services: builtins.dict[str, ServiceWatcher] = {}
        self._background_tasks: builtins.list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

        # Statistics
        self._stats = {
            "start_time": 0.0,
            "uptime": 0.0,
            "total_discoveries": 0,
            "successful_discoveries": 0,
            "failed_discoveries": 0,
            "registry_failures": 0,
            "circuit_breaker_trips": 0,
        }

    async def start(self):
        """Start the service discovery manager."""
        if self.state != DiscoveryManagerState.STOPPED:
            raise RuntimeError(f"Cannot start manager in state: {self.state}")

        self.state = DiscoveryManagerState.STARTING
        self._stats["start_time"] = time.time()

        try:
            # Initialize components
            await self._initialize_registries()
            await self._initialize_load_balancer()
            await self._initialize_discovery_client()
            await self._initialize_health_monitoring()
            await self._initialize_circuit_breakers()
            await self._initialize_service_mesh()
            await self._initialize_monitoring()

            # Start background tasks
            await self._start_background_tasks()

            self.state = DiscoveryManagerState.RUNNING
            logger.info("Service discovery manager started successfully")

        except Exception as e:
            self.state = DiscoveryManagerState.ERROR
            logger.error("Failed to start service discovery manager: %s", e)
            raise

    async def stop(self):
        """Stop the service discovery manager."""
        if self.state == DiscoveryManagerState.STOPPED:
            return

        self.state = DiscoveryManagerState.STOPPING
        self._shutdown_event.set()

        try:
            # Stop background tasks
            await self._stop_background_tasks()

            # Shutdown components
            await self._shutdown_monitoring()
            await self._shutdown_service_mesh()
            await self._shutdown_health_monitoring()
            await self._shutdown_discovery_client()
            await self._shutdown_registries()

            self.state = DiscoveryManagerState.STOPPED
            logger.info("Service discovery manager stopped successfully")

        except Exception as e:
            self.state = DiscoveryManagerState.ERROR
            logger.error("Failed to stop service discovery manager: %s", e)
            raise

    async def register_service(self, instance: ServiceInstance) -> bool:
        """Register a service instance."""
        if self.state != DiscoveryManagerState.RUNNING:
            raise RuntimeError(f"Manager not running: {self.state}")

        try:
            # Register with primary registry
            success = await self._primary_registry.register_instance(instance)

            if success:
                self._registered_services.add(instance.instance_id)

                # Setup health monitoring if enabled
                if self.config.health_monitoring_enabled:
                    await self._setup_health_monitoring(instance)

                logger.info("Registered service instance: %s", instance.instance_id)
                return True
            logger.error("Failed to register service instance: %s", instance.instance_id)
            return False

        except Exception as e:
            logger.error("Error registering service instance %s: %s", instance.instance_id, e)
            return False

    async def deregister_service(self, instance_id: str) -> bool:
        """Deregister a service instance."""
        if self.state != DiscoveryManagerState.RUNNING:
            raise RuntimeError(f"Manager not running: {self.state}")

        try:
            # Deregister from primary registry
            success = await self._primary_registry.deregister_instance(instance_id)

            if success:
                self._registered_services.discard(instance_id)
                logger.info("Deregistered service instance: %s", instance_id)
                return True
            logger.error("Failed to deregister service instance: %s", instance_id)
            return False

        except Exception as e:
            logger.error("Error deregistering service instance %s: %s", instance_id, e)
            return False

    async def discover_service(
        self, query: ServiceQuery, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Discover and select a service instance."""
        if self.state != DiscoveryManagerState.RUNNING:
            raise RuntimeError(f"Manager not running: {self.state}")

        start_time = time.time()

        try:
            self._stats["total_discoveries"] += 1

            # Use discovery client to find services
            result = await self._discovery_client.discover_instances(query)

            if not result.instances:
                logger.warning("No instances found for service: %s", query.service_name)
                return None

            # Use load balancer to select instance if configured
            if self._load_balancer:
                await self._load_balancer.update_instances(result.instances)
                instance = await self._load_balancer.select_with_fallback(context)
            else:
                # Simple selection
                instance = result.instances[0]

            if instance:
                self._stats["successful_discoveries"] += 1

                # Record metrics
                duration = time.time() - start_time
                self._discovery_metrics.record_discovery_request(True, duration, query.service_name)

                return instance
            self._stats["failed_discoveries"] += 1
            return None

        except Exception as e:
            self._stats["failed_discoveries"] += 1
            duration = time.time() - start_time
            self._discovery_metrics.record_discovery_request(False, duration, query.service_name)
            logger.error("Service discovery failed for %s: %s", query.service_name, e)
            return None

    async def get_service_instances(self, service_name: str) -> builtins.list[ServiceInstance]:
        """Get all instances for a service."""
        if self.state != DiscoveryManagerState.RUNNING:
            raise RuntimeError(f"Manager not running: {self.state}")

        try:
            return await self._primary_registry.get_instances(service_name)
        except Exception as e:
            logger.error("Error getting service instances for %s: %s", service_name, e)
            return []

    async def watch_service(
        self,
        service_name: str,
        callback: Callable[[builtins.list[ServiceInstance]], None],
    ):
        """Watch a service for changes."""
        if self.state != DiscoveryManagerState.RUNNING:
            raise RuntimeError(f"Manager not running: {self.state}")

        try:
            watcher = await self._primary_registry.watch_service(service_name, callback)
            self._watched_services[service_name] = watcher
            logger.info("Started watching service: %s", service_name)
        except Exception as e:
            logger.error("Error watching service %s: %s", service_name, e)

    async def stop_watching_service(self, service_name: str):
        """Stop watching a service."""
        watcher = self._watched_services.pop(service_name, None)
        if watcher:
            await watcher.stop()
            logger.info("Stopped watching service: %s", service_name)

    def get_health_status(self) -> builtins.dict[str, Any]:
        """Get health status of the discovery manager."""
        return {
            "state": self.state.value,
            "uptime": time.time() - self._stats["start_time"]
            if self._stats["start_time"] > 0
            else 0,
            "primary_registry_healthy": self._primary_registry is not None,
            "backup_registries_count": len(self._backup_registries),
            "registered_services": len(self._registered_services),
            "watched_services": len(self._watched_services),
            "background_tasks": len(self._background_tasks),
            "statistics": self._stats.copy(),
        }

    def get_detailed_stats(self) -> builtins.dict[str, Any]:
        """Get detailed statistics."""
        stats = {
            "manager": self.get_health_status(),
            "discovery_client": self._discovery_client.get_stats()
            if self._discovery_client
            else {},
            "load_balancer": self._load_balancer.get_stats() if self._load_balancer else {},
            "health_monitor": self._health_monitor.get_all_health_status()
            if self._health_monitor
            else {},
            "circuit_breakers": self._circuit_breaker_manager.get_all_stats(),
            "service_mesh": self._service_mesh_manager.health_check_all_meshes()
            if self._service_mesh_manager
            else {},
            "metrics": self._metrics_collector.export_metrics(),
        }

        return stats

    async def _initialize_registries(self):
        """Initialize service registries."""
        # Initialize primary registry
        self._primary_registry = await self._create_registry(self.config.primary_registry_type)

        # Initialize backup registries
        for registry_type in self.config.backup_registry_types:
            try:
                registry = await self._create_registry(registry_type)
                self._backup_registries.append(registry)
            except Exception as e:
                logger.warning("Failed to initialize backup registry %s: %s", registry_type, e)

    async def _create_registry(self, registry_type: str) -> ServiceRegistry:
        """Create service registry instance."""
        if registry_type == "memory":
            return InMemoryServiceRegistry()
        if registry_type == "consul":
            return ConsulServiceRegistry()
        if registry_type == "etcd":
            return EtcdServiceRegistry()
        if registry_type == "kubernetes":
            return KubernetesServiceRegistry()
        raise ValueError(f"Unsupported registry type: {registry_type}")

    async def _initialize_load_balancer(self):
        """Initialize load balancer."""
        if self.config.load_balancing_enabled:
            lb_config = self.config.load_balancing_config or LoadBalancingConfig()
            self._load_balancer = create_load_balancer(lb_config)

    async def _initialize_discovery_client(self):
        """Initialize discovery client."""
        discovery_config = self.config.discovery_config or DiscoveryConfig()
        self._discovery_client = ClientSideDiscovery(self._primary_registry, discovery_config)

    async def _initialize_health_monitoring(self):
        """Initialize health monitoring."""
        if self.config.health_monitoring_enabled:
            # Health monitor is already created in __init__
            pass

    async def _initialize_circuit_breakers(self):
        """Initialize circuit breakers."""
        if self.config.circuit_breaker_enabled:
            if self.config.circuit_breaker_config:
                self._circuit_breaker_manager.set_default_config(self.config.circuit_breaker_config)

    async def _initialize_service_mesh(self):
        """Initialize service mesh integration."""
        if self.config.service_mesh_enabled:
            for mesh_config in self.config.service_mesh_configs:
                try:
                    client = create_service_mesh_client(mesh_config)
                    await client.connect()
                    self._service_mesh_manager.add_mesh_client(
                        f"{mesh_config.mesh_type.value}-client", client
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to initialize service mesh %s: %s",
                        mesh_config.mesh_type,
                        e,
                    )

    async def _initialize_monitoring(self):
        """Initialize monitoring and metrics."""
        if self.config.metrics_enabled:
            self._metrics_aggregator.add_collector(self._metrics_collector)
            self._metrics_aggregator.set_export_interval(self.config.metrics_export_interval)
            await self._metrics_aggregator.start()

    async def _setup_health_monitoring(self, instance: ServiceInstance):
        """Setup health monitoring for service instance."""
        if self.config.default_health_check_config:
            checker = create_health_checker(self.config.default_health_check_config)
            self._health_monitor.add_checker(f"{instance.instance_id}-health", checker)
            await self._health_monitor.start_monitoring(instance)

    async def _start_background_tasks(self):
        """Start background tasks."""
        # Cleanup task
        cleanup_task = asyncio.create_task(self._cleanup_task())
        self._background_tasks.append(cleanup_task)

        # Metrics collection task
        if self.config.metrics_enabled:
            metrics_task = asyncio.create_task(self._metrics_collection_task())
            self._background_tasks.append(metrics_task)

        # Health monitoring task (if not already started)
        if self.config.health_monitoring_enabled:
            # Health monitor starts its own tasks
            pass

    async def _stop_background_tasks(self):
        """Stop background tasks."""
        for task in self._background_tasks:
            task.cancel()

        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks.clear()

    async def _cleanup_task(self):
        """Background cleanup task."""
        while not self._shutdown_event.is_set():
            try:
                await self._perform_cleanup()
                await asyncio.wait_for(
                    self._shutdown_event.wait(), timeout=self.config.cleanup_interval
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cleanup task error: %s", e)
                await asyncio.sleep(60)  # Wait before retry

    async def _metrics_collection_task(self):
        """Background metrics collection task."""
        while not self._shutdown_event.is_set():
            try:
                await self._collect_metrics()
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.config.metrics_collection_interval,
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Metrics collection task error: %s", e)
                await asyncio.sleep(60)

    async def _perform_cleanup(self):
        """Perform periodic cleanup operations."""
        # Update uptime
        if self._stats["start_time"] > 0:
            self._stats["uptime"] = time.time() - self._stats["start_time"]

        # Clean up expired cache entries, stale registrations, etc.
        # This would be implemented based on specific needs

        logger.debug("Performed cleanup operations")

    async def _collect_metrics(self):
        """Collect and update metrics."""
        # Update service counts
        if self._primary_registry:
            try:
                all_services = []
                for service_name in self._registered_services:
                    instances = await self._primary_registry.get_instances(service_name)
                    all_services.extend(instances)

                total_services = len(all_services)
                healthy_services = len([s for s in all_services if s.is_healthy()])

                self._discovery_metrics.update_service_counts(total_services, healthy_services)
            except Exception as e:
                logger.warning("Failed to collect service metrics: %s", e)

        logger.debug("Collected metrics")

    async def _shutdown_monitoring(self):
        """Shutdown monitoring components."""
        if self._metrics_aggregator:
            await self._metrics_aggregator.stop()

    async def _shutdown_service_mesh(self):
        """Shutdown service mesh components."""
        # Service mesh manager would handle client disconnections

    async def _shutdown_health_monitoring(self):
        """Shutdown health monitoring."""
        if self._health_monitor:
            await self._health_monitor.stop_monitoring()

    async def _shutdown_discovery_client(self):
        """Shutdown discovery client."""
        # Clean up watchers
        for service_name in list(self._watched_services.keys()):
            await self.stop_watching_service(service_name)

    async def _shutdown_registries(self):
        """Shutdown service registries."""
        # Deregister all services if graceful shutdown
        if self.config.graceful_shutdown:
            for instance_id in list(self._registered_services):
                try:
                    await self.deregister_service(instance_id)
                except Exception as e:
                    logger.warning(
                        "Failed to deregister service %s during shutdown: %s",
                        instance_id,
                        e,
                    )


# Convenience function to create manager with defaults
def create_discovery_manager(
    service_name: str = "discovery-manager", environment: str = "development", **kwargs
) -> ServiceDiscoveryManager:
    """Create service discovery manager with default configuration."""

    config = DiscoveryManagerConfig(service_name=service_name, environment=environment, **kwargs)

    return ServiceDiscoveryManager(config)
