import builtins
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NamedTuple
import numpy as np

class PerformanceTestType(Enum):
    """Types of performance tests."""
    LOAD_TEST = "load_test"
    STRESS_TEST = "stress_test"
    SPIKE_TEST = "spike_test"
    ENDURANCE_TEST = "endurance_test"
    VOLUME_TEST = "volume_test"
    BASELINE_TEST = "baseline_test"

class LoadPattern(Enum):
    """Load generation patterns."""
    CONSTANT = "constant"
    RAMP_UP = "ramp_up"
    RAMP_DOWN = "ramp_down"
    STEP = "step"
    SPIKE = "spike"
    WAVE = "wave"

@dataclass
class RequestSpec:
    """Specification for a request."""
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    body: Any | None = None
    timeout: float = 30.0
    expected_status_codes: list[int] = field(default_factory=lambda: [200])

@dataclass
class LoadConfiguration:
    """Load generation configuration."""
    pattern: LoadPattern
    initial_users: int = 1
    max_users: int = 100
    ramp_duration: int = 60  # seconds
    hold_duration: int = 120  # seconds
    ramp_down_duration: int = 30  # seconds
    iterations_per_user: int | None = None
    duration: int | None = None  # Total test duration in seconds
    think_time: float = 1.0  # seconds between requests
    think_time_variation: float = 0.2  # variation factor

class ResponseMetric(NamedTuple):
    """Individual response metrics."""
    timestamp: float
    response_time: float
    status_code: int
    error: str | None
    request_size: int
    response_size: int

@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0

    # Response time metrics
    min_response_time: float = float("inf")
    max_response_time: float = 0.0
    avg_response_time: float = 0.0
    median_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0

    # Throughput metrics
    requests_per_second: float = 0.0
    bytes_per_second: float = 0.0

    # Error breakdown
    error_breakdown: dict[str, int] = field(default_factory=dict)
    status_code_breakdown: dict[int, int] = field(default_factory=dict)

    # Time series data
    response_times: list[float] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)

    def calculate_percentiles(self):
        """Calculate response time percentiles."""
        if self.response_times:
            sorted_times = sorted(self.response_times)
            self.median_response_time = statistics.median(sorted_times)
            self.p95_response_time = np.percentile(sorted_times, 95)
            self.p99_response_time = np.percentile(sorted_times, 99)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate": self.error_rate,
            "min_response_time": self.min_response_time,
            "max_response_time": self.max_response_time,
            "avg_response_time": self.avg_response_time,
            "median_response_time": self.median_response_time,
            "p95_response_time": self.p95_response_time,
            "p99_response_time": self.p99_response_time,
            "requests_per_second": self.requests_per_second,
            "bytes_per_second": self.bytes_per_second,
            "error_breakdown": self.error_breakdown,
            "status_code_breakdown": self.status_code_breakdown,
        }

class PerformanceTestCase:
    """Test case for performance testing."""

    def __init__(
        self,
        name: str,
        request_spec: RequestSpec,
        load_config: LoadConfiguration,
        test_type: PerformanceTestType = PerformanceTestType.LOAD_TEST,
        performance_criteria: dict[str, Any] | None = None,
    ):
        self.name = name
        self.request_spec = request_spec
        self.load_config = load_config
        self.performance_test_type = test_type
        self.performance_criteria = performance_criteria or {}
