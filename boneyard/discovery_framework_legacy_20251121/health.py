"""
Health Monitoring for Service Discovery

Advanced health monitoring with HTTP, TCP, custom checks, and health aggregation
for service discovery and load balancing systems.
"""

import asyncio
import builtins
import logging
import socket
import ssl
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiohttp

from .core import ServiceInstance

logger = logging.getLogger(__name__)


class HealthCheckType(Enum):
    """Health check types."""

    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    UDP = "udp"
    GRPC = "grpc"
    CUSTOM = "custom"
    COMPOSITE = "composite"


class HealthCheckStatus(Enum):
    """Health check status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    WARNING = "warning"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"


@dataclass
class HealthCheckConfig:
    """Configuration for health checks."""

    # Basic configuration
    check_type: HealthCheckType = HealthCheckType.HTTP
    interval: float = 30.0
    timeout: float = 5.0
    retries: int = 3
    retry_delay: float = 1.0

    # HTTP/HTTPS specific
    http_method: str = "GET"
    http_path: str = "/health"
    http_headers: builtins.dict[str, str] = field(default_factory=dict)
    expected_status_codes: builtins.list[int] = field(default_factory=lambda: [200])
    expected_response_body: str | None = None
    follow_redirects: bool = False
    verify_ssl: bool = True

    # TCP/UDP specific
    tcp_port: int | None = None
    udp_port: int | None = None
    send_data: bytes | None = None
    expected_response: bytes | None = None

    # Custom check specific
    custom_check_function: Callable | None = None
    custom_check_args: builtins.dict[str, Any] = field(default_factory=dict)

    # Thresholds
    healthy_threshold: int = 2  # Consecutive successes to mark healthy
    unhealthy_threshold: int = 3  # Consecutive failures to mark unhealthy
    warning_threshold: float = 2.0  # Response time threshold for warning

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0

    # Grace periods
    startup_grace_period: float = 60.0  # Grace period after service start
    shutdown_grace_period: float = 30.0  # Grace period during shutdown


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    status: HealthCheckStatus
    response_time: float
    timestamp: float
    message: str = ""
    details: builtins.dict[str, Any] = field(default_factory=dict)

    # HTTP specific
    http_status_code: int | None = None
    http_response_body: str | None = None

    # Network specific
    network_error: str | None = None

    def is_healthy(self) -> bool:
        """Check if result indicates healthy status."""
        return self.status == HealthCheckStatus.HEALTHY

    def is_warning(self) -> bool:
        """Check if result indicates warning status."""
        return self.status == HealthCheckStatus.WARNING


class HealthChecker(ABC):
    """Abstract health checker interface."""

    def __init__(self, config: HealthCheckConfig):
        self.config = config
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure = 0.0
        self._circuit_breaker_open = False

    @abstractmethod
    async def check_health(self, instance: ServiceInstance) -> HealthCheckResult:
        """Perform health check on service instance."""

    async def check_with_circuit_breaker(self, instance: ServiceInstance) -> HealthCheckResult:
        """Check health with circuit breaker protection."""

        # Check circuit breaker state
        if self._circuit_breaker_open:
            # Check if recovery timeout has passed
            if (
                time.time() - self._circuit_breaker_last_failure
                > self.config.circuit_breaker_recovery_timeout
            ):
                self._circuit_breaker_open = False
                self._circuit_breaker_failures = 0
                logger.info("Circuit breaker closed for health checker")
            else:
                return HealthCheckResult(
                    status=HealthCheckStatus.UNHEALTHY,
                    response_time=0.0,
                    timestamp=time.time(),
                    message="Circuit breaker open",
                )

        try:
            result = await self.check_health(instance)

            # Reset circuit breaker on success
            if result.is_healthy():
                self._circuit_breaker_failures = 0
            else:
                self._circuit_breaker_failures += 1
                self._circuit_breaker_last_failure = time.time()

                # Open circuit breaker if threshold reached
                if (
                    self.config.circuit_breaker_enabled
                    and self._circuit_breaker_failures
                    >= self.config.circuit_breaker_failure_threshold
                ):
                    self._circuit_breaker_open = True
                    logger.warning("Circuit breaker opened for health checker")

            return result

        except Exception as e:
            self._circuit_breaker_failures += 1
            self._circuit_breaker_last_failure = time.time()

            if (
                self.config.circuit_breaker_enabled
                and self._circuit_breaker_failures >= self.config.circuit_breaker_failure_threshold
            ):
                self._circuit_breaker_open = True
                logger.warning("Circuit breaker opened for health checker")

            return HealthCheckResult(
                status=HealthCheckStatus.UNHEALTHY,
                response_time=0.0,
                timestamp=time.time(),
                message=f"Health check failed: {e}",
                network_error=str(e),
            )


class HTTPHealthChecker(HealthChecker):
    """HTTP/HTTPS health checker."""

    def __init__(self, config: HealthCheckConfig):
        super().__init__(config)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self._session:
            connector = aiohttp.TCPConnector(
                ssl=ssl.create_default_context() if self.config.verify_ssl else False
            )

            timeout = aiohttp.ClientTimeout(total=self.config.timeout)

            self._session = aiohttp.ClientSession(
                connector=connector, timeout=timeout, headers=self.config.http_headers
            )

        return self._session

    async def check_health(self, instance: ServiceInstance) -> HealthCheckResult:
        """Perform HTTP health check."""
        start_time = time.time()

        # Construct URL
        scheme = "https" if self.config.check_type == HealthCheckType.HTTPS else "http"
        port = instance.port

        # Use specific port if configured
        if self.config.check_type == HealthCheckType.HTTPS and not port:
            port = 443
        elif self.config.check_type == HealthCheckType.HTTP and not port:
            port = 80

        url = f"{scheme}://{instance.host}:{port}{self.config.http_path}"

        session = await self._get_session()

        try:
            async with session.request(
                method=self.config.http_method,
                url=url,
                allow_redirects=self.config.follow_redirects,
            ) as response:
                response_time = time.time() - start_time
                response_body = await response.text()

                # Check status code
                if response.status not in self.config.expected_status_codes:
                    return HealthCheckResult(
                        status=HealthCheckStatus.UNHEALTHY,
                        response_time=response_time,
                        timestamp=time.time(),
                        message=f"Unexpected status code: {response.status}",
                        http_status_code=response.status,
                        http_response_body=response_body,
                    )

                # Check response body if specified
                if (
                    self.config.expected_response_body
                    and self.config.expected_response_body not in response_body
                ):
                    return HealthCheckResult(
                        status=HealthCheckStatus.UNHEALTHY,
                        response_time=response_time,
                        timestamp=time.time(),
                        message="Response body does not contain expected content",
                        http_status_code=response.status,
                        http_response_body=response_body,
                    )

                # Check response time for warning
                status = HealthCheckStatus.HEALTHY
                if response_time > self.config.warning_threshold:
                    status = HealthCheckStatus.WARNING

                return HealthCheckResult(
                    status=status,
                    response_time=response_time,
                    timestamp=time.time(),
                    message="Health check successful",
                    http_status_code=response.status,
                    http_response_body=response_body[:1000],  # Limit body size
                )

        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            return HealthCheckResult(
                status=HealthCheckStatus.TIMEOUT,
                response_time=response_time,
                timestamp=time.time(),
                message=f"Request timeout after {self.config.timeout}s",
            )

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                status=HealthCheckStatus.UNHEALTHY,
                response_time=response_time,
                timestamp=time.time(),
                message=f"HTTP health check failed: {e}",
                network_error=str(e),
            )

    async def close(self):
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None


class TCPHealthChecker(HealthChecker):
    """TCP health checker."""

    async def check_health(self, instance: ServiceInstance) -> HealthCheckResult:
        """Perform TCP health check."""
        start_time = time.time()

        port = self.config.tcp_port or instance.port

        try:
            # Create socket connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config.timeout)

            try:
                # Connect to service
                sock.connect((instance.host, port))

                # Send data if configured
                if self.config.send_data:
                    sock.sendall(self.config.send_data)

                    # Check response if expected
                    if self.config.expected_response:
                        response = sock.recv(len(self.config.expected_response))
                        if response != self.config.expected_response:
                            response_time = time.time() - start_time
                            return HealthCheckResult(
                                status=HealthCheckStatus.UNHEALTHY,
                                response_time=response_time,
                                timestamp=time.time(),
                                message="Unexpected TCP response",
                            )

                response_time = time.time() - start_time

                # Check response time for warning
                status = HealthCheckStatus.HEALTHY
                if response_time > self.config.warning_threshold:
                    status = HealthCheckStatus.WARNING

                return HealthCheckResult(
                    status=status,
                    response_time=response_time,
                    timestamp=time.time(),
                    message="TCP connection successful",
                )

            finally:
                sock.close()

        except TimeoutError:
            response_time = time.time() - start_time
            return HealthCheckResult(
                status=HealthCheckStatus.TIMEOUT,
                response_time=response_time,
                timestamp=time.time(),
                message=f"TCP connection timeout after {self.config.timeout}s",
            )

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                status=HealthCheckStatus.UNHEALTHY,
                response_time=response_time,
                timestamp=time.time(),
                message=f"TCP health check failed: {e}",
                network_error=str(e),
            )


class UDPHealthChecker(HealthChecker):
    """UDP health checker."""

    async def check_health(self, instance: ServiceInstance) -> HealthCheckResult:
        """Perform UDP health check."""
        start_time = time.time()

        port = self.config.udp_port or instance.port

        try:
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.config.timeout)

            try:
                # Send data if configured
                if self.config.send_data:
                    sock.sendto(self.config.send_data, (instance.host, port))

                    # Check response if expected
                    if self.config.expected_response:
                        response, addr = sock.recvfrom(len(self.config.expected_response))
                        if response != self.config.expected_response:
                            response_time = time.time() - start_time
                            return HealthCheckResult(
                                status=HealthCheckStatus.UNHEALTHY,
                                response_time=response_time,
                                timestamp=time.time(),
                                message="Unexpected UDP response",
                            )
                else:
                    # Just try to connect
                    sock.connect((instance.host, port))

                response_time = time.time() - start_time

                # Check response time for warning
                status = HealthCheckStatus.HEALTHY
                if response_time > self.config.warning_threshold:
                    status = HealthCheckStatus.WARNING

                return HealthCheckResult(
                    status=status,
                    response_time=response_time,
                    timestamp=time.time(),
                    message="UDP check successful",
                )

            finally:
                sock.close()

        except TimeoutError:
            response_time = time.time() - start_time
            return HealthCheckResult(
                status=HealthCheckStatus.TIMEOUT,
                response_time=response_time,
                timestamp=time.time(),
                message=f"UDP check timeout after {self.config.timeout}s",
            )

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                status=HealthCheckStatus.UNHEALTHY,
                response_time=response_time,
                timestamp=time.time(),
                message=f"UDP health check failed: {e}",
                network_error=str(e),
            )


class CustomHealthChecker(HealthChecker):
    """Custom health checker using user-defined function."""

    async def check_health(self, instance: ServiceInstance) -> HealthCheckResult:
        """Perform custom health check."""
        if not self.config.custom_check_function:
            return HealthCheckResult(
                status=HealthCheckStatus.UNHEALTHY,
                response_time=0.0,
                timestamp=time.time(),
                message="No custom check function configured",
            )

        start_time = time.time()

        try:
            # Call custom check function
            if asyncio.iscoroutinefunction(self.config.custom_check_function):
                result = await self.config.custom_check_function(
                    instance, **self.config.custom_check_args
                )
            else:
                result = self.config.custom_check_function(
                    instance, **self.config.custom_check_args
                )

            response_time = time.time() - start_time

            # Handle different result types
            if isinstance(result, bool):
                status = HealthCheckStatus.HEALTHY if result else HealthCheckStatus.UNHEALTHY
                message = "Custom check successful" if result else "Custom check failed"
            elif isinstance(result, HealthCheckResult):
                return result
            elif isinstance(result, dict):
                status = result.get("status", HealthCheckStatus.HEALTHY)
                message = result.get("message", "Custom check completed")
                if isinstance(status, str):
                    status = HealthCheckStatus(status)
            else:
                status = HealthCheckStatus.UNKNOWN
                message = f"Unexpected custom check result: {result}"

            # Check response time for warning
            if (
                status == HealthCheckStatus.HEALTHY
                and response_time > self.config.warning_threshold
            ):
                status = HealthCheckStatus.WARNING

            return HealthCheckResult(
                status=status,
                response_time=response_time,
                timestamp=time.time(),
                message=message,
            )

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                status=HealthCheckStatus.UNHEALTHY,
                response_time=response_time,
                timestamp=time.time(),
                message=f"Custom health check failed: {e}",
            )


class CompositeHealthChecker(HealthChecker):
    """Composite health checker that runs multiple checks."""

    def __init__(self, config: HealthCheckConfig, checkers: builtins.list[HealthChecker]):
        super().__init__(config)
        self.checkers = checkers
        self.require_all_healthy = True  # Configurable

    async def check_health(self, instance: ServiceInstance) -> HealthCheckResult:
        """Perform composite health check."""
        start_time = time.time()

        # Run all health checks concurrently
        results = await asyncio.gather(
            *[checker.check_with_circuit_breaker(instance) for checker in self.checkers],
            return_exceptions=True,
        )

        response_time = time.time() - start_time

        # Analyze results
        healthy_count = 0
        warning_count = 0
        unhealthy_count = 0
        timeout_count = 0
        error_count = 0

        details = {}
        messages = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_count += 1
                messages.append(f"Checker {i} failed: {result}")
                details[f"checker_{i}"] = {"error": str(result)}
            elif isinstance(result, HealthCheckResult):
                if result.is_healthy():
                    healthy_count += 1
                elif result.is_warning():
                    warning_count += 1
                elif result.status == HealthCheckStatus.TIMEOUT:
                    timeout_count += 1
                else:
                    unhealthy_count += 1

                messages.append(f"Checker {i}: {result.message}")
                details[f"checker_{i}"] = {
                    "status": result.status.value,
                    "response_time": result.response_time,
                    "message": result.message,
                }

        # Determine overall status
        total_checks = len(self.checkers)

        if self.require_all_healthy:
            if healthy_count == total_checks:
                status = HealthCheckStatus.HEALTHY
            elif warning_count > 0 and (healthy_count + warning_count) == total_checks:
                status = HealthCheckStatus.WARNING
            else:
                status = HealthCheckStatus.UNHEALTHY
        # At least one healthy check required
        elif healthy_count > 0:
            if unhealthy_count == 0 and timeout_count == 0 and error_count == 0:
                status = HealthCheckStatus.HEALTHY
            else:
                status = HealthCheckStatus.WARNING
        else:
            status = HealthCheckStatus.UNHEALTHY

        return HealthCheckResult(
            status=status,
            response_time=response_time,
            timestamp=time.time(),
            message=f"Composite check: {healthy_count}/{total_checks} healthy",
            details={
                "individual_results": details,
                "summary": {
                    "healthy": healthy_count,
                    "warning": warning_count,
                    "unhealthy": unhealthy_count,
                    "timeout": timeout_count,
                    "error": error_count,
                    "total": total_checks,
                },
            },
        )


class HealthMonitor:
    """Health monitor that manages multiple health checkers."""

    def __init__(self):
        self._checkers: builtins.dict[str, HealthChecker] = {}
        self._monitoring_tasks: builtins.dict[str, asyncio.Task] = {}
        self._health_callbacks: builtins.dict[str, builtins.list[Callable]] = {}
        self._health_history: builtins.dict[str, builtins.list[HealthCheckResult]] = {}
        self._running = False

    def add_checker(self, name: str, checker: HealthChecker):
        """Add health checker."""
        self._checkers[name] = checker
        self._health_callbacks[name] = []
        self._health_history[name] = []

    def remove_checker(self, name: str):
        """Remove health checker."""
        if name in self._checkers:
            # Stop monitoring task
            if name in self._monitoring_tasks:
                self._monitoring_tasks[name].cancel()
                del self._monitoring_tasks[name]

            # Clean up
            del self._checkers[name]
            del self._health_callbacks[name]
            del self._health_history[name]

    def add_health_callback(self, checker_name: str, callback: Callable):
        """Add callback for health status changes."""
        if checker_name in self._health_callbacks:
            self._health_callbacks[checker_name].append(callback)

    async def start_monitoring(self, instance: ServiceInstance):
        """Start health monitoring for an instance."""
        self._running = True

        for name, checker in self._checkers.items():
            if name not in self._monitoring_tasks:
                task = asyncio.create_task(self._monitor_instance_health(name, checker, instance))
                self._monitoring_tasks[name] = task

    async def stop_monitoring(self):
        """Stop all health monitoring."""
        self._running = False

        # Cancel all monitoring tasks
        for task in self._monitoring_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self._monitoring_tasks:
            await asyncio.gather(*self._monitoring_tasks.values(), return_exceptions=True)

        self._monitoring_tasks.clear()

        # Close HTTP checkers
        for checker in self._checkers.values():
            if isinstance(checker, HTTPHealthChecker):
                await checker.close()

    async def _monitor_instance_health(
        self, checker_name: str, checker: HealthChecker, instance: ServiceInstance
    ):
        """Monitor health for a specific instance and checker."""

        consecutive_failures = 0
        consecutive_successes = 0
        last_status = HealthCheckStatus.UNKNOWN

        while self._running:
            try:
                # Perform health check
                result = await checker.check_with_circuit_breaker(instance)

                # Store result in history
                history = self._health_history[checker_name]
                history.append(result)

                # Keep only recent history (last 100 results)
                if len(history) > 100:
                    history[:] = history[-100:]

                # Update consecutive counters
                if result.is_healthy():
                    consecutive_successes += 1
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    consecutive_successes = 0

                # Determine if status change should be reported
                current_status = result.status
                status_changed = False

                if last_status != current_status:
                    # Check thresholds for status changes
                    if (
                        (
                            current_status == HealthCheckStatus.HEALTHY
                            and consecutive_successes >= checker.config.healthy_threshold
                        )
                        or (
                            current_status
                            in [HealthCheckStatus.UNHEALTHY, HealthCheckStatus.TIMEOUT]
                            and consecutive_failures >= checker.config.unhealthy_threshold
                        )
                        or current_status == HealthCheckStatus.WARNING
                    ):
                        status_changed = True

                # Notify callbacks on status change
                if status_changed:
                    last_status = current_status

                    for callback in self._health_callbacks[checker_name]:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(instance, result)
                            else:
                                callback(instance, result)
                        except Exception as e:
                            logger.error("Health callback failed: %s", e)

                # Wait for next check
                await asyncio.sleep(checker.config.interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health monitoring error for %s: %s", checker_name, e)
                await asyncio.sleep(checker.config.interval)

    def get_health_status(self, checker_name: str) -> HealthCheckResult | None:
        """Get latest health status for a checker."""
        history = self._health_history.get(checker_name, [])
        return history[-1] if history else None

    def get_health_history(
        self, checker_name: str, limit: int = 10
    ) -> builtins.list[HealthCheckResult]:
        """Get health check history for a checker."""
        history = self._health_history.get(checker_name, [])
        return history[-limit:] if history else []

    def get_all_health_status(self) -> builtins.dict[str, HealthCheckResult]:
        """Get latest health status for all checkers."""
        return {name: self.get_health_status(name) for name in self._checkers.keys()}


def create_health_checker(config: HealthCheckConfig) -> HealthChecker:
    """Factory function to create health checker."""

    if config.check_type in [HealthCheckType.HTTP, HealthCheckType.HTTPS]:
        return HTTPHealthChecker(config)
    if config.check_type == HealthCheckType.TCP:
        return TCPHealthChecker(config)
    if config.check_type == HealthCheckType.UDP:
        return UDPHealthChecker(config)
    if config.check_type == HealthCheckType.CUSTOM:
        return CustomHealthChecker(config)
    raise ValueError(f"Unsupported health check type: {config.check_type}")


# Pre-configured health check configs
DEFAULT_HTTP_CONFIG = HealthCheckConfig(
    check_type=HealthCheckType.HTTP, http_path="/health", interval=30.0, timeout=5.0
)

DEFAULT_HTTPS_CONFIG = HealthCheckConfig(
    check_type=HealthCheckType.HTTPS,
    http_path="/health",
    interval=30.0,
    timeout=5.0,
    verify_ssl=True,
)

DEFAULT_TCP_CONFIG = HealthCheckConfig(check_type=HealthCheckType.TCP, interval=30.0, timeout=5.0)
