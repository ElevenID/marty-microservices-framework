"""
Performance Test Configuration

This module provides pytest configuration and fixtures for performance testing.
Performance tests include load testing, stress testing, and benchmark validation.
"""

import statistics
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

import psutil
import pytest


@dataclass
class PerformanceMetrics:
    """Container for performance test metrics."""
    response_times: List[float]
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
            'duration': end_time - start_time,
            'cpu_usage': (initial_cpu + final_cpu) / 2,
            'memory_usage': (initial_memory + final_memory) / 2
        }

    return monitor


@pytest.fixture
def load_test_config():
    """Configuration for load testing scenarios."""
    return {
        'concurrent_users': [1, 5, 10, 25, 50],
        'test_duration': 60,  # seconds
        'ramp_up_time': 10,   # seconds
        'target_endpoints': [
            '/health',
            '/authenticate',
            '/users'
        ],
        'acceptable_response_time': 1.0,  # seconds
        'acceptable_error_rate': 0.01     # 1%
    }


@pytest.fixture
def stress_test_config():
    """Configuration for stress testing scenarios."""
    return {
        'max_concurrent_users': 1000,
        'ramp_up_steps': [50, 100, 200, 500, 1000],
        'step_duration': 30,  # seconds
        'breaking_point_threshold': 0.05,  # 5% error rate
        'recovery_time': 60   # seconds
    }


@pytest.fixture
def benchmark_config():
    """Configuration for benchmark testing."""
    return {
        'baseline_metrics': {
            'health_check_time': 0.01,    # 10ms
            'authentication_time': 0.1,   # 100ms
            'user_list_time': 0.05,       # 50ms
        },
        'regression_threshold': 0.1,  # 10% slower than baseline
        'warmup_requests': 10,
        'benchmark_requests': 100
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

    def get_metrics() -> Dict[str, float]:
        if not response_times:
            return {}

        return {
            'count': len(response_times),
            'avg': statistics.mean(response_times),
            'min': min(response_times),
            'max': max(response_times),
            'p50': statistics.median(response_times),
            'p95': sorted(response_times)[int(0.95 * len(response_times))],
            'p99': sorted(response_times)[int(0.99 * len(response_times))],
        }

    tracker = type('ResponseTimeTracker', (), {
        'track': track_request,
        'metrics': property(lambda self: get_metrics()),
        'reset': lambda self: response_times.clear()
    })()

    return tracker


# Performance test thresholds
PERFORMANCE_THRESHOLDS = {
    'max_response_time': 1.0,      # 1 second
    'max_p95_response_time': 2.0,  # 2 seconds
    'min_throughput': 100,         # requests per second
    'max_error_rate': 0.01,        # 1%
    'max_cpu_usage': 80,           # 80%
    'max_memory_usage': 80,        # 80%
}


# Performance test markers
pytest.mark.performance = pytest.mark.performance
pytest.mark.load_test = pytest.mark.load_test
pytest.mark.stress_test = pytest.mark.stress_test
pytest.mark.benchmark = pytest.mark.benchmark
pytest.mark.slow = pytest.mark.slow
