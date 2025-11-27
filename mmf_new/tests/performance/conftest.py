"""
Performance Test Configuration

This module provides pytest configuration and fixtures for performance testing.
Performance tests include load testing, stress testing, and benchmark validation.
"""

import asyncio
import statistics
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import psutil
import pytest


@dataclass
class EventMessage:
    message_id: str
    event_type: str
    source: str
    data: Any


@dataclass
class EventSubscription:
    subscription_id: str
    consumer_group: str
    event_types: list[str]
    handler: Callable


class InMemoryEventBus:
    def __init__(self):
        self.subscriptions = []

    async def publish(self, message: EventMessage):
        for sub in self.subscriptions:
            if message.event_type in sub.event_types:
                await sub.handler(message)

    async def subscribe(self, subscription: EventSubscription):
        self.subscriptions.append(subscription)


@dataclass
class PerformanceMetrics:
    """Container for performance test metrics."""

    response_times: list[float]
    throughput: float
    error_rate: float
    cpu_usage: float
    memory_usage: float
    concurrent_users: int

    @property
    def avg_response_time(self) -> float:
        return statistics.mean(self.response_times) if self.response_times else 0.0

    @property
    def p95_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(0.95 * len(sorted_times))
        return sorted_times[index]

    def record_response_time(self, time_ms: float) -> None:
        """Record a response time measurement."""
        self.response_times.append(time_ms)

    def record_throughput(self, rps: float) -> None:
        """Record a throughput measurement."""
        self.throughput = rps

    def record_memory_usage(self, memory_mb: float) -> None:
        """Record a memory usage measurement."""
        self.memory_usage = memory_mb

    def record_cpu_usage(self, cpu_percent: float) -> None:
        """Record a CPU usage measurement."""
        self.cpu_usage = cpu_percent


@pytest.fixture
def performance_monitor():
    """Provides system resource monitoring during tests."""

    @contextmanager
    def monitor():
        initial_cpu = psutil.cpu_percent()
        initial_memory = psutil.virtual_memory().percent
        start_time = time.time()

        yield

        end_time = time.time()
        final_cpu = psutil.cpu_percent()
        final_memory = psutil.virtual_memory().percent

        return {
            "duration": end_time - start_time,
            "cpu_usage": (initial_cpu + final_cpu) / 2,
            "memory_usage": (initial_memory + final_memory) / 2,
        }

    return monitor


@pytest.fixture
def load_test_config():
    """Configuration for load testing scenarios."""
    return {
        "concurrent_users": [1, 5, 10, 25, 50],
        "test_duration": 60,  # seconds
        "ramp_up_time": 10,  # seconds
        "target_endpoints": ["/health", "/authenticate", "/users"],
        "acceptable_response_time": 1.0,  # seconds
        "acceptable_error_rate": 0.01,  # 1%
    }


@pytest.fixture
def stress_test_config():
    """Configuration for stress testing scenarios."""
    return {
        "max_concurrent_users": 1000,
        "ramp_up_steps": [50, 100, 200, 500, 1000],
        "step_duration": 30,  # seconds
        "breaking_point_threshold": 0.05,  # 5% error rate
        "recovery_time": 60,  # seconds
    }


@pytest.fixture
def benchmark_config():
    """Configuration for benchmark testing."""
    return {
        "baseline_metrics": {
            "health_check_time": 0.01,  # 10ms
            "authentication_time": 0.1,  # 100ms
            "user_list_time": 0.05,  # 50ms
        },
        "regression_threshold": 0.1,  # 10% slower than baseline
        "warmup_requests": 10,
        "benchmark_requests": 100,
    }


