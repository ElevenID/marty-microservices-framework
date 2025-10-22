"""
Smart Dependency Management for Marty Microservices Framework

This module provides intelligent dependency injection, service discovery, and
automatic infrastructure integration for generated microservices.
"""

import asyncio
import builtins
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import networkx as nx
import yaml

from marty_msf.framework.cache.manager import CacheManager
from marty_msf.framework.config import BaseServiceConfig
from marty_msf.framework.messaging import EventStreamManager, MessageQueue


class DependencyType(Enum):
    """Types of dependencies in the framework."""

    INFRASTRUCTURE = "infrastructure"
    SERVICE = "service"
    LIBRARY = "library"
    CONFIGURATION = "configuration"
    DEPLOYMENT = "deployment"


class DependencyScope(Enum):
    """Dependency injection scopes."""

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"
    REQUEST = "request"


class ServiceLifecycle(Enum):
    """Service lifecycle states."""

    INACTIVE = "inactive"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass
class DependencySpec:
    """Specification for a dependency."""

    name: str
    type: DependencyType
    version: str
    scope: DependencyScope = DependencyScope.SINGLETON
    required: bool = True
    interface: str | None = None
    implementation: str | None = None
    configuration: builtins.dict[str, Any] = field(default_factory=dict)
    health_check: str | None = None
    retry_policy: builtins.dict[str, Any] = field(default_factory=dict)
    circuit_breaker: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceInterface:
    """Interface definition for a service."""

    name: str
    methods: builtins.list[str]
    events: builtins.list[str] = field(default_factory=list)
    schema: builtins.dict[str, Any] | None = None


@dataclass
class ServiceRegistration:
    """Service registration information."""

    name: str
    address: str
    port: int
    protocol: str
    interfaces: builtins.list[ServiceInterface]
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    health_check_endpoint: str | None = None
    tags: builtins.list[str] = field(default_factory=list)


class DependencyGraph:
    """Manages service dependency relationships."""

    def __init__(self):
        """Initialize the dependency graph."""
        self.graph = nx.DiGraph()
        self.services: builtins.dict[str, ServiceRegistration] = {}
        self.dependencies: builtins.dict[str, builtins.list[DependencySpec]] = {}

    def add_service(self, service: ServiceRegistration) -> None:
        """Add a service to the graph."""
        self.services[service.name] = service
        self.graph.add_node(service.name, **service.metadata)

    def add_dependency(self, service_name: str, dependency: DependencySpec) -> None:
        """Add a dependency relationship."""
        if service_name not in self.dependencies:
            self.dependencies[service_name] = []

        self.dependencies[service_name].append(dependency)

        # Add edge to graph if dependency is a service
        if dependency.type == DependencyType.SERVICE and dependency.name in self.services:
            self.graph.add_edge(service_name, dependency.name, dependency=dependency)

    def get_dependencies(self, service_name: str) -> builtins.list[DependencySpec]:
        """Get all dependencies for a service."""
        return self.dependencies.get(service_name, [])

    def get_dependents(self, service_name: str) -> builtins.list[str]:
        """Get all services that depend on this service."""
        return list(self.graph.predecessors(service_name))

    def resolve_startup_order(self) -> builtins.list[str]:
        """Resolve the startup order for services."""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXError as e:
            raise ValueError(f"Circular dependency detected: {e}")

    def detect_cycles(self) -> builtins.list[builtins.list[str]]:
        """Detect circular dependencies."""
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except nx.NetworkXError:
            return []

    def get_critical_path(self, start_service: str, end_service: str) -> builtins.list[str]:
        """Get the critical path between two services."""
        try:
            return nx.shortest_path(self.graph, start_service, end_service)
        except nx.NetworkXNoPath:
            return []


