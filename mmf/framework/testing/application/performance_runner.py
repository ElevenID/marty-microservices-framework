import asyncio
import json
import logging
import random
import statistics
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any

import aiohttp
import numpy as np

from mmf.framework.testing.domain.entities import (
    TestMetrics,
    TestResult,
    TestSeverity,
    TestStatus,
    TestType,
)
from mmf.framework.testing.domain.performance import (
    LoadConfiguration,
    LoadPattern,
    PerformanceMetrics,
    PerformanceTestType,
    RequestSpec,
    ResponseMetric,
)

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and aggregates performance metrics."""

    def __init__(self):
        self.raw_metrics: list[ResponseMetric] = []
        self.real_time_metrics = deque(maxlen=1000)  # Last 1000 requests for real-time monitoring
        self.lock = threading.Lock()
        self.start_time: float | None = None
        self.end_time: float | None = None

    def start_collection(self):
        """Start metrics collection."""
        self.start_time = time.time()

    def stop_collection(self):
        """Stop metrics collection."""
        self.end_time = time.time()

    def record_response(self, metric: ResponseMetric):
        """Record a response metric."""
        with self.lock:
            self.raw_metrics.append(metric)
            self.real_time_metrics.append(metric)

    def get_aggregated_metrics(self) -> PerformanceMetrics:
        """Get aggregated performance metrics."""
        with self.lock:
            if not self.raw_metrics:
                return PerformanceMetrics()

            metrics = PerformanceMetrics()

            # Basic counts
            metrics.total_requests = len(self.raw_metrics)
            metrics.successful_requests = sum(1 for m in self.raw_metrics if m.error is None)
            metrics.failed_requests = metrics.total_requests - metrics.successful_requests
            metrics.error_rate = (
                metrics.failed_requests / metrics.total_requests
                if metrics.total_requests > 0
                else 0
            )

            # Response time metrics
            response_times = [m.response_time for m in self.raw_metrics if m.error is None]
            if response_times:
                metrics.response_times = response_times
                metrics.min_response_time = min(response_times)
                metrics.max_response_time = max(response_times)
                metrics.avg_response_time = statistics.mean(response_times)
                metrics.calculate_percentiles()

            # Throughput metrics
            if self.start_time and self.end_time:
                duration = self.end_time - self.start_time
                metrics.requests_per_second = metrics.total_requests / duration

                total_bytes = sum(m.response_size for m in self.raw_metrics)
                metrics.bytes_per_second = total_bytes / duration

            # Error breakdown
            for metric in self.raw_metrics:
                if metric.error:
                    metrics.error_breakdown[metric.error] = (
                        metrics.error_breakdown.get(metric.error, 0) + 1
                    )

                metrics.status_code_breakdown[metric.status_code] = (
                    metrics.status_code_breakdown.get(metric.status_code, 0) + 1
                )

            # Time series data
            metrics.timestamps = [m.timestamp for m in self.raw_metrics]

            return metrics

    def get_real_time_metrics(self, window_seconds: int = 10) -> dict[str, Any]:
        """Get real-time metrics for the last N seconds."""
        with self.lock:
            current_time = time.time()
            cutoff_time = current_time - window_seconds

            recent_metrics = [m for m in self.real_time_metrics if m.timestamp >= cutoff_time]

            if not recent_metrics:
                return {"rps": 0, "avg_response_time": 0, "error_rate": 0}

            successful = [m for m in recent_metrics if m.error is None]

            rps = len(recent_metrics) / window_seconds
            avg_response_time = (
                statistics.mean([m.response_time for m in successful]) if successful else 0
            )
            error_rate = (len(recent_metrics) - len(successful)) / len(recent_metrics)

            return {
                "rps": rps,
                "avg_response_time": avg_response_time,
                "error_rate": error_rate,
                "active_requests": len(recent_metrics),
            }


class LoadGenerator:
    """Generates load based on specified patterns."""

    def __init__(self, request_spec: RequestSpec, load_config: LoadConfiguration):
        self.request_spec = request_spec
        self.load_config = load_config
        self.metrics_collector = MetricsCollector()
        self.session: aiohttp.ClientSession | None = None
        self.active_tasks: list[asyncio.Task] = []
        self.stop_event = asyncio.Event()

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

        # Cancel any remaining tasks
        for task in self.active_tasks:
            if not task.done():
                task.cancel()

        if self.active_tasks:
            await asyncio.gather(*self.active_tasks, return_exceptions=True)

    async def run_load_test(self) -> PerformanceMetrics:
        """Run the load test according to configuration."""
        logger.info(f"Starting load test with pattern: {self.load_config.pattern}")

        self.metrics_collector.start_collection()

        try:
            if self.load_config.pattern == LoadPattern.CONSTANT:
                await self._run_constant_load()
            elif self.load_config.pattern == LoadPattern.RAMP_UP:
                await self._run_ramp_up_load()
            elif self.load_config.pattern == LoadPattern.STEP:
                await self._run_step_load()
            elif self.load_config.pattern == LoadPattern.SPIKE:
                await self._run_spike_load()
            elif self.load_config.pattern == LoadPattern.WAVE:
                await self._run_wave_load()
            else:
                raise ValueError(f"Unsupported load pattern: {self.load_config.pattern}")

        finally:
            self.metrics_collector.stop_collection()

        return self.metrics_collector.get_aggregated_metrics()

    async def _run_constant_load(self):
        """Run constant load test."""
        duration = self.load_config.duration or self.load_config.hold_duration

        # Start user tasks
        for user_id in range(self.load_config.max_users):
            task = asyncio.create_task(self._user_session(user_id, duration))
            self.active_tasks.append(task)

        # Wait for completion
        await asyncio.sleep(duration)
        self.stop_event.set()

        # Wait for all user sessions to complete
        await asyncio.gather(*self.active_tasks, return_exceptions=True)

    async def _run_ramp_up_load(self):
        """Run ramp-up load test."""
        ramp_duration = self.load_config.ramp_duration
        hold_duration = self.load_config.hold_duration
        max_users = self.load_config.max_users

        # Calculate user start intervals
        user_interval = ramp_duration / max_users if max_users > 0 else 0

        # Start users gradually
        for user_id in range(max_users):
            task = asyncio.create_task(self._user_session(user_id, ramp_duration + hold_duration))
            self.active_tasks.append(task)

            if user_id < max_users - 1:  # Don't wait after the last user
                await asyncio.sleep(user_interval)

        # Hold the load
        await asyncio.sleep(hold_duration)
        self.stop_event.set()

        # Wait for all sessions to complete
        await asyncio.gather(*self.active_tasks, return_exceptions=True)

    async def _run_step_load(self):
        """Run step load test."""
        max_users = self.load_config.max_users
        initial_users = self.load_config.initial_users
        hold_duration = self.load_config.hold_duration

        # Define steps (for simplicity, use 4 steps)
        steps = 4
        users_per_step = (max_users - initial_users) // steps
        step_duration = hold_duration // steps

        current_users = initial_users

        for step in range(steps + 1):
            # Start new users for this step
            if step > 0:
                new_users = users_per_step if step < steps else (max_users - current_users)
                for user_id in range(current_users, current_users + new_users):
                    task = asyncio.create_task(
                        self._user_session(user_id, hold_duration - (step * step_duration))
                    )
                    self.active_tasks.append(task)
                current_users += new_users
            else:
                # Start initial users
                for user_id in range(initial_users):
                    task = asyncio.create_task(self._user_session(user_id, hold_duration))
                    self.active_tasks.append(task)

            if step < steps:
                await asyncio.sleep(step_duration)

        self.stop_event.set()
        await asyncio.gather(*self.active_tasks, return_exceptions=True)

    async def _run_spike_load(self):
        """Run spike load test."""
        normal_users = self.load_config.initial_users
        spike_users = self.load_config.max_users
        spike_duration = 30  # 30 seconds spike
        total_duration = self.load_config.hold_duration

        # Start normal load
        for user_id in range(normal_users):
            task = asyncio.create_task(self._user_session(user_id, total_duration))
            self.active_tasks.append(task)

        # Wait for baseline period
        baseline_duration = (total_duration - spike_duration) // 2
        await asyncio.sleep(baseline_duration)

        # Start spike users
        spike_tasks = []
        for user_id in range(normal_users, spike_users):
            task = asyncio.create_task(self._user_session(user_id, spike_duration))
            spike_tasks.append(task)
            self.active_tasks.append(task)

        # Wait for spike to complete
        await asyncio.sleep(spike_duration)

        # Wait for remaining baseline period
        await asyncio.sleep(total_duration - baseline_duration - spike_duration)

        self.stop_event.set()
        await asyncio.gather(*self.active_tasks, return_exceptions=True)

    async def _run_wave_load(self):
        """Run wave pattern load test."""
        max_users = self.load_config.max_users
        min_users = self.load_config.initial_users
        wave_duration = self.load_config.hold_duration
        wave_cycles = 3  # Number of wave cycles

        cycle_duration = wave_duration / wave_cycles

        for cycle in range(wave_cycles):
            # Ramp up
            for user_count in range(min_users, max_users + 1, (max_users - min_users) // 10):
                # Adjust user count
                current_task_count = len([t for t in self.active_tasks if not t.done()])

                if user_count > current_task_count:
                    # Add users
                    for user_id in range(current_task_count, user_count):
                        task = asyncio.create_task(
                            self._user_session(user_id, wave_duration - (cycle * cycle_duration))
                        )
                        self.active_tasks.append(task)

                await asyncio.sleep(cycle_duration / 20)  # Small interval for smooth wave

            # Hold peak briefly
            await asyncio.sleep(cycle_duration / 4)

            # Ramp down (by letting some tasks complete naturally)
            await asyncio.sleep(cycle_duration / 4)

        self.stop_event.set()
        await asyncio.gather(*self.active_tasks, return_exceptions=True)

    async def _user_session(self, user_id: int, max_duration: float):
        """Simulate a user session."""
        start_time = time.time()
        iteration = 0

        while not self.stop_event.is_set() and (time.time() - start_time) < max_duration:
            # Check iteration limit
            if (
                self.load_config.iterations_per_user
                and iteration >= self.load_config.iterations_per_user
            ):
                break

            # Make request
            await self._make_request(user_id, iteration)

            # Think time
            think_time = self._calculate_think_time()
            if think_time > 0:
                await asyncio.sleep(think_time)

            iteration += 1

    async def _make_request(self, user_id: int, iteration: int):
        """Make a single request and record metrics."""
        start_time = time.time()
        request_size = 0
        response_size = 0
        error = None
        status_code = 0

        try:
            # Prepare request data
            if isinstance(self.request_spec.body, str):
                request_size = len(self.request_spec.body.encode("utf-8"))
            elif self.request_spec.body:
                request_size = len(json.dumps(self.request_spec.body).encode("utf-8"))

            # Make request
            async with self.session.request(
                method=self.request_spec.method,
                url=self.request_spec.url,
                headers=self.request_spec.headers,
                params=self.request_spec.params,
                json=self.request_spec.body
                if self.request_spec.method in ["POST", "PUT", "PATCH"]
                else None,
                timeout=aiohttp.ClientTimeout(total=self.request_spec.timeout),
            ) as response:
                status_code = response.status
                response_data = await response.read()
                response_size = len(response_data)

                # Check if status code is expected
                if status_code not in self.request_spec.expected_status_codes:
                    error = f"Unexpected status code: {status_code}"

        except asyncio.TimeoutError:
            error = "Request timeout"
        except aiohttp.ClientError as e:
            error = f"Client error: {e!s}"
        except Exception as e:
            error = f"Unexpected error: {e!s}"

        # Record metrics
        response_time = time.time() - start_time
        metric = ResponseMetric(
            timestamp=start_time,
            response_time=response_time,
            status_code=status_code,
            error=error,
            request_size=request_size,
            response_size=response_size,
        )

        self.metrics_collector.record_response(metric)

    def _calculate_think_time(self) -> float:
        """Calculate think time with variation."""
        base_time = self.load_config.think_time
        variation = self.load_config.think_time_variation

        # Add random variation

        variation_factor = 1 + random.uniform(-variation, variation)
        return max(0, base_time * variation_factor)


class PerformanceRunner:
    """Executes performance tests."""

    def __init__(
        self,
        name: str,
        request_spec: RequestSpec,
        load_config: LoadConfiguration,
        test_type: PerformanceTestType = PerformanceTestType.LOAD_TEST,
        performance_criteria: dict[str, Any] = None,
    ):
        self.name = name
        self.request_spec = request_spec
        self.load_config = load_config
        self.performance_test_type = test_type
        self.performance_criteria = performance_criteria or {}
        self.load_generator: LoadGenerator | None = None

    async def run(self) -> TestResult:
        """Execute performance test."""
        start_time = datetime.utcnow()
        test_id = f"perf-{int(time.time())}"

        try:
            async with LoadGenerator(self.request_spec, self.load_config) as generator:
                self.load_generator = generator
                metrics = await generator.run_load_test()

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            # Evaluate performance criteria
            criteria_results = self._evaluate_criteria(metrics)

            # Determine test status
            if all(criteria_results.values()):
                status = TestStatus.PASSED
                severity = TestSeverity.LOW
                error_message = None
            else:
                status = TestStatus.FAILED
                severity = TestSeverity.HIGH
                failed_criteria = [k for k, v in criteria_results.items() if not v]
                error_message = f"Performance criteria failed: {', '.join(failed_criteria)}"

            return TestResult(
                test_id=test_id,
                name=f"Performance Test: {self.name}",
                test_type=TestType.PERFORMANCE,
                status=status,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                error_message=error_message,
                severity=severity,
                metrics=TestMetrics(
                    execution_time=execution_time,
                    custom_metrics={
                        "performance_type": self.performance_test_type.value,
                        "total_requests": metrics.total_requests,
                        "requests_per_second": metrics.requests_per_second,
                        "avg_response_time": metrics.avg_response_time,
                        "p95_response_time": metrics.p95_response_time,
                        "error_rate": metrics.error_rate,
                        "criteria_results": criteria_results,
                    },
                ),
                artifacts={
                    "performance_metrics": metrics.to_dict(),
                    "load_configuration": {
                        "pattern": self.load_config.pattern.value,
                        "max_users": self.load_config.max_users,
                        "duration": self.load_config.duration or self.load_config.hold_duration,
                    },
                },
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return TestResult(
                test_id=test_id,
                name=f"Performance Test: {self.name}",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.ERROR,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                error_message=str(e),
                severity=TestSeverity.CRITICAL,
            )

    def _evaluate_criteria(self, metrics: PerformanceMetrics) -> dict[str, bool]:
        """Evaluate performance criteria."""
        results = {}

        # Check response time criteria
        if "max_response_time" in self.performance_criteria:
            results["max_response_time"] = (
                metrics.max_response_time <= self.performance_criteria["max_response_time"]
            )

        if "avg_response_time" in self.performance_criteria:
            results["avg_response_time"] = (
                metrics.avg_response_time <= self.performance_criteria["avg_response_time"]
            )

        if "p95_response_time" in self.performance_criteria:
            results["p95_response_time"] = (
                metrics.p95_response_time <= self.performance_criteria["p95_response_time"]
            )

        # Check throughput criteria
        if "min_requests_per_second" in self.performance_criteria:
            results["min_requests_per_second"] = (
                metrics.requests_per_second >= self.performance_criteria["min_requests_per_second"]
            )

        # Check error rate criteria
        if "max_error_rate" in self.performance_criteria:
            results["max_error_rate"] = (
                metrics.error_rate <= self.performance_criteria["max_error_rate"]
            )

        # Check success rate criteria
        if "min_success_rate" in self.performance_criteria:
            success_rate = (
                metrics.successful_requests / metrics.total_requests
                if metrics.total_requests > 0
                else 0
            )
            results["min_success_rate"] = (
                success_rate >= self.performance_criteria["min_success_rate"]
            )

        return results