@pytest.fixture
def response_time_tracker():
    """Tracks response times for performance analysis."""
    response_times = []

    def track_request(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            response_times.append(end_time - start_time)
            return result

        return wrapper

    def get_metrics() -> dict[str, float]:
        if not response_times:
            return {}

        return {
            "count": len(response_times),
            "avg": statistics.mean(response_times),
            "min": min(response_times),
            "max": max(response_times),
            "p50": statistics.median(response_times),
            "p95": sorted(response_times)[int(0.95 * len(response_times))],
            "p99": sorted(response_times)[int(0.99 * len(response_times))],
        }

    tracker = type(
        "ResponseTimeTracker",
        (),
        {
            "track": track_request,
            "metrics": property(lambda self: get_metrics()),
            "reset": lambda self: response_times.clear(),
        },
    )()

    return tracker


@pytest.fixture
def performance_metrics():
    """Performance metrics fixture for recording test results."""
    return PerformanceMetrics(
        response_times=[],
        throughput=0.0,
        error_rate=0.0,
        cpu_usage=0.0,
        memory_usage=0.0,
        concurrent_users=0,
    )


@pytest.fixture
def message_broker():
    """Message broker fixture using in-memory implementation for testing."""

    class MessageBrokerAdapter:
        """Adapter to provide simple publish/subscribe interface for performance tests."""

        def __init__(self):
            self.event_bus = InMemoryEventBus()

        async def publish(self, topic: str, event):
            """Publish an event to a topic."""
            # Convert to EventMessage if needed
            if hasattr(event, "event_type") and hasattr(event, "data"):
                # It's already an Event object from mmf_new.framework.events
                event_message = EventMessage(
                    message_id=getattr(event, "event_id", f"perf-{hash(event)}"),
                    event_type=event.event_type,
                    source=topic,
                    data=event.data,
                )
            else:
                # Fallback for simple objects
                event_message = EventMessage(
                    message_id=f"perf-{hash(str(event))}",
                    event_type="performance_test",
                    source=topic,
                    data={"event": str(event)},
                )

            return await self.event_bus.publish(event_message)

        async def subscribe(self, topic: str, handler):
            """Subscribe a handler to a topic."""
            subscription = EventSubscription(
                subscription_id=f"perf-sub-{hash(topic + str(handler))}",
                consumer_group="performance_test",
                event_types=[topic],
                handler=handler,
            )
            return await self.event_bus.subscribe(subscription)

    return MessageBrokerAdapter()


@pytest.fixture
def event_processor():
    """Event processor fixture for testing event processing performance."""

    class MockEventProcessor:
        def __init__(self):
            self.processed_events = []

        async def process_event(self, event):
            """Process an event (mock implementation)."""
            # Simulate some processing time
            await asyncio.sleep(0.001)  # 1ms
            self.processed_events.append(event)
            return {"status": "processed", "event_id": getattr(event, "id", "unknown")}

        async def process_batch(self, events):
            """Process a batch of events."""
            results = []
            for event in events:
                result = await self.process_event(event)
                results.append(result)
            return results

    return MockEventProcessor()


@pytest.fixture
def resource_monitor():
    """Resource monitor fixture for testing system resource usage."""

    class MockResourceMonitor:
        def get_memory_usage(self):
            """Get current memory usage in MB."""
            return 128.5  # Mock value

        def get_cpu_usage(self):
            """Get current CPU usage percentage."""
            return 25.0  # Mock value

        async def monitor_during_load(self, duration_seconds=10):
            """Monitor resources during a load test."""
            # Simulate monitoring
            await asyncio.sleep(0.1)
            return {"peak_memory": 256.0, "avg_memory": 180.0, "peak_cpu": 75.0, "avg_cpu": 45.0}

    return MockResourceMonitor()


@pytest.fixture
def system_under_test():
    """System under test fixture for end-to-end performance testing."""

    class MockSystemUnderTest:
        def __init__(self):
            self.requests_processed = 0

        async def process_request(self, request_data):
            """Process a request through the system."""
            # Simulate processing
            await asyncio.sleep(0.01)  # 10ms
            self.requests_processed += 1
            return {"status": "success", "request_id": request_data.get("id", "unknown")}

        async def process_batch_requests(self, requests):
            """Process multiple requests."""
            results = []
            for request in requests:
                result = await self.process_request(request)
                results.append(result)
            return results

    return MockSystemUnderTest()


@pytest.fixture
def network_client():
    """Network client fixture for testing network I/O performance."""

    class MockNetworkClient:
        def __init__(self):
            self.requests_made = 0

        async def make_request(self, url, method="GET", data=None):
            """Make a network request."""
            # Simulate network latency
            await asyncio.sleep(0.05)  # 50ms
            self.requests_made += 1
            return {"status_code": 200, "response_time": 0.05, "url": url, "method": method}

        async def make_concurrent_requests(self, urls, concurrency=10):
            """Make multiple concurrent requests."""
            semaphore = asyncio.Semaphore(concurrency)

            async def bounded_request(url):
                async with semaphore:
                    return await self.make_request(url)

            tasks = [bounded_request(url) for url in urls]
            return await asyncio.gather(*tasks)

    return MockNetworkClient()


# Performance test thresholds
PERFORMANCE_THRESHOLDS = {
    "max_response_time": 1.0,  # 1 second
    "max_p95_response_time": 2.0,  # 2 seconds
    "min_throughput": 100,  # requests per second
    "max_error_rate": 0.01,  # 1%
    "max_cpu_usage": 80,  # 80%
    "max_memory_usage": 80,  # 80%
}


# Performance test markers
pytest.mark.performance = pytest.mark.performance
pytest.mark.load_test = pytest.mark.load_test
pytest.mark.stress_test = pytest.mark.stress_test
pytest.mark.benchmark = pytest.mark.benchmark
pytest.mark.slow = pytest.mark.slow