class ServiceDiscovery:
    """Service discovery mechanism."""

    def __init__(self, framework_root: Path):
        """Initialize service discovery."""
        self.framework_root = framework_root
        self.registry: builtins.dict[str, ServiceRegistration] = {}
        self.watchers: builtins.list[callable] = []
        self.health_checks: builtins.dict[str, builtins.dict[str, Any]] = {}

    async def register_service(self, service: ServiceRegistration) -> None:
        """Register a service."""
        self.registry[service.name] = service
        await self._notify_watchers("register", service)

    async def deregister_service(self, service_name: str) -> None:
        """Deregister a service."""
        if service_name in self.registry:
            service = self.registry.pop(service_name)
            await self._notify_watchers("deregister", service)

    async def discover_service(self, service_name: str) -> ServiceRegistration | None:
        """Discover a service by name."""
        return self.registry.get(service_name)

    async def discover_services_by_tag(self, tag: str) -> builtins.list[ServiceRegistration]:
        """Discover services by tag."""
        return [service for service in self.registry.values() if tag in service.tags]

    async def discover_services_by_interface(
        self, interface_name: str
    ) -> builtins.list[ServiceRegistration]:
        """Discover services by interface."""
        return [
            service
            for service in self.registry.values()
            if any(iface.name == interface_name for iface in service.interfaces)
        ]

    def add_watcher(self, callback: callable) -> None:
        """Add a service registry watcher."""
        self.watchers.append(callback)

    async def _notify_watchers(self, event: str, service: ServiceRegistration) -> None:
        """Notify watchers of registry changes."""
        for watcher in self.watchers:
            try:
                if asyncio.iscoroutinefunction(watcher):
                    await watcher(event, service)
                else:
                    watcher(event, service)
            except Exception as e:
                print(f"Watcher error: {e}")


class DependencyInjectionContainer:
    """Dependency injection container."""

    def __init__(self):
        """Initialize the DI container."""
        self.dependencies: builtins.dict[str, DependencySpec] = {}
        self.instances: builtins.dict[str, Any] = {}
        self.factories: builtins.dict[str, callable] = {}
        self.lifecycle_managers: builtins.dict[str, ServiceLifecycleManager] = {}

    def register_dependency(self, spec: DependencySpec, factory: callable | None = None) -> None:
        """Register a dependency."""
        self.dependencies[spec.name] = spec
        if factory:
            self.factories[spec.name] = factory

    def register_instance(self, name: str, instance: Any) -> None:
        """Register a singleton instance."""
        self.instances[name] = instance

    async def resolve(self, name: str) -> Any:
        """Resolve a dependency."""
        if name not in self.dependencies:
            raise ValueError(f"Dependency '{name}' not registered")

        spec = self.dependencies[name]

        # Return existing instance for singletons
        if spec.scope == DependencyScope.SINGLETON and name in self.instances:
            return self.instances[name]

        # Create new instance
        instance = await self._create_instance(spec)

        # Store singleton instances
        if spec.scope == DependencyScope.SINGLETON:
            self.instances[name] = instance

        return instance

    async def _create_instance(self, spec: DependencySpec) -> Any:
        """Create an instance of a dependency."""
        if spec.name in self.factories:
            factory = self.factories[spec.name]
            if asyncio.iscoroutinefunction(factory):
                return await factory()
            return factory()

        # Default factory for infrastructure components
        if spec.type == DependencyType.INFRASTRUCTURE:
            return await self._create_infrastructure_instance(spec)

        raise ValueError(f"No factory registered for dependency '{spec.name}'")

    async def _create_infrastructure_instance(self, spec: DependencySpec) -> Any:
        """Create infrastructure component instances."""
        if spec.name.startswith("framework-config"):

            return BaseServiceConfig(**spec.configuration)

        if spec.name.startswith("framework-cache"):

            return CacheManager(spec.configuration)

        if spec.name.startswith("framework-messaging"):

            return MessageQueue(spec.configuration)

        if spec.name.startswith("framework-events"):

            return EventStreamManager(spec.configuration)

        raise ValueError(f"Unknown infrastructure component: {spec.name}")


