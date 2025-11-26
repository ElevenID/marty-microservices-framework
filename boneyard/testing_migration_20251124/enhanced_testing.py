"""
Enhanced testing capabilities for MMF, ported from Marty's comprehensive testing framework.

This module provides chaos engineering tests, contract testing, performance baselines,
and quality gate implementations for the Marty Microservices Framework.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..resilience.enhanced.chaos_engineering import ChaosInjector, ResilienceTestSuite

logger = logging.getLogger(__name__)


class TestType(str, Enum):
    """Types of tests supported by the enhanced testing framework."""

    UNIT = "unit"
    INTEGRATION = "integration"
    CONTRACT = "contract"
    CHAOS = "chaos"
    PERFORMANCE = "performance"
    E2E = "e2e"
    SECURITY = "security"


@dataclass
class TestMetrics:
    """Metrics collected during test execution."""

    test_name: str
    test_type: TestType
    duration: float
    success: bool
    error_message: str | None = None
    performance_metrics: dict[str, float] = field(default_factory=dict)
    chaos_injected: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class ContractTestConfig:
    """Configuration for contract testing."""

    service_name: str
    endpoints: list[str] = field(default_factory=list)
    expected_response_times: dict[str, float] = field(default_factory=dict)
    health_check_endpoints: list[str] = field(default_factory=list)
    grpc_services: list[str] = field(default_factory=list)


@dataclass
class PerformanceBaseline:
    """Performance baseline configuration."""

    endpoint: str
    max_response_time: float
    max_memory_usage: float
    max_cpu_usage: float
    min_throughput: float


class EnhancedTestRunner:
    """Enhanced test runner with comprehensive testing capabilities."""

    def __init__(self, framework_name: str = "mmf"):
        self.framework_name = framework_name
        self.test_results: list[TestMetrics] = []
        self.chaos_injector = ChaosInjector()
        self.resilience_test_suite = ResilienceTestSuite(self.chaos_injector)

    async def run_contract_tests(
        self, config: ContractTestConfig, test_function: Callable[..., Any]
    ) -> list[TestMetrics]:
        """Run contract tests for service endpoints."""
        results = []

        for endpoint in config.endpoints:
            start_time = time.time()
            test_name = f"contract_test_{config.service_name}_{endpoint}"

            try:
                # Execute the test function for this endpoint
                await test_function(endpoint)

                duration = time.time() - start_time
                expected_time = config.expected_response_times.get(endpoint, 5.0)

                success = duration <= expected_time
                metrics = TestMetrics(
                    test_name=test_name,
                    test_type=TestType.CONTRACT,
                    duration=duration,
                    success=success,
                    performance_metrics={"response_time": duration, "expected_time": expected_time},
                )

                if not success:
                    metrics.error_message = (
                        f"Response time {duration:.2f}s exceeded expected {expected_time}s"
                    )

                results.append(metrics)
                logger.info(
                    "Contract test %s: %s (%.2fs)",
                    test_name,
                    "PASS" if success else "FAIL",
                    duration,
                )

            except Exception as e:  # noqa: BLE001
                duration = time.time() - start_time
                metrics = TestMetrics(
                    test_name=test_name,
                    test_type=TestType.CONTRACT,
                    duration=duration,
                    success=False,
                    error_message=str(e),
                )
                results.append(metrics)
                logger.error("Contract test %s failed: %s", test_name, e)

        self.test_results.extend(results)
        return results

    async def run_chaos_tests(
        self, target_function: Callable[..., Any], test_name: str = "chaos_test", *args, **kwargs
    ) -> list[TestMetrics]:
        """Run comprehensive chaos engineering tests."""
        results = []
        start_time = time.time()

        try:
            # Run comprehensive chaos tests
            chaos_results = await self.resilience_test_suite.run_comprehensive_test(
                target_function, *args, **kwargs
            )

            total_duration = time.time() - start_time

            # Convert chaos results to test metrics
            for category, scenarios in chaos_results.items():
                if category == "total_test_time" or category == "injection_history":
                    continue

                for scenario_name, scenario_result in scenarios.items():
                    metrics = TestMetrics(
                        test_name=f"{test_name}_{category}_{scenario_name}",
                        test_type=TestType.CHAOS,
                        duration=scenario_result.get("execution_time", 0.0),
                        success=scenario_result.get("success", False),
                        error_message=scenario_result.get("error"),
                        chaos_injected=True,
                    )
                    results.append(metrics)

            # Add summary metrics
            summary_metrics = TestMetrics(
                test_name=f"{test_name}_summary",
                test_type=TestType.CHAOS,
                duration=total_duration,
                success=True,
                performance_metrics={
                    "total_scenarios": len(
                        [r for r in results if r.test_name.startswith(test_name)]
                    ),
                    "successful_scenarios": len(
                        [r for r in results if r.test_name.startswith(test_name) and r.success]
                    ),
                },
                chaos_injected=True,
            )
            results.append(summary_metrics)

        except Exception as e:  # noqa: BLE001
            duration = time.time() - start_time
            metrics = TestMetrics(
                test_name=test_name,
                test_type=TestType.CHAOS,
                duration=duration,
                success=False,
                error_message=str(e),
                chaos_injected=True,
            )
            results.append(metrics)
            logger.error("Chaos test %s failed: %s", test_name, e)

        self.test_results.extend(results)
        return results

    async def run_performance_tests(
        self,
        target_function: Callable[..., Any],
        baseline: PerformanceBaseline,
        test_name: str = "performance_test",
        iterations: int = 10,
        *args,
        **kwargs,
    ) -> TestMetrics:
        """Run performance tests against baseline."""
        start_time = time.time()
        response_times = []

        try:
            for i in range(iterations):
                iteration_start = time.time()
                await target_function(*args, **kwargs)
                iteration_time = time.time() - iteration_start
                response_times.append(iteration_time)

                logger.debug("Performance test iteration %d: %.3fs", i + 1, iteration_time)

            total_duration = time.time() - start_time
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            min_response_time = min(response_times)

            # Check against baseline
            meets_baseline = (
                avg_response_time <= baseline.max_response_time
                and max_response_time
                <= baseline.max_response_time * 1.5  # Allow 50% tolerance for max
            )

            metrics = TestMetrics(
                test_name=test_name,
                test_type=TestType.PERFORMANCE,
                duration=total_duration,
                success=meets_baseline,
                performance_metrics={
                    "avg_response_time": avg_response_time,
                    "max_response_time": max_response_time,
                    "min_response_time": min_response_time,
                    "baseline_max_response_time": baseline.max_response_time,
                    "iterations": iterations,
                    "throughput": iterations / total_duration,
                },
            )

            if not meets_baseline:
                metrics.error_message = (
                    f"Performance baseline not met. Avg: {avg_response_time:.3f}s, "
                    f"Max: {max_response_time:.3f}s, Baseline: {baseline.max_response_time:.3f}s"
                )

            logger.info(
                "Performance test %s: %s (avg: %.3fs, max: %.3fs)",
                test_name,
                "PASS" if meets_baseline else "FAIL",
                avg_response_time,
                max_response_time,
            )

        except Exception as e:  # noqa: BLE001
            duration = time.time() - start_time
            metrics = TestMetrics(
                test_name=test_name,
                test_type=TestType.PERFORMANCE,
                duration=duration,
                success=False,
                error_message=str(e),
            )
            logger.error("Performance test %s failed: %s", test_name, e)

        self.test_results.append(metrics)
        return metrics

    def get_test_summary(self) -> dict[str, Any]:
        """Get comprehensive test summary."""
        if not self.test_results:
            return {"message": "No tests run yet"}

        total_tests = len(self.test_results)
        successful_tests = len([r for r in self.test_results if r.success])
        failed_tests = total_tests - successful_tests

        by_type = {}
        for result in self.test_results:
            test_type = result.test_type.value
            if test_type not in by_type:
                by_type[test_type] = {"total": 0, "passed": 0, "failed": 0}

            by_type[test_type]["total"] += 1
            if result.success:
                by_type[test_type]["passed"] += 1
            else:
                by_type[test_type]["failed"] += 1

        avg_duration = sum(r.duration for r in self.test_results) / total_tests
        chaos_tests = len([r for r in self.test_results if r.chaos_injected])

        return {
            "framework": self.framework_name,
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": successful_tests / total_tests if total_tests > 0 else 0,
            "average_duration": avg_duration,
            "chaos_tests_run": chaos_tests,
            "test_types": by_type,
            "last_run": max(r.timestamp for r in self.test_results) if self.test_results else None,
        }

    def generate_quality_report(self) -> dict[str, Any]:
        """Generate quality gates report."""
        summary = self.get_test_summary()

        # Define quality gates
        quality_gates = {
            "minimum_success_rate": 0.95,  # 95% success rate
            "maximum_avg_duration": 10.0,  # 10 seconds average
            "minimum_chaos_coverage": 0.2,  # 20% chaos tests
            "minimum_performance_tests": 1,  # At least 1 performance test
        }

        # Check quality gates
        gates_passed = {}
        gates_passed["success_rate"] = (
            summary["success_rate"] >= quality_gates["minimum_success_rate"]
        )
        gates_passed["avg_duration"] = (
            summary["average_duration"] <= quality_gates["maximum_avg_duration"]
        )

        chaos_coverage = (
            summary["chaos_tests_run"] / summary["total_tests"] if summary["total_tests"] > 0 else 0
        )
        gates_passed["chaos_coverage"] = chaos_coverage >= quality_gates["minimum_chaos_coverage"]

        performance_tests = summary["test_types"].get("performance", {}).get("total", 0)
        gates_passed["performance_tests"] = (
            performance_tests >= quality_gates["minimum_performance_tests"]
        )

        all_gates_passed = all(gates_passed.values())

        return {
            "quality_gates": quality_gates,
            "gates_status": gates_passed,
            "all_gates_passed": all_gates_passed,
            "summary": summary,
            "recommendations": self._get_recommendations(gates_passed, summary),
        }

    def _get_recommendations(
        self, gates_passed: dict[str, bool], summary: dict[str, Any]
    ) -> list[str]:
        """Get recommendations for improving test quality."""
        recommendations = []

        if not gates_passed["success_rate"]:
            recommendations.append(
                f"Improve test success rate (current: {summary['success_rate']:.1%})"
            )

        if not gates_passed["avg_duration"]:
            recommendations.append(
                f"Reduce average test duration (current: {summary['average_duration']:.2f}s)"
            )

        if not gates_passed["chaos_coverage"]:
            chaos_coverage = (
                summary["chaos_tests_run"] / summary["total_tests"]
                if summary["total_tests"] > 0
                else 0
            )
            recommendations.append(
                f"Increase chaos testing coverage (current: {chaos_coverage:.1%})"
            )

        if not gates_passed["performance_tests"]:
            recommendations.append("Add performance baseline tests")

        if not recommendations:
            recommendations.append("All quality gates passed! Consider tightening criteria.")

        return recommendations
