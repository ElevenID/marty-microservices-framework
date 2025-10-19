"""
MMF Demo: Load Testing and Error Simulation Script
Demonstrates transaction flows, error handling, and performance bottlenecks
"""
import asyncio
import json
import os
import random
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from io import StringIO
from typing import Any

import aiohttp
from mmf_analytics_plugin import PluginRegistry, TransactionAnalyticsPlugin


class OutputCapture:
    """Captures print output to both console and file"""

    def __init__(self, filename: str):
        self.filename = filename
        self.terminal = sys.stdout
        self.captured_output = []

    def write(self, message):
        self.terminal.write(message)
        self.captured_output.append(message)

    def flush(self):
        self.terminal.flush()

    def save_to_file(self):
        """Save captured output to file"""
        with open(self.filename, 'w') as f:
            f.writelines(self.captured_output)

@dataclass
class TestScenario:
    """Configuration for a test scenario"""
    name: str
    requests_per_second: int
    duration_seconds: int
    error_rate_percent: float
    large_order_percent: float  # Percentage of orders that will trigger payment delays

@dataclass
class TestResult:
    """Results from a test run"""
    scenario_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    max_response_time: float
    error_rate_percent: float
    throughput_rps: float
    test_duration: float

class LoadTester:
    """Load testing framework for MMF services"""

    def __init__(self, base_url: str = None):
        # Auto-detect if running in Docker
        if base_url is None:
            if os.getenv('DOCKER_ENV') == 'true':
                self.base_url = "http://order-service"
            else:
                self.base_url = "http://localhost"
        else:
            self.base_url = base_url
        self.plugin_registry = PluginRegistry()
        self.analytics_plugin = TransactionAnalyticsPlugin()

        # Initialize analytics plugin
        self.plugin_registry.register_plugin(self.analytics_plugin, {
            'performance_threshold_ms': 500,
            'error_threshold_percent': 2
        })

        self.test_results: list[TestResult] = []

    async def run_scenario(self, scenario: TestScenario) -> TestResult:
        """Run a specific test scenario"""
        print(f"\n🧪 Running scenario: {scenario.name}")
        print(f"   RPS: {scenario.requests_per_second}, Duration: {scenario.duration_seconds}s")
        print(f"   Expected error rate: {scenario.error_rate_percent}%")

        start_time = time.time()
        tasks = []
        request_times = []
        successful_requests = 0
        failed_requests = 0

        # Calculate total requests
        total_requests = scenario.requests_per_second * scenario.duration_seconds
        request_interval = 1.0 / scenario.requests_per_second

        async with aiohttp.ClientSession() as session:
            for i in range(total_requests):
                # Create request task
                task = asyncio.create_task(
                    self._make_order_request(
                        session,
                        i,
                        scenario.error_rate_percent,
                        scenario.large_order_percent
                    )
                )
                tasks.append(task)

                # Space out requests to maintain RPS
                if i < total_requests - 1:  # Don't wait after the last request
                    await asyncio.sleep(request_interval)

            # Wait for all requests to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in results:
                if isinstance(result, Exception):
                    failed_requests += 1
                    self._publish_error_event(str(result))
                elif result:
                    successful_requests += 1
                    request_times.append(result['response_time'])
                    self._publish_success_event(result)
                else:
                    failed_requests += 1

        end_time = time.time()
        test_duration = end_time - start_time

        # Calculate metrics
        avg_response_time = sum(request_times) / len(request_times) if request_times else 0
        max_response_time = max(request_times) if request_times else 0
        error_rate = (failed_requests / total_requests) * 100
        throughput = total_requests / test_duration

        result = TestResult(
            scenario_name=scenario.name,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            average_response_time=avg_response_time,
            max_response_time=max_response_time,
            error_rate_percent=error_rate,
            throughput_rps=throughput,
            test_duration=test_duration
        )

        self.test_results.append(result)
        self._print_scenario_results(result)
        return result

    async def _make_order_request(self, session: aiohttp.ClientSession, request_id: int,
                                  error_rate: float, large_order_percent: float) -> dict[str, Any] | None:
        """Make a single order request"""
        correlation_id = f"LOAD-TEST-{request_id}-{int(time.time() * 1000)}"

        # Simulate different order types that trigger different behaviors
        order_amount = 50.0  # Default small order

        # Some orders will be large (triggering payment delays)
        if random.random() < (large_order_percent / 100):
            order_amount = random.uniform(1000, 5000)  # Large order triggers fraud check delay

        # Some orders will have invalid data (triggering errors)
        if random.random() < (error_rate / 100):
            order_amount = -1  # Invalid amount triggers error

        # Use actual product IDs from inventory
        available_products = ["LAPTOP-001", "PHONE-002", "TABLET-003", "HEADPHONES-004", "MONITOR-005"]
        product_prices = {"LAPTOP-001": 999.99, "PHONE-002": 599.99, "TABLET-003": 399.99, "HEADPHONES-004": 199.99, "MONITOR-005": 299.99}

        selected_product = random.choice(available_products)
        item_quantity = random.randint(1, 3)

        # For large orders, increase quantity or select expensive items
        if order_amount > 1000:
            if selected_product in ["LAPTOP-001", "PHONE-002"]:
                item_quantity = random.randint(2, 5)  # More expensive items

        order_data = {
            "customer_id": f"user_{request_id % 100}",  # Simulate 100 different users
            "items": [
                {
                    "product_id": selected_product,
                    "quantity": item_quantity,
                    "price": product_prices[selected_product]
                }
            ],
            "shipping_address": f"123 Test St, City {request_id % 10}, State {random.randint(10000, 99999)}"
        }

        start_time = time.time()

        try:
            async with session.post(
                f"{self.base_url}:8001/orders",
                json=order_data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to milliseconds

                if response.status == 200:
                    response_data = await response.json()
                    return {
                        'correlation_id': correlation_id,
                        'response_time': response_time,
                        'status': 'success',
                        'order_id': response_data.get('order_id'),
                        'amount': order_amount
                    }
                else:
                    error_text = await response.text()
                    self._publish_error_event(f"HTTP {response.status}: {error_text}", correlation_id)
                    return None

        except Exception as e:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            self._publish_error_event(str(e), correlation_id)
            return None

    def _publish_success_event(self, result: dict[str, Any]) -> None:
        """Publish success event to analytics plugin"""
        event = {
            'event': 'load_test_order_completed',
            'correlation_id': result['correlation_id'],
            'processing_time_ms': result['response_time'],
            'order_amount': result.get('amount', 0),
            'timestamp': datetime.utcnow().isoformat()
        }
        self.plugin_registry.process_event(event)

    def _publish_error_event(self, error_message: str, correlation_id: str = None) -> None:
        """Publish error event to analytics plugin"""
        event = {
            'event': 'load_test_order_failed',
            'correlation_id': correlation_id or f"ERROR-{int(time.time() * 1000)}",
            'error': error_message,
            'timestamp': datetime.utcnow().isoformat()
        }
        self.plugin_registry.process_event(event)

    def _print_scenario_results(self, result: TestResult) -> None:
        """Print results for a scenario"""
        print(f"\n📊 Results for {result.scenario_name}:")
        print(f"   Total Requests: {result.total_requests}")
        print(f"   Successful: {result.successful_requests}")
        print(f"   Failed: {result.failed_requests}")
        print(f"   Success Rate: {((result.successful_requests / result.total_requests) * 100):.1f}%")
        print(f"   Average Response Time: {result.average_response_time:.2f}ms")
        print(f"   Max Response Time: {result.max_response_time:.2f}ms")
        print(f"   Throughput: {result.throughput_rps:.2f} RPS")
        print(f"   Test Duration: {result.test_duration:.2f}s")

    def generate_load_test_report(self) -> dict[str, Any]:
        """Generate comprehensive load test report"""
        if not self.test_results:
            return {"error": "No test results available"}

        # Calculate overall statistics
        total_requests = sum(r.total_requests for r in self.test_results)
        total_successful = sum(r.successful_requests for r in self.test_results)
        total_failed = sum(r.failed_requests for r in self.test_results)

        avg_response_times = [r.average_response_time for r in self.test_results]
        overall_avg_response = sum(avg_response_times) / len(avg_response_times)

        # Get analytics report
        analytics_report = self.analytics_plugin.generate_performance_report()

        report = {
            'load_test_summary': {
                'test_scenarios_run': len(self.test_results),
                'total_requests': total_requests,
                'total_successful_requests': total_successful,
                'total_failed_requests': total_failed,
                'overall_success_rate_percent': (total_successful / total_requests * 100) if total_requests > 0 else 0,
                'average_response_time_ms': overall_avg_response,
                'scenarios': [asdict(result) for result in self.test_results]
            },
            'performance_analysis': analytics_report,
            'test_execution_timestamp': datetime.utcnow().isoformat()
        }

        return report

class DemoOrchestrator:
    """Orchestrates the complete MMF demo"""

    def __init__(self):
        self.load_tester = LoadTester()

    async def run_comprehensive_demo(self) -> None:
        """Run the complete demo showcasing MMF features"""
        print("🚀 Starting MMF Comprehensive Demo")
        print("=" * 60)
        print("This demo will showcase:")
        print("✅ Transaction traceability and audit logging")
        print("✅ Error handling and root cause analysis")
        print("✅ Performance bottleneck identification")
        print("✅ Plugin architecture with real-time analytics")
        print("✅ Load testing and scalability analysis")
        print("=" * 60)

        # Define test scenarios (adjusted for realistic throughput given payment service bottlenecks)
        scenarios = [
            TestScenario(
                name="Baseline Performance Test",
                requests_per_second=2,  # Reduced to match payment service capacity
                duration_seconds=10,
                error_rate_percent=0,
                large_order_percent=0
            ),
            TestScenario(
                name="High Load Test",
                requests_per_second=3,  # Slightly over capacity to show bottlenecks
                duration_seconds=8,
                error_rate_percent=0,
                large_order_percent=50  # More large orders to trigger payment delays
            ),
            TestScenario(
                name="Error Scenario Test",
                requests_per_second=2,
                duration_seconds=10,
                error_rate_percent=15,  # 15% error rate
                large_order_percent=20
            ),
            TestScenario(
                name="Mixed Workload Test",
                requests_per_second=2,
                duration_seconds=15,
                error_rate_percent=5,
                large_order_percent=30
            )
        ]

        # Run all scenarios
        for scenario in scenarios:
            try:
                await self.load_tester.run_scenario(scenario)
                # Brief pause between scenarios
                await asyncio.sleep(2)
            except Exception as e:
                print(f"❌ Error running scenario {scenario.name}: {e}")

        # Generate comprehensive report
        print("\n🔍 Generating Comprehensive Analysis Report...")
        report = self.load_tester.generate_load_test_report()

        # Save report to reports directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Determine report directory
        if os.getenv('DOCKER_ENV') == 'true':
            report_dir = '/app/reports'
        else:
            # Use local reports directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            report_dir = os.path.join(script_dir, 'reports')

        os.makedirs(report_dir, exist_ok=True)

        # Save JSON report
        json_filename = f"{report_dir}/mmf_demo_report_{timestamp}.json"
        with open(json_filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"📄 JSON report saved to: {json_filename}")

        # Save text report with all output
        text_filename = f"{report_dir}/mmf_demo_output_{timestamp}.txt"

        # Print key insights and capture output
        print(f"📄 Text report will be saved to: {text_filename}")
        self._print_demo_insights(report)

        # Save the insights to text file as well
        with open(text_filename, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("MMF STORE DEMO - COMPREHENSIVE ANALYSIS REPORT\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

            # Capture insights output
            original_stdout = sys.stdout
            insights_output = StringIO()
            sys.stdout = insights_output

            self._print_demo_insights(report)

            sys.stdout = original_stdout
            f.write(insights_output.getvalue())

    def _print_demo_insights(self, report: dict[str, Any]) -> None:
        """Print key insights from the demo"""
        print("\n" + "=" * 60)
        print("🎯 KEY DEMO INSIGHTS")
        print("=" * 60)

        # Load test summary
        load_summary = report['load_test_summary']
        print("\n📈 LOAD TEST RESULTS:")
        print(f"   Total Requests Processed: {load_summary['total_requests']}")
        print(f"   Overall Success Rate: {load_summary['overall_success_rate_percent']:.1f}%")
        print(f"   Average Response Time: {load_summary['average_response_time_ms']:.2f}ms")

        # Performance analysis
        perf_analysis = report['performance_analysis']
        summary = perf_analysis['summary']
        print("\n⚡ PERFORMANCE ANALYSIS:")
        print(f"   Transaction Success Rate: {summary['success_rate_percent']:.1f}%")
        print(f"   Average Processing Time: {summary['average_processing_time_ms']:.2f}ms")
        print(f"   Max Processing Time: {summary['max_processing_time_ms']:.2f}ms")

        # Bottleneck analysis
        bottlenecks = perf_analysis['bottleneck_analysis']
        if bottlenecks['bottlenecks_found'] > 0:
            print("\n🚨 BOTTLENECKS IDENTIFIED:")
            for bottleneck in bottlenecks['critical_services']:
                print(f"   {bottleneck['service']}: {bottleneck['average_response_time_ms']:.0f}ms "
                      f"({bottleneck['severity']} severity)")
        else:
            print("\n✅ NO CRITICAL BOTTLENECKS DETECTED")

        # Error analysis
        error_analysis = perf_analysis['error_analysis']
        print("\n🔍 ERROR ANALYSIS:")
        print(f"   Total Errors: {error_analysis['total_errors']}")
        print(f"   Error Rate: {error_analysis['error_rate_percent']:.1f}%")
        if error_analysis['common_errors']:
            print("   Common Error Types:")
            for error in error_analysis['common_errors'][:3]:
                print(f"     - {error['error_type']}: {error['count']} occurrences")

        # Recommendations
        recommendations = perf_analysis['recommendations']
        print("\n💡 RECOMMENDATIONS:")
        for rec in recommendations:
            print(f"   {rec}")

        print("\n" + "=" * 60)
        print("🎉 MMF DEMO COMPLETE!")
        print("Key features demonstrated:")
        print("✅ Distributed transaction traceability with correlation IDs")
        print("✅ Comprehensive audit logging for compliance")
        print("✅ Real-time performance monitoring and bottleneck detection")
        print("✅ Plugin architecture with custom analytics")
        print("✅ Error handling and root cause analysis")
        print("✅ Load testing and scalability insights")
        print("=" * 60)

async def main():
    """Main demo entry point"""
    print("🔧 Checking if services are running...")
    print("Expected services:")
    print("   - Order Service: http://localhost:8001")
    print("   - Payment Service: http://localhost:8002")
    print("   - Inventory Service: http://localhost:8003")
    print("\nNote: Make sure to start the services before running this demo!")
    print("You can start them with:")
    print("   uv run mmf_order_service.py")
    print("   uv run mmf_payment_service.py")
    print("   uv run mmf_inventory_service.py")
    print("\nStarting demo in 3 seconds...")
    await asyncio.sleep(3)

    orchestrator = DemoOrchestrator()
    await orchestrator.run_comprehensive_demo()

def main_with_output_capture():
    """Main entry point with output capture for text file generation"""
    # Determine report directory and timestamp first
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if os.getenv('DOCKER_ENV') == 'true':
        report_dir = '/app/reports'
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        report_dir = os.path.join(script_dir, 'reports')

    os.makedirs(report_dir, exist_ok=True)
    text_filename = f"{report_dir}/mmf_demo_output_{timestamp}.txt"

    # Capture all output from the start
    original_stdout = sys.stdout
    all_output = StringIO()

    class TeeOutput:
        def __init__(self, original, capture):
            self.original = original
            self.capture = capture

        def write(self, text):
            self.original.write(text)
            self.capture.write(text)

        def flush(self):
            self.original.flush()

    sys.stdout = TeeOutput(original_stdout, all_output)

    try:
        # Run the main demo
        asyncio.run(main())
    finally:
        # Restore stdout and save captured output
        sys.stdout = original_stdout

        # Save complete output to text file
        with open(text_filename, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("MMF STORE DEMO - COMPLETE OUTPUT LOG\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            f.write(all_output.getvalue())

        print(f"📄 Complete demo output saved to: {text_filename}")

if __name__ == "__main__":
    main_with_output_capture()