class ServiceLifecycleManager:
    """Manages service lifecycle."""

    def __init__(self, service_name: str, dependency_graph: DependencyGraph):
        """Initialize lifecycle manager."""
        self.service_name = service_name
        self.dependency_graph = dependency_graph
        self.state = ServiceLifecycle.INACTIVE
        self.health_checks: builtins.list[callable] = []
        self.startup_hooks: builtins.list[callable] = []
        self.shutdown_hooks: builtins.list[callable] = []

    async def start(self) -> None:
        """Start the service."""
        if self.state != ServiceLifecycle.INACTIVE:
            return

        self.state = ServiceLifecycle.STARTING

        try:
            # Start dependencies first
            dependencies = self.dependency_graph.get_dependencies(self.service_name)
            for dep in dependencies:
                if dep.type == DependencyType.SERVICE:
                    dep_manager = self.dependency_graph.services.get(dep.name)
                    if dep_manager and hasattr(dep_manager, "lifecycle_manager"):
                        await dep_manager.lifecycle_manager.start()

            # Run startup hooks
            for hook in self.startup_hooks:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()

            self.state = ServiceLifecycle.ACTIVE

        except Exception as e:
            self.state = ServiceLifecycle.FAILED
            raise RuntimeError(f"Failed to start service {self.service_name}: {e}")

    async def stop(self) -> None:
        """Stop the service."""
        if self.state not in [ServiceLifecycle.ACTIVE, ServiceLifecycle.FAILED]:
            return

        self.state = ServiceLifecycle.STOPPING

        try:
            # Run shutdown hooks
            for hook in reversed(self.shutdown_hooks):
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()

            self.state = ServiceLifecycle.INACTIVE

        except Exception as e:
            self.state = ServiceLifecycle.FAILED
            raise RuntimeError(f"Failed to stop service {self.service_name}: {e}")

    async def health_check(self) -> bool:
        """Perform health check."""
        if self.state != ServiceLifecycle.ACTIVE:
            return False

        try:
            for check in self.health_checks:
                if asyncio.iscoroutinefunction(check):
                    result = await check()
                else:
                    result = check()

                if not result:
                    return False

            return True

        except Exception:
            return False

    def add_startup_hook(self, hook: callable) -> None:
        """Add a startup hook."""
        self.startup_hooks.append(hook)

    def add_shutdown_hook(self, hook: callable) -> None:
        """Add a shutdown hook."""
        self.shutdown_hooks.append(hook)

    def add_health_check(self, check: callable) -> None:
        """Add a health check."""
        self.health_checks.append(check)


