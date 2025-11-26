"""
Example load testing scripts for common scenarios
"""

import argparse
import asyncio
import os
import sys

# Add the framework to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from mmf_new.framework.observability.load_testing.load_tester import (
    LoadTestConfig,
    LoadTestRunner,
)


async def test_grpc_service():
    """Example gRPC service load test"""
    config = LoadTestConfig(
        target_host="localhost",
        target_port=50051,
        test_duration_seconds=30,
        concurrent_users=5,
        ramp_up_seconds=5,
        protocol="grpc",
        test_name="grpc_service_test",
        grpc_service="UserService",
        grpc_method="GetUser",
        grpc_payload={"user_id": "123"},
    )

    runner = LoadTestRunner()
    report = await runner.run_load_test(config)

    runner.print_summary(report)
    runner.save_report(report, "grpc_load_test_report.json")


async def test_http_api():
    """Example HTTP API load test"""
    config = LoadTestConfig(
        target_host="localhost",
        target_port=8000,
        test_duration_seconds=60,
        concurrent_users=10,
        ramp_up_seconds=10,
        requests_per_second=50,
        protocol="http",
        test_name="http_api_test",
        http_path="/api/v1/health",
        http_method="GET",
        http_headers={"Content-Type": "application/json"},
    )

    runner = LoadTestRunner()
    report = await runner.run_load_test(config)

    runner.print_summary(report)
    runner.save_report(report, "http_load_test_report.json")


async def stress_test():
    """High-load stress test scenario"""
    config = LoadTestConfig(
        target_host="localhost",
        target_port=50051,
        test_duration_seconds=120,
        concurrent_users=50,
        ramp_up_seconds=30,
        requests_per_second=500,
        protocol="grpc",
        test_name="stress_test",
        grpc_service="OrderService",
        grpc_method="CreateOrder",
    )

    runner = LoadTestRunner()
    report = await runner.run_load_test(config)

    runner.print_summary(report)
    runner.save_report(report, "stress_test_report.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run load tests")
    parser.add_argument(
        "test_type", choices=["grpc", "http", "stress"], help="Type of load test to run"
    )

    args = parser.parse_args()

    if args.test_type == "grpc":
        asyncio.run(test_grpc_service())
    elif args.test_type == "http":
        asyncio.run(test_http_api())
    elif args.test_type == "stress":
        asyncio.run(stress_test())
