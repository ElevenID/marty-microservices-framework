"""
Service health checking implementation for Marty Microservices Framework

This module provides comprehensive health checking functionality for service instances
including HTTP, TCP, gRPC, and custom health check strategies.
"""

import asyncio
import builtins
import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from .models import HealthStatus, ServiceInstance


class ServiceHealthChecker:
    """Advanced health checking for services."""

    def __init__(self, check_interval: int = 30, timeout: int = 5):
        """Initialize health checker."""
        self.check_interval = check_interval
        self.timeout = timeout

        # Health check tasks
        self.health_tasks: builtins.dict[str, asyncio.Task] = {}
        self.health_results: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Health check strategies
        self.check_strategies: builtins.dict[str, Callable] = {
            "http": self._http_health_check,
            "https": self._http_health_check,
            "tcp": self._tcp_health_check,
            "grpc": self._grpc_health_check,
            "custom": self._custom_health_check,
        }

        # Health check history
        self.health_history: builtins.dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

    async def start_health_monitoring(self, service: ServiceInstance):
        """Start health monitoring for a service."""
        if service.instance_id in self.health_tasks:
            return  # Already monitoring

        task = asyncio.create_task(self._health_check_loop(service))
        self.health_tasks[service.instance_id] = task

        logging.info(f"Started health monitoring for {service.service_name}:{service.instance_id}")

    async def stop_health_monitoring(self, instance_id: str):
        """Stop health monitoring for a service."""
        if instance_id in self.health_tasks:
            task = self.health_tasks[instance_id]
            task.cancel()
            del self.health_tasks[instance_id]

            logging.info(f"Stopped health monitoring for instance {instance_id}")

    async def _health_check_loop(self, service: ServiceInstance):
        """Health check loop for a service."""
        while True:
            try:
                await self._perform_health_check(service)
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception(f"Health check error for {service.instance_id}: {e}")
                await asyncio.sleep(self.check_interval)

    async def _perform_health_check(self, service: ServiceInstance):
        """Perform health check for a service."""
        protocol = service.protocol.value
        strategy = self.check_strategies.get(protocol, self._http_health_check)

        start_time = time.time()
        try:
            health_result = await strategy(service)
            response_time = time.time() - start_time

            # Update service health status
            service.health_status = (
                HealthStatus.HEALTHY if health_result["healthy"] else HealthStatus.UNHEALTHY
            )
            service.last_health_check = datetime.now(timezone.utc)
            service.last_seen = datetime.now(timezone.utc)

            # Store health result
            health_data = {
                "timestamp": datetime.now(timezone.utc),
                "healthy": health_result["healthy"],
                "response_time": response_time,
                "details": health_result.get("details", {}),
                "error": health_result.get("error"),
            }

            self.health_results[service.instance_id] = health_data
            self.health_history[service.instance_id].append(health_data)

        except Exception as e:
            response_time = time.time() - start_time
            service.health_status = HealthStatus.UNHEALTHY
            service.last_health_check = datetime.now(timezone.utc)

            error_data = {
                "timestamp": datetime.now(timezone.utc),
                "healthy": False,
                "response_time": response_time,
                "error": str(e),
            }

            self.health_results[service.instance_id] = error_data
            self.health_history[service.instance_id].append(error_data)

    async def _http_health_check(self, service: ServiceInstance) -> builtins.dict[str, Any]:
        """HTTP/HTTPS health check."""
        scheme = "https" if service.ssl_enabled else "http"
        health_url = f"{scheme}://{service.host}:{service.port}{service.health_check_url}"

        timeout = aiohttp.ClientTimeout(total=self.timeout)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(health_url) as response:
                body = await response.text()

                healthy = 200 <= response.status < 300

                return {
                    "healthy": healthy,
                    "details": {
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": body[:1000],  # Limit body size
                    },
                }

    async def _tcp_health_check(self, service: ServiceInstance) -> builtins.dict[str, Any]:
        """TCP health check."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(service.host, service.port),
                timeout=self.timeout,
            )

            writer.close()
            await writer.wait_closed()

            return {"healthy": True, "details": {"connection": "successful"}}

        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _grpc_health_check(self, service: ServiceInstance) -> builtins.dict[str, Any]:
        """gRPC health check."""
        # Simplified gRPC health check
        # In practice, this would use the gRPC health checking protocol
        try:
            # For now, fall back to TCP check
            return await self._tcp_health_check(service)
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _custom_health_check(self, service: ServiceInstance) -> builtins.dict[str, Any]:
        """Custom health check based on service configuration."""
        # Custom health check logic based on service metadata
        custom_check = service.metadata.get("health_check")

        if not custom_check:
            return await self._tcp_health_check(service)

        # Implement custom check based on configuration
        return {"healthy": True, "details": {"custom_check": "not_implemented"}}

    def get_health_status(self, instance_id: str) -> builtins.dict[str, Any] | None:
        """Get current health status for an instance."""
        return self.health_results.get(instance_id)

    def get_health_history(
        self, instance_id: str, limit: int = 50
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Get health check history for an instance."""
        history = self.health_history.get(instance_id, deque())
        return list(history)[-limit:]

    def calculate_availability(self, instance_id: str, window_minutes: int = 60) -> float:
        """Calculate service availability over a time window."""
        history = self.health_history.get(instance_id, deque())

        if not history:
            return 0.0

        # Filter to time window
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        recent_checks = [check for check in history if check["timestamp"] >= cutoff_time]

        if not recent_checks:
            return 0.0

        healthy_checks = sum(1 for check in recent_checks if check["healthy"])
        return healthy_checks / len(recent_checks)

    def cleanup(self):
        """Clean up all health check tasks."""
        for task in self.health_tasks.values():
            task.cancel()
        self.health_tasks.clear()
