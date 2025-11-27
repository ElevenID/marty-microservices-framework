"""
Master End-to-End Test Runner

This test orchestrates all comprehensive end-to-end tests:
1. Bottleneck analysis with example plugins
2. Timeout detection and circuit breaker testing
3. Auditability and error tracking
4. Playwright visual testing
5. Comprehensive performance reporting with charts

Run with: pytest tests/e2e/test_master_e2e.py -v -s
"""

import asyncio
import builtins
import json
from pathlib import Path

import pytest
from tests.e2e.conftest import PerformanceAnalyzer, TimeoutMonitor
from tests.e2e.performance_reporting import generate_comprehensive_performance_report
from tests.e2e.test_auditability import TestAuditability
from tests.e2e.test_bottleneck_analysis import TestBottleneckAnalysis
from tests.e2e.test_playwright_visual import TestPlaywrightVisual
from tests.e2e.test_timeout_detection import TestTimeoutDetection


class TestMasterE2E:
    """Master end-to-end test suite that runs all performance tests."""

    @pytest.mark.asyncio
    async def test_comprehensive_end_to_end_analysis(
        self,
        simulation_plugin,
        pipeline_plugin,
        monitoring_plugin,
        circuit_breaker_plugin,
        performance_analyzer: PerformanceAnalyzer,
        timeout_monitor: TimeoutMonitor,
        test_report_dir: Path,
    ):
        """
        Master end-to-end test that runs all performance analysis tests
        and generates comprehensive reports with visual charts.
        """

        print("\\n" + "=" * 70)
        print("🚀 STARTING COMPREHENSIVE END-TO-END ANALYSIS")
        print("=" * 70)
        print("This test will run:")
        print("  1. 📊 Bottleneck Analysis (performance under load)")
        print("  2. ⏱️  Timeout Detection (circuit breaker testing)")
        print("  3. 📋 Auditability (error tracking and compliance)")
        print("  4. 🎭 Visual Testing (Playwright UI testing)")
        print("  5. 📈 Performance Reporting (charts and insights)")
        print("=" * 70)

        # Initialize test results storage
        test_results = {
            "bottleneck_analysis": None,
            "timeout_detection": None,
            "auditability": None,
            "visual_testing": None,
        }

        # Create master report directory
        master_report_dir = test_report_dir / "master_e2e_report"
        master_report_dir.mkdir(exist_ok=True)

        try:
            # Test 1: Bottleneck Analysis
            print("\\n📊 PHASE 1: Bottleneck Analysis")
            print("-" * 50)

            bottleneck_test = TestBottleneckAnalysis()

            # Run bottleneck analysis and capture results
            try:
                await bottleneck_test.test_comprehensive_bottleneck_analysis(
                    simulation_plugin=simulation_plugin,
                    pipeline_plugin=pipeline_plugin,
                    monitoring_plugin=monitoring_plugin,
                    performance_analyzer=performance_analyzer,
                    test_report_dir=master_report_dir,
                )

                # Load the generated report
                bottleneck_report_file = master_report_dir / "bottleneck_analysis_report.json"
                if bottleneck_report_file.exists():
                    with open(bottleneck_report_file) as f:
                        test_results["bottleneck_analysis"] = json.load(f)

                print("✅ Bottleneck analysis completed successfully")

            except Exception as e:
                print(f"❌ Bottleneck analysis failed: {e}")
                test_results["bottleneck_analysis"] = {
                    "error": str(e),
                    "status": "failed",
                }

            # Brief pause between tests
            await asyncio.sleep(3)

            # Test 2: Timeout Detection
            print("\\n⏱️  PHASE 2: Timeout Detection & Circuit Breaker Testing")
            print("-" * 50)

            timeout_test = TestTimeoutDetection()

            try:
                await timeout_test.test_timeout_detection_and_circuit_breaker(
                    simulation_plugin=simulation_plugin,
                    circuit_breaker_plugin=circuit_breaker_plugin,
                    performance_analyzer=performance_analyzer,
                    timeout_monitor=timeout_monitor,
                    test_report_dir=master_report_dir,
                )

                # Load the generated report
                timeout_report_file = master_report_dir / "timeout_detection_report.json"
                if timeout_report_file.exists():
                    with open(timeout_report_file) as f:
                        test_results["timeout_detection"] = json.load(f)

                print("✅ Timeout detection completed successfully")

            except Exception as e:
                print(f"❌ Timeout detection failed: {e}")
                test_results["timeout_detection"] = {
                    "error": str(e),
                    "status": "failed",
                }

            # Brief pause between tests
            await asyncio.sleep(3)

            # Test 3: Auditability
            print("\\n📋 PHASE 3: Auditability & Error Tracking")
            print("-" * 50)

            audit_test = TestAuditability()

            try:
                await audit_test.test_comprehensive_auditability(
                    simulation_plugin=simulation_plugin,
                    pipeline_plugin=pipeline_plugin,
                    monitoring_plugin=monitoring_plugin,
                    performance_analyzer=performance_analyzer,
                    test_report_dir=master_report_dir,
                )

                # Load the generated report
                audit_report_file = master_report_dir / "auditability_report.json"
                if audit_report_file.exists():
                    with open(audit_report_file) as f:
                        test_results["auditability"] = json.load(f)

                print("✅ Auditability analysis completed successfully")

            except Exception as e:
                print(f"❌ Auditability analysis failed: {e}")
                test_results["auditability"] = {"error": str(e), "status": "failed"}

            # Brief pause between tests
            await asyncio.sleep(3)

            # Test 4: Visual Testing (Playwright)
            print("\\n🎭 PHASE 4: Visual Testing (Playwright)")
            print("-" * 50)

            visual_test = TestPlaywrightVisual()

            try:
                await visual_test.test_dashboard_visual_testing(
                    simulation_plugin=simulation_plugin,
                    monitoring_plugin=monitoring_plugin,
                    performance_analyzer=performance_analyzer,
                    test_report_dir=master_report_dir,
                )

                # Load the generated report
                visual_report_file = master_report_dir / "visual_testing_report.json"
                if visual_report_file.exists():
                    with open(visual_report_file) as f:
                        test_results["visual_testing"] = json.load(f)

                print("✅ Visual testing completed successfully")

            except Exception as e:
                print(f"❌ Visual testing failed: {e}")
                test_results["visual_testing"] = {"error": str(e), "status": "failed"}

            # Test 5: Comprehensive Reporting
            print("\\n📈 PHASE 5: Comprehensive Performance Reporting")
            print("-" * 50)

            try:
                comprehensive_report = await generate_comprehensive_performance_report(
                    test_report_dir=master_report_dir,
                    bottleneck_report=test_results["bottleneck_analysis"],
                    timeout_report=test_results["timeout_detection"],
                    audit_report=test_results["auditability"],
                    visual_report=test_results["visual_testing"],
                )

                print("✅ Comprehensive reporting completed successfully")

            except Exception as e:
                print(f"❌ Comprehensive reporting failed: {e}")
                comprehensive_report = {"error": str(e), "status": "failed"}

            # Generate master summary
            master_summary = self._generate_master_summary(test_results, comprehensive_report)

            # Save master summary
            summary_file = master_report_dir / "master_e2e_summary.json"
            with open(summary_file, "w") as f:
                json.dump(master_summary, f, indent=2)

            # Print final summary
            self._print_master_summary(master_summary, master_report_dir)

            # Assertions for test validation
            self._validate_test_results(test_results, master_summary)

        except Exception as e:
            print(f"\\n❌ CRITICAL ERROR in master E2E test: {e}")
            raise

        print("\\n" + "=" * 70)
        print("✅ COMPREHENSIVE END-TO-END ANALYSIS COMPLETED")
        print("=" * 70)

    def _generate_master_summary(
        self, test_results: builtins.dict, comprehensive_report: builtins.dict
    ) -> builtins.dict:
        """Generate master summary of all test results."""

        # Count successful tests
        successful_tests = 0
        total_tests = len(test_results)

        test_status = {}
        for test_name, result in test_results.items():
            if result and not result.get("error"):
                successful_tests += 1
                test_status[test_name] = "passed"
            else:
                test_status[test_name] = "failed"

        # Extract key metrics
        key_metrics = {}

        # Bottleneck metrics
        if (
            test_results["bottleneck_analysis"]
            and "test_summary" in test_results["bottleneck_analysis"]
        ):
            bottleneck_summary = test_results["bottleneck_analysis"]["test_summary"]
            key_metrics["bottleneck"] = {
                "load_levels_tested": len(bottleneck_summary.get("load_levels_tested", [])),
                "total_bottlenecks": bottleneck_summary.get("total_bottlenecks", 0),
            }

        # Timeout metrics
        if (
            test_results["timeout_detection"]
            and "test_summary" in test_results["timeout_detection"]
        ):
            timeout_summary = test_results["timeout_detection"]["test_summary"]
            key_metrics["timeout"] = {
                "phases_tested": len(timeout_summary.get("phases_tested", [])),
                "total_timeouts": timeout_summary.get("total_timeouts", 0),
                "timeout_rate": timeout_summary.get("overall_timeout_rate", 0),
            }

        # Audit metrics
        if test_results["auditability"] and "test_summary" in test_results["auditability"]:
            audit_summary = test_results["auditability"]["test_summary"]
            key_metrics["audit"] = {
                "total_events": audit_summary.get("total_events_generated", 0),
                "correlation_chains": audit_summary.get("total_correlation_chains", 0),
            }

        # Visual metrics
        if test_results["visual_testing"] and "test_summary" in test_results["visual_testing"]:
            visual_summary = test_results["visual_testing"]["test_summary"]
            key_metrics["visual"] = {
                "success_rate": visual_summary.get("success_rate", 0),
                "screenshots_generated": len(
                    test_results["visual_testing"].get("screenshots_generated", [])
                ),
            }

        # Overall health assessment
        overall_health = "excellent"
        if successful_tests < total_tests:
            overall_health = "needs_attention" if successful_tests < total_tests * 0.5 else "good"

        # Critical issues count
        critical_issues = []
        if comprehensive_report and "executive_summary" in comprehensive_report:
            critical_issues = comprehensive_report["executive_summary"].get("key_findings", [])

        return {
            "test_execution_summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": (successful_tests / total_tests * 100) if total_tests > 0 else 0,
                "test_status": test_status,
            },
            "key_metrics": key_metrics,
            "overall_assessment": {
                "health_status": overall_health,
                "critical_issues_count": len(critical_issues),
                "critical_issues": critical_issues,
            },
            "test_results": test_results,
            "comprehensive_report_available": comprehensive_report
            and not comprehensive_report.get("error"),
        }

    def _print_master_summary(self, master_summary: builtins.dict, report_dir: Path):
        """Print comprehensive master summary."""

        print("\\n" + "=" * 70)
        print("📋 MASTER END-TO-END TEST SUMMARY")
        print("=" * 70)

        execution = master_summary["test_execution_summary"]
        assessment = master_summary["overall_assessment"]
        metrics = master_summary["key_metrics"]

        # Test execution summary
        print("\\n🎯 TEST EXECUTION:")
        print(f"   Tests Run: {execution['successful_tests']}/{execution['total_tests']}")
        print(f"   Success Rate: {execution['success_rate']:.1f}%")

        # Individual test status
        print("\\n📊 INDIVIDUAL TEST STATUS:")
        for test_name, status in execution["test_status"].items():
            status_icon = "✅" if status == "passed" else "❌"
            test_display = test_name.replace("_", " ").title()
            print(f"   {status_icon} {test_display}")

        # Key metrics
        print("\\n📈 KEY METRICS:")
        if "bottleneck" in metrics:
            b_metrics = metrics["bottleneck"]
            print(
                f"   🔍 Bottleneck Analysis: {b_metrics['load_levels_tested']} load levels, "
                f"{b_metrics['total_bottlenecks']} bottlenecks detected"
            )

        if "timeout" in metrics:
            t_metrics = metrics["timeout"]
            print(
                f"   ⏱️  Timeout Detection: {t_metrics['phases_tested']} phases, "
                f"{t_metrics['total_timeouts']} timeouts ({t_metrics['timeout_rate']:.1f}% rate)"
            )

        if "audit" in metrics:
            a_metrics = metrics["audit"]
            print(
                f"   📋 Auditability: {a_metrics['total_events']} events, "
                f"{a_metrics['correlation_chains']} correlation chains"
            )

        if "visual" in metrics:
            v_metrics = metrics["visual"]
            print(
                f"   🎭 Visual Testing: {v_metrics['success_rate']:.1f}% success rate, "
                f"{v_metrics['screenshots_generated']} screenshots"
            )

        # Overall assessment
        print("\\n🏆 OVERALL ASSESSMENT:")
        health_icon = {"excellent": "🟢", "good": "🟡", "needs_attention": "🔴"}.get(
            assessment["health_status"], "⚪"
        )
        print(
            f"   {health_icon} Health Status: {assessment['health_status'].replace('_', ' ').title()}"
        )
        print(f"   ⚠️  Critical Issues: {assessment['critical_issues_count']}")

        if assessment["critical_issues"]:
            print("\\n🚨 CRITICAL ISSUES:")
            for i, issue in enumerate(assessment["critical_issues"][:3], 1):
                print(f"   {i}. {issue}")

        # Report locations
        print("\\n📁 REPORTS GENERATED:")
        print(f"   📋 Master Summary: {report_dir / 'master_e2e_summary.json'}")
        print(f"   📊 Comprehensive Report: {report_dir / 'comprehensive_performance_report.json'}")
        print(f"   🌐 HTML Report: {report_dir / 'performance_report.html'}")
        print(f"   📈 Charts Directory: {report_dir / 'charts'}")

        # Next steps
        print("\\n💡 RECOMMENDED NEXT STEPS:")
        if assessment["health_status"] == "excellent":
            print("   ✨ System is performing excellently!")
            print("   📚 Document current configurations as best practices")
            print("   🔄 Continue regular monitoring with current test suite")
        elif assessment["health_status"] == "good":
            print("   🔧 Address identified performance bottlenecks")
            print("   📊 Review detailed reports for optimization opportunities")
            print("   🔍 Increase monitoring frequency for at-risk areas")
        else:
            print("   🚨 IMMEDIATE ACTION REQUIRED")
            print("   🔥 Address all critical issues identified")
            print("   📈 Implement emergency performance optimizations")
            print("   👥 Consider involving performance engineering team")

        print("\\n" + "=" * 70)

    def _validate_test_results(self, test_results: builtins.dict, master_summary: builtins.dict):
        """Validate test results and assert critical requirements."""

        execution = master_summary["test_execution_summary"]

        # At least 75% of tests should pass
        assert execution["success_rate"] >= 75, (
            f"Test success rate too low: {execution['success_rate']:.1f}% (minimum: 75%)"
        )

        # At least one test should have completed successfully
        assert execution["successful_tests"] > 0, "No tests completed successfully"

        # Critical assertion: if bottleneck analysis ran, it should detect the framework
        if test_results["bottleneck_analysis"] and not test_results["bottleneck_analysis"].get(
            "error"
        ):
            bottleneck_report = test_results["bottleneck_analysis"]
            assert "test_summary" in bottleneck_report, (
                "Bottleneck analysis should generate test summary"
            )

        # Critical assertion: if timeout detection ran, it should have phase results
        if test_results["timeout_detection"] and not test_results["timeout_detection"].get("error"):
            timeout_report = test_results["timeout_detection"]
            assert "test_summary" in timeout_report, (
                "Timeout detection should generate test summary"
            )

        # Critical assertion: if audit ran, it should track events
        if test_results["auditability"] and not test_results["auditability"].get("error"):
            audit_report = test_results["auditability"]
            assert "test_summary" in audit_report, "Audit analysis should generate test summary"

            # Should have generated some events
            if "test_summary" in audit_report:
                events_generated = audit_report["test_summary"].get("total_events_generated", 0)
                assert events_generated > 0, "Audit analysis should generate audit events"

        # Warning assertions (non-blocking)
        assessment = master_summary["overall_assessment"]
        if assessment["critical_issues_count"] > 5:
            print(f"\\n⚠️  WARNING: {assessment['critical_issues_count']} critical issues detected")

        print("\\n✅ All validation assertions passed!")
        print(f"   📊 Success Rate: {execution['success_rate']:.1f}%")
        print(f"   🎯 Tests Passed: {execution['successful_tests']}/{execution['total_tests']}")
        print(f"   🚨 Critical Issues: {assessment['critical_issues_count']}")


# Convenience function for running master E2E test standalone
async def run_master_e2e_test():
    """Run master E2E test as standalone function."""

    print("🚀 Running Master End-to-End Test Suite...")
    print("This may take several minutes to complete all tests.")

    # This would typically be called by pytest, but can be used standalone
    # Note: Requires proper fixture setup when run outside pytest


if __name__ == "__main__":
    print("To run the master E2E test, use:")
    print("pytest tests/e2e/test_master_e2e.py -v -s")
    print("\\nOr run individual tests:")
    print("pytest tests/e2e/test_bottleneck_analysis.py -v -s")
    print("pytest tests/e2e/test_timeout_detection.py -v -s")
    print("pytest tests/e2e/test_auditability.py -v -s")
    print("pytest tests/e2e/test_playwright_visual.py -v -s")
