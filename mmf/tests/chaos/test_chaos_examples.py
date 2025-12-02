"""
Example Chaos Engineering Tests for MMF Framework

This module demonstrates chaos engineering testing patterns using the MMF testing framework.
"""

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class ChaosTestResult:
    """Result of a chaos engineering test."""

    test_name: str
    chaos_type: str
    success: bool
    recovery_time: float
    error_rate: float
    description: str


@pytest.mark.chaos
class TestNetworkChaos:
    """Chaos tests for network-related failures."""

    async def test_network_partition_resilience(self, chaos_experiment, system_under_test):
        """Test system resilience during network partitions."""
        baseline_requests = 100
        partition_duration = 30  # seconds

        # Establish baseline performance
        baseline_success_count = 0

        for _ in range(baseline_requests):
            try:
                await system_under_test.make_request()
                baseline_success_count += 1
            except Exception:
                pass

        baseline_success_rate = baseline_success_count / baseline_requests

        # Inject network partition
        async with chaos_experiment.network_partition():
            partition_start = time.time()
            partition_success_count = 0
            partition_requests = 0

            # Continue making requests during partition
            while time.time() - partition_start < partition_duration:
                try:
                    await system_under_test.make_request()
                    partition_success_count += 1
                except Exception:
                    pass

                partition_requests += 1
                await asyncio.sleep(0.1)

            partition_success_rate = (
                partition_success_count / partition_requests if partition_requests > 0 else 0
            )

        # Measure recovery time
        recovery_start = time.time()
        recovery_success_count = 0
        recovery_requests = 0

        # Wait for system to recover
        while time.time() - recovery_start < 60:  # Max 60s recovery
            try:
                await system_under_test.make_request()
                recovery_success_count += 1
            except Exception:
                pass

            recovery_requests += 1
            recovery_success_rate = recovery_success_count / recovery_requests

            # Consider recovered when success rate returns to 90% of baseline
            if recovery_success_rate >= baseline_success_rate * 0.9:
                break

            await asyncio.sleep(1)

        recovery_time = time.time() - recovery_start

        # Assertions
        assert (
            partition_success_rate < baseline_success_rate
        ), "System should show degraded performance during partition"
        assert recovery_time < 30, f"Recovery took too long: {recovery_time:.2f}s"
        assert recovery_success_rate >= baseline_success_rate * 0.9, (
            f"System did not recover properly: {recovery_success_rate:.2f} vs "
            f"{baseline_success_rate * 0.9:.2f}"
        )

    async def test_high_latency_resilience(self, chaos_experiment, system_under_test):
        """Test system resilience under high network latency."""
        latency_values = [100, 500, 1000, 2000]  # milliseconds
        timeout_threshold = 5000  # 5 seconds

        for latency_ms in latency_values:
            async with chaos_experiment.network_latency(latency_ms):
                success_count = 0
                timeout_count = 0
                total_requests = 50

                for _ in range(total_requests):
                    try:
                        response_start = time.time()
                        await system_under_test.make_request()
                        response_time = (time.time() - response_start) * 1000

                        if response_time > timeout_threshold:
                            timeout_count += 1
                        else:
                            success_count += 1

                    except asyncio.TimeoutError:
                        timeout_count += 1
                    except Exception:
                        pass

                success_rate = success_count / total_requests
                timeout_rate = timeout_count / total_requests

                # Assertions based on latency level
                if latency_ms <= 500:
                    assert success_rate >= 0.9, f"High failure rate at {latency_ms}ms latency"
                elif latency_ms <= 1000:
                    assert success_rate >= 0.7, f"Excessive failure rate at {latency_ms}ms latency"
                else:
                    assert success_rate >= 0.3, f"System completely fails at {latency_ms}ms latency"

                # System should implement proper timeouts
                assert timeout_rate < 0.5, f"Too many timeouts at {latency_ms}ms latency"

    async def test_packet_loss_resilience(self, chaos_experiment, system_under_test):
        """Test system resilience under packet loss."""
        packet_loss_rates = [0.05, 0.1, 0.2, 0.3]  # 5%, 10%, 20%, 30%

        for loss_rate in packet_loss_rates:
            async with chaos_experiment.packet_loss(loss_rate):
                success_count = 0
                error_count = 0
                total_requests = 100

                for _ in range(total_requests):
                    try:
                        await system_under_test.make_request()
                        success_count += 1
                    except Exception:
                        error_count += 1

                success_rate = success_count / total_requests

                # System should handle packet loss gracefully
                expected_min_success = max(0.5, 1 - loss_rate * 2)  # Account for retries
                assert (
                    success_rate >= expected_min_success
                ), f"Success rate {success_rate:.2f} too low for {loss_rate:.1%} packet loss"


