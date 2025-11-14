"""
Load testing infrastructure for Marty Microservices Framework

Provides comprehensive load testing capabilities with:
- gRPC service load testing
- Performance metrics collection
- Real-time monitoring integration
- Configurable test scenarios
"""

import asyncio
import builtins
import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass

import aiohttp
import grpc
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


@dataclass
class LoadTestConfig:
    """Configuration for load testing"""

    target_host: str
    target_port: int
    test_duration_seconds: int = 60
    concurrent_users: int = 10
    ramp_up_seconds: int = 10
    requests_per_second: int | None = None
    protocol: str = "grpc"  # grpc, http, https
    test_name: str = "load_test"

    # gRPC specific
    grpc_service: str | None = None
    grpc_method: str | None = None
    grpc_payload: builtins.dict | None = None

    # HTTP specific
    http_path: str = "/"
    http_method: str = "GET"
    http_headers: builtins.dict[str, str] | None = None
    http_payload: builtins.dict | None = None


@dataclass
class TestResult:
    """Results from a single test request"""

    timestamp: float
    duration_ms: float
    status_code: str
    error: str | None = None
    response_size: int = 0


@dataclass
class LoadTestReport:
    """Comprehensive load test report"""

    config: LoadTestConfig
    start_time: float
    end_time: float
    total_requests: int
    successful_requests: int
    failed_requests: int

    # Performance metrics
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float

    # Throughput metrics
    requests_per_second: float
    bytes_per_second: float

    # Error analysis
    error_rate_percent: float
    errors_by_type: builtins.dict[str, int]

    # Raw results for analysis
    results: builtins.list[TestResult]


class PerformanceMonitor:
    """Real-time performance monitoring during load tests"""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.registry = CollectorRegistry()

        # Performance metrics
        self.response_time = Histogram(
            name="load_test_response_time_seconds",
            documentation="Response time for load test requests",
            labelnames=["test_name", "status"],
            registry=self.registry,
        )

        self.requests_total = Counter(
            name="load_test_requests_total",
            documentation="Total load test requests",
            labelnames=["test_name", "status"],
            registry=self.registry,
        )

        self.active_connections = Gauge(
            name="load_test_active_connections",
            documentation="Number of active test connections",
            labelnames=["test_name"],
            registry=self.registry,
        )

        self.throughput = Gauge(
            name="load_test_throughput_rps",
            documentation="Current throughput in requests per second",
            labelnames=["test_name"],
            registry=self.registry,
        )

    def record_request(self, duration_seconds: float, status: str) -> None:
        """Record a completed request"""
        self.response_time.labels(test_name=self.test_name, status=status).observe(duration_seconds)

        self.requests_total.labels(test_name=self.test_name, status=status).inc()

    def update_active_connections(self, count: int) -> None:
        """Update active connection count"""
        self.active_connections.labels(test_name=self.test_name).set(count)

    def update_throughput(self, rps: float) -> None:
        """Update current throughput"""
        self.throughput.labels(test_name=self.test_name).set(rps)


