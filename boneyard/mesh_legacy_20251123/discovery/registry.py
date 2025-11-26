"""
Service registry core implementation for Marty Microservices Framework

This module provides the core service registry functionality including
service registration, deregistration, and discovery.
"""

import builtins
import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from ..service_mesh import ServiceDiscoveryConfig, ServiceEndpoint


class ServiceRegistry:
    """Service registry for service discovery and management."""

    def __init__(self, config: ServiceDiscoveryConfig):
        """Initialize service registry."""
        self.config = config

        # Service storage
        self.services: builtins.dict[str, builtins.list[ServiceEndpoint]] = defaultdict(list)
        self.service_metadata: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Health tracking
        self.health_status: builtins.dict[str, builtins.dict[str, Any]] = defaultdict(dict)

        # Service watchers and callbacks
        self.service_watchers: builtins.list[Callable] = []

        # Thread safety
        self._lock = threading.RLock()

    def register_service(self, service: ServiceEndpoint) -> bool:
        """Register a service endpoint."""
        try:
            with self._lock:
                # Add to service list
                self.services[service.service_name].append(service)

                # Initialize health status
                endpoint_key = f"{service.host}:{service.port}"
                self.health_status[service.service_name][endpoint_key] = {
                    "healthy": True,
                    "last_check": None,
                    "consecutive_failures": 0,
                    "consecutive_successes": 1,
                }

                # Notify watchers
                self._notify_watchers(
                    "service_registered",
                    {
                        "service_name": service.service_name,
                        "host": service.host,
                        "port": service.port,
                        "endpoint": service,
                    },
                )

                logging.info(
                    "Registered service: %s at %s:%s",
                    service.service_name,
                    service.host,
                    service.port,
                )
                return True

        except Exception as e:
            logging.exception("Failed to register service %s: %s", service.service_name, e)
            return False

    def deregister_service(self, service_name: str, host: str, port: int) -> bool:
        """Deregister a service endpoint."""
        try:
            with self._lock:
                if service_name in self.services:
                    # Remove the specific endpoint
                    self.services[service_name] = [
                        s
                        for s in self.services[service_name]
                        if not (s.host == host and s.port == port)
                    ]

                    # Remove health status
                    endpoint_key = f"{host}:{port}"
                    if endpoint_key in self.health_status[service_name]:
                        del self.health_status[service_name][endpoint_key]

                    # Clean up empty service entries
                    if not self.services[service_name]:
                        del self.services[service_name]
                        if service_name in self.health_status:
                            del self.health_status[service_name]

                    # Notify watchers
                    self._notify_watchers(
                        "service_deregistered",
                        {"service_name": service_name, "host": host, "port": port},
                    )

                    logging.info("Deregistered service: %s at %s:%s", service_name, host, port)
                    return True

        except Exception as e:
            logging.exception("Failed to deregister service %s: %s", service_name, e)
            return False

        return False

    def discover_services(
        self, service_name: str, healthy_only: bool = True
    ) -> builtins.list[ServiceEndpoint]:
        """Discover available service endpoints."""
        with self._lock:
            if service_name not in self.services:
                return []

            endpoints = self.services[service_name].copy()

            if healthy_only:
                # Filter only healthy endpoints
                healthy_endpoints = []
                for endpoint in endpoints:
                    endpoint_key = f"{endpoint.host}:{endpoint.port}"
                    health_info = self.health_status[service_name].get(endpoint_key, {})
                    if health_info.get("healthy", False):
                        healthy_endpoints.append(endpoint)
                endpoints = healthy_endpoints

            return endpoints

    def get_service_metadata(self, service_name: str) -> builtins.dict[str, Any]:
        """Get service metadata."""
        return self.service_metadata.get(service_name, {})

    def set_service_metadata(self, service_name: str, metadata: builtins.dict[str, Any]):
        """Set service metadata."""
        self.service_metadata[service_name] = metadata

    def add_service_watcher(self, callback: Callable):
        """Add service change watcher."""
        self.service_watchers.append(callback)

    def remove_service_watcher(self, callback: Callable):
        """Remove service change watcher."""
        if callback in self.service_watchers:
            self.service_watchers.remove(callback)

    def _notify_watchers(self, event_type: str, event_data: builtins.dict[str, Any]):
        """Notify all watchers of service changes."""
        for watcher in self.service_watchers:
            try:
                watcher(event_type, event_data)
            except Exception as e:
                logging.exception("Error notifying watcher: %s", e)

    def get_all_services(self) -> builtins.dict[str, builtins.list[ServiceEndpoint]]:
        """Get all registered services."""
        with self._lock:
            return {name: endpoints.copy() for name, endpoints in self.services.items()}

    def get_service_count(self, service_name: str | None = None) -> int:
        """Get count of services or endpoints for a specific service."""
        with self._lock:
            if service_name:
                return len(self.services.get(service_name, []))
            return sum(len(endpoints) for endpoints in self.services.values())
