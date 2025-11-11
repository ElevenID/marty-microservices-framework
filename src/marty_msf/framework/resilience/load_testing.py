"""
Enhanced Load Testing Framework for Resilience Validation

Provides comprehensive load testing capabilities to validate resilience patterns
under realistic concurrency scenarios with detailed metrics and reporting.
"""

import asyncio
import json
import logging
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Union

import aiofiles
import aiohttp

from .connection_pools.manager import get_pool_manager
from .middleware import ResilienceConfig, ResilienceService

logger = logging.getLogger(__name__)


class LoadTestType(Enum):
    """Types of load tests"""

    SPIKE = "spike"  # Sudden traffic increase
    RAMP_UP = "ramp_up"  # Gradual traffic increase
    SUSTAINED = "sustained"  # Constant high load
    STRESS = "stress"  # Beyond normal capacity
    VOLUME = "volume"  # Large amounts of data
    ENDURANCE = "endurance"  # Long duration testing


@dataclass
class LoadTestScenario:
    """Configuration for a load test scenario"""

    name: str
    test_type: LoadTestType

    # Load parameters
    initial_users: int = 1
    max_users: int = 100
    ramp_up_duration: int = 60  # seconds
    test_duration: int = 300  # seconds
    ramp_down_duration: int = 30  # seconds

    # Request parameters
    target_url: str = "http://localhost:8000"
    request_method: str = "GET"
    request_paths: list[str] = field(default_factory=lambda: ["/"])
    request_headers: dict[str, str] = field(default_factory=dict)
    request_data: dict[str, Any] | None = None

    # Timing parameters
    think_time_min: float = 0.1  # seconds between requests
    think_time_max: float = 2.0
    request_timeout: float = 30.0

    # Success criteria
    max_error_rate: float = 0.05  # 5%
    max_response_time_p95: float = 2.0  # seconds
    min_throughput: float = 10.0  # requests per second

    # Resilience validation
    validate_circuit_breakers: bool = True
    validate_connection_pools: bool = True
    validate_bulkheads: bool = True

    # Output configuration
    report_format: str = "json"
    output_directory: str = "./load_test_results"


@dataclass
class LoadTestMetrics:
    """Metrics collected during load testing"""

    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0

    # Response time metrics (in seconds)
    response_times: list[float] = field(default_factory=list)
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    avg_response_time: float = 0.0
    p50_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0

    # Throughput metrics
    requests_per_second: float = 0.0
    bytes_per_second: float = 0.0

    # Concurrency metrics
    concurrent_users: list[int] = field(default_factory=list)
    max_concurrent_users: int = 0

    # HTTP status codes
    status_codes: dict[int, int] = field(default_factory=dict)

    # Resilience metrics
    circuit_breaker_opens: int = 0
    bulkhead_rejections: int = 0
    connection_pool_exhaustion: int = 0

    # Test execution metrics
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration: float = 0.0


@dataclass
class UserSession:
    """Individual user session for load testing"""

    user_id: int
    session_start: float
    requests_made: int = 0
    errors_encountered: int = 0
    last_request_time: float = 0.0
    session_metrics: LoadTestMetrics = field(default_factory=LoadTestMetrics)