class SmartDependencyManager:
    """Main dependency management orchestrator."""

    def __init__(self, framework_root: Path):
        """Initialize the dependency manager."""
        self.framework_root = framework_root
        self.dependency_graph = DependencyGraph()
        self.service_discovery = ServiceDiscovery(framework_root)
        self.di_container = DependencyInjectionContainer()
        self.lifecycle_managers: builtins.dict[str, ServiceLifecycleManager] = {}

        # Configuration paths
        self.config_dir = framework_root / "config" / "dependencies"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        """Initialize the dependency manager."""
        await self._load_configuration()
        await self._setup_infrastructure_dependencies()
        await self._register_builtin_services()

    async def add_service(self, service_config: builtins.dict[str, Any]) -> None:
        """Add a service with automatic dependency resolution."""
        service_name = service_config["name"]

        # Create service registration
        service = ServiceRegistration(
            name=service_name,
            address=service_config.get("address", "localhost"),
            port=service_config.get("port", 8000),
            protocol=service_config.get("protocol", "http"),
            interfaces=[
                ServiceInterface(
                    name=iface["name"],
                    methods=iface.get("methods", []),
                    events=iface.get("events", []),
                    schema=iface.get("schema"),
                )
                for iface in service_config.get("interfaces", [])
            ],
            metadata=service_config.get("metadata", {}),
            health_check_endpoint=service_config.get("health_check"),
            tags=service_config.get("tags", []),
        )

        # Add to dependency graph
        self.dependency_graph.add_service(service)

        # Register with service discovery
        await self.service_discovery.register_service(service)

        # Process dependencies
        for dep_config in service_config.get("dependencies", []):
            dependency = DependencySpec(
                name=dep_config["name"],
                type=DependencyType(dep_config.get("type", "library")),
                version=dep_config.get("version", "latest"),
                scope=DependencyScope(dep_config.get("scope", "singleton")),
                required=dep_config.get("required", True),
                interface=dep_config.get("interface"),
                implementation=dep_config.get("implementation"),
                configuration=dep_config.get("configuration", {}),
                health_check=dep_config.get("health_check"),
                retry_policy=dep_config.get("retry_policy", {}),
                circuit_breaker=dep_config.get("circuit_breaker", {}),
            )

            self.dependency_graph.add_dependency(service_name, dependency)
            self.di_container.register_dependency(dependency)

        # Create lifecycle manager
        lifecycle_manager = ServiceLifecycleManager(service_name, self.dependency_graph)
        self.lifecycle_managers[service_name] = lifecycle_manager

    async def start_services(self, services: builtins.list[str] | None = None) -> None:
        """Start services in dependency order."""
        if services is None:
            services = list(self.dependency_graph.services.keys())

        # Resolve startup order
        startup_order = self.dependency_graph.resolve_startup_order()

        # Filter to requested services
        startup_order = [s for s in startup_order if s in services]

        # Start services
        for service_name in startup_order:
            if service_name in self.lifecycle_managers:
                await self.lifecycle_managers[service_name].start()

    async def stop_services(self, services: builtins.list[str] | None = None) -> None:
        """Stop services in reverse dependency order."""
        if services is None:
            services = list(self.dependency_graph.services.keys())

        # Resolve startup order and reverse it
        startup_order = self.dependency_graph.resolve_startup_order()
        shutdown_order = [s for s in reversed(startup_order) if s in services]

        # Stop services
        for service_name in shutdown_order:
            if service_name in self.lifecycle_managers:
                await self.lifecycle_managers[service_name].stop()

    async def health_check_all(self) -> builtins.dict[str, bool]:
        """Perform health checks on all services."""
        results = {}

        for service_name, manager in self.lifecycle_managers.items():
            results[service_name] = await manager.health_check()

        return results

    def generate_dependency_config(self, service_name: str, output_path: Path) -> None:
        """Generate dependency injection configuration for a service."""
        dependencies = self.dependency_graph.get_dependencies(service_name)

        config = {
            "service": service_name,
            "dependencies": [
                {
                    "name": dep.name,
                    "type": dep.type.value,
                    "version": dep.version,
                    "scope": dep.scope.value,
                    "required": dep.required,
                    "interface": dep.interface,
                    "implementation": dep.implementation,
                    "configuration": dep.configuration,
                    "health_check": dep.health_check,
                    "retry_policy": dep.retry_policy,
                    "circuit_breaker": dep.circuit_breaker,
                }
                for dep in dependencies
            ],
            "startup_order": self.dependency_graph.resolve_startup_order(),
            "metadata": {
                "generated_by": "Marty Framework Smart Dependency Manager",
                "framework_version": "4.0.0",
                "phase": "phase4",
            },
        }

        output_path.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")

    def analyze_dependencies(self, service_name: str) -> builtins.dict[str, Any]:
        """Analyze dependencies for a service."""
        dependencies = self.dependency_graph.get_dependencies(service_name)
        dependents = self.dependency_graph.get_dependents(service_name)
        cycles = self.dependency_graph.detect_cycles()

        analysis = {
            "service": service_name,
            "direct_dependencies": len(dependencies),
            "dependent_services": len(dependents),
            "dependency_types": {},
            "dependency_scopes": {},
            "critical_dependencies": [],
            "optional_dependencies": [],
            "circular_dependencies": [],
            "startup_position": 0,
        }

        # Analyze dependency types and scopes
        for dep in dependencies:
            dep_type = dep.type.value
            dep_scope = dep.scope.value

            analysis["dependency_types"][dep_type] = (
                analysis["dependency_types"].get(dep_type, 0) + 1
            )
            analysis["dependency_scopes"][dep_scope] = (
                analysis["dependency_scopes"].get(dep_scope, 0) + 1
            )

            if dep.required:
                analysis["critical_dependencies"].append(dep.name)
            else:
                analysis["optional_dependencies"].append(dep.name)

        # Check for circular dependencies
        for cycle in cycles:
            if service_name in cycle:
                analysis["circular_dependencies"].append(cycle)

        # Determine startup position
        startup_order = self.dependency_graph.resolve_startup_order()
        if service_name in startup_order:
            analysis["startup_position"] = startup_order.index(service_name) + 1

        return analysis

    async def _load_configuration(self) -> None:
        """Load dependency configuration files."""
        config_files = list(self.config_dir.glob("*.yaml")) + list(self.config_dir.glob("*.yml"))

        for config_file in config_files:
            try:
                with open(config_file, encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                if "services" in config:
                    for service_config in config["services"]:
                        await self.add_service(service_config)

            except Exception as e:
                print(f"Warning: Failed to load config {config_file}: {e}")

    async def _setup_infrastructure_dependencies(self) -> None:
        """Setup Phase 1-3 infrastructure dependencies."""
        # Phase 1 infrastructure
        phase1_deps = [
            DependencySpec(
                name="framework-config",
                type=DependencyType.INFRASTRUCTURE,
                version="1.0.0",
                scope=DependencyScope.SINGLETON,
                configuration={"env_prefix": "MARTY_"},
            ),
            DependencySpec(
                name="framework-observability",
                type=DependencyType.INFRASTRUCTURE,
                version="1.0.0",
                scope=DependencyScope.SINGLETON,
                configuration={"service_name": "framework"},
            ),
        ]

        # Phase 2 infrastructure
        phase2_deps = [
            DependencySpec(
                name="framework-cache",
                type=DependencyType.INFRASTRUCTURE,
                version="2.0.0",
                scope=DependencyScope.SINGLETON,
                configuration={"backend": "redis", "host": "localhost", "port": 6379},
            ),
            DependencySpec(
                name="framework-messaging",
                type=DependencyType.INFRASTRUCTURE,
                version="2.0.0",
                scope=DependencyScope.SINGLETON,
                configuration={
                    "backend": "rabbitmq",
                    "host": "localhost",
                    "port": 5672,
                },
            ),
        ]

        for dep in phase1_deps + phase2_deps:
            self.di_container.register_dependency(dep)

    async def _register_builtin_services(self) -> None:
        """Register built-in framework services."""
        # Service discovery service
        discovery_service = ServiceRegistration(
            name="service-discovery",
            address="localhost",
            port=8500,
            protocol="http",
            interfaces=[
                ServiceInterface(
                    name="ServiceDiscovery",
                    methods=["register", "deregister", "discover", "health_check"],
                )
            ],
            tags=["infrastructure", "discovery"],
        )

        await self.service_discovery.register_service(discovery_service)


def create_dependency_config_template(service_name: str, output_path: Path) -> None:
    """Create a template dependency configuration file."""
    template = {
        "services": [
            {
                "name": service_name,
                "address": "localhost",
                "port": 8000,
                "protocol": "http",
                "interfaces": [
                    {
                        "name": f"{service_name.title()}Service",
                        "methods": ["health_check"],
                        "events": [],
                    }
                ],
                "dependencies": [
                    {
                        "name": "framework-config",
                        "type": "infrastructure",
                        "version": "1.0.0",
                        "scope": "singleton",
                        "required": True,
                        "configuration": {"env_prefix": f"{service_name.upper()}_"},
                    },
                    {
                        "name": "framework-observability",
                        "type": "infrastructure",
                        "version": "1.0.0",
                        "scope": "singleton",
                        "required": True,
                        "configuration": {"service_name": service_name},
                    },
                ],
                "metadata": {"phase": "phase4", "generated": True},
                "tags": ["microservice", "generated"],
            }
        ]
    }

    output_path.write_text(yaml.dump(template, default_flow_style=False), encoding="utf-8")
