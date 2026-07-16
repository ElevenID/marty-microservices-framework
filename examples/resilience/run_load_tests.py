"""
Load Testing Script for Resilience Framework

Demonstrates how to use the load testing framework to validate
resilience patterns under realistic concurrency scenarios.
"""

import asyncio
import logging
from pathlib import Path

from mmf.framework.resilience.load_testing import (
    LoadTester,
    LoadTestScenario,
    LoadTestSuite,
    LoadTestType,
    create_resilience_test_scenarios,
)

logger = logging.getLogger(__name__)


async def run_individual_test():
    """Run a single load test scenario"""
    print("\n=== Running Individual Load Test ===")

    # Define a custom spike test scenario
    scenario = LoadTestScenario(
        name="custom_spike_test",
        test_type=LoadTestType.SPIKE,

        # Load parameters
        initial_users=5,
        max_users=50,
        ramp_up_duration=15,    # Quick spike
        test_duration=60,       # 1 minute sustained
        ramp_down_duration=10,

        # Target service
        target_url="http://localhost:8000",
        request_paths=[
            "/api/external-data",
            "/api/cache/test-key",
            "/api/heavy-computation",
            "/api/error-prone"
        ],

        # Request configuration
        request_method="GET",
        request_headers={"User-Agent": "LoadTester-1.0"},
        think_time_min=0.5,
        think_time_max=2.0,
        request_timeout=10.0,

        # Success criteria
        max_error_rate=0.15,           # Allow 15% error rate for spike test
        max_response_time_p95=5.0,     # 5 second P95
        min_throughput=5.0,            # 5 RPS minimum

        # Resilience validation
        validate_circuit_breakers=True,
        validate_connection_pools=True,
        validate_bulkheads=True,

        # Output
        output_directory="./load_test_results"
    )

    # Run the test
    tester = LoadTester(scenario)
    try:
        await tester.initialize()
        print(f"Starting load test: {scenario.name}")

        metrics = await tester.run_test()

        # Display results
        print(f"\n=== Test Results: {scenario.name} ===")
        print(f"Total Requests: {metrics.total_requests}")
        print(f"Successful Requests: {metrics.successful_requests}")
        print(f"Failed Requests: {metrics.failed_requests}")
        print(f"Error Rate: {metrics.error_rate:.2%}")
        print(f"Average Response Time: {metrics.avg_response_time:.3f}s")
        print(f"P95 Response Time: {metrics.p95_response_time:.3f}s")
        print(f"P99 Response Time: {metrics.p99_response_time:.3f}s")
        print(f"Throughput: {metrics.requests_per_second:.2f} RPS")
        print(f"Test Duration: {metrics.duration:.1f}s")

        # Validation results
        error_rate_pass = metrics.error_rate <= scenario.max_error_rate
        response_time_pass = metrics.p95_response_time <= scenario.max_response_time_p95
        throughput_pass = metrics.requests_per_second >= scenario.min_throughput

        print(f"\n=== Validation Results ===")
        print(f"Error Rate Pass: {'✓' if error_rate_pass else '✗'} ({metrics.error_rate:.2%} <= {scenario.max_error_rate:.2%})")
        print(f"Response Time Pass: {'✓' if response_time_pass else '✗'} ({metrics.p95_response_time:.3f}s <= {scenario.max_response_time_p95}s)")
        print(f"Throughput Pass: {'✓' if throughput_pass else '✗'} ({metrics.requests_per_second:.2f} >= {scenario.min_throughput} RPS)")

        overall_pass = error_rate_pass and response_time_pass and throughput_pass
        print(f"Overall Test Result: {'✓ PASSED' if overall_pass else '✗ FAILED'}")

    finally:
        await tester.close()