@pytest.mark.chaos
class TestResourceChaos:
    """Chaos tests for resource-related failures."""

    async def test_memory_pressure_resilience(self, chaos_experiment, system_under_test):
        """Test system behavior under memory pressure."""
        memory_pressure_levels = [0.7, 0.8, 0.9]  # 70%, 80%, 90% memory usage

        for pressure_level in memory_pressure_levels:
            async with chaos_experiment.memory_pressure(pressure_level):
                # Monitor system behavior under memory pressure
                success_count = 0
                oom_errors = 0
                total_requests = 50

                for _ in range(total_requests):
                    try:
                        await system_under_test.make_request()
                        success_count += 1
                    except MemoryError:
                        oom_errors += 1
                    except Exception:
                        pass

                    await asyncio.sleep(0.1)

                success_rate = success_count / total_requests
                oom_rate = oom_errors / total_requests

                # System should handle memory pressure gracefully
                if pressure_level <= 0.8:
                    assert (
                        success_rate >= 0.8
                    ), f"High failure rate under {pressure_level:.0%} memory pressure"
                    assert oom_rate == 0, "Should not have OOM errors at moderate memory pressure"
                else:
                    assert (
                        success_rate >= 0.5
                    ), f"System fails completely under {pressure_level:.0%} memory pressure"
                    assert oom_rate < 0.3, "Too many OOM errors under high memory pressure"

    async def test_cpu_stress_resilience(self, chaos_experiment, system_under_test):
        """Test system behavior under high CPU load."""
        cpu_load_levels = [0.7, 0.8, 0.9, 0.95]  # 70%, 80%, 90%, 95% CPU usage

        for cpu_load in cpu_load_levels:
            async with chaos_experiment.cpu_stress(cpu_load):
                response_times = []
                success_count = 0
                total_requests = 30

                for _ in range(total_requests):
                    try:
                        start_time = time.time()
                        await system_under_test.make_request()
                        response_time = time.time() - start_time
                        response_times.append(response_time)
                        success_count += 1
                    except Exception:
                        pass

                success_rate = success_count / total_requests
                avg_response_time = (
                    sum(response_times) / len(response_times) if response_times else float("inf")
                )

                # System should remain responsive under CPU stress
                assert success_rate >= 0.7, f"High failure rate under {cpu_load:.0%} CPU load"

                # Response times may increase but should remain reasonable
                max_acceptable_response = 10.0  # 10 seconds
                assert (
                    avg_response_time < max_acceptable_response
                ), f"Response time {avg_response_time:.2f}s too high under {cpu_load:.0%} CPU load"

    async def test_disk_io_chaos(self, chaos_experiment, system_under_test):
        """Test system resilience during disk I/O issues."""
        io_scenarios = [
            {"type": "slow_disk", "latency_ms": 1000},
            {"type": "disk_full", "usage_percent": 95},
            {"type": "io_errors", "error_rate": 0.1},
        ]

        for scenario in io_scenarios:
            scenario_type = scenario["type"]

            if scenario_type == "slow_disk":
                async with chaos_experiment.slow_disk_io(scenario["latency_ms"]):
                    await self._test_disk_resilience(system_under_test, "slow_disk")

            elif scenario_type == "disk_full":
                async with chaos_experiment.disk_full(scenario["usage_percent"]):
                    await self._test_disk_resilience(system_under_test, "disk_full")

            elif scenario_type == "io_errors":
                async with chaos_experiment.disk_io_errors(scenario["error_rate"]):
                    await self._test_disk_resilience(system_under_test, "io_errors")

    async def _test_disk_resilience(self, system_under_test, scenario_type):
        """Helper method to test disk resilience scenarios."""
        success_count = 0
        error_count = 0
        total_operations = 20

        for _ in range(total_operations):
            try:
                await system_under_test.perform_disk_operation()
                success_count += 1
            except Exception:
                error_count += 1

        success_rate = success_count / total_operations

        # Expectations vary by scenario
        if scenario_type == "slow_disk":
            assert success_rate >= 0.8, f"High failure rate during {scenario_type}"
        elif scenario_type == "disk_full":
            assert success_rate >= 0.5, f"System should handle {scenario_type} gracefully"
        elif scenario_type == "io_errors":
            assert success_rate >= 0.6, f"Too many failures during {scenario_type}"


