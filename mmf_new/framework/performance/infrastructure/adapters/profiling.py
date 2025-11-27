"""
Profiling Infrastructure Adapters.
"""

import cProfile
import io
import pstats
import time
from collections.abc import Callable
from typing import Any

from mmf_new.framework.performance.domain.entities import (
    PerformanceProfile,
    ProfilerType,
)
from mmf_new.framework.performance.domain.ports import ProfilerPort


class CProfileAdapter(ProfilerPort):
    """Profiler implementation using cProfile."""

    async def profile_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> tuple[Any, PerformanceProfile]:
        """Profile an async function execution."""
        profiler = cProfile.Profile()
        profiler.enable()
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)
        finally:
            profiler.disable()
            end_time = time.time()

        profile_data = self._process_stats(profiler, end_time - start_time)
        return result, profile_data

    def profile(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> tuple[Any, PerformanceProfile]:
        """Profile a synchronous function execution."""
        profiler = cProfile.Profile()
        profiler.enable()
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
        finally:
            profiler.disable()
            end_time = time.time()

        profile_data = self._process_stats(profiler, end_time - start_time)
        return result, profile_data

    def _process_stats(self, profiler: cProfile.Profile, duration: float) -> PerformanceProfile:
        """Process cProfile stats into PerformanceProfile."""
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
        ps.print_stats(20)  # Top 20 lines

        # Extract stats
        function_stats: dict[str, dict[str, float]] = {}
        hotspots: list[str] = []

        # pstats.stats is a dict: (filename, line, funcname) -> (cc, nc, tt, ct, callers)
        # cc: primitive calls, nc: number of calls, tt: total time, ct: cumulative time
        for func_tuple, (_cc, nc, tt, ct, _callers) in ps.stats.items():  # type: ignore
            func_name = f"{func_tuple[2]} ({func_tuple[0]}:{func_tuple[1]})"
            function_stats[func_name] = {
                "calls": float(nc),
                "total_time": tt,
                "cumulative_time": ct,
                "per_call": ct / nc if nc > 0 else 0,
            }

            # Identify hotspots (simple heuristic: > 10% of total duration)
            if duration > 0 and ct / duration > 0.1:
                hotspots.append(func_name)

        # Sort hotspots by cumulative time
        hotspots.sort(key=lambda x: function_stats[x]["cumulative_time"], reverse=True)

        return PerformanceProfile(
            profiler_type=ProfilerType.CPU_PROFILER,
            duration=duration,
            function_stats=function_stats,
            hotspots=hotspots[:10],  # Top 10 hotspots
            memory_usage={},  # cProfile doesn't track memory
            recommendations=[],  # To be filled by analyzer
        )
