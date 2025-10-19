"""
End-to-End Test Configuration and Fixtures for Marty Framework

This module provides comprehensive testing infrastructure for performance
analysis, bottleneck detection, timeout monitoring, and auditability testing
using the modern framework testing components.
"""

import asyncio
import builtins
import os
import platform
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
import psutil
import pytest
import pytest_asyncio
import redis.asyncio as redis
from observability import ServiceMonitor
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from marty_msf.framework.events.enhanced_event_bus import (
    EnhancedEventBus as InMemoryEventBus,
)
from marty_msf.framework.testing import PerformanceTestCase, TestEventCollector
from marty_msf.framework.testing.performance_testing import (
    LoadConfiguration,
    LoadPattern,
    RequestSpec,
)
from marty_msf.observability.monitoring import MetricsCollector


@dataclass
class PerformanceMetrics:
    """Container for performance metrics during testing."""

    cpu_usage: builtins.list[float] = field(default_factory=list)
    memory_usage: builtins.list[float] = field(default_factory=list)
    response_times: builtins.list[float] = field(default_factory=list)
    error_count: int = 0
    success_count: int = 0
    timeout_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def avg_response_time(self) -> float:
        """Calculate average response time."""
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0

    @property
    def p95_response_time(self) -> float:
        """Calculate 95th percentile response time."""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(0.95 * len(sorted_times))
        return sorted_times[index] if index < len(sorted_times) else sorted_times[-1]

    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage."""
        total = self.error_count + self.success_count
        return (self.error_count / total * 100) if total > 0 else 0.0


@dataclass
class BottleneckAnalysis:
    """Analysis results for bottleneck detection."""

    service_name: str
    bottleneck_type: str  # 'cpu', 'memory', 'response_time', 'error_rate'
    severity: str  # 'low', 'medium', 'high', 'critical'
    current_value: float
    threshold_value: float
    recommendations: builtins.list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AuditEvent:
    """Audit event for tracking system behavior."""

    timestamp: datetime
    service: str
    event_type: str  # 'performance', 'error', 'security', 'business'
    severity: str  # 'info', 'warning', 'error', 'critical'
    message: str
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None
    request_id: str | None = None


class PerformanceAnalyzer:
    """Analyzes performance metrics and identifies bottlenecks."""

    def __init__(self):
        self.metrics_history: builtins.dict[str, builtins.list[PerformanceMetrics]] = defaultdict(
            list
        )
        self.bottlenecks: builtins.list[BottleneckAnalysis] = []
        self.audit_events: builtins.list[AuditEvent] = []

        # Thresholds for bottleneck detection
        self.thresholds = {
            "cpu_usage": 80.0,  # 80% CPU usage
            "memory_usage": 85.0,  # 85% memory usage
            "avg_response_time": 2.0,  # 2 seconds
            "p95_response_time": 5.0,  # 5 seconds
            "error_rate": 5.0,  # 5% error rate
        }

    def collect_metrics(self, service_name: str) -> PerformanceMetrics:
        """Collect current performance metrics."""
        process = psutil.Process()

        metrics = PerformanceMetrics(
            cpu_usage=[psutil.cpu_percent(interval=0.1)],
            memory_usage=[process.memory_percent()],
        )

        self.metrics_history[service_name].append(metrics)
        return metrics

    def analyze_bottlenecks(
        self, service_name: str, metrics: PerformanceMetrics
    ) -> builtins.list[BottleneckAnalysis]:
        """Analyze metrics for bottlenecks."""
        bottlenecks = []

        # CPU bottleneck analysis
        if metrics.cpu_usage and max(metrics.cpu_usage) > self.thresholds["cpu_usage"]:
            bottlenecks.append(
                BottleneckAnalysis(
                    service_name=service_name,
                    bottleneck_type="cpu",
                    severity="high" if max(metrics.cpu_usage) > 90 else "medium",
                    current_value=max(metrics.cpu_usage),
                    threshold_value=self.thresholds["cpu_usage"],
                    recommendations=[
                        "Consider horizontal scaling",
                        "Optimize CPU-intensive operations",
                        "Implement caching for computational results",
                    ],
                )
            )

        # Memory bottleneck analysis
        if metrics.memory_usage and max(metrics.memory_usage) > self.thresholds["memory_usage"]:
            bottlenecks.append(
                BottleneckAnalysis(
                    service_name=service_name,
                    bottleneck_type="memory",
                    severity="critical" if max(metrics.memory_usage) > 95 else "high",
                    current_value=max(metrics.memory_usage),
                    threshold_value=self.thresholds["memory_usage"],
                    recommendations=[
                        "Investigate memory leaks",
                        "Optimize data structures",
                        "Implement memory pooling",
                    ],
                )
            )

        # Response time bottleneck analysis
        if metrics.avg_response_time > self.thresholds["avg_response_time"]:
            bottlenecks.append(
                BottleneckAnalysis(
                    service_name=service_name,
                    bottleneck_type="response_time",
                    severity="high" if metrics.avg_response_time > 3.0 else "medium",
                    current_value=metrics.avg_response_time,
                    threshold_value=self.thresholds["avg_response_time"],
                    recommendations=[
                        "Optimize database queries",
                        "Implement response caching",
                        "Consider async processing for heavy operations",
                    ],
                )
            )

        # Error rate bottleneck analysis
        if metrics.error_rate > self.thresholds["error_rate"]:
            bottlenecks.append(
                BottleneckAnalysis(
                    service_name=service_name,
                    bottleneck_type="error_rate",
                    severity="critical" if metrics.error_rate > 15.0 else "high",
                    current_value=metrics.error_rate,
                    threshold_value=self.thresholds["error_rate"],
                    recommendations=[
                        "Investigate error root causes",
                        "Implement better error handling",
                        "Add circuit breaker patterns",
                    ],
                )
            )

        self.bottlenecks.extend(bottlenecks)
        return bottlenecks

    def create_audit_event(
        self,
        service: str,
        event_type: str,
        severity: str,
        message: str,
        metadata: builtins.dict | None = None,
    ) -> AuditEvent:
        """Create an audit event for tracking."""
        event = AuditEvent(
            timestamp=datetime.now(),
            service=service,
            event_type=event_type,
            severity=severity,
            message=message,
            metadata=metadata or {},
            request_id=f"req_{int(time.time() * 1000)}",
        )
        self.audit_events.append(event)
        return event

    def generate_report(self) -> builtins.dict[str, Any]:
        """Generate comprehensive performance report."""
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_services": len(self.metrics_history),
                "total_bottlenecks": len(self.bottlenecks),
                "critical_bottlenecks": len(
                    [b for b in self.bottlenecks if b.severity == "critical"]
                ),
                "total_audit_events": len(self.audit_events),
                "error_events": len([e for e in self.audit_events if e.severity == "error"]),
            },
            "bottlenecks": [
                {
                    "service": b.service_name,
                    "type": b.bottleneck_type,
                    "severity": b.severity,
                    "current_value": b.current_value,
                    "threshold": b.threshold_value,
                    "recommendations": b.recommendations,
                    "timestamp": b.timestamp.isoformat(),
                }
                for b in self.bottlenecks
            ],
            "audit_trail": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "service": e.service,
                    "type": e.event_type,
                    "severity": e.severity,
                    "message": e.message,
                    "metadata": e.metadata,
                    "request_id": e.request_id,
                }
                for e in self.audit_events
            ],
            "metrics_summary": {
                service: {
                    "total_measurements": len(metrics_list),
                    "avg_cpu": sum(m.cpu_usage[0] if m.cpu_usage else 0 for m in metrics_list)
                    / len(metrics_list)
                    if metrics_list
                    else 0,
                    "avg_memory": sum(
                        m.memory_usage[0] if m.memory_usage else 0 for m in metrics_list
                    )
                    / len(metrics_list)
                    if metrics_list
                    else 0,
                    "avg_response_time": sum(m.avg_response_time for m in metrics_list)
                    / len(metrics_list)
                    if metrics_list
                    else 0,
                }
                for service, metrics_list in self.metrics_history.items()
            },
        }


@pytest_asyncio.fixture
async def service_monitor():
    """Create service monitor for testing."""
    monitor = ServiceMonitor("test_service")
    monitor.start_monitoring()
    yield monitor
    monitor.stop_monitoring()


@pytest_asyncio.fixture
async def performance_analyzer():
    """Create performance analyzer for testing."""
    return PerformanceAnalyzer()


@pytest_asyncio.fixture
async def metrics_collector():
    """Create and initialize metrics collector."""
    collector = MetricsCollector("test_service")
    yield collector


@pytest_asyncio.fixture
async def test_event_collector():
    """Create and initialize test event collector."""
    collector = TestEventCollector()
    yield collector


@pytest_asyncio.fixture
async def performance_test_case():
    """Create performance test case for testing."""

    request_spec = RequestSpec(method="GET", url="http://localhost:8000/health")
    load_config = LoadConfiguration(pattern=LoadPattern.CONSTANT, max_users=10, duration=30)
    test_case = PerformanceTestCase("test_performance", request_spec, load_config)
    yield test_case


@pytest_asyncio.fixture
async def framework_performance_monitor():
    """Create framework performance monitor for circuit breaker simulation."""
    # Use the framework's monitoring instead of chassis plugins
    monitor = ServiceMonitor("circuit_breaker_test")
    monitor.start_monitoring()
    yield monitor
    monitor.stop_monitoring()


@pytest.fixture
def test_report_dir():
    """Create directory for test reports."""
    report_dir = Path("test_reports")
    report_dir.mkdir(exist_ok=True)
    return report_dir


class TimeoutMonitor:
    """Monitor for timeout scenarios during testing."""

    def __init__(self, timeout_threshold: float = 5.0):
        self.timeout_threshold = timeout_threshold
        self.timeout_events: builtins.list[builtins.dict[str, Any]] = []

    async def monitor_operation(self, operation_name: str, operation_func, *args, **kwargs):
        """Monitor an operation for timeouts."""
        start_time = time.time()

        try:
            # Run operation with timeout
            result = await asyncio.wait_for(
                operation_func(*args, **kwargs), timeout=self.timeout_threshold
            )

            duration = time.time() - start_time

            # Log if operation took too long (90% of timeout)
            if duration > self.timeout_threshold * 0.9:
                self.timeout_events.append(
                    {
                        "operation": operation_name,
                        "duration": duration,
                        "threshold": self.timeout_threshold,
                        "status": "slow",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            return result

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            self.timeout_events.append(
                {
                    "operation": operation_name,
                    "duration": duration,
                    "threshold": self.timeout_threshold,
                    "status": "timeout",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            raise

    def get_timeout_report(self) -> builtins.dict[str, Any]:
        """Get timeout monitoring report."""
        return {
            "total_operations": len(self.timeout_events),
            "timeouts": len([e for e in self.timeout_events if e["status"] == "timeout"]),
            "slow_operations": len([e for e in self.timeout_events if e["status"] == "slow"]),
            "events": self.timeout_events,
        }


@pytest.fixture
def timeout_monitor():
    """Create timeout monitor for testing."""
    return TimeoutMonitor(timeout_threshold=5.0)


# Real infrastructure fixtures for E2E tests


# Configure Docker client for testcontainers
def configure_docker_client():
    """Configure Docker client for testcontainers on macOS Docker Desktop."""

    if platform.system() == "Darwin":  # macOS
        # Set Docker socket path for Docker Desktop
        docker_host = "unix:///Users/" + os.environ.get("USER", "user") + "/.docker/run/docker.sock"
        if os.path.exists(docker_host.replace("unix://", "")):
            os.environ["DOCKER_HOST"] = docker_host
        elif os.path.exists("/var/run/docker.sock"):
            os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"


@pytest.fixture(scope="session")
async def postgres_container():
    """Provide a PostgreSQL container for E2E tests."""

    # Configure Docker client before creating container
    configure_docker_client()

    with PostgresContainer("postgres:15-alpine") as postgres:
        postgres.start()
        yield postgres


@pytest.fixture(scope="session")
async def redis_container():
    """Provide a Redis container for E2E tests."""

    # Configure Docker client before creating container
    configure_docker_client()

    with RedisContainer("redis:7-alpine") as redis:
        redis.start()
        yield redis


@pytest.fixture
async def real_database_connection(postgres_container):
    """Provide a real database connection for E2E tests."""

    connection_url = postgres_container.get_connection_url()
    # Convert psycopg2 URL to asyncpg format
    asyncpg_url = connection_url.replace("postgresql+psycopg2://", "postgresql://")

    connection = await asyncpg.connect(asyncpg_url)

    # Setup test schema for E2E tests
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await connection.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    await connection.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    yield connection

    # Cleanup
    await connection.execute("DROP TABLE IF EXISTS orders")
    await connection.execute("DROP TABLE IF EXISTS items")
    await connection.execute("DROP TABLE IF EXISTS users")
    await connection.close()


@pytest.fixture
async def real_redis_client(redis_container):
    """Provide a real Redis client for E2E tests."""

    redis_url = f"redis://localhost:{redis_container.get_exposed_port(6379)}/0"
    client = redis.from_url(redis_url)

    yield client

    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture
async def real_event_bus(test_service_name: str):
    """Provide a real event bus for E2E tests."""

    # Create in-memory event bus for E2E tests
    event_bus = InMemoryEventBus()
    await event_bus.start()

    yield event_bus

    # Cleanup
    await event_bus.stop()
