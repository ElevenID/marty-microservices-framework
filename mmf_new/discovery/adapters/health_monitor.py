"""
Service Health Monitoring Adapter.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from mmf_new.discovery.domain.models import HealthStatus, ServiceInstance, ServiceInstanceType

logger = logging.getLogger(__name__)


class ServiceHealthMonitor:
    """Advanced health checking for services."""

    def __init__(self, check_interval: int = 30, timeout: int = 5):
        """Initialize health monitor."""
        self.check_interval = check_interval
        self.timeout = timeout

        # Health check tasks
        self.health_tasks: dict[str, asyncio.Task] = {}
        self.health_results: dict[str, dict[str, Any]] = {}

        # Health check strategies
        self.check_strategies: dict[ServiceInstanceType, Callable] = {
            ServiceInstanceType.HTTP: self._http_health_check,
            ServiceInstanceType.HTTPS: self._http_health_check,
            ServiceInstanceType.TCP: self._tcp_health_check,
            ServiceInstanceType.GRPC: self._grpc_health_check,
        }

        # Health check history
        self.health_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

    async def start_health_monitoring(self, service: ServiceInstance):
        """Start health monitoring for a service."""
        if service.instance_id in self.health_tasks:
            return  # Already monitoring

        task = asyncio.create_task(self._health_check_loop(service))
        self.health_tasks[service.instance_id] = task

        logger.info(f"Started health monitoring for {service.service_name}:{service.instance_id}")

    async def stop_health_monitoring(self, instance_id: str):
        """Stop health monitoring for a service."""
        if instance_id in self.health_tasks:
            task = self.health_tasks[instance_id]
            task.cancel()
            del self.health_tasks[instance_id]

            logger.info(f"Stopped health monitoring for instance {instance_id}")

    async def _health_check_loop(self, service: ServiceInstance):
        """Health check loop for a service."""
        while True:
            try:
                await self._perform_health_check(service)
                # Use configured interval if available, else default
                interval = service.health_check.interval if service.health_check else self.check_interval
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Health check error for {service.instance_id}: {e}")
                await asyncio.sleep(self.check_interval)

    async def _perform_health_check(self, service: ServiceInstance):
        """Perform health check for a service."""
        protocol = service.endpoint.protocol
        strategy = self.check_strategies.get(protocol, self._http_health_check)

        start_time = time.time()
        try:
            health_result = await strategy(service)
            response_time = time.time() - start_time

            # Update service health status
            new_status = (
                HealthStatus.HEALTHY if health_result["healthy"] else HealthStatus.UNHEALTHY
            )
            service.update_health_status(new_status)

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
            service.update_health_status(HealthStatus.UNHEALTHY)

            error_data = {
                "timestamp": datetime.now(timezone.utc),
                "healthy": False,
                "response_time": response_time,
                "error": str(e),
            }

            self.health_results[service.instance_id] = error_data
            self.health_history[service.instance_id].append(error_data)

    async def _http_health_check(self, service: ServiceInstance) -> dict[str, Any]:
        """HTTP/HTTPS health check."""
        # Determine URL
        if service.health_check and service.health_check.url:
            health_url = service.health_check.url
        else:
            # Construct from endpoint
            scheme = "https" if service.endpoint.ssl_enabled or service.endpoint.protocol == ServiceInstanceType.HTTPS else "http"
            path = "/health" # Default
            if service.endpoint.path:
                path = service.endpoint.path

            health_url = f"{scheme}://{service.endpoint.host}:{service.endpoint.port}{path}"

        timeout = aiohttp.ClientTimeout(total=self.timeout)

        # Get method and headers from config
        method = service.health_check.method if service.health_check else "GET"
        headers = service.health_check.headers if service.health_check else {}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(method, health_url, headers=headers) as response:
                body = await response.text()

                expected_status = service.health_check.expected_status if service.health_check else 200
                healthy = response.status == expected_status or (200 <= response.status < 300)

                return {
                    "healthy": healthy,
                    "details": {
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": body[:1000],  # Limit body size
                    },
                }

    async def _tcp_health_check(self, service: ServiceInstance) -> dict[str, Any]:
        """TCP health check."""
        host = service.endpoint.host
        port = service.health_check.tcp_port if service.health_check and service.health_check.tcp_port else service.endpoint.port
        
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.timeout,
            )

            writer.close()
            await writer.wait_closed()

            return {"healthy": True, "details": {"connection": "successful"}}

        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _grpc_health_check(self, service: ServiceInstance) -> dict[str, Any]:
        """gRPC health check."""
        # Simplified gRPC health check - fallback to TCP for now
        # In a real implementation, we would use grpc-health-checking
        return await self._tcp_health_check(service)

    def get_health_status(self, instance_id: str) -> dict[str, Any] | None:
        """Get current health status for an instance."""
        return self.health_results.get(instance_id)

    def get_health_history(
        self, instance_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
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