@pytest.mark.chaos
class TestServiceChaos:
    """Chaos tests for service-level failures."""

    async def test_dependency_failure_resilience(self, chaos_experiment, system_under_test):
        """Test system resilience when dependencies fail."""
        dependencies = ["database", "cache", "external_api", "message_queue"]

        for dependency in dependencies:
            async with chaos_experiment.service_failure(dependency):
                success_count = 0
                degraded_count = 0
                failure_count = 0
                total_requests = 50

                for _ in range(total_requests):
                    try:
                        result = await system_under_test.make_request()

                        if result.status == "success":
                            success_count += 1
                        elif result.status == "degraded":
                            degraded_count += 1
                        else:
                            failure_count += 1

                    except Exception:
                        failure_count += 1

                success_rate = success_count / total_requests
                degraded_rate = degraded_count / total_requests

                # Expectations vary by dependency criticality
                if dependency in ["database", "message_queue"]:
                    # Critical dependencies - expect graceful degradation
                    assert (
                        success_rate + degraded_rate >= 0.8
                    ), f"System should degrade gracefully when {dependency} fails"
                else:
                    # Non-critical dependencies - expect continued operation
                    assert (
                        success_rate >= 0.9
                    ), f"System should continue operating when {dependency} fails"

    async def test_cascading_failure_prevention(self, chaos_experiment, system_under_test):
        """Test prevention of cascading failures."""
        # Simulate multiple simultaneous failures
        failure_scenarios = [
            ["database"],
            ["database", "cache"],
            ["database", "cache", "external_api"],
        ]

        for failed_services in failure_scenarios:
            async with chaos_experiment.multiple_service_failures(failed_services):
                # Monitor system for cascading effects
                success_count = 0
                total_requests = 30
                response_times = []

                for _ in range(total_requests):
                    try:
                        start_time = time.time()
                        await system_under_test.make_request()
                        response_time = time.time() - start_time
                        response_times.append(response_time)
                        success_count += 1
                    except Exception:
                        pass

                success_rate = success_count / total_requests
                avg_response_time = (
                    sum(response_times) / len(response_times) if response_times else 0
                )

                # System should implement circuit breakers and fail-safes
                failure_count = len(failed_services)
                expected_min_success = max(0.3, 1.0 - (failure_count * 0.2))

                assert success_rate >= expected_min_success, (
                    f"Cascading failure detected with {failed_services}: "
                    f"success rate {success_rate:.2f} below expected {expected_min_success:.2f}"
                )

                # Response times should not degrade excessively
                assert (
                    avg_response_time < 10.0
                ), f"Response time degradation indicates cascading failure: {avg_response_time:.2f}s"

    async def test_traffic_spike_resilience(self, chaos_experiment, system_under_test):
        """Test system behavior under sudden traffic spikes."""
        baseline_rps = 10
        spike_multipliers = [2, 5, 10, 20]

        for multiplier in spike_multipliers:
            spike_rps = baseline_rps * multiplier
            spike_duration = 30  # seconds

            async with chaos_experiment.traffic_spike(spike_rps, spike_duration):
                start_time = time.time()
                success_count = 0
                rate_limited_count = 0
                error_count = 0
                total_requests = 0

                while time.time() - start_time < spike_duration:
                    batch_size = min(10, spike_rps)
                    batch_tasks = []

                    for _ in range(batch_size):
                        task = asyncio.create_task(system_under_test.make_request())
                        batch_tasks.append(task)

                    results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                    for result in results:
                        total_requests += 1

                        if isinstance(result, Exception):
                            if "rate limit" in str(result).lower():
                                rate_limited_count += 1
                            else:
                                error_count += 1
                        else:
                            success_count += 1

                    # Rate limiting to achieve target RPS
                    await asyncio.sleep(1.0)

                success_rate = success_count / total_requests if total_requests > 0 else 0
                rate_limited_rate = rate_limited_count / total_requests if total_requests > 0 else 0
                error_rate = error_count / total_requests if total_requests > 0 else 0

                # System should handle traffic spikes gracefully
                if multiplier <= 5:
                    assert success_rate >= 0.7, f"High failure rate at {multiplier}x traffic"
                    assert (
                        rate_limited_rate <= 0.3
                    ), f"Excessive rate limiting at {multiplier}x traffic"
                else:
                    # High traffic - rate limiting expected
                    assert (
                        success_rate + rate_limited_rate >= 0.8
                    ), f"System should rate limit gracefully at {multiplier}x traffic"

                # Should not have excessive errors
                assert error_rate <= 0.1, f"Too many errors at {multiplier}x traffic"


