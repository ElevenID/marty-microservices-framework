"""
Health checking implementation for service discovery

This module provides health checking functionality for service endpoints
including periodic health checks and status management.
"""

import asyncio
import builtins
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from ..service_mesh import ServiceDiscoveryConfig


class HealthChecker:
    """Health checker for service endpoints."""

    def __init__(self, config: ServiceDiscoveryConfig):
        """Initialize health checker."""
        self.config = config
        self.health_check_tasks: builtins.dict[str, asyncio.Task] = {}
        self._session: aiohttp.ClientSession | None = None

    def start_health_checking(self, service_name: str, registry):
        """Start health checking for a service."""
        if service_name not in self.health_check_tasks:
            task = asyncio.create_task(self._health_check_loop(service_name, registry))
            self.health_check_tasks[service_name] = task

    def stop_health_checking(self, service_name: str):
        """Stop health checking for a service."""
        if service_name in self.health_check_tasks:
            self.health_check_tasks[service_name].cancel()
            del self.health_check_tasks[service_name]

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _health_check_loop(self, service_name: str, registry):
        """Health check loop for a service."""
        while True:
            try:
                await self._perform_health_checks(service_name, registry)
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception("Health check error for %s: %s", service_name, e)
                await asyncio.sleep(self.config.health_check_interval)

    async def _perform_health_checks(self, service_name: str, registry):
        """Perform health checks for service endpoints."""
        endpoints = registry.services.get(service_name, [])
        session = await self._get_session()

        for endpoint in endpoints:
            endpoint_key = f"{endpoint.host}:{endpoint.port}"

            try:
                # Perform health check
                health_url = f"{endpoint.protocol}://{endpoint.host}:{endpoint.port}{endpoint.health_check_path}"

                async with session.get(health_url) as response:
                    is_healthy = response.status == 200

                # Update health status
                with registry._lock:
                    health_info = registry.health_status[service_name][endpoint_key]
                    health_info["last_check"] = datetime.now(timezone.utc)

                    if is_healthy:
                        health_info["consecutive_successes"] += 1
                        health_info["consecutive_failures"] = 0

                        # Mark as healthy if we have enough successes
                        if health_info["consecutive_successes"] >= self.config.healthy_threshold:
                            was_unhealthy = not health_info.get("healthy", False)
                            health_info["healthy"] = True

                            if was_unhealthy:
                                # Notify watchers of health recovery
                                registry._notify_watchers(
                                    "service_healthy",
                                    {
                                        "service_name": service_name,
                                        "endpoint": endpoint,
                                        "health_info": health_info.copy(),
                                    },
                                )
                                logging.info(
                                    "Service %s at %s:%s is now healthy",
                                    service_name,
                                    endpoint.host,
                                    endpoint.port,
                                )
                    else:
                        health_info["consecutive_failures"] += 1
                        health_info["consecutive_successes"] = 0

                        # Mark as unhealthy if we have enough failures
                        if health_info["consecutive_failures"] >= self.config.unhealthy_threshold:
                            was_healthy = health_info.get("healthy", True)
                            health_info["healthy"] = False

                            if was_healthy:
                                # Notify watchers of health failure
                                registry._notify_watchers(
                                    "service_unhealthy",
                                    {
                                        "service_name": service_name,
                                        "endpoint": endpoint,
                                        "health_info": health_info.copy(),
                                    },
                                )
                                logging.warning(
                                    "Service %s at %s:%s is now unhealthy",
                                    service_name,
                                    endpoint.host,
                                    endpoint.port,
                                )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                # Handle health check failure
                with registry._lock:
                    health_info = registry.health_status[service_name][endpoint_key]
                    health_info["last_check"] = datetime.now(timezone.utc)
                    health_info["consecutive_failures"] += 1
                    health_info["consecutive_successes"] = 0

                    # Mark as unhealthy if we have enough failures
                    if health_info["consecutive_failures"] >= self.config.unhealthy_threshold:
                        was_healthy = health_info.get("healthy", True)
                        health_info["healthy"] = False

                        if was_healthy:
                            registry._notify_watchers(
                                "service_unhealthy",
                                {
                                    "service_name": service_name,
                                    "endpoint": endpoint,
                                    "health_info": health_info.copy(),
                                    "error": str(e),
                                },
                            )
                            logging.warning(
                                "Service %s at %s:%s health check failed: %s",
                                service_name,
                                endpoint.host,
                                endpoint.port,
                                e,
                            )

    def get_health_status(
        self, registry, service_name: str | None = None
    ) -> builtins.dict[str, Any]:
        """Get health status for services."""
        with registry._lock:
            if service_name:
                return registry.health_status.get(service_name, {})
            return {name: status.copy() for name, status in registry.health_status.items()}

    def cleanup(self):
        """Clean up all health check tasks."""
        for task in self.health_check_tasks.values():
            task.cancel()
        self.health_check_tasks.clear()

    async def close(self):
        """Close the health checker and cleanup resources."""
        self.cleanup()
        if self._session and not self._session.closed:
            await self._session.close()
