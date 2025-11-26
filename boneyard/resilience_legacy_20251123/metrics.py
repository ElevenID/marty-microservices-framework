"""
Metrics collection and monitoring for resilience patterns.

This module provides comprehensive metrics collection, aggregation, and monitoring
capabilities for circuit breakers, retries, timeouts, and other resilience patterns.
"""

import logging
import statistics
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"


class MetricStatus(Enum):
    """Status of metric collection."""

    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class MetricValue:
    """A single metric value with timestamp."""

    value: float
    timestamp: float
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """Summary statistics for a metric."""

    name: str
    metric_type: MetricType
    count: int = 0
    sum: float = 0.0
    min: float = float("inf")
    max: float = float("-inf")
    avg: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    last_updated: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)


class Counter:
    """A counter metric that only increases."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._value = 0.0
        self._lock = threading.Lock()

    def increment(self, amount: float = 1.0) -> None:
        """Increment the counter."""
        with self._lock:
            self._value += amount

    def get_value(self) -> float:
        """Get the current counter value."""
        with self._lock:
            return self._value

    def reset(self) -> None:
        """Reset the counter to zero."""
        with self._lock:
            self._value = 0.0


class Gauge:
    """A gauge metric that can increase or decrease."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._value = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        """Set the gauge value."""
        with self._lock:
            self._value = value

    def increment(self, amount: float = 1.0) -> None:
        """Increment the gauge."""
        with self._lock:
            self._value += amount

    def decrement(self, amount: float = 1.0) -> None:
        """Decrement the gauge."""
        with self._lock:
            self._value -= amount

    def get_value(self) -> float:
        """Get the current gauge value."""
        with self._lock:
            return self._value


class Histogram:
    """A histogram metric for tracking distributions."""

    def __init__(self, name: str, description: str = "", max_size: int = 1000):
        self.name = name
        self.description = description
        self.max_size = max_size
        self._values: deque[float] = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        """Record a value in the histogram."""
        with self._lock:
            self._values.append(value)

    def get_summary(self) -> MetricSummary:
        """Get summary statistics for the histogram."""
        with self._lock:
            if not self._values:
                return MetricSummary(
                    name=self.name, metric_type=MetricType.HISTOGRAM, last_updated=time.time()
                )

            values = list(self._values)
            sorted_values = sorted(values)

            return MetricSummary(
                name=self.name,
                metric_type=MetricType.HISTOGRAM,
                count=len(values),
                sum=sum(values),
                min=min(values),
                max=max(values),
                avg=statistics.mean(values),
                p50=statistics.median(values),
                p95=sorted_values[int(len(sorted_values) * 0.95)]
                if len(sorted_values) > 1
                else sorted_values[0],
                p99=sorted_values[int(len(sorted_values) * 0.99)]
                if len(sorted_values) > 1
                else sorted_values[0],
                last_updated=time.time(),
            )

    def reset(self) -> None:
        """Clear all recorded values."""
        with self._lock:
            self._values.clear()


class Timer:
    """A timer metric for measuring execution time."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._histogram = Histogram(f"{name}_duration", f"{description} execution time")

    def time(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Time the execution of a function."""
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            duration = time.time() - start_time
            self._histogram.observe(duration)

    async def time_async(self, coro) -> Any:
        """Time the execution of an async function."""
        start_time = time.time()
        try:
            result = await coro
            return result
        finally:
            duration = time.time() - start_time
            self._histogram.observe(duration)

    def get_summary(self) -> MetricSummary:
        """Get timing summary statistics."""
        return self._histogram.get_summary()

    def reset(self) -> None:
        """Reset timing measurements."""
        self._histogram.reset()


class RateCounter:
    """A counter that tracks rate over time windows."""

    def __init__(self, name: str, window_seconds: float = 60.0, description: str = ""):
        self.name = name
        self.description = description
        self.window_seconds = window_seconds
        self._events: deque[float] = deque()
        self._lock = threading.Lock()

    def increment(self, amount: float = 1.0) -> None:
        """Record an event."""
        with self._lock:
            current_time = time.time()
            self._events.append(current_time)
            self._cleanup_old_events(current_time)

    def get_rate(self) -> float:
        """Get the current rate (events per second)."""
        with self._lock:
            current_time = time.time()
            self._cleanup_old_events(current_time)

            if not self._events:
                return 0.0

            time_span = current_time - self._events[0]
            if time_span == 0:
                return 0.0

            return len(self._events) / time_span

    def _cleanup_old_events(self, current_time: float) -> None:
        """Remove events outside the time window."""
        cutoff_time = current_time - self.window_seconds
        while self._events and self._events[0] < cutoff_time:
            self._events.popleft()


class ResilienceMetrics:
    """Comprehensive metrics for resilience patterns."""

    def __init__(self, component_name: str):
        self.component_name = component_name

        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(f"{component_name}_circuit_breaker_state")
        self.circuit_breaker_failures = Counter(f"{component_name}_circuit_breaker_failures")
        self.circuit_breaker_successes = Counter(f"{component_name}_circuit_breaker_successes")
        self.circuit_breaker_rejections = Counter(f"{component_name}_circuit_breaker_rejections")

        # Retry metrics
        self.retry_attempts = Counter(f"{component_name}_retry_attempts")
        self.retry_failures = Counter(f"{component_name}_retry_failures")
        self.retry_successes = Counter(f"{component_name}_retry_successes")
        self.retry_exhausted = Counter(f"{component_name}_retry_exhausted")

        # Timeout metrics
        self.timeout_operations = Counter(f"{component_name}_timeout_operations")
        self.timeout_successes = Counter(f"{component_name}_timeout_successes")
        self.timeout_failures = Counter(f"{component_name}_timeout_failures")

        # Bulkhead metrics
        self.bulkhead_active_requests = Gauge(f"{component_name}_bulkhead_active_requests")
        self.bulkhead_queued_requests = Gauge(f"{component_name}_bulkhead_queued_requests")
        self.bulkhead_rejections = Counter(f"{component_name}_bulkhead_rejections")

        # General performance metrics
        self.request_duration = Timer(f"{component_name}_request_duration")
        self.request_rate = RateCounter(f"{component_name}_request_rate")
        self.error_rate = RateCounter(f"{component_name}_error_rate")

    def record_circuit_breaker_event(self, event_type: str, state: int = 0) -> None:
        """Record a circuit breaker event."""
        if event_type == "failure":
            self.circuit_breaker_failures.increment()
        elif event_type == "success":
            self.circuit_breaker_successes.increment()
        elif event_type == "rejection":
            self.circuit_breaker_rejections.increment()
        elif event_type == "state_change":
            self.circuit_breaker_state.set(state)

    def record_retry_event(self, event_type: str) -> None:
        """Record a retry event."""
        if event_type == "attempt":
            self.retry_attempts.increment()
        elif event_type == "failure":
            self.retry_failures.increment()
        elif event_type == "success":
            self.retry_successes.increment()
        elif event_type == "exhausted":
            self.retry_exhausted.increment()

    def record_timeout_event(self, event_type: str) -> None:
        """Record a timeout event."""
        self.timeout_operations.increment()
        if event_type == "success":
            self.timeout_successes.increment()
        elif event_type == "failure":
            self.timeout_failures.increment()

    def record_bulkhead_event(self, event_type: str, value: float = 1.0) -> None:
        """Record a bulkhead event."""
        if event_type == "active_requests":
            self.bulkhead_active_requests.set(value)
        elif event_type == "queued_requests":
            self.bulkhead_queued_requests.set(value)
        elif event_type == "rejection":
            self.bulkhead_rejections.increment()

    def record_request(self, duration: float, success: bool) -> None:
        """Record a request with its duration and success status."""
        self.request_duration._histogram.observe(duration)
        self.request_rate.increment()

        if not success:
            self.error_rate.increment()


class MetricsCollector:
    """Central collector for all resilience metrics."""

    def __init__(self):
        self._metrics: dict[str, ResilienceMetrics] = {}
        self._custom_metrics: dict[str, Counter | Gauge | Histogram | Timer] = {}
        self._lock = threading.Lock()
        self._collection_enabled = True

    def get_or_create_resilience_metrics(self, component_name: str) -> ResilienceMetrics:
        """Get or create resilience metrics for a component."""
        with self._lock:
            if component_name not in self._metrics:
                self._metrics[component_name] = ResilienceMetrics(component_name)
            return self._metrics[component_name]

    def register_custom_metric(self, metric: Counter | Gauge | Histogram | Timer) -> None:
        """Register a custom metric."""
        with self._lock:
            self._custom_metrics[metric.name] = metric

    def get_all_summaries(self) -> dict[str, dict[str, Any]]:
        """Get summary of all metrics."""
        with self._lock:
            summaries = {}

            # Resilience metrics
            for component_name, metrics in self._metrics.items():
                component_summary = {
                    "circuit_breaker": {
                        "state": metrics.circuit_breaker_state.get_value(),
                        "failures": metrics.circuit_breaker_failures.get_value(),
                        "successes": metrics.circuit_breaker_successes.get_value(),
                        "rejections": metrics.circuit_breaker_rejections.get_value(),
                    },
                    "retry": {
                        "attempts": metrics.retry_attempts.get_value(),
                        "failures": metrics.retry_failures.get_value(),
                        "successes": metrics.retry_successes.get_value(),
                        "exhausted": metrics.retry_exhausted.get_value(),
                    },
                    "timeout": {
                        "operations": metrics.timeout_operations.get_value(),
                        "successes": metrics.timeout_successes.get_value(),
                        "failures": metrics.timeout_failures.get_value(),
                    },
                    "bulkhead": {
                        "active_requests": metrics.bulkhead_active_requests.get_value(),
                        "queued_requests": metrics.bulkhead_queued_requests.get_value(),
                        "rejections": metrics.bulkhead_rejections.get_value(),
                    },
                    "performance": {
                        "request_duration": metrics.request_duration.get_summary(),
                        "request_rate": metrics.request_rate.get_rate(),
                        "error_rate": metrics.error_rate.get_rate(),
                    },
                }
                summaries[component_name] = component_summary

            # Custom metrics
            custom_summaries = {}
            for name, metric in self._custom_metrics.items():
                if isinstance(metric, Counter | Gauge):
                    custom_summaries[name] = metric.get_value()
                elif isinstance(metric, Histogram | Timer):
                    custom_summaries[name] = metric.get_summary()

            if custom_summaries:
                summaries["custom"] = custom_summaries

            return summaries

    def reset_all(self) -> None:
        """Reset all metrics."""
        with self._lock:
            for metrics in self._metrics.values():
                # Reset all counters and histograms
                for attr_name in dir(metrics):
                    attr = getattr(metrics, attr_name)
                    if hasattr(attr, "reset"):
                        attr.reset()

            for metric in self._custom_metrics.values():
                if hasattr(metric, "reset"):
                    metric.reset()

    def enable_collection(self) -> None:
        """Enable metrics collection."""
        self._collection_enabled = True

    def disable_collection(self) -> None:
        """Disable metrics collection."""
        self._collection_enabled = False

    def is_collection_enabled(self) -> bool:
        """Check if metrics collection is enabled."""
        return self._collection_enabled


# Global metrics collector instance
default_metrics_collector = MetricsCollector()


def get_resilience_metrics(component_name: str) -> ResilienceMetrics:
    """Get resilience metrics for a component."""
    return default_metrics_collector.get_or_create_resilience_metrics(component_name)


def create_counter(name: str, description: str = "") -> Counter:
    """Create and register a counter metric."""
    counter = Counter(name, description)
    default_metrics_collector.register_custom_metric(counter)
    return counter


def create_gauge(name: str, description: str = "") -> Gauge:
    """Create and register a gauge metric."""
    gauge = Gauge(name, description)
    default_metrics_collector.register_custom_metric(gauge)
    return gauge


def create_histogram(name: str, description: str = "", max_size: int = 1000) -> Histogram:
    """Create and register a histogram metric."""
    histogram = Histogram(name, description, max_size)
    default_metrics_collector.register_custom_metric(histogram)
    return histogram


def create_timer(name: str, description: str = "") -> Timer:
    """Create and register a timer metric."""
    timer = Timer(name, description)
    default_metrics_collector.register_custom_metric(timer)
    return timer


# Decorator for automatic timing
def timed(metric_name: str = ""):
    """Decorator to automatically time function execution."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        timer_name = metric_name or f"{func.__module__}.{func.__name__}"
        timer = create_timer(timer_name, f"Execution time for {func.__name__}")

        def wrapper(*args, **kwargs) -> T:
            return timer.time(func, *args, **kwargs)

        return wrapper

    return decorator


def async_timed(metric_name: str = ""):
    """Decorator to automatically time async function execution."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        timer_name = metric_name or f"{func.__module__}.{func.__name__}"
        timer = create_timer(timer_name, f"Execution time for {func.__name__}")

        async def wrapper(*args, **kwargs) -> Any:
            return await timer.time_async(func(*args, **kwargs))

        return wrapper

    return decorator