@pytest.mark.chaos
@pytest.mark.slow
class TestChaosMonkey:
    """Comprehensive chaos monkey tests."""

    async def test_random_pod_termination(self, chaos_experiment, kubernetes_cluster):
        """Test system resilience to random pod terminations."""
        test_duration = 300  # 5 minutes
        termination_interval = 30  # seconds

        start_time = time.time()
        termination_count = 0

        async def chaos_monkey():
            """Randomly terminate pods during the test."""
            nonlocal termination_count

            while time.time() - start_time < test_duration:
                await asyncio.sleep(termination_interval)

                # Get list of non-critical pods
                pods = await kubernetes_cluster.get_pods(exclude_critical=True)

                if pods:
                    # Randomly select a pod to terminate
                    pod_to_terminate = random.choice(pods)
                    await kubernetes_cluster.terminate_pod(pod_to_terminate)
                    termination_count += 1

        async def system_monitor():
            """Monitor system health during chaos."""
            health_checks = []

            while time.time() - start_time < test_duration:
                try:
                    health_status = await kubernetes_cluster.check_system_health()
                    health_checks.append(
                        {
                            "timestamp": time.time(),
                            "status": health_status,
                            "healthy": health_status.overall_health >= 0.8,
                        }
                    )
                except Exception as e:
                    health_checks.append(
                        {
                            "timestamp": time.time(),
                            "status": None,
                            "healthy": False,
                            "error": str(e),
                        }
                    )

                await asyncio.sleep(10)

            return health_checks

        # Run chaos monkey and system monitor concurrently
        chaos_task = asyncio.create_task(chaos_monkey())
        monitor_task = asyncio.create_task(system_monitor())

        health_checks = await monitor_task
        await chaos_task

        # Analyze results
        healthy_checks = [check for check in health_checks if check["healthy"]]
        health_rate = len(healthy_checks) / len(health_checks) if health_checks else 0

        # System should maintain health despite pod terminations
        assert termination_count > 0, "Chaos monkey should have terminated some pods"
        assert health_rate >= 0.9, (
            f"System health degraded too much: {health_rate:.2f} healthy rate "
            f"with {termination_count} pod terminations"
        )

    async def test_comprehensive_chaos_scenario(self, chaos_experiment, system_under_test):
        """Test system under comprehensive chaos conditions."""
        test_duration = 180  # 3 minutes

        # Define chaos scenarios to run simultaneously
        chaos_scenarios = [
            {"type": "network_latency", "params": {"latency_ms": 200}},
            {"type": "packet_loss", "params": {"loss_rate": 0.05}},
            {"type": "cpu_stress", "params": {"cpu_load": 0.6}},
            {"type": "memory_pressure", "params": {"pressure_level": 0.7}},
            {"type": "service_failure", "params": {"service": "cache"}},
        ]

        async def run_chaos_scenario(scenario):
            """Run a specific chaos scenario."""
            scenario_type = scenario["type"]
            params = scenario["params"]

            if scenario_type == "network_latency":
                async with chaos_experiment.network_latency(params["latency_ms"]):
                    await asyncio.sleep(test_duration)
            elif scenario_type == "packet_loss":
                async with chaos_experiment.packet_loss(params["loss_rate"]):
                    await asyncio.sleep(test_duration)
            elif scenario_type == "cpu_stress":
                async with chaos_experiment.cpu_stress(params["cpu_load"]):
                    await asyncio.sleep(test_duration)
            elif scenario_type == "memory_pressure":
                async with chaos_experiment.memory_pressure(params["pressure_level"]):
                    await asyncio.sleep(test_duration)
            elif scenario_type == "service_failure":
                async with chaos_experiment.service_failure(params["service"]):
                    await asyncio.sleep(test_duration)

        async def monitor_system_performance():
            """Monitor system performance during comprehensive chaos."""
            metrics = []
            start_time = time.time()

            while time.time() - start_time < test_duration:
                try:
                    response_start = time.time()
                    result = await system_under_test.make_request()
                    response_time = time.time() - response_start

                    metrics.append(
                        {
                            "timestamp": time.time(),
                            "response_time": response_time,
                            "success": True,
                            "status": getattr(result, "status", "success"),
                        }
                    )

                except Exception as e:
                    metrics.append(
                        {
                            "timestamp": time.time(),
                            "response_time": None,
                            "success": False,
                            "error": str(e),
                        }
                    )

                await asyncio.sleep(2)

            return metrics

        # Run all chaos scenarios and monitoring concurrently
        chaos_tasks = [
            asyncio.create_task(run_chaos_scenario(scenario)) for scenario in chaos_scenarios
        ]
        monitor_task = asyncio.create_task(monitor_system_performance())

        metrics = await monitor_task
        await asyncio.gather(*chaos_tasks)

        # Analyze comprehensive chaos results
        successful_requests = [m for m in metrics if m["success"]]
        success_rate = len(successful_requests) / len(metrics) if metrics else 0

        response_times = [m["response_time"] for m in successful_requests if m["response_time"]]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        # System should maintain reasonable performance under comprehensive chaos
        assert (
            success_rate >= 0.7
        ), f"System failed under comprehensive chaos: {success_rate:.2f} success rate"
        assert (
            avg_response_time < 15.0
        ), f"Response times too high under comprehensive chaos: {avg_response_time:.2f}s"

        # System should not have complete outages
        consecutive_failures = 0
        max_consecutive_failures = 0

        for metric in metrics:
            if metric["success"]:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                max_consecutive_failures = max(max_consecutive_failures, consecutive_failures)

        assert (
            max_consecutive_failures <= 5
        ), f"Too many consecutive failures: {max_consecutive_failures}"
