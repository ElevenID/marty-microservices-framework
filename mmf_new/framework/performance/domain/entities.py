"""
Performance Domain Entities.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

class OptimizationType(Enum):
    """Types of performance optimizations."""
    CPU_OPTIMIZATION = "cpu_optimization"
    MEMORY_OPTIMIZATION = "memory_optimization"
    IO_OPTIMIZATION = "io_optimization"
    CACHE_OPTIMIZATION = "cache_optimization"
    DATABASE_OPTIMIZATION = "database_optimization"
    NETWORK_OPTIMIZATION = "network_optimization"

class ProfilerType(Enum):
    """Types of profilers."""
    CPU_PROFILER = "cpu_profiler"
    MEMORY_PROFILER = "memory_profiler"
    LINE_PROFILER = "line_profiler"
    ASYNC_PROFILER = "async_profiler"

@dataclass
class PerformanceProfile:
    """Performance profiling results."""
    profiler_type: ProfilerType
    duration: float
    function_stats: dict[str, dict[str, float]]
    hotspots: list[str]
    memory_usage: dict[str, float]
    recommendations: list[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation."""
    optimization_type: OptimizationType
    title: str
    description: str
    priority: int  # 1-10, higher is more important
    estimated_impact: float  # 0-1, percentage improvement expected
    implementation_effort: str  # "low", "medium", "high"
    code_location: str | None = None
    specific_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ResourceMetrics:
    """System resource metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available: int
    disk_io_read: int
    disk_io_write: int
    network_bytes_sent: int
    network_bytes_recv: int
    process_count: int
    thread_count: int