class LoadTester:
    """Main load testing orchestrator"""

    def __init__(self, scenario: LoadTestScenario):
        self.scenario = scenario
        self.metrics = LoadTestMetrics()
        self.user_sessions: list[UserSession] = []
        self.resilience_service: ResilienceService | None = None
        self._running = False
        self._tasks: list[asyncio.Task] = []

        # Initialize output directory
        Path(scenario.output_directory).mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize load tester with resilience service"""
        try:
            config = ResilienceConfig(
                enable_connection_pools=self.scenario.validate_connection_pools,
                enable_circuit_breaker=self.scenario.validate_circuit_breakers,
                enable_bulkhead=self.scenario.validate_bulkheads,
            )
            self.resilience_service = ResilienceService(config)
            await self.resilience_service.initialize()

            logger.info(f"Load tester initialized for scenario: {self.scenario.name}")

        except Exception as e:
            logger.error(f"Failed to initialize load tester: {e}")
            raise

    async def run_test(self) -> LoadTestMetrics:
        """Execute the load test scenario"""
        logger.info(f"Starting load test: {self.scenario.name}")

        self.metrics.start_time = datetime.now(timezone.utc)
        self._running = True

        try:
            # Phase 1: Ramp up users
            await self._ramp_up_phase()

            # Phase 2: Sustained load
            await self._sustained_load_phase()

            # Phase 3: Ramp down
            await self._ramp_down_phase()

        except Exception as e:
            logger.error(f"Load test failed: {e}")
            raise
        finally:
            self._running = False
            self.metrics.end_time = datetime.now(timezone.utc)

            # Wait for all tasks to complete
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)

            # Calculate final metrics
            await self._calculate_final_metrics()

            # Generate report
            await self._generate_report()

        logger.info(f"Load test completed: {self.scenario.name}")
        return self.metrics

    async def _ramp_up_phase(self):
        """Gradually increase user load"""
        logger.info("Starting ramp-up phase")

        users_per_second = (
            self.scenario.max_users - self.scenario.initial_users
        ) / self.scenario.ramp_up_duration

        # Start initial users
        for i in range(self.scenario.initial_users):
            await self._start_user_session(i)

        # Gradually add more users
        for second in range(self.scenario.ramp_up_duration):
            users_to_add = (
                int(users_per_second * (second + 1))
                - len(self.user_sessions)
                + self.scenario.initial_users
            )

            for _ in range(users_to_add):
                user_id = len(self.user_sessions)
                if user_id < self.scenario.max_users:
                    await self._start_user_session(user_id)

            await asyncio.sleep(1)

    async def _sustained_load_phase(self):
        """Maintain sustained load"""
        logger.info("Starting sustained load phase")

        # Maintain target user count for test duration
        await asyncio.sleep(self.scenario.test_duration)

    async def _ramp_down_phase(self):
        """Gradually decrease user load"""
        logger.info("Starting ramp-down phase")

        users_per_second = len(self.user_sessions) / self.scenario.ramp_down_duration

        for second in range(self.scenario.ramp_down_duration):
            users_to_remove = int(users_per_second * (second + 1))

            # Cancel user tasks
            tasks_to_cancel = self._tasks[:users_to_remove]
            for task in tasks_to_cancel:
                task.cancel()

            await asyncio.sleep(1)

    async def _start_user_session(self, user_id: int):
        """Start a user session"""
        session = UserSession(user_id=user_id, session_start=time.time())
        self.user_sessions.append(session)

        # Create and start user task
        task = asyncio.create_task(self._run_user_session(session))
        self._tasks.append(task)

    async def _run_user_session(self, session: UserSession):
        """Run individual user session"""
        try:
            while self._running:
                # Select request path
                path = self.scenario.request_paths[
                    session.requests_made % len(self.scenario.request_paths)
                ]
                url = f"{self.scenario.target_url}{path}"

                # Make request
                start_time = time.time()
                success = await self._make_request(session, url)
                response_time = time.time() - start_time

                # Update metrics
                session.requests_made += 1
                session.last_request_time = time.time()
                session.session_metrics.response_times.append(response_time)

                if success:
                    session.session_metrics.successful_requests += 1
                else:
                    session.errors_encountered += 1
                    session.session_metrics.failed_requests += 1

                session.session_metrics.total_requests += 1

                # Think time between requests
                think_time = self.scenario.think_time_min + (
                    (self.scenario.think_time_max - self.scenario.think_time_min)
                    * (session.user_id % 100)
                    / 100
                )
                await asyncio.sleep(think_time)

        except asyncio.CancelledError:
            logger.debug(f"User session {session.user_id} cancelled")
        except Exception as e:
            logger.error(f"User session {session.user_id} failed: {e}")

    async def _make_request(self, _session: UserSession, url: str) -> bool:
        """Make HTTP request and return success status"""
        try:
            if self.resilience_service:
                # Use resilience service if available
                async with self.resilience_service.http_request(
                    self.scenario.request_method,
                    url,
                    headers=self.scenario.request_headers,
                    json=self.scenario.request_data,
                    timeout=aiohttp.ClientTimeout(total=self.scenario.request_timeout),
                ) as response:
                    # Record status code
                    status = response.status
                    self.metrics.status_codes[status] = self.metrics.status_codes.get(status, 0) + 1

                    # Read response to measure bytes
                    await response.read()

                    return 200 <= status < 400
            else:
                # Direct HTTP request
                async with aiohttp.ClientSession() as client:
                    async with client.request(
                        self.scenario.request_method,
                        url,
                        headers=self.scenario.request_headers,
                        json=self.scenario.request_data,
                        timeout=aiohttp.ClientTimeout(total=self.scenario.request_timeout),
                    ) as response:
                        status = response.status
                        self.metrics.status_codes[status] = (
                            self.metrics.status_codes.get(status, 0) + 1
                        )
                        await response.read()
                        return 200 <= status < 400

        except asyncio.TimeoutError:
            self.metrics.status_codes[408] = self.metrics.status_codes.get(408, 0) + 1
            return False
        except Exception as e:
            logger.debug(f"Request failed: {e}")
            self.metrics.status_codes[0] = (
                self.metrics.status_codes.get(0, 0) + 1
            )  # Connection error
            return False

    async def _calculate_final_metrics(self):
        """Calculate final aggregated metrics"""
        all_response_times = []
        total_requests = 0
        successful_requests = 0
        failed_requests = 0

        for session in self.user_sessions:
            all_response_times.extend(session.session_metrics.response_times)
            total_requests += session.session_metrics.total_requests
            successful_requests += session.session_metrics.successful_requests
            failed_requests += session.session_metrics.failed_requests

        self.metrics.total_requests = total_requests
        self.metrics.successful_requests = successful_requests
        self.metrics.failed_requests = failed_requests
        self.metrics.error_rate = failed_requests / max(total_requests, 1)

        if all_response_times:
            self.metrics.response_times = all_response_times
            self.metrics.min_response_time = min(all_response_times)
            self.metrics.max_response_time = max(all_response_times)
            self.metrics.avg_response_time = statistics.mean(all_response_times)

            sorted_times = sorted(all_response_times)
            self.metrics.p50_response_time = statistics.quantiles(sorted_times, n=2)[0]
            self.metrics.p95_response_time = statistics.quantiles(sorted_times, n=20)[18]
            self.metrics.p99_response_time = statistics.quantiles(sorted_times, n=100)[98]

        # Calculate throughput
        if self.metrics.start_time and self.metrics.end_time:
            duration = (self.metrics.end_time - self.metrics.start_time).total_seconds()
            self.metrics.duration = duration
            self.metrics.requests_per_second = total_requests / max(duration, 1)

        self.metrics.max_concurrent_users = len(self.user_sessions)

        # Collect resilience metrics if available
        if self.resilience_service and self.resilience_service.pool_manager:
            # Extract relevant resilience metrics from pool manager
            pass

        logger.info(
            f"Test completed: {total_requests} requests, {self.metrics.error_rate:.2%} error rate"
        )

    async def _generate_report(self):
        """Generate load test report"""
        report_data = {
            "scenario": {
                "name": self.scenario.name,
                "test_type": self.scenario.test_type.value,
                "max_users": self.scenario.max_users,
                "test_duration": self.scenario.test_duration,
                "target_url": self.scenario.target_url,
            },
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "error_rate": self.metrics.error_rate,
                "response_time_stats": {
                    "min": self.metrics.min_response_time,
                    "max": self.metrics.max_response_time,
                    "avg": self.metrics.avg_response_time,
                    "p50": self.metrics.p50_response_time,
                    "p95": self.metrics.p95_response_time,
                    "p99": self.metrics.p99_response_time,
                },
                "throughput": {
                    "requests_per_second": self.metrics.requests_per_second,
                    "duration": self.metrics.duration,
                },
                "status_codes": self.metrics.status_codes,
            },
            "validation": {
                "error_rate_pass": self.metrics.error_rate <= self.scenario.max_error_rate,
                "response_time_pass": self.metrics.p95_response_time
                <= self.scenario.max_response_time_p95,
                "throughput_pass": self.metrics.requests_per_second >= self.scenario.min_throughput,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.scenario.name}_{self.scenario.test_type.value}_{timestamp}.json"
        filepath = Path(self.scenario.output_directory) / filename

        async with aiofiles.open(filepath, "w") as f:
            await f.write(json.dumps(report_data, indent=2))

        logger.info(f"Load test report saved to: {filepath}")

    async def close(self):
        """Clean up resources"""
        if self.resilience_service:
            await self.resilience_service.close()


class LoadTestSuite:
    """Collection of load test scenarios for comprehensive validation"""

    def __init__(self, scenarios: list[LoadTestScenario]):
        self.scenarios = scenarios
        self.results: list[LoadTestMetrics] = []

    async def run_all_tests(self) -> list[LoadTestMetrics]:
        """Run all test scenarios in sequence"""
        logger.info(f"Starting load test suite with {len(self.scenarios)} scenarios")

        for scenario in self.scenarios:
            logger.info(f"Running scenario: {scenario.name}")

            tester = LoadTester(scenario)
            try:
                await tester.initialize()
                metrics = await tester.run_test()
                self.results.append(metrics)
            finally:
                await tester.close()

            # Brief pause between tests
            await asyncio.sleep(5)

        await self._generate_suite_report()
        return self.results

    async def _generate_suite_report(self):
        """Generate comprehensive suite report"""
        suite_data = {
            "suite_summary": {
                "total_scenarios": len(self.scenarios),
                "total_requests": sum(r.total_requests for r in self.results),
                "overall_error_rate": sum(r.failed_requests for r in self.results)
                / max(sum(r.total_requests for r in self.results), 1),
                "avg_throughput": statistics.mean(
                    [r.requests_per_second for r in self.results if r.requests_per_second > 0]
                ),
            },
            "scenario_results": [],
        }

        for i, result in enumerate(self.results):
            scenario = self.scenarios[i]
            suite_data["scenario_results"].append(
                {
                    "scenario_name": scenario.name,
                    "test_type": scenario.test_type.value,
                    "passed": (
                        result.error_rate <= scenario.max_error_rate
                        and result.p95_response_time <= scenario.max_response_time_p95
                        and result.requests_per_second >= scenario.min_throughput
                    ),
                    "metrics": {
                        "requests": result.total_requests,
                        "error_rate": result.error_rate,
                        "p95_response_time": result.p95_response_time,
                        "throughput": result.requests_per_second,
                    },
                }
            )

        # Save suite report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"load_test_suite_{timestamp}.json"

        # Use first scenario's output directory
        output_dir = self.scenarios[0].output_directory if self.scenarios else "./load_test_results"
        filepath = Path(output_dir) / filename

        async with aiofiles.open(filepath, "w") as f:
            await f.write(json.dumps(suite_data, indent=2))

        logger.info(f"Load test suite report saved to: {filepath}")


# Pre-configured test scenarios for common resilience validation
def create_resilience_test_scenarios(
    base_url: str = "http://localhost:8000",
) -> list[LoadTestScenario]:
    """Create a set of test scenarios for resilience validation"""

    scenarios = [
        # Spike test - sudden load increase
        LoadTestScenario(
            name="spike_test",
            test_type=LoadTestType.SPIKE,
            initial_users=5,
            max_users=100,
            ramp_up_duration=10,  # Quick ramp up
            test_duration=60,
            target_url=base_url,
            request_paths=["/health", "/api/users", "/api/products"],
            max_error_rate=0.1,  # Allow higher error rate for spike
            validate_circuit_breakers=True,
        ),
        # Sustained load test
        LoadTestScenario(
            name="sustained_load_test",
            test_type=LoadTestType.SUSTAINED,
            initial_users=10,
            max_users=50,
            ramp_up_duration=60,
            test_duration=300,  # 5 minutes
            target_url=base_url,
            request_paths=["/api/data", "/api/search"],
            max_error_rate=0.05,
            validate_connection_pools=True,
        ),
        # Stress test - beyond normal capacity
        LoadTestScenario(
            name="stress_test",
            test_type=LoadTestType.STRESS,
            initial_users=20,
            max_users=200,
            ramp_up_duration=120,
            test_duration=180,
            target_url=base_url,
            request_paths=["/api/heavy-computation", "/api/database-query"],
            max_error_rate=0.15,  # Higher error tolerance
            validate_bulkheads=True,
        ),
    ]

    return scenarios