async def run_resilience_test_suite():
    """Run a comprehensive resilience test suite"""
    print("\n=== Running Resilience Test Suite ===")

    # Create pre-configured resilience test scenarios
    scenarios = create_resilience_test_scenarios("http://localhost:8000")

    # Customize scenarios for local testing
    for scenario in scenarios:
        scenario.max_users = min(scenario.max_users, 30)  # Reduce load for local testing
        scenario.test_duration = min(scenario.test_duration, 120)  # Shorter tests
        scenario.output_directory = "./load_test_results"

    print(f"Created {len(scenarios)} test scenarios:")
    for scenario in scenarios:
        print(f"  - {scenario.name} ({scenario.test_type.value}): {scenario.max_users} users, {scenario.test_duration}s")

    # Run the test suite
    suite = LoadTestSuite(scenarios)

    try:
        results = await suite.run_all_tests()

        # Display suite results
        print(f"\n=== Test Suite Results ===")
        print(f"Total Scenarios: {len(scenarios)}")

        passed_tests = 0
        total_requests = 0
        total_errors = 0

        for i, (scenario, result) in enumerate(zip(scenarios, results)):
            error_rate_pass = result.error_rate <= scenario.max_error_rate
            response_time_pass = result.p95_response_time <= scenario.max_response_time_p95
            throughput_pass = result.requests_per_second >= scenario.min_throughput

            test_passed = error_rate_pass and response_time_pass and throughput_pass
            if test_passed:
                passed_tests += 1

            total_requests += result.total_requests
            total_errors += result.failed_requests

            print(f"\n{i+1}. {scenario.name} ({scenario.test_type.value}):")
            print(f"   Requests: {result.total_requests}, Errors: {result.failed_requests} ({result.error_rate:.2%})")
            print(f"   Response Time P95: {result.p95_response_time:.3f}s")
            print(f"   Throughput: {result.requests_per_second:.2f} RPS")
            print(f"   Result: {'✓ PASSED' if test_passed else '✗ FAILED'}")

        overall_error_rate = total_errors / max(total_requests, 1)

        print(f"\n=== Suite Summary ===")
        print(f"Passed Tests: {passed_tests}/{len(scenarios)}")
        print(f"Overall Success Rate: {passed_tests/len(scenarios):.1%}")
        print(f"Total Requests: {total_requests}")
        print(f"Overall Error Rate: {overall_error_rate:.2%}")

        suite_passed = passed_tests == len(scenarios)
        print(f"Suite Result: {'✓ ALL TESTS PASSED' if suite_passed else '✗ SOME TESTS FAILED'}")

    except Exception as e:
        print(f"Test suite failed: {e}")
        logger.error(f"Test suite error: {e}")


async def run_endurance_test():
    """Run a long-duration endurance test"""
    print("\n=== Running Endurance Test ===")

    scenario = LoadTestScenario(
        name="endurance_test",
        test_type=LoadTestType.ENDURANCE,

        # Moderate sustained load
        initial_users=10,
        max_users=25,
        ramp_up_duration=60,
        test_duration=600,      # 10 minutes
        ramp_down_duration=30,

        target_url="http://localhost:8000",
        request_paths=[
            "/api/cache/endurance-key",
            "/health",
            "/api/external-data"
        ],

        # Conservative settings for stability
        think_time_min=1.0,
        think_time_max=3.0,
        request_timeout=15.0,

        # Strict criteria for endurance
        max_error_rate=0.02,         # 2% max error rate
        max_response_time_p95=3.0,   # 3 second P95
        min_throughput=3.0,          # 3 RPS minimum

        validate_circuit_breakers=True,
        validate_connection_pools=True,
        output_directory="./load_test_results"
    )

    tester = LoadTester(scenario)
    try:
        await tester.initialize()
        print(f"Starting endurance test (this will take {scenario.test_duration/60:.1f} minutes)...")

        metrics = await tester.run_test()

        # Analyze endurance-specific metrics
        print(f"\n=== Endurance Test Results ===")
        print(f"Test Duration: {metrics.duration/60:.1f} minutes")
        print(f"Total Requests: {metrics.total_requests}")
        print(f"Error Rate: {metrics.error_rate:.3%}")
        print(f"Average Response Time: {metrics.avg_response_time:.3f}s")
        print(f"Response Time Stability (P95): {metrics.p95_response_time:.3f}s")
        print(f"Sustained Throughput: {metrics.requests_per_second:.2f} RPS")

        # Check for performance degradation over time
        if len(metrics.response_times) > 100:
            first_quarter = metrics.response_times[:len(metrics.response_times)//4]
            last_quarter = metrics.response_times[-len(metrics.response_times)//4:]

            first_avg = sum(first_quarter) / len(first_quarter)
            last_avg = sum(last_quarter) / len(last_quarter)
            degradation = (last_avg - first_avg) / first_avg if first_avg > 0 else 0

            print(f"Performance Degradation: {degradation:.2%}")

            if abs(degradation) < 0.1:  # Less than 10% change
                print("✓ Performance remained stable")
            else:
                print("⚠ Performance degradation detected")

    finally:
        await tester.close()


async def main():
    """Main load testing execution"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Ensure output directory exists
    Path("./load_test_results").mkdir(exist_ok=True)

    print("Resilience Framework Load Testing")
    print("=================================")
    print("Make sure the example service is running on http://localhost:8000")
    print("Start it with: python examples/example_resilient_service.py")

    # Wait for user confirmation
    input("\nPress Enter to continue with load testing...")

    try:
        # Run different types of load tests
        await run_individual_test()

        # Brief pause between tests
        print("\nWaiting 10 seconds before next test...")
        await asyncio.sleep(10)

        await run_resilience_test_suite()

        # Ask if user wants to run endurance test
        run_endurance = input("\nRun endurance test (10 minutes)? [y/N]: ").lower() == 'y'
        if run_endurance:
            await run_endurance_test()

        print("\n=== Load Testing Complete ===")
        print("Check the './load_test_results' directory for detailed reports.")

    except KeyboardInterrupt:
        print("\nLoad testing interrupted by user")
    except Exception as e:
        print(f"Load testing failed: {e}")
        logger.error(f"Load testing error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
