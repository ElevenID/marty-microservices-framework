"""
Performance Optimization Engine for Marty Framework

This module provides comprehensive performance optimization capabilities including
automated profiling, resource optimization, intelligent caching, and performance tuning.
"""

import asyncio
import builtins
import cProfile
import io
import json
import pstats
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import psutil
import redis.asyncio as redis
from cachetools import LRUCache, TTLCache


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


class CacheStrategy(Enum):
    """Caching strategies."""

    LRU = "lru"
    TTL = "ttl"
    WRITE_THROUGH = "write_through"
    WRITE_BACK = "write_back"
    WRITE_AROUND = "write_around"


@dataclass
class PerformanceProfile:
    """Performance profiling results."""

    profiler_type: ProfilerType
    duration: float
    function_stats: builtins.dict[str, builtins.dict[str, float]]
    hotspots: builtins.list[str]
    memory_usage: builtins.dict[str, float]
    recommendations: builtins.list[str]
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
    specific_actions: builtins.list[str] = field(default_factory=list)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


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


class PerformanceProfiler:
    """Advanced performance profiling system."""

    def __init__(self, service_name: str):
        """Initialize performance profiler."""
        self.service_name = service_name
        self.profiles: deque = deque(maxlen=100)
        self.active_profilers: builtins.dict[str, Any] = {}
        self.profiling_enabled = True

        # Resource monitoring
        self.resource_history: deque = deque(maxlen=1440)  # 24 hours at 1-minute intervals
        self.monitoring_thread: threading.Thread | None = None
        self._stop_monitoring = threading.Event()

        # Function call tracking
        self.function_calls: builtins.dict[str, builtins.list[float]] = defaultdict(list)
        self.slow_functions: builtins.set[str] = set()

        # Memory tracking
        self.memory_snapshots: deque = deque(maxlen=50)
        self.memory_leaks: builtins.list[builtins.dict[str, Any]] = []

    def start_resource_monitoring(self):
        """Start resource monitoring in background."""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return

        self._stop_monitoring.clear()
        self.monitoring_thread = threading.Thread(
            target=self._resource_monitoring_loop, daemon=True
        )
        self.monitoring_thread.start()

    def stop_resource_monitoring(self):
        """Stop resource monitoring."""
        self._stop_monitoring.set()
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5.0)

    def _resource_monitoring_loop(self):
        """Resource monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                self._collect_resource_metrics()
                self._stop_monitoring.wait(60)  # Collect every minute
            except Exception as e:
                print(f"Error in resource monitoring: {e}")
                self._stop_monitoring.wait(60)

    def _collect_resource_metrics(self):
        """Collect current resource metrics."""
        try:
            process = psutil.Process()

            metrics = ResourceMetrics(
                timestamp=datetime.now(timezone.utc),
                cpu_percent=process.cpu_percent(),
                memory_percent=process.memory_percent(),
                memory_available=psutil.virtual_memory().available,
                disk_io_read=psutil.disk_io_counters().read_bytes
                if psutil.disk_io_counters()
                else 0,
                disk_io_write=psutil.disk_io_counters().write_bytes
                if psutil.disk_io_counters()
                else 0,
                network_bytes_sent=psutil.net_io_counters().bytes_sent
                if psutil.net_io_counters()
                else 0,
                network_bytes_recv=psutil.net_io_counters().bytes_recv
                if psutil.net_io_counters()
                else 0,
                process_count=len(psutil.pids()),
                thread_count=threading.active_count(),
            )

            self.resource_history.append(metrics)

        except Exception as e:
            print(f"Error collecting resource metrics: {e}")

    @contextmanager
    def profile_function(
        self,
        function_name: str,
        profiler_type: ProfilerType = ProfilerType.CPU_PROFILER,
    ):
        """Context manager for profiling a function."""
        if not self.profiling_enabled:
            yield
            return

        profiler_id = f"{function_name}_{time.time()}"

        try:
            # Start profiling
            if profiler_type == ProfilerType.CPU_PROFILER:
                profiler = cProfile.Profile()
                profiler.enable()
            elif profiler_type == ProfilerType.MEMORY_PROFILER:
                initial_memory = self._get_memory_usage()

            start_time = time.time()

            self.active_profilers[profiler_id] = {
                "type": profiler_type,
                "start_time": start_time,
                "function_name": function_name,
            }

            yield

        finally:
            # Stop profiling and collect results
            end_time = time.time()
            duration = end_time - start_time

            if profiler_id in self.active_profilers:
                del self.active_profilers[profiler_id]

            if profiler_type == ProfilerType.CPU_PROFILER and "profiler" in locals():
                profiler.disable()
                profile_result = self._analyze_cpu_profile(profiler, duration, function_name)
                self.profiles.append(profile_result)
            elif profiler_type == ProfilerType.MEMORY_PROFILER and "initial_memory" in locals():
                final_memory = self._get_memory_usage()
                profile_result = self._analyze_memory_profile(
                    initial_memory, final_memory, duration, function_name
                )
                self.profiles.append(profile_result)

            # Track function call performance
            self.function_calls[function_name].append(duration)
            self._check_slow_function(function_name, duration)

    def _analyze_cpu_profile(
        self, profiler: cProfile.Profile, duration: float, function_name: str
    ) -> PerformanceProfile:
        """Analyze CPU profiling results."""
        # Get profiling stats
        stats_stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stats_stream)
        stats.sort_stats("cumulative")

        # Extract function statistics
        function_stats = {}
        hotspots = []

        for func_key, (cc, _nc, tt, ct, _callers) in stats.stats.items():
            func_name = f"{func_key[0]}:{func_key[1]}:{func_key[2]}"
            function_stats[func_name] = {
                "call_count": cc,
                "total_time": tt,
                "cumulative_time": ct,
                "per_call_time": tt / cc if cc > 0 else 0,
            }

            # Identify hotspots (functions taking >5% of total time)
            if ct > duration * 0.05:
                hotspots.append(func_name)

        # Generate recommendations
        recommendations = self._generate_cpu_recommendations(function_stats, hotspots, duration)

        return PerformanceProfile(
            profiler_type=ProfilerType.CPU_PROFILER,
            duration=duration,
            function_stats=function_stats,
            hotspots=hotspots,
            memory_usage={},
            recommendations=recommendations,
        )

    def _analyze_memory_profile(
        self,
        initial_memory: builtins.dict[str, int],
        final_memory: builtins.dict[str, int],
        duration: float,
        function_name: str,
    ) -> PerformanceProfile:
        """Analyze memory profiling results."""
        memory_diff = {
            key: final_memory.get(key, 0) - initial_memory.get(key, 0)
            for key in set(initial_memory.keys()) | set(final_memory.keys())
        }

        # Generate memory recommendations
        recommendations = self._generate_memory_recommendations(memory_diff, duration)

        return PerformanceProfile(
            profiler_type=ProfilerType.MEMORY_PROFILER,
            duration=duration,
            function_stats={},
            hotspots=[],
            memory_usage=memory_diff,
            recommendations=recommendations,
        )

    def _get_memory_usage(self) -> builtins.dict[str, int]:
        """Get current memory usage statistics."""
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            "rss": memory_info.rss,
            "vms": memory_info.vms,
            "percent": process.memory_percent(),
            "available": psutil.virtual_memory().available,
            "used": psutil.virtual_memory().used,
        }

    def _check_slow_function(self, function_name: str, duration: float):
        """Check if function is consistently slow."""
        calls = self.function_calls[function_name]

        if len(calls) >= 5:  # Need minimum calls for analysis
            avg_duration = sum(calls[-5:]) / 5  # Average of last 5 calls
            if avg_duration > 1.0:  # Threshold: 1 second
                self.slow_functions.add(function_name)

    def _generate_cpu_recommendations(
        self,
        function_stats: builtins.dict[str, builtins.dict[str, float]],
        hotspots: builtins.list[str],
        duration: float,
    ) -> builtins.list[str]:
        """Generate CPU optimization recommendations."""
        recommendations = []

        if hotspots:
            recommendations.append(f"Optimize hotspot functions: {', '.join(hotspots[:3])}")

        # Check for frequent function calls
        frequent_functions = [
            func for func, stats in function_stats.items() if stats["call_count"] > 1000
        ]

        if frequent_functions:
            recommendations.append("Consider caching results for frequently called functions")

        # Check for slow functions
        slow_functions = [
            func
            for func, stats in function_stats.items()
            if stats["per_call_time"] > 0.1  # 100ms per call
        ]

        if slow_functions:
            recommendations.append("Optimize slow functions or consider async execution")

        return recommendations

    def _generate_memory_recommendations(
        self, memory_diff: builtins.dict[str, int], duration: float
    ) -> builtins.list[str]:
        """Generate memory optimization recommendations."""
        recommendations = []

        # Check for memory growth
        rss_growth = memory_diff.get("rss", 0)
        if rss_growth > 100 * 1024 * 1024:  # 100MB growth
            recommendations.append("Significant memory growth detected - check for memory leaks")

        # Check memory usage percentage
        percent_usage = memory_diff.get("percent", 0)
        if percent_usage > 10:  # 10% increase
            recommendations.append("High memory usage increase - consider memory optimization")

        return recommendations

    def get_performance_summary(self) -> builtins.dict[str, Any]:
        """Get performance profiling summary."""
        recent_profiles = list(self.profiles)[-10:]  # Last 10 profiles

        if not recent_profiles:
            return {"message": "No profiling data available"}

        # Aggregate statistics
        total_duration = sum(p.duration for p in recent_profiles)
        avg_duration = total_duration / len(recent_profiles)

        # Most common hotspots
        all_hotspots = []
        for profile in recent_profiles:
            all_hotspots.extend(profile.hotspots)

        hotspot_counts = defaultdict(int)
        for hotspot in all_hotspots:
            hotspot_counts[hotspot] += 1

        top_hotspots = sorted(hotspot_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # Resource utilization
        recent_metrics = list(self.resource_history)[-60:]  # Last hour

        if recent_metrics:
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        else:
            avg_cpu = avg_memory = 0

        return {
            "service": self.service_name,
            "profiling_summary": {
                "total_profiles": len(recent_profiles),
                "average_duration": avg_duration,
                "total_duration": total_duration,
                "top_hotspots": top_hotspots,
            },
            "resource_utilization": {
                "average_cpu_percent": avg_cpu,
                "average_memory_percent": avg_memory,
                "data_points": len(recent_metrics),
            },
            "slow_functions": list(self.slow_functions),
            "recommendations": self._generate_overall_recommendations(),
        }

    def _generate_overall_recommendations(self) -> builtins.list[str]:
        """Generate overall performance recommendations."""
        recommendations = []

        # Resource-based recommendations
        recent_metrics = list(self.resource_history)[-60:]
        if recent_metrics:
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)

            if avg_cpu > 80:
                recommendations.append("High CPU usage detected - consider CPU optimization")
            if avg_memory > 80:
                recommendations.append("High memory usage detected - consider memory optimization")

        # Function-based recommendations
        if self.slow_functions:
            recommendations.append(
                f"Optimize slow functions: {', '.join(list(self.slow_functions)[:3])}"
            )

        return recommendations


class IntelligentCaching:
    """Intelligent caching system with adaptive strategies."""

    def __init__(self, service_name: str):
        """Initialize intelligent caching."""
        self.service_name = service_name

        # Multiple cache layers
        self.l1_cache = LRUCache(maxsize=1000)  # Fast in-memory cache
        self.l2_cache = TTLCache(maxsize=10000, ttl=3600)  # Larger TTL cache
        self.distributed_cache: Any | None = None  # Redis client

        # Cache analytics
        self.cache_stats = defaultdict(lambda: {"hits": 0, "misses": 0, "evictions": 0})
        self.access_patterns = defaultdict(list)
        self.cache_performance = deque(maxlen=1000)

        # Adaptive configuration
        self.cache_strategies: builtins.dict[str, CacheStrategy] = {}
        self.ttl_values: builtins.dict[str, int] = {}
        self.cache_sizes: builtins.dict[str, int] = {}

        # Machine learning for cache optimization
        self.access_predictor = None
        self.cache_efficiency_tracker = defaultdict(float)

    async def initialize_distributed_cache(self, redis_url: str = "redis://localhost:6379"):
        """Initialize distributed cache (Redis)."""
        try:
            self.distributed_cache = redis.from_url(redis_url)
        except Exception as e:
            print(f"Failed to initialize distributed cache: {e}")

    async def get(self, key: str, namespace: str = "default") -> Any | None:
        """Get value from cache with intelligent fallback."""
        start_time = time.time()
        cache_key = f"{namespace}:{key}"

        try:
            # Try L1 cache first (fastest)
            if cache_key in self.l1_cache:
                value = self.l1_cache[cache_key]
                self._record_cache_hit("l1", cache_key, time.time() - start_time)
                return value

            # Try L2 cache
            if cache_key in self.l2_cache:
                value = self.l2_cache[cache_key]
                # Promote to L1 cache
                self.l1_cache[cache_key] = value
                self._record_cache_hit("l2", cache_key, time.time() - start_time)
                return value

            # Try distributed cache
            if self.distributed_cache:
                value = await self.distributed_cache.get(cache_key)
                if value:
                    # Deserialize and promote to local caches
                    deserialized_value = json.loads(value)
                    self.l1_cache[cache_key] = deserialized_value
                    self.l2_cache[cache_key] = deserialized_value
                    self._record_cache_hit("distributed", cache_key, time.time() - start_time)
                    return deserialized_value

            # Cache miss
            self._record_cache_miss(cache_key, time.time() - start_time)
            return None

        except Exception as e:
            print(f"Cache get error for key {cache_key}: {e}")
            self._record_cache_miss(cache_key, time.time() - start_time)
            return None

    async def set(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: int | None = None,
        strategy: CacheStrategy | None = None,
    ) -> bool:
        """Set value in cache with intelligent placement."""
        cache_key = f"{namespace}:{key}"

        try:
            # Determine optimal strategy
            if strategy is None:
                strategy = self._determine_optimal_strategy(cache_key, value)

            # Determine optimal TTL
            if ttl is None:
                ttl = self._determine_optimal_ttl(cache_key)

            # Store in appropriate caches based on strategy
            if strategy in [CacheStrategy.LRU, CacheStrategy.WRITE_THROUGH]:
                self.l1_cache[cache_key] = value
                self.l2_cache[cache_key] = value

            # Store in distributed cache if available
            if self.distributed_cache and strategy != CacheStrategy.WRITE_AROUND:
                serialized_value = json.dumps(value, default=str)
                await self.distributed_cache.setex(cache_key, ttl or 3600, serialized_value)

            # Update strategy and TTL mappings
            self.cache_strategies[cache_key] = strategy
            self.ttl_values[cache_key] = ttl or 3600

            return True

        except Exception as e:
            print(f"Cache set error for key {cache_key}: {e}")
            return False

    async def invalidate(self, key: str, namespace: str = "default") -> bool:
        """Invalidate cache entry across all layers."""
        cache_key = f"{namespace}:{key}"

        try:
            # Remove from local caches
            self.l1_cache.pop(cache_key, None)
            self.l2_cache.pop(cache_key, None)

            # Remove from distributed cache
            if self.distributed_cache:
                await self.distributed_cache.delete(cache_key)

            return True

        except Exception as e:
            print(f"Cache invalidation error for key {cache_key}: {e}")
            return False

    def _determine_optimal_strategy(self, cache_key: str, value: Any) -> CacheStrategy:
        """Determine optimal caching strategy for a key."""
        # Analyze access patterns
        accesses = self.access_patterns[cache_key]

        if len(accesses) < 5:
            return CacheStrategy.LRU  # Default for new keys

        # Calculate access frequency
        now = time.time()
        recent_accesses = [t for t in accesses if now - t < 3600]  # Last hour
        access_frequency = len(recent_accesses)

        # Determine value size (approximate)
        value_size = len(str(value))

        # Strategy selection logic
        if access_frequency > 10 and value_size < 1024:  # Frequent small objects
            return CacheStrategy.LRU
        if value_size > 10240:  # Large objects
            return CacheStrategy.WRITE_AROUND
        return CacheStrategy.TTL

    def _determine_optimal_ttl(self, cache_key: str) -> int:
        """Determine optimal TTL for a cache key."""
        accesses = self.access_patterns[cache_key]

        if len(accesses) < 2:
            return 3600  # Default 1 hour

        # Calculate access intervals
        intervals = []
        for i in range(1, len(accesses)):
            intervals.append(accesses[i] - accesses[i - 1])

        if intervals:
            # Use median interval as basis for TTL
            median_interval = sorted(intervals)[len(intervals) // 2]
            optimal_ttl = int(median_interval * 2)  # 2x median interval

            # Bounds checking
            return max(300, min(86400, optimal_ttl))  # 5 minutes to 24 hours

        return 3600

    def _record_cache_hit(self, cache_layer: str, cache_key: str, duration: float):
        """Record cache hit statistics."""
        self.cache_stats[cache_layer]["hits"] += 1
        self.access_patterns[cache_key].append(time.time())

        self.cache_performance.append(
            {
                "type": "hit",
                "layer": cache_layer,
                "key": cache_key,
                "duration": duration,
                "timestamp": time.time(),
            }
        )

    def _record_cache_miss(self, cache_key: str, duration: float):
        """Record cache miss statistics."""
        self.cache_stats["total"]["misses"] += 1

        self.cache_performance.append(
            {
                "type": "miss",
                "key": cache_key,
                "duration": duration,
                "timestamp": time.time(),
            }
        )

    def get_cache_analytics(self) -> builtins.dict[str, Any]:
        """Get comprehensive cache analytics."""
        # Calculate hit rates
        hit_rates = {}
        for layer, stats in self.cache_stats.items():
            total_requests = stats["hits"] + stats["misses"]
            hit_rates[layer] = stats["hits"] / total_requests if total_requests > 0 else 0

        # Analyze performance
        recent_performance = list(self.cache_performance)[-100:]

        hit_durations = [p["duration"] for p in recent_performance if p["type"] == "hit"]
        miss_durations = [p["duration"] for p in recent_performance if p["type"] == "miss"]

        avg_hit_duration = sum(hit_durations) / len(hit_durations) if hit_durations else 0
        avg_miss_duration = sum(miss_durations) / len(miss_durations) if miss_durations else 0

        # Cache efficiency by strategy
        strategy_efficiency = {}
        for key, strategy in self.cache_strategies.items():
            key_hits = sum(
                1 for p in recent_performance if p.get("key") == key and p["type"] == "hit"
            )
            key_total = sum(1 for p in recent_performance if p.get("key") == key)

            if key_total > 0:
                efficiency = key_hits / key_total
                strategy_name = strategy.value

                if strategy_name not in strategy_efficiency:
                    strategy_efficiency[strategy_name] = []
                strategy_efficiency[strategy_name].append(efficiency)

        # Average efficiency by strategy
        avg_strategy_efficiency = {
            strategy: sum(efficiencies) / len(efficiencies)
            for strategy, efficiencies in strategy_efficiency.items()
        }

        return {
            "service": self.service_name,
            "hit_rates": hit_rates,
            "performance": {
                "average_hit_duration": avg_hit_duration,
                "average_miss_duration": avg_miss_duration,
                "total_operations": len(recent_performance),
            },
            "cache_sizes": {
                "l1_cache": len(self.l1_cache),
                "l2_cache": len(self.l2_cache),
            },
            "strategy_efficiency": avg_strategy_efficiency,
            "recommendations": self._generate_cache_recommendations(),
        }

    def _generate_cache_recommendations(self) -> builtins.list[str]:
        """Generate cache optimization recommendations."""
        recommendations = []

        # Analyze hit rates
        overall_hit_rate = self._calculate_overall_hit_rate()

        if overall_hit_rate < 0.7:
            recommendations.append("Consider increasing cache sizes or adjusting TTL values")

        # Analyze cache efficiency
        if len(self.l1_cache) == self.l1_cache.maxsize:
            recommendations.append("L1 cache is full - consider increasing size")

        if len(self.l2_cache) == self.l2_cache.maxsize:
            recommendations.append("L2 cache is full - consider increasing size or reducing TTL")

        # Strategy recommendations
        low_efficiency_strategies = [
            strategy
            for strategy, efficiency in self._get_strategy_efficiency().items()
            if efficiency < 0.5
        ]

        if low_efficiency_strategies:
            recommendations.append(
                f"Review caching strategies: {', '.join(low_efficiency_strategies)}"
            )

        return recommendations

    def _calculate_overall_hit_rate(self) -> float:
        """Calculate overall cache hit rate."""
        total_hits = sum(stats["hits"] for stats in self.cache_stats.values())
        total_misses = sum(stats["misses"] for stats in self.cache_stats.values())
        total_requests = total_hits + total_misses

        return total_hits / total_requests if total_requests > 0 else 0

    def _get_strategy_efficiency(self) -> builtins.dict[str, float]:
        """Get efficiency by caching strategy."""
        strategy_performance = defaultdict(list)

        for performance_data in self.cache_performance:
            key = performance_data.get("key")
            if key and key in self.cache_strategies:
                strategy = self.cache_strategies[key].value
                is_hit = performance_data["type"] == "hit"
                strategy_performance[strategy].append(1 if is_hit else 0)

        return {
            strategy: sum(hits) / len(hits) if hits else 0
            for strategy, hits in strategy_performance.items()
        }


class ResourceOptimizer:
    """Resource optimization engine."""

    def __init__(self, service_name: str):
        """Initialize resource optimizer."""
        self.service_name = service_name
        self.optimization_history: deque = deque(maxlen=100)
        self.resource_targets: builtins.dict[str, float] = {
            "cpu_utilization": 0.7,  # Target 70% CPU utilization
            "memory_utilization": 0.8,  # Target 80% memory utilization
            "response_time": 200,  # Target 200ms response time
            "throughput": 1000,  # Target 1000 requests/second
        }

        # Optimization strategies
        self.optimization_strategies: builtins.dict[OptimizationType, Callable] = {
            OptimizationType.CPU_OPTIMIZATION: self._optimize_cpu,
            OptimizationType.MEMORY_OPTIMIZATION: self._optimize_memory,
            OptimizationType.IO_OPTIMIZATION: self._optimize_io,
            OptimizationType.CACHE_OPTIMIZATION: self._optimize_cache,
        }

    def analyze_and_optimize(
        self,
        resource_metrics: ResourceMetrics,
        performance_data: builtins.dict[str, Any],
    ) -> builtins.list[OptimizationRecommendation]:
        """Analyze current state and generate optimization recommendations."""
        recommendations = []

        # CPU optimization
        if resource_metrics.cpu_percent > self.resource_targets["cpu_utilization"] * 100:
            cpu_recommendations = self._optimize_cpu(resource_metrics, performance_data)
            recommendations.extend(cpu_recommendations)

        # Memory optimization
        if resource_metrics.memory_percent > self.resource_targets["memory_utilization"] * 100:
            memory_recommendations = self._optimize_memory(resource_metrics, performance_data)
            recommendations.extend(memory_recommendations)

        # IO optimization
        if self._is_io_bottleneck(resource_metrics):
            io_recommendations = self._optimize_io(resource_metrics, performance_data)
            recommendations.extend(io_recommendations)

        # Cache optimization
        cache_recommendations = self._optimize_cache(resource_metrics, performance_data)
        recommendations.extend(cache_recommendations)

        # Sort by priority and estimated impact
        recommendations.sort(key=lambda x: (x.priority, x.estimated_impact), reverse=True)

        return recommendations

    def _optimize_cpu(
        self,
        resource_metrics: ResourceMetrics,
        performance_data: builtins.dict[str, Any],
    ) -> builtins.list[OptimizationRecommendation]:
        """Generate CPU optimization recommendations."""
        recommendations = []

        cpu_usage = resource_metrics.cpu_percent

        if cpu_usage > 90:
            recommendations.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.CPU_OPTIMIZATION,
                    title="Critical CPU Usage",
                    description=f"CPU usage is at {cpu_usage:.1f}%, immediate optimization needed",
                    priority=9,
                    estimated_impact=0.3,
                    implementation_effort="medium",
                    specific_actions=[
                        "Implement horizontal scaling",
                        "Optimize hot code paths",
                        "Consider async processing for CPU-intensive tasks",
                        "Review and optimize algorithms",
                    ],
                )
            )
        elif cpu_usage > 80:
            recommendations.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.CPU_OPTIMIZATION,
                    title="High CPU Usage",
                    description=f"CPU usage is at {cpu_usage:.1f}%, optimization recommended",
                    priority=6,
                    estimated_impact=0.2,
                    implementation_effort="low",
                    specific_actions=[
                        "Profile CPU usage patterns",
                        "Optimize frequently called functions",
                        "Consider caching CPU-intensive calculations",
                        "Review concurrency patterns",
                    ],
                )
            )

        return recommendations

    def _optimize_memory(
        self,
        resource_metrics: ResourceMetrics,
        performance_data: builtins.dict[str, Any],
    ) -> builtins.list[OptimizationRecommendation]:
        """Generate memory optimization recommendations."""
        recommendations = []

        memory_usage = resource_metrics.memory_percent

        if memory_usage > 95:
            recommendations.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.MEMORY_OPTIMIZATION,
                    title="Critical Memory Usage",
                    description=f"Memory usage is at {memory_usage:.1f}%, immediate action needed",
                    priority=10,
                    estimated_impact=0.4,
                    implementation_effort="high",
                    specific_actions=[
                        "Immediately increase memory allocation",
                        "Investigate memory leaks",
                        "Implement memory profiling",
                        "Review large object allocations",
                        "Consider memory-efficient data structures",
                    ],
                )
            )
        elif memory_usage > 85:
            recommendations.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.MEMORY_OPTIMIZATION,
                    title="High Memory Usage",
                    description=f"Memory usage is at {memory_usage:.1f}%, optimization needed",
                    priority=7,
                    estimated_impact=0.25,
                    implementation_effort="medium",
                    specific_actions=[
                        "Implement garbage collection tuning",
                        "Optimize data structures",
                        "Review caching strategies",
                        "Consider object pooling",
                        "Monitor memory allocation patterns",
                    ],
                )
            )

        return recommendations

    def _optimize_io(
        self,
        resource_metrics: ResourceMetrics,
        performance_data: builtins.dict[str, Any],
    ) -> builtins.list[OptimizationRecommendation]:
        """Generate I/O optimization recommendations."""
        recommendations = []

        # Check for high I/O operations
        read_rate = resource_metrics.disk_io_read
        write_rate = resource_metrics.disk_io_write

        high_io_threshold = 100 * 1024 * 1024  # 100 MB/s

        if read_rate > high_io_threshold or write_rate > high_io_threshold:
            recommendations.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.IO_OPTIMIZATION,
                    title="High I/O Usage Detected",
                    description=f"Disk I/O is high: {read_rate / 1024 / 1024:.1f}MB/s read, {write_rate / 1024 / 1024:.1f}MB/s write",
                    priority=5,
                    estimated_impact=0.2,
                    implementation_effort="medium",
                    specific_actions=[
                        "Implement I/O batching",
                        "Consider async I/O operations",
                        "Optimize database queries",
                        "Implement connection pooling",
                        "Review file access patterns",
                    ],
                )
            )

        return recommendations

    def _optimize_cache(
        self,
        resource_metrics: ResourceMetrics,
        performance_data: builtins.dict[str, Any],
    ) -> builtins.list[OptimizationRecommendation]:
        """Generate cache optimization recommendations."""
        recommendations = []

        # This would integrate with the IntelligentCaching component
        cache_hit_rate = performance_data.get("cache_hit_rate", 0.5)

        if cache_hit_rate < 0.5:
            recommendations.append(
                OptimizationRecommendation(
                    optimization_type=OptimizationType.CACHE_OPTIMIZATION,
                    title="Low Cache Hit Rate",
                    description=f"Cache hit rate is {cache_hit_rate:.1%}, optimization needed",
                    priority=4,
                    estimated_impact=0.15,
                    implementation_effort="low",
                    specific_actions=[
                        "Review caching strategies",
                        "Increase cache sizes",
                        "Optimize cache TTL values",
                        "Implement cache warming",
                        "Consider distributed caching",
                    ],
                )
            )

        return recommendations

    def _is_io_bottleneck(self, resource_metrics: ResourceMetrics) -> bool:
        """Determine if I/O is a bottleneck."""
        # Simple heuristic: high I/O with low CPU might indicate I/O bottleneck
        high_io = (
            resource_metrics.disk_io_read + resource_metrics.disk_io_write
        ) > 50 * 1024 * 1024  # 50MB/s
        low_cpu = resource_metrics.cpu_percent < 50

        return high_io and low_cpu

    def apply_optimization(
        self, recommendation: OptimizationRecommendation
    ) -> builtins.dict[str, Any]:
        """Apply an optimization recommendation."""
        result = {
            "recommendation_id": recommendation.title,
            "applied": False,
            "result": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            if recommendation.optimization_type in self.optimization_strategies:
                self.optimization_strategies[recommendation.optimization_type]
                # Note: This is a simplified implementation
                # In practice, these would trigger actual system changes

                result["applied"] = True
                result["result"] = f"Applied {recommendation.optimization_type.value} optimization"

                # Record optimization
                self.optimization_history.append(
                    {
                        "recommendation": recommendation,
                        "result": result,
                        "timestamp": datetime.now(timezone.utc),
                    }
                )

        except Exception as e:
            result["result"] = f"Error applying optimization: {e}"

        return result


class PerformanceOptimizationEngine:
    """Main performance optimization engine."""

    def __init__(self, service_name: str):
        """Initialize performance optimization engine."""
        self.service_name = service_name

        # Core components
        self.profiler = PerformanceProfiler(service_name)
        self.caching = IntelligentCaching(service_name)
        self.optimizer = ResourceOptimizer(service_name)

        # Optimization state
        self.optimization_enabled = True
        self.auto_optimization = False
        self.optimization_results: deque = deque(maxlen=100)

        # Performance monitoring
        self.performance_baseline: builtins.dict[str, float] = {}
        self.performance_trends: builtins.dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

    async def start_optimization_engine(self):
        """Start the performance optimization engine."""
        # Start profiler monitoring
        self.profiler.start_resource_monitoring()

        # Initialize distributed cache if available
        await self.caching.initialize_distributed_cache()

        # Start optimization loop if auto-optimization is enabled
        if self.auto_optimization:
            asyncio.create_task(self._optimization_loop())

    async def stop_optimization_engine(self):
        """Stop the performance optimization engine."""
        self.profiler.stop_resource_monitoring()
        self.optimization_enabled = False

    async def _optimization_loop(self):
        """Main optimization loop."""
        while self.optimization_enabled:
            try:
                # Get current performance data
                performance_data = await self._collect_performance_data()

                # Generate recommendations
                recommendations = await self._generate_recommendations(performance_data)

                # Apply high-priority optimizations automatically
                for recommendation in recommendations:
                    if (
                        recommendation.priority >= 8
                        and recommendation.implementation_effort == "low"
                    ):
                        result = self.optimizer.apply_optimization(recommendation)
                        self.optimization_results.append(result)

                # Wait before next optimization cycle
                await asyncio.sleep(300)  # 5 minutes

            except Exception as e:
                print(f"Error in optimization loop: {e}")
                await asyncio.sleep(60)

    async def _collect_performance_data(self) -> builtins.dict[str, Any]:
        """Collect comprehensive performance data."""
        # Get profiler data
        profiler_summary = self.profiler.get_performance_summary()

        # Get cache analytics
        cache_analytics = self.caching.get_cache_analytics()

        # Get latest resource metrics
        resource_metrics = None
        if self.profiler.resource_history:
            resource_metrics = self.profiler.resource_history[-1]

        return {
            "profiler": profiler_summary,
            "cache": cache_analytics,
            "resources": resource_metrics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _generate_recommendations(
        self, performance_data: builtins.dict[str, Any]
    ) -> builtins.list[OptimizationRecommendation]:
        """Generate comprehensive optimization recommendations."""
        recommendations = []

        # Resource-based recommendations
        if performance_data["resources"]:
            resource_recommendations = self.optimizer.analyze_and_optimize(
                performance_data["resources"], performance_data
            )
            recommendations.extend(resource_recommendations)

        # Cache-based recommendations
        cache_data = performance_data.get("cache", {})
        if cache_data.get("recommendations"):
            for cache_rec in cache_data["recommendations"]:
                recommendations.append(
                    OptimizationRecommendation(
                        optimization_type=OptimizationType.CACHE_OPTIMIZATION,
                        title="Cache Optimization",
                        description=cache_rec,
                        priority=3,
                        estimated_impact=0.1,
                        implementation_effort="low",
                        specific_actions=[cache_rec],
                    )
                )

        # Profiler-based recommendations
        profiler_data = performance_data.get("profiler", {})
        if profiler_data.get("recommendations"):
            for prof_rec in profiler_data["recommendations"]:
                recommendations.append(
                    OptimizationRecommendation(
                        optimization_type=OptimizationType.CPU_OPTIMIZATION,
                        title="Profiler Recommendation",
                        description=prof_rec,
                        priority=5,
                        estimated_impact=0.15,
                        implementation_effort="medium",
                        specific_actions=[prof_rec],
                    )
                )

        return recommendations

    def get_optimization_status(self) -> builtins.dict[str, Any]:
        """Get comprehensive optimization status."""
        return {
            "service": self.service_name,
            "optimization_enabled": self.optimization_enabled,
            "auto_optimization": self.auto_optimization,
            "profiler_status": self.profiler.get_performance_summary(),
            "cache_status": self.caching.get_cache_analytics(),
            "recent_optimizations": len(self.optimization_results),
            "performance_trends": {
                name: list(trend)[-10:] for name, trend in self.performance_trends.items()
            },
        }


def create_performance_optimization_engine(
    service_name: str,
) -> PerformanceOptimizationEngine:
    """Create performance optimization engine instance."""
    return PerformanceOptimizationEngine(service_name)
