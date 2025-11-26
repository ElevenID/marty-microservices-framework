"""
Pool Health Checking Framework

Provides comprehensive health checking for connection pools with
configurable checks, alerting, and automatic recovery.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status levels"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check operation"""

    status: HealthStatus
    message: str
    timestamp: datetime
    metrics: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class HealthCheckConfig:
    """Configuration for health checking"""

    # Check intervals
    check_interval: float = 60.0  # seconds
    check_timeout: float = 5.0  # seconds

    # Thresholds
    error_rate_threshold: float = 0.1  # 10%
    utilization_threshold: float = 0.9  # 90%
    response_time_threshold: float = 1.0  # 1 second

    # Failure handling
    consecutive_failures_threshold: int = 3
    recovery_check_interval: float = 30.0  # seconds

    # Alerting
    enable_alerts: bool = True
    alert_channels: list[str] = field(default_factory=list)

    # Custom checks
    custom_checks: list[Callable] = field(default_factory=list)


class PoolHealthChecker:
    """Health checker for connection pools"""

    def __init__(self, config: HealthCheckConfig):
        self.config = config
        self._results: dict[str, list[HealthCheckResult]] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._last_alert_time: dict[str, float] = {}
        self._check_tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start_monitoring(self, pools: dict[str, Any]):
        """Start health monitoring for all pools"""
        if self._running:
            logger.warning("Health checker already running")
            return

        self._running = True

        for pool_name, pool in pools.items():
            task = asyncio.create_task(self._monitor_pool(pool_name, pool))
            self._check_tasks[pool_name] = task

        logger.info(f"Started health monitoring for {len(pools)} pools")

    async def stop_monitoring(self):
        """Stop health monitoring"""
        self._running = False

        for task in self._check_tasks.values():
            task.cancel()

        # Wait for all tasks to complete
        if self._check_tasks:
            await asyncio.gather(*self._check_tasks.values(), return_exceptions=True)

        self._check_tasks.clear()
        logger.info("Stopped health monitoring")

    async def _monitor_pool(self, pool_name: str, pool: Any):
        """Monitor a specific pool"""
        while self._running:
            try:
                result = await self._check_pool_health(pool_name, pool)
                await self._record_result(pool_name, result)

                # Determine next check interval
                if result.status == HealthStatus.UNHEALTHY:
                    check_interval = self.config.recovery_check_interval
                else:
                    check_interval = self.config.check_interval

                await asyncio.sleep(check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring pool '{pool_name}': {e}")
                await asyncio.sleep(self.config.check_interval)

    async def _check_pool_health(self, pool_name: str, pool: Any) -> HealthCheckResult:
        """Perform comprehensive health check on a pool"""
        start_time = time.time()

        try:
            # Get pool metrics
            if hasattr(pool, "get_metrics"):
                metrics = pool.get_metrics()
            else:
                metrics = {}

            # Perform basic checks
            status = HealthStatus.HEALTHY
            messages = []

            # Check error rate
            error_rate = metrics.get("error_rate", 0)
            if error_rate > self.config.error_rate_threshold:
                status = (
                    HealthStatus.DEGRADED
                    if status == HealthStatus.HEALTHY
                    else HealthStatus.UNHEALTHY
                )
                messages.append(f"High error rate: {error_rate:.2%}")

            # Check utilization
            active_connections = metrics.get("active_connections", 0)
            max_connections = metrics.get("max_connections", 1)
            utilization = active_connections / max_connections

            if utilization > self.config.utilization_threshold:
                status = (
                    HealthStatus.DEGRADED
                    if status == HealthStatus.HEALTHY
                    else HealthStatus.UNHEALTHY
                )
                messages.append(f"High utilization: {utilization:.2%}")

            # Check if pool has any active connections (might be completely down)
            if active_connections == 0 and metrics.get("total_connections", 0) == 0:
                status = HealthStatus.UNHEALTHY
                messages.append("No active connections")

            # Run custom checks
            for custom_check in self.config.custom_checks:
                try:
                    custom_result = await custom_check(pool_name, pool, metrics)
                    if isinstance(custom_result, HealthCheckResult):
                        if custom_result.status.value < status.value:  # Lower status means worse
                            status = custom_result.status
                        messages.append(custom_result.message)
                except Exception as e:
                    logger.error(f"Custom health check failed for '{pool_name}': {e}")
                    status = HealthStatus.UNKNOWN
                    messages.append(f"Custom check error: {e}")

            # Specific pool type checks
            if hasattr(pool, "_connections"):  # HTTP/Redis pools
                try:
                    await self._check_connection_health(pool)
                except Exception as e:
                    status = HealthStatus.DEGRADED
                    messages.append(f"Connection check failed: {e}")

            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                status=status,
                message="; ".join(messages) if messages else "All checks passed",
                timestamp=datetime.now(timezone.utc),
                metrics=metrics,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                message=f"Health check failed: {e}",
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                error=str(e),
            )

    async def _check_connection_health(self, pool: Any):
        """Check if we can acquire and use a connection"""
        try:
            # Try to acquire a connection
            if hasattr(pool, "acquire"):
                connection = await asyncio.wait_for(
                    pool.acquire(), timeout=self.config.check_timeout
                )

                # Test the connection
                async with connection as conn:
                    if hasattr(conn, "ping"):
                        await conn.ping()
                    elif hasattr(conn, "execute_command"):
                        await conn.execute_command("PING")
                    # For HTTP pools, we could make a test request

        except asyncio.TimeoutError:
            raise Exception("Connection acquisition timeout")
        except Exception as e:
            raise Exception(f"Connection test failed: {e}")

    async def _record_result(self, pool_name: str, result: HealthCheckResult):
        """Record health check result and handle alerting"""
        # Initialize if needed
        if pool_name not in self._results:
            self._results[pool_name] = []
            self._consecutive_failures[pool_name] = 0

        # Store result (keep last 100 results)
        self._results[pool_name].append(result)
        if len(self._results[pool_name]) > 100:
            self._results[pool_name].pop(0)

        # Track consecutive failures
        if result.status in (HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN):
            self._consecutive_failures[pool_name] += 1
        else:
            self._consecutive_failures[pool_name] = 0

        # Handle alerting
        await self._handle_alerting(pool_name, result)

        # Log significant status changes
        if result.status in (HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN):
            logger.warning(
                f"Pool '{pool_name}' health check: {result.status.value} - {result.message}"
            )
        elif result.status == HealthStatus.DEGRADED:
            logger.info(
                f"Pool '{pool_name}' health check: {result.status.value} - {result.message}"
            )
        else:
            logger.debug(f"Pool '{pool_name}' health check: {result.status.value}")

    async def _handle_alerting(self, pool_name: str, result: HealthCheckResult):
        """Handle alerting for health check results"""
        if not self.config.enable_alerts:
            return

        # Check if we should send an alert
        should_alert = (
            result.status == HealthStatus.UNHEALTHY
            and self._consecutive_failures[pool_name] >= self.config.consecutive_failures_threshold
        )

        if not should_alert:
            return

        # Rate limit alerts (don't send more than once per hour)
        current_time = time.time()
        last_alert = self._last_alert_time.get(pool_name, 0)

        if current_time - last_alert < 3600:  # 1 hour
            return

        self._last_alert_time[pool_name] = current_time

        # Send alert
        alert_message = (
            f"ALERT: Pool '{pool_name}' is unhealthy\n"
            f"Status: {result.status.value}\n"
            f"Message: {result.message}\n"
            f"Consecutive failures: {self._consecutive_failures[pool_name]}\n"
            f"Timestamp: {result.timestamp.isoformat()}"
        )

        logger.error(alert_message)

        # In a real implementation, you would send this to your alerting channels
        # (email, Slack, PagerDuty, etc.)
        for channel in self.config.alert_channels:
            await self._send_alert(channel, alert_message)

    async def _send_alert(self, channel: str, message: str):
        """Send alert to a specific channel"""
        try:
            # Placeholder for actual alerting implementation
            logger.info(f"Sending alert to {channel}: {message}")
        except Exception as e:
            logger.error(f"Failed to send alert to {channel}: {e}")

    def get_health_summary(self) -> dict[str, Any]:
        """Get health summary for all monitored pools"""
        summary = {
            "overall_status": HealthStatus.HEALTHY,
            "pools": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        unhealthy_count = 0
        total_pools = len(self._results)

        for pool_name, results in self._results.items():
            if not results:
                pool_status = HealthStatus.UNKNOWN
            else:
                latest_result = results[-1]
                pool_status = latest_result.status

            summary["pools"][pool_name] = {
                "status": pool_status.value,
                "consecutive_failures": self._consecutive_failures.get(pool_name, 0),
                "last_check": results[-1].timestamp.isoformat() if results else None,
                "last_message": results[-1].message if results else None,
            }

            if pool_status in (HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN):
                unhealthy_count += 1

        # Determine overall status
        if unhealthy_count == 0:
            summary["overall_status"] = HealthStatus.HEALTHY
        elif unhealthy_count < total_pools:
            summary["overall_status"] = HealthStatus.DEGRADED
        else:
            summary["overall_status"] = HealthStatus.UNHEALTHY

        summary["summary"] = {
            "total_pools": total_pools,
            "healthy_pools": total_pools - unhealthy_count,
            "unhealthy_pools": unhealthy_count,
        }

        return summary

    def get_pool_history(self, pool_name: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get health check history for a specific pool"""
        results = self._results.get(pool_name, [])

        history = []
        for result in results[-limit:]:
            history.append(
                {
                    "status": result.status.value,
                    "message": result.message,
                    "timestamp": result.timestamp.isoformat(),
                    "duration_ms": result.duration_ms,
                    "metrics": result.metrics,
                    "error": result.error,
                }
            )

        return history