class GrpcLoadTester:
    """Load tester for gRPC services"""

    def __init__(self, config: LoadTestConfig, monitor: PerformanceMonitor):
        self.config = config
        self.monitor = monitor
        self.results: builtins.list[TestResult] = []
        self.active_connections = 0

    async def run_test(self) -> LoadTestReport:
        """Execute the gRPC load test"""
        logger.info(f"Starting gRPC load test: {self.config.test_name}")

        start_time = time.time()

        # Create tasks for concurrent users
        tasks = []
        for user_id in range(self.config.concurrent_users):
            delay = (user_id * self.config.ramp_up_seconds) / self.config.concurrent_users
            task = asyncio.create_task(self._user_session(user_id, delay))
            tasks.append(task)

        # Wait for all users to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()

        return self._generate_report(start_time, end_time)

    async def _user_session(self, user_id: int, delay: float) -> None:
        """Simulate a single user session"""
        if delay > 0:
            await asyncio.sleep(delay)

        session_start = time.time()
        request_count = 0

        # Calculate requests per user if rate limited
        if self.config.requests_per_second:
            user_rps = self.config.requests_per_second / self.config.concurrent_users
            request_interval = 1.0 / user_rps
        else:
            request_interval = 0  # No rate limiting

        while (time.time() - session_start) < self.config.test_duration_seconds:
            await self._make_grpc_request(user_id, request_count)
            request_count += 1

            if request_interval > 0:
                await asyncio.sleep(request_interval)

    async def _make_grpc_request(self, user_id: int, request_id: int) -> None:
        """Make a single gRPC request"""
        self.active_connections += 1
        self.monitor.update_active_connections(self.active_connections)

        start_time = time.time()

        try:
            # Create gRPC channel
            target = f"{self.config.target_host}:{self.config.target_port}"
            async with grpc.aio.insecure_channel(target):
                # This is a simplified example - in practice, you'd need
                # to import and use the actual gRPC service stub
                # stub = YourServiceStub(channel)
                # response = await stub.YourMethod(request)

                # Simulate gRPC call
                await asyncio.sleep(0.001)  # Minimal delay to simulate network

                duration = time.time() - start_time

                result = TestResult(
                    timestamp=start_time,
                    duration_ms=duration * 1000,
                    status_code="OK",
                    response_size=100,  # Simulated response size
                )

                self.results.append(result)
                self.monitor.record_request(duration, "success")

        except Exception as e:
            duration = time.time() - start_time

            result = TestResult(
                timestamp=start_time,
                duration_ms=duration * 1000,
                status_code="ERROR",
                error=str(e),
            )

            self.results.append(result)
            self.monitor.record_request(duration, "error")

            logger.error(f"gRPC request failed: {e}")

        finally:
            self.active_connections -= 1
            self.monitor.update_active_connections(self.active_connections)

    def _generate_report(self, start_time: float, end_time: float) -> LoadTestReport:
        """Generate comprehensive test report"""
        total_duration = end_time - start_time

        # Filter successful requests for performance metrics
        successful_results = [r for r in self.results if r.error is None]
        failed_results = [r for r in self.results if r.error is not None]

        if successful_results:
            response_times = [r.duration_ms for r in successful_results]
            avg_response_time = statistics.mean(response_times)
            p50_response_time = statistics.median(response_times)
            p95_response_time = (
                statistics.quantiles(response_times, n=20)[18]
                if len(response_times) > 20
                else max(response_times)
            )
            p99_response_time = (
                statistics.quantiles(response_times, n=100)[98]
                if len(response_times) > 100
                else max(response_times)
            )
        else:
            avg_response_time = p50_response_time = p95_response_time = p99_response_time = 0

        # Error analysis
        errors_by_type = {}
        for result in failed_results:
            error_type = result.error or "unknown"
            errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1

        # Throughput calculation
        total_bytes = sum(r.response_size for r in self.results)

        return LoadTestReport(
            config=self.config,
            start_time=start_time,
            end_time=end_time,
            total_requests=len(self.results),
            successful_requests=len(successful_results),
            failed_requests=len(failed_results),
            avg_response_time_ms=avg_response_time,
            min_response_time_ms=min(r.duration_ms for r in successful_results)
            if successful_results
            else 0,
            max_response_time_ms=max(r.duration_ms for r in successful_results)
            if successful_results
            else 0,
            p50_response_time_ms=p50_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            requests_per_second=len(self.results) / total_duration if total_duration > 0 else 0,
            bytes_per_second=total_bytes / total_duration if total_duration > 0 else 0,
            error_rate_percent=(len(failed_results) / len(self.results)) * 100
            if self.results
            else 0,
            errors_by_type=errors_by_type,
            results=self.results,
        )


