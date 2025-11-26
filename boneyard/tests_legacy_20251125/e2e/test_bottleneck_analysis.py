"""
End-to-End Test for Performance Analysis and Bottleneck Detection

This test demonstrates:
1. Using example plugins to generate realistic workload
2. Analyzing performance bottlenecks in real-time
3. Measuring response times and resource usage
4. Identifying services with performance issues
"""

import asyncio
import json
import time
from pathlib import Path

import pytest

from tests.e2e.conftest import PerformanceAnalyzer


class TestBottleneckAnalysis:
    """Test suite for performance bottleneck analysis."""

    @pytest.mark.asyncio
    async def test_comprehensive_bottleneck_analysis(
        self,
        simulation_plugin,
        pipeline_plugin,
        monitoring_plugin,
        performance_analyzer: PerformanceAnalyzer,
        test_report_dir: Path,
    ):
        """
        Comprehensive test that uses multiple plugins to generate load
        and analyzes performance bottlenecks.
        """
        print("\\n🚀 Starting comprehensive bottleneck analysis test...")

        # Test configuration
        test_duration = 30  # seconds
        load_levels = [1, 5, 10, 20]  # Different load levels to test

        results = {}

        for load_level in load_levels:
            print(f"\\n📊 Testing with load level: {load_level}")

            # Configure plugins for different load levels
            simulation_plugin.config.update(
                {
                    "complexity_multiplier": load_level,
                    "error_rate": 0.1 + (load_level * 0.02),  # Increase error rate with load
                    "background_task_count": load_level,
                }
            )

            # Start background monitoring
            monitoring_task = asyncio.create_task(
                self._monitor_system_performance(
                    performance_analyzer, f"load_level_{load_level}", test_duration
                )
            )

            # Generate workload using simulation plugin
            simulation_tasks = []
            for i in range(load_level):
                task = asyncio.create_task(
                    self._generate_simulation_workload(simulation_plugin, f"sim_{i}", test_duration)
                )
                simulation_tasks.append(task)

            # Generate pipeline workload
            pipeline_tasks = []
            for i in range(load_level):
                task = asyncio.create_task(
                    self._generate_pipeline_workload(
                        pipeline_plugin, f"pipeline_{i}", test_duration
                    )
                )
                pipeline_tasks.append(task)

            # Wait for all tasks to complete
            try:
                await asyncio.gather(
                    monitoring_task,
                    *simulation_tasks,
                    *pipeline_tasks,
                    return_exceptions=True,
                )
            except Exception as e:
                print(f"⚠️  Some tasks failed with load level {load_level}: {e}")

            # Analyze results for this load level
            load_results = await self._analyze_load_level_results(performance_analyzer, load_level)
            results[f"load_level_{load_level}"] = load_results

            print(f"✅ Completed load level {load_level} analysis")

            # Brief pause between load levels
            await asyncio.sleep(2)

        # Generate comprehensive report
        report = self._generate_bottleneck_report(results, performance_analyzer)

        # Save report to file
        report_file = test_report_dir / "bottleneck_analysis_report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\\n📋 Report saved to: {report_file}")

        # Assertions to verify test functionality
        assert len(results) == len(load_levels), "Should have results for all load levels"
        assert any(load_results["bottlenecks"] for load_results in results.values()), (
            "Should detect some bottlenecks under high load"
        )

        # Print summary
        self._print_test_summary(report)

    async def _monitor_system_performance(
        self, analyzer: PerformanceAnalyzer, service_name: str, duration: int
    ):
        """Monitor system performance during test."""
        start_time = time.time()

        while time.time() - start_time < duration:
            # Collect metrics
            metrics = analyzer.collect_metrics(service_name)

            # Analyze for bottlenecks
            bottlenecks = analyzer.analyze_bottlenecks(service_name, metrics)

            # Create audit events for significant performance issues
            for bottleneck in bottlenecks:
                analyzer.create_audit_event(
                    service=service_name,
                    event_type="performance",
                    severity=bottleneck.severity,
                    message=f"{bottleneck.bottleneck_type} bottleneck detected: {bottleneck.current_value:.2f}",
                    metadata={
                        "bottleneck_type": bottleneck.bottleneck_type,
                        "current_value": bottleneck.current_value,
                        "threshold": bottleneck.threshold_value,
                        "recommendations": bottleneck.recommendations,
                    },
                )

            await asyncio.sleep(1)  # Monitor every second

    async def _generate_simulation_workload(self, plugin, task_name: str, duration: int):
        """Generate workload using simulation plugin."""
        start_time = time.time()
        operation_count = 0

        while time.time() - start_time < duration:
            try:
                # Simulate work with varying complexity
                complexity = 1 + (operation_count % 5)  # Cycle complexity 1-5

                start_op = time.time()
                await plugin.simulate_work(
                    task_name=f"{task_name}_op_{operation_count}", complexity=complexity
                )
                end_op = time.time()

                # Record response time (simulated)
                end_op - start_op

                operation_count += 1

                # Brief pause between operations
                await asyncio.sleep(0.1)

            except Exception as e:
                print(f"⚠️  Simulation operation failed: {e}")
                await asyncio.sleep(0.5)  # Longer pause on error

    async def _generate_pipeline_workload(self, plugin, task_name: str, duration: int):
        """Generate workload using pipeline plugin."""
        start_time = time.time()
        job_count = 0

        while time.time() - start_time < duration:
            try:
                # Submit job to pipeline
                job_data = {
                    "id": f"{task_name}_job_{job_count}",
                    "data": f"test_data_{job_count}",
                    "priority": job_count % 3,  # Vary priority
                }

                time.time()
                await plugin.submit_job(job_data)
                time.time()

                job_count += 1

                # Brief pause between jobs
                await asyncio.sleep(0.2)

            except Exception as e:
                print(f"⚠️  Pipeline operation failed: {e}")
                await asyncio.sleep(0.5)  # Longer pause on error

    async def _analyze_load_level_results(
        self, analyzer: PerformanceAnalyzer, load_level: int
    ) -> dict:
        """Analyze results for a specific load level."""
        service_name = f"load_level_{load_level}"

        # Get recent bottlenecks for this service
        recent_bottlenecks = [b for b in analyzer.bottlenecks if b.service_name == service_name]

        # Get recent audit events
        recent_events = [e for e in analyzer.audit_events if e.service == service_name]

        # Calculate performance summary
        metrics_list = analyzer.metrics_history.get(service_name, [])

        if metrics_list:
            avg_cpu = sum(m.cpu_usage[0] if m.cpu_usage else 0 for m in metrics_list) / len(
                metrics_list
            )
            avg_memory = sum(
                m.memory_usage[0] if m.memory_usage else 0 for m in metrics_list
            ) / len(metrics_list)
            max_cpu = max(max(m.cpu_usage) if m.cpu_usage else 0 for m in metrics_list)
            max_memory = max(max(m.memory_usage) if m.memory_usage else 0 for m in metrics_list)
        else:
            avg_cpu = avg_memory = max_cpu = max_memory = 0

        return {
            "load_level": load_level,
            "metrics_count": len(metrics_list),
            "bottlenecks": [
                {
                    "type": b.bottleneck_type,
                    "severity": b.severity,
                    "value": b.current_value,
                    "threshold": b.threshold_value,
                }
                for b in recent_bottlenecks
            ],
            "performance_summary": {
                "avg_cpu_usage": avg_cpu,
                "avg_memory_usage": avg_memory,
                "max_cpu_usage": max_cpu,
                "max_memory_usage": max_memory,
            },
            "audit_events": len(recent_events),
            "error_events": len([e for e in recent_events if e.severity == "error"]),
        }

    def _generate_bottleneck_report(self, results: dict, analyzer: PerformanceAnalyzer) -> dict:
        """Generate comprehensive bottleneck analysis report."""

        # Identify trend patterns
        load_levels = sorted([int(k.split("_")[-1]) for k in results])
        cpu_trend = [
            results[f"load_level_{level}"]["performance_summary"]["avg_cpu_usage"]
            for level in load_levels
        ]
        memory_trend = [
            results[f"load_level_{level}"]["performance_summary"]["avg_memory_usage"]
            for level in load_levels
        ]

        return {
            "test_summary": {
                "test_name": "Comprehensive Bottleneck Analysis",
                "test_duration": "30 seconds per load level",
                "load_levels_tested": load_levels,
                "total_bottlenecks": len(analyzer.bottlenecks),
                "total_audit_events": len(analyzer.audit_events),
            },
            "performance_trends": {
                "cpu_usage_by_load": dict(zip(load_levels, cpu_trend, strict=False)),
                "memory_usage_by_load": dict(zip(load_levels, memory_trend, strict=False)),
                "bottlenecks_by_load": {
                    level: len(results[f"load_level_{level}"]["bottlenecks"])
                    for level in load_levels
                },
            },
            "bottleneck_analysis": {
                "critical_bottlenecks": [
                    {
                        "service": b.service_name,
                        "type": b.bottleneck_type,
                        "severity": b.severity,
                        "value": b.current_value,
                        "threshold": b.threshold_value,
                        "recommendations": b.recommendations,
                    }
                    for b in analyzer.bottlenecks
                    if b.severity in ["critical", "high"]
                ],
                "bottleneck_types": {
                    bt: len([b for b in analyzer.bottlenecks if b.bottleneck_type == bt])
                    for bt in ["cpu", "memory", "response_time", "error_rate"]
                },
            },
            "detailed_results": results,
            "recommendations": self._generate_recommendations(analyzer.bottlenecks),
        }

    def _generate_recommendations(self, bottlenecks: list) -> list:
        """Generate actionable recommendations based on bottlenecks."""
        recommendations = []

        cpu_bottlenecks = [b for b in bottlenecks if b.bottleneck_type == "cpu"]
        memory_bottlenecks = [b for b in bottlenecks if b.bottleneck_type == "memory"]
        response_bottlenecks = [b for b in bottlenecks if b.bottleneck_type == "response_time"]
        error_bottlenecks = [b for b in bottlenecks if b.bottleneck_type == "error_rate"]

        if cpu_bottlenecks:
            recommendations.append(
                {
                    "category": "CPU Optimization",
                    "priority": "high",
                    "actions": [
                        "Implement horizontal pod autoscaling",
                        "Optimize CPU-intensive algorithms",
                        "Add CPU resource limits and requests",
                        "Consider async processing for heavy computations",
                    ],
                }
            )

        if memory_bottlenecks:
            recommendations.append(
                {
                    "category": "Memory Optimization",
                    "priority": "critical",
                    "actions": [
                        "Investigate memory leaks",
                        "Implement object pooling",
                        "Add memory monitoring and alerts",
                        "Optimize data structures and caching",
                    ],
                }
            )

        if response_bottlenecks:
            recommendations.append(
                {
                    "category": "Response Time Optimization",
                    "priority": "medium",
                    "actions": [
                        "Implement response caching",
                        "Optimize database queries",
                        "Add connection pooling",
                        "Consider CDN for static resources",
                    ],
                }
            )

        if error_bottlenecks:
            recommendations.append(
                {
                    "category": "Error Rate Reduction",
                    "priority": "high",
                    "actions": [
                        "Implement circuit breaker patterns",
                        "Add retry mechanisms with exponential backoff",
                        "Improve error handling and logging",
                        "Add health checks and monitoring",
                    ],
                }
            )

        return recommendations

    def _print_test_summary(self, report: dict):
        """Print a summary of the test results."""
        print("\\n" + "=" * 50)
        print("🎯 BOTTLENECK ANALYSIS TEST SUMMARY")
        print("=" * 50)

        summary = report["test_summary"]
        print(f"📊 Load levels tested: {summary['load_levels_tested']}")
        print(f"🚨 Total bottlenecks detected: {summary['total_bottlenecks']}")
        print(f"📝 Total audit events: {summary['total_audit_events']}")

        critical_bottlenecks = report["bottleneck_analysis"]["critical_bottlenecks"]
        if critical_bottlenecks:
            print("\\n⚠️  CRITICAL BOTTLENECKS DETECTED:")
            for bottleneck in critical_bottlenecks[:3]:  # Show top 3
                print(
                    f"   • {bottleneck['service']}: {bottleneck['type']} "
                    f"({bottleneck['value']:.2f} > {bottleneck['threshold']:.2f})"
                )

        print("\\n💡 RECOMMENDATIONS:")
        for rec in report["recommendations"][:2]:  # Show top 2 categories
            print(f"   🎯 {rec['category']} ({rec['priority']} priority)")
            for action in rec["actions"][:2]:  # Show top 2 actions
                print(f"      - {action}")

        print("\\n✅ Test completed successfully!")
        print("=" * 50)
