"""
Service Discovery Implementation for Marty Microservices Framework

This module provides a comprehensive service discovery system combining
service registration, health checking, and service endpoint management.
"""

from ..service_mesh import ServiceDiscoveryConfig, ServiceEndpoint
from .health_checker import HealthChecker
from .registry import ServiceRegistry


class ServiceDiscovery:
    """Complete service discovery system with registry and health checking."""

    def __init__(self, config: ServiceDiscoveryConfig):
        """Initialize service discovery system."""
        self.config = config
        self.registry = ServiceRegistry(config)
        self.health_checker = HealthChecker(config)

    def register_service(self, service: ServiceEndpoint) -> bool:
        """Register a service and start health checking."""
        success = self.registry.register_service(service)
        if success:
            # Start health checking for this service
            self.health_checker.start_health_checking(service.service_name, self.registry)
        return success

    def deregister_service(self, service_name: str, host: str, port: int) -> bool:
        """Deregister a service endpoint."""
        success = self.registry.deregister_service(service_name, host, port)

        # Stop health checking if no more endpoints for this service
        if not self.registry.services.get(service_name):
            self.health_checker.stop_health_checking(service_name)

        return success

    def discover_services(self, service_name: str, healthy_only: bool = True):
        """Discover available service endpoints."""
        return self.registry.discover_services(service_name, healthy_only)

    def get_service_metadata(self, service_name: str):
        """Get service metadata."""
        return self.registry.get_service_metadata(service_name)

    def set_service_metadata(self, service_name: str, metadata):
        """Set service metadata."""
        self.registry.set_service_metadata(service_name, metadata)

    def add_service_watcher(self, callback):
        """Add service change watcher."""
        self.registry.add_service_watcher(callback)

    def remove_service_watcher(self, callback):
        """Remove service change watcher."""
        self.registry.remove_service_watcher(callback)

    def get_health_status(self, service_name: str | None = None):
        """Get health status for services."""
        return self.health_checker.get_health_status(self.registry, service_name)

    def get_all_services(self):
        """Get all registered services."""
        return self.registry.get_all_services()

    def get_service_count(self, service_name: str | None = None) -> int:
        """Get count of services or endpoints for a specific service."""
        return self.registry.get_service_count(service_name)

    def cleanup(self):
        """Clean up resources."""
        self.health_checker.cleanup()


# Re-export for backward compatibility
__all__ = [
    "ServiceDiscovery",
    "ServiceRegistry",
    "HealthChecker",
    "ServiceEndpoint",
    "ServiceDiscoveryConfig",
]