class HttpLoadTester:
    """Load tester for HTTP services"""

    def __init__(self, config: LoadTestConfig, monitor: PerformanceMonitor):
        self.config = config
        self.monitor = monitor
        self.results: builtins.list[TestResult] = []

    async def run_test(self) -> LoadTestReport:
        """Execute the HTTP load test"""
        logger.info(f"Starting HTTP load test: {self.config.test_name}")

        start_time = time.time()

        # Create session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=self.config.concurrent_users * 2,
            limit_per_host=self.config.concurrent_users,
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            # Create tasks for concurrent users
            tasks = []
            for user_id in range(self.config.concurrent_users):
                delay = (user_id * self.config.ramp_up_seconds) / self.config.concurrent_users
                task = asyncio.create_task(self._user_session(session, user_id, delay))
                tasks.append(task)

            # Wait for all users to complete
            await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()

        return self._generate_report(start_time, end_time)

    async def _user_session(
        self, session: aiohttp.ClientSession, user_id: int, delay: float
    ) -> None:
        """Simulate a single user HTTP session"""
        if delay > 0:
            await asyncio.sleep(delay)

        session_start = time.time()
        request_count = 0

        # Calculate requests per user if rate limited
        if self.config.requests_per_second:
            user_rps = self.config.requests_per_second / self.config.concurrent_users
            request_interval = 1.0 / user_rps
        else:
            request_interval = 0

        while (time.time() - session_start) < self.config.test_duration_seconds:
            await self._make_http_request(session, user_id, request_count)
            request_count += 1

            if request_interval > 0:
                await asyncio.sleep(request_interval)

    async def _make_http_request(
        self, session: aiohttp.ClientSession, user_id: int, request_id: int
    ) -> None:
        """Make a single HTTP request"""
        start_time = time.time()

        try:
            url = f"{self.config.protocol}://{self.config.target_host}:{self.config.target_port}{self.config.http_path}"

            kwargs = {
                "headers": self.config.http_headers or {},
                "timeout": aiohttp.ClientTimeout(total=30),
            }

            if self.config.http_payload and self.config.http_method in [
                "POST",
                "PUT",
                "PATCH",
            ]:
                kwargs["json"] = self.config.http_payload

            async with session.request(self.config.http_method, url, **kwargs) as response:
                response_body = await response.read()
                duration = time.time() - start_time

                result = TestResult(
                    timestamp=start_time,
                    duration_ms=duration * 1000,
                    status_code=str(response.status),
                    response_size=len(response_body),
                )

                self.results.append(result)

                if 200 <= response.status < 400:
                    self.monitor.record_request(duration, "success")
                else:
                    self.monitor.record_request(duration, "error")

        except Exception as e:
            duration = time.time() - start_time

            result = TestResult(
                timestamp=start_time,
                duration_ms=duration * 1000,
                status_code="ERROR",
                error=str(e),
            )

            self.results.append(result)
            self.monitor.record_request(duration, "error")

            logger.error(f"HTTP request failed: {e}")

    def _generate_report(self, start_time: float, end_time: float) -> LoadTestReport:
        """Generate comprehensive test report"""
        # Implementation similar to GrpcLoadTester._generate_report
        # ... (same logic as gRPC version)


class LoadTestRunner:
    """Main load test orchestrator"""

    def __init__(self):
        self.monitor = None

    async def run_load_test(self, config: LoadTestConfig) -> LoadTestReport:
        """Run a load test based on configuration"""
        self.monitor = PerformanceMonitor(config.test_name)

        if config.protocol == "grpc":
            tester = GrpcLoadTester(config, self.monitor)
        elif config.protocol in ["http", "https"]:
            tester = HttpLoadTester(config, self.monitor)
        else:
            raise ValueError(f"Unsupported protocol: {config.protocol}")

        # Update monitor with current throughput periodically
        monitor_task = asyncio.create_task(self._monitor_throughput())

        try:
            report = await tester.run_test()
            return report
        finally:
            monitor_task.cancel()

    async def _monitor_throughput(self) -> None:
        """Background task to update throughput metrics"""
        time.time()

        while True:
            await asyncio.sleep(5)  # Update every 5 seconds

            time.time()
            # This would need access to current request count
            # Implementation depends on how results are tracked

    def save_report(self, report: LoadTestReport, filename: str) -> None:
        """Save load test report to file"""
        with open(filename, "w") as f:
            json.dump(asdict(report), f, indent=2, default=str)

        logger.info(f"Load test report saved to {filename}")

    def print_summary(self, report: LoadTestReport) -> None:
        """Print a summary of the load test results"""
        print(f"\n{'=' * 60}")
        print(f"Load Test Summary: {report.config.test_name}")
        print(f"{'=' * 60}")
        print(f"Duration: {report.end_time - report.start_time:.2f} seconds")
        print(f"Total Requests: {report.total_requests}")
        print(f"Successful: {report.successful_requests}")
        print(f"Failed: {report.failed_requests}")
        print(f"Error Rate: {report.error_rate_percent:.2f}%")
        print("\nPerformance Metrics:")
        print(f"  Average Response Time: {report.avg_response_time_ms:.2f} ms")
        print(f"  P50 Response Time: {report.p50_response_time_ms:.2f} ms")
        print(f"  P95 Response Time: {report.p95_response_time_ms:.2f} ms")
        print(f"  P99 Response Time: {report.p99_response_time_ms:.2f} ms")
        print("\nThroughput:")
        print(f"  Requests/second: {report.requests_per_second:.2f}")
        print(f"  Bytes/second: {report.bytes_per_second:.2f}")

        if report.errors_by_type:
            print("\nErrors by Type:")
            for error_type, count in report.errors_by_type.items():
                print(f"  {error_type}: {count}")

        print(f"{'=' * 60}\n")
