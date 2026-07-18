"""
End-to-End Test for Timeout Detection and Circuit Breaker Testing

This test demonstrates:
1. Services under increased workload leading to timeouts
2. Circuit breaker functionality and state transitions
3. Timeout pattern identification and analysis
4. Service resilience under stress conditions
"""

import asyncio
import json
import random
import time
from pathlib import Path

import pytest

from mmf.tests.e2e.conftest import PerformanceAnalyzer, TimeoutMonitor


class TestTimeoutDetection:
    """Test suite for timeout detection and circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_timeout_detection_and_circuit_breaker(
        self,
        simulation_plugin,
        circuit_breaker_plugin,
        performance_analyzer: PerformanceAnalyzer,
        timeout_monitor: TimeoutMonitor,
        test_report_dir: Path,
    ):
        """
        Test that identifies services with increased timeouts under load
        and demonstrates circuit breaker functionality.
        """
        print("\\n⏱️  Starting timeout detection and circuit breaker test...")

        # Test phases with increasing load and timeout scenarios
        test_phases = [
            {
                "name": "baseline",
                "duration": 15,
                "load_factor": 1,
                "timeout_injection": 0.0,
                "complexity_multiplier": 1,
            },
            {
                "name": "moderate_load",
                "duration": 20,
                "load_factor": 3,
                "timeout_injection": 0.1,  # 10% operations will be slow
                "complexity_multiplier": 2,
            },
            {
                "name": "high_load",
                "duration": 25,
                "load_factor": 5,
                "timeout_injection": 0.2,  # 20% operations will be slow
                "complexity_multiplier": 4,
            },
            {
                "name": "stress_test",
                "duration": 30,
                "load_factor": 8,
                "timeout_injection": 0.3,  # 30% operations will be slow
                "complexity_multiplier": 6,
            },
        ]

        results = {}

        for phase in test_phases:
            print(f"\\n🔄 Starting phase: {phase['name']}")

            # Configure plugins for this phase
            await self._configure_phase(simulation_plugin, circuit_breaker_plugin, phase)

            # Execute phase test
            phase_results = await self._execute_timeout_test_phase(
                phase,
                simulation_plugin,
                circuit_breaker_plugin,
                performance_analyzer,
                timeout_monitor,
            )

            results[phase["name"]] = phase_results

            print(f"✅ Completed phase: {phase['name']}")
            print(f"   Timeouts: {phase_results['timeouts']}")
            print(f"   Circuit breaker trips: {phase_results['circuit_breaker_trips']}")

            # Brief pause between phases
            await asyncio.sleep(3)

        # Analyze timeout patterns
        timeout_analysis = await self._analyze_timeout_patterns(results, timeout_monitor)

        # Generate comprehensive report
        report = self._generate_timeout_report(results, timeout_analysis, timeout_monitor)

        # Save report
        report_file = test_report_dir / "timeout_detection_report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\\n📋 Timeout report saved to: {report_file}")

        # Assertions
        assert len(results) == len(test_phases), "Should have results for all phases"
        assert any(phase["timeouts"] > 0 for phase in results.values()), (
            "Should detect timeouts under high load"
        )
        assert any(phase["circuit_breaker_trips"] > 0 for phase in results.values()), (
            "Circuit breaker should trip under stress"
        )

        # Print summary
        self._print_timeout_summary(report)

    async def _configure_phase(self, simulation_plugin, circuit_breaker_plugin, phase):
        """Configure plugins for the test phase."""

        # Configure simulation plugin for load and timeout injection
        simulation_plugin.config.update(
            {
                "complexity_multiplier": phase["complexity_multiplier"],
                "timeout_injection_rate": phase["timeout_injection"],
                "background_task_count": phase["load_factor"],
                "error_rate": 0.05 + (phase["load_factor"] * 0.02),
            }
        )

        # Configure circuit breaker with appropriate thresholds
        circuit_breaker_plugin.config.update(
            {
                "failure_threshold": 5,  # Trip after 5 failures
                "timeout_threshold": 3.0,  # 3 second timeout
                "recovery_timeout": 10.0,  # 10 second recovery period
            }
        )

    async def _execute_timeout_test_phase(
        self,
        phase,
        simulation_plugin,
        circuit_breaker_plugin,
        performance_analyzer,
        timeout_monitor,
    ):
        """Execute a single test phase with timeout monitoring."""

        start_time = time.time()
        duration = phase["duration"]

        # Track phase metrics
        phase_metrics = {
            "operations_attempted": 0,
            "operations_succeeded": 0,
            "operations_failed": 0,
            "timeouts": 0,
            "circuit_breaker_trips": 0,
            "avg_response_time": 0.0,
            "max_response_time": 0.0,
            "response_times": [],
        }

        # Start background monitoring
        monitoring_task = asyncio.create_task(
            self._monitor_phase_performance(
                performance_analyzer, f"timeout_test_{phase['name']}", duration
            )
        )

        # Generate concurrent workload
        worker_tasks = []
        for i in range(phase["load_factor"]):
            task = asyncio.create_task(
                self._run_timeout_test_worker(
                    f"worker_{i}",
                    simulation_plugin,
                    circuit_breaker_plugin,
                    timeout_monitor,
                    phase_metrics,
                    start_time,
                    duration,
                )
            )
            worker_tasks.append(task)

        # Wait for all tasks
        await asyncio.gather(monitoring_task, *worker_tasks, return_exceptions=True)

        # Calculate final metrics
        if phase_metrics["response_times"]:
            phase_metrics["avg_response_time"] = sum(phase_metrics["response_times"]) / len(
                phase_metrics["response_times"]
            )
            phase_metrics["max_response_time"] = max(phase_metrics["response_times"])

        return phase_metrics

    async def _monitor_phase_performance(self, analyzer, service_name, duration):
        """Monitor performance during a test phase."""
        start_time = time.time()

        while time.time() - start_time < duration:
            # Collect metrics
            metrics = analyzer.collect_metrics(service_name)

            # Create audit events for performance issues
            if metrics.cpu_usage and max(metrics.cpu_usage) > 80:
                analyzer.create_audit_event(
                    service=service_name,
                    event_type="performance",
                    severity="warning",
                    message=f"High CPU usage detected: {max(metrics.cpu_usage):.1f}%",
                    metadata={"cpu_usage": max(metrics.cpu_usage)},
                )

            await asyncio.sleep(1)

    async def _run_timeout_test_worker(
        self,
        worker_name,
        simulation_plugin,
        circuit_breaker_plugin,
        timeout_monitor,
        phase_metrics,
        start_time,
        duration,
    ):
        """Run a worker that generates load and monitors timeouts."""

        operation_count = 0

        while time.time() - start_time < duration:
            operation_count += 1
            phase_metrics["operations_attempted"] += 1

            try:
                # Create operation that might timeout
                operation_name = f"{worker_name}_op_{operation_count}"

                # Use timeout monitor to track the operation
                result = await timeout_monitor.monitor_operation(
                    operation_name,
                    self._simulate_potentially_slow_operation,
                    simulation_plugin,
                    operation_name,
                )

                phase_metrics["operations_succeeded"] += 1

                # Record response time
                if hasattr(result, "duration"):
                    phase_metrics["response_times"].append(result.duration)

            except asyncio.TimeoutError:
                phase_metrics["timeouts"] += 1
                phase_metrics["operations_failed"] += 1

                # Test circuit breaker response to timeout
                try:
                    await circuit_breaker_plugin.handle_failure("timeout_service")
                    if circuit_breaker_plugin.is_open():
                        phase_metrics["circuit_breaker_trips"] += 1
                except Exception:
                    pass  # Circuit breaker handling

            except Exception as e:
                phase_metrics["operations_failed"] += 1
                print(f"⚠️  Operation failed: {e}")

            # Brief pause between operations
            await asyncio.sleep(0.1)

    async def _simulate_potentially_slow_operation(self, simulation_plugin, operation_name):
        """Simulate an operation that might be slow or timeout."""

        # Check if we should inject a timeout (make operation artificially slow)
        timeout_injection_rate = getattr(simulation_plugin.config, "timeout_injection_rate", 0.0)

        if random.random() < timeout_injection_rate:
            # Inject artificial delay that might cause timeout
            delay = random.uniform(3.0, 8.0)  # 3-8 second delay
            await asyncio.sleep(delay)

        # Regular simulation work
        result = await simulation_plugin.simulate_work(
            task_name=operation_name,
            complexity=getattr(simulation_plugin.config, "complexity_multiplier", 1),
        )

        return result

    async def _analyze_timeout_patterns(self, results, timeout_monitor):
        """Analyze timeout patterns across test phases."""

        patterns = {
            "timeout_progression": [],
            "circuit_breaker_effectiveness": [],
            "response_time_degradation": [],
            "load_impact_analysis": {},
        }

        for phase_name, phase_results in results.items():
            # Timeout progression analysis
            timeout_rate = (
                phase_results["timeouts"] / phase_results["operations_attempted"] * 100
                if phase_results["operations_attempted"] > 0
                else 0
            )

            patterns["timeout_progression"].append(
                {
                    "phase": phase_name,
                    "timeout_rate": timeout_rate,
                    "absolute_timeouts": phase_results["timeouts"],
                }
            )

            # Circuit breaker effectiveness
            cb_trip_rate = (
                phase_results["circuit_breaker_trips"] / max(phase_results["timeouts"], 1)
                if phase_results["timeouts"] > 0
                else 0
            )

            patterns["circuit_breaker_effectiveness"].append(
                {
                    "phase": phase_name,
                    "trip_rate": cb_trip_rate,
                    "trips": phase_results["circuit_breaker_trips"],
                    "timeouts": phase_results["timeouts"],
                }
            )

            # Response time analysis
            patterns["response_time_degradation"].append(
                {
                    "phase": phase_name,
                    "avg_response_time": phase_results["avg_response_time"],
                    "max_response_time": phase_results["max_response_time"],
                }
            )

        # Load impact analysis
        for phase_name, phase_results in results.items():
            operations = phase_results["operations_attempted"]
            success_rate = (
                phase_results["operations_succeeded"] / operations * 100 if operations > 0 else 0
            )

            patterns["load_impact_analysis"][phase_name] = {
                "operations_per_second": operations / 15,  # Approximate
                "success_rate": success_rate,
                "timeout_rate": timeout_rate,
            }

        return patterns

    def _generate_timeout_report(self, results, timeout_analysis, timeout_monitor):
        """Generate comprehensive timeout detection report."""

        # Overall statistics
        total_operations = sum(r["operations_attempted"] for r in results.values())
        total_timeouts = sum(r["timeouts"] for r in results.values())
        total_cb_trips = sum(r["circuit_breaker_trips"] for r in results.values())

        return {
            "test_summary": {
                "test_name": "Timeout Detection and Circuit Breaker Test",
                "phases_tested": list(results.keys()),
                "total_operations": total_operations,
                "total_timeouts": total_timeouts,
                "total_circuit_breaker_trips": total_cb_trips,
                "overall_timeout_rate": (total_timeouts / total_operations * 100)
                if total_operations > 0
                else 0,
            },
            "timeout_patterns": timeout_analysis,
            "phase_results": results,
            "timeout_monitor_report": timeout_monitor.get_timeout_report(),
            "insights": self._generate_timeout_insights(results, timeout_analysis),
            "recommendations": self._generate_timeout_recommendations(results, timeout_analysis),
        }

    def _generate_timeout_insights(self, results, patterns):
        """Generate insights from timeout analysis."""
        insights = []

        # Check for timeout progression
        timeout_rates = [p["timeout_rate"] for p in patterns["timeout_progression"]]
        if len(timeout_rates) > 1 and timeout_rates[-1] > timeout_rates[0] * 2:
            insights.append(
                {
                    "type": "timeout_escalation",
                    "message": "Timeout rate significantly increased under load",
                    "severity": "high",
                    "data": {
                        "initial_rate": timeout_rates[0],
                        "final_rate": timeout_rates[-1],
                    },
                }
            )

        # Check circuit breaker effectiveness
        cb_effectiveness = patterns["circuit_breaker_effectiveness"]
        avg_trip_rate = sum(cb["trip_rate"] for cb in cb_effectiveness) / len(cb_effectiveness)
        if avg_trip_rate > 0.8:
            insights.append(
                {
                    "type": "circuit_breaker_effective",
                    "message": "Circuit breaker is effectively protecting services",
                    "severity": "info",
                    "data": {"average_trip_rate": avg_trip_rate},
                }
            )
        elif avg_trip_rate < 0.3:
            insights.append(
                {
                    "type": "circuit_breaker_tuning",
                    "message": "Circuit breaker may need threshold tuning",
                    "severity": "warning",
                    "data": {"average_trip_rate": avg_trip_rate},
                }
            )

        # Check response time degradation
        response_times = [p["avg_response_time"] for p in patterns["response_time_degradation"]]
        if len(response_times) > 1 and response_times[-1] > response_times[0] * 3:
            insights.append(
                {
                    "type": "response_degradation",
                    "message": "Significant response time degradation under load",
                    "severity": "critical",
                    "data": {
                        "initial_time": response_times[0],
                        "final_time": response_times[-1],
                    },
                }
            )

        return insights

    def _generate_timeout_recommendations(self, results, patterns):
        """Generate recommendations based on timeout analysis."""
        recommendations = []

        # High timeout rate recommendations
        max_timeout_rate = max(p["timeout_rate"] for p in patterns["timeout_progression"])
        if max_timeout_rate > 15:
            recommendations.append(
                {
                    "category": "Timeout Mitigation",
                    "priority": "high",
                    "actions": [
                        "Implement adaptive timeout strategies",
                        "Add request queuing and rate limiting",
                        "Consider horizontal scaling",
                        "Optimize slow operations identified in bottleneck analysis",
                    ],
                }
            )

        # Circuit breaker tuning recommendations
        cb_data = patterns["circuit_breaker_effectiveness"]
        if any(cb["trip_rate"] < 0.5 for cb in cb_data):
            recommendations.append(
                {
                    "category": "Circuit Breaker Tuning",
                    "priority": "medium",
                    "actions": [
                        "Lower failure threshold for faster protection",
                        "Adjust timeout thresholds based on service characteristics",
                        "Implement half-open state monitoring",
                        "Add circuit breaker metrics and alerting",
                    ],
                }
            )

        # Response time recommendations
        max_response_time = max(
            p["avg_response_time"]
            for p in patterns["response_time_degradation"]
            if p["avg_response_time"] > 0
        )
        if max_response_time > 2.0:
            recommendations.append(
                {
                    "category": "Performance Optimization",
                    "priority": "high",
                    "actions": [
                        "Implement caching for frequently accessed data",
                        "Optimize database queries and connections",
                        "Add asynchronous processing for heavy operations",
                        "Consider CDN for static resources",
                    ],
                }
            )

        return recommendations

    def _print_timeout_summary(self, report):
        """Print timeout test summary."""
        print("\\n" + "=" * 50)
        print("⏱️  TIMEOUT DETECTION TEST SUMMARY")
        print("=" * 50)

        summary = report["test_summary"]
        print(f"📊 Phases tested: {len(summary['phases_tested'])}")
        print(f"🔄 Total operations: {summary['total_operations']}")
        print(f"⏱️  Total timeouts: {summary['total_timeouts']}")
        print(f"🔌 Circuit breaker trips: {summary['total_circuit_breaker_trips']}")
        print(f"📈 Overall timeout rate: {summary['overall_timeout_rate']:.2f}%")

        insights = report["insights"]
        if insights:
            print("\\n💡 KEY INSIGHTS:")
            for insight in insights[:3]:
                print(f"   • {insight['message']} ({insight['severity']})")

        recommendations = report["recommendations"]
        if recommendations:
            print("\\n🎯 RECOMMENDATIONS:")
            for rec in recommendations[:2]:
                print(f"   📋 {rec['category']} ({rec['priority']} priority)")
                for action in rec["actions"][:2]:
                    print(f"      - {action}")

        print("\\n✅ Timeout detection test completed!")
        print("=" * 50)
