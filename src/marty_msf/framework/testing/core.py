"""
Core testing framework for Marty Microservices Framework.

This module provides the foundational testing infrastructure for enterprise microservices,
including test orchestration, test data management, and test execution coordination.
"""

import asyncio
import builtins
import json
import logging
import os
import traceback
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TestType(Enum):
    """Types of tests supported by the framework."""

    UNIT = "unit"
    INTEGRATION = "integration"
    CONTRACT = "contract"
    PERFORMANCE = "performance"
    CHAOS = "chaos"
    END_TO_END = "end_to_end"
    SMOKE = "smoke"
    REGRESSION = "regression"


class TestStatus(Enum):
    """Test execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestSeverity(Enum):
    """Test failure severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TestMetrics:
    """Test execution metrics."""

    execution_time: float
    memory_usage: float | None = None
    cpu_usage: float | None = None
    network_calls: int = 0
    database_operations: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    custom_metrics: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    """Test execution result."""

    test_id: str
    name: str
    test_type: TestType
    status: TestStatus
    execution_time: float
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    stack_trace: str | None = None
    metrics: TestMetrics | None = None
    artifacts: builtins.dict[str, Any] = field(default_factory=dict)
    tags: builtins.list[str] = field(default_factory=list)
    severity: TestSeverity = TestSeverity.MEDIUM

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert test result to dictionary."""
        return {
            "test_id": self.test_id,
            "name": self.name,
            "test_type": self.test_type.value,
            "status": self.status.value,
            "execution_time": self.execution_time,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "metrics": self.metrics.__dict__ if self.metrics else None,
            "artifacts": self.artifacts,
            "tags": self.tags,
            "severity": self.severity.value,
        }


class TestCase(ABC):
    """Abstract base class for test cases."""

    def __init__(self, name: str, test_type: TestType, tags: builtins.list[str] = None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.test_type = test_type
        self.tags = tags or []
        self.setup_functions: builtins.list[Callable] = []
        self.teardown_functions: builtins.list[Callable] = []

    @abstractmethod
    async def execute(self) -> TestResult:
        """Execute the test case."""

    async def setup(self):
        """Setup test case."""
        for setup_fn in self.setup_functions:
            if asyncio.iscoroutinefunction(setup_fn):
                await setup_fn()
            else:
                setup_fn()

    async def teardown(self):
        """Teardown test case."""
        for teardown_fn in reversed(self.teardown_functions):
            try:
                if asyncio.iscoroutinefunction(teardown_fn):
                    await teardown_fn()
                else:
                    teardown_fn()
            except Exception as e:
                logger.warning(f"Teardown function failed: {e}")

    def add_setup(self, func: Callable):
        """Add setup function."""
        self.setup_functions.append(func)

    def add_teardown(self, func: Callable):
        """Add teardown function."""
        self.teardown_functions.append(func)


class TestSuite:
    """Collection of test cases."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.test_cases: builtins.list[TestCase] = []
        self.setup_functions: builtins.list[Callable] = []
        self.teardown_functions: builtins.list[Callable] = []
        self.tags: builtins.list[str] = []
        self.parallel_execution = True
        self.max_workers = 4

    def add_test(self, test_case: TestCase):
        """Add test case to suite."""
        self.test_cases.append(test_case)

    def add_setup(self, func: Callable):
        """Add suite-level setup function."""
        self.setup_functions.append(func)

    def add_teardown(self, func: Callable):
        """Add suite-level teardown function."""
        self.teardown_functions.append(func)

    async def setup(self):
        """Setup test suite."""
        for setup_fn in self.setup_functions:
            if asyncio.iscoroutinefunction(setup_fn):
                await setup_fn()
            else:
                setup_fn()

    async def teardown(self):
        """Teardown test suite."""
        for teardown_fn in reversed(self.teardown_functions):
            try:
                if asyncio.iscoroutinefunction(teardown_fn):
                    await teardown_fn()
                else:
                    teardown_fn()
            except Exception as e:
                logger.warning(f"Suite teardown function failed: {e}")

    def filter_tests(
        self,
        tags: builtins.list[str] = None,
        test_types: builtins.list[TestType] = None,
    ) -> builtins.list[TestCase]:
        """Filter test cases by tags and types."""
        filtered_tests = self.test_cases

        if tags:
            filtered_tests = [
                test for test in filtered_tests if any(tag in test.tags for tag in tags)
            ]

        if test_types:
            filtered_tests = [test for test in filtered_tests if test.test_type in test_types]

        return filtered_tests


@dataclass
class TestConfiguration:
    """Test execution configuration."""

    parallel_execution: bool = True
    max_workers: int = 4
    timeout: int = 300  # seconds
    retry_failed_tests: bool = True
    max_retries: int = 3
    fail_fast: bool = False
    collect_metrics: bool = True
    generate_reports: bool = True
    report_formats: builtins.list[str] = field(default_factory=lambda: ["json", "html"])
    output_directory: str = "./test_results"
    log_level: str = "INFO"
    tags_to_run: builtins.list[str] = field(default_factory=list)
    tags_to_exclude: builtins.list[str] = field(default_factory=list)
    test_types_to_run: builtins.list[TestType] = field(default_factory=list)


class TestDataManager:
    """Manages test data and fixtures."""

    def __init__(self):
        self.fixtures: builtins.dict[str, Any] = {}
        self.test_data: builtins.dict[str, Any] = {}
        self.cleanup_callbacks: builtins.list[Callable] = []

    def register_fixture(self, name: str, fixture: Any):
        """Register a test fixture."""
        self.fixtures[name] = fixture

    def get_fixture(self, name: str) -> Any:
        """Get a test fixture."""
        if name not in self.fixtures:
            raise ValueError(f"Fixture '{name}' not found")
        return self.fixtures[name]

    def set_test_data(self, key: str, data: Any):
        """Set test data."""
        self.test_data[key] = data

    def get_test_data(self, key: str) -> Any:
        """Get test data."""
        return self.test_data.get(key)

    def add_cleanup(self, callback: Callable):
        """Add cleanup callback."""
        self.cleanup_callbacks.append(callback)

    async def cleanup(self):
        """Clean up test data and fixtures."""
        for callback in reversed(self.cleanup_callbacks):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.warning(f"Cleanup callback failed: {e}")

        self.fixtures.clear()
        self.test_data.clear()
        self.cleanup_callbacks.clear()


class TestReporter:
    """Generates test reports in various formats."""

    def __init__(self, output_dir: str = "./test_results"):
        self.output_dir = output_dir
        self.results: builtins.list[TestResult] = []

    def add_result(self, result: TestResult):
        """Add test result."""
        self.results.append(result)

    def generate_json_report(self) -> str:
        """Generate JSON test report."""
        report = {
            "summary": self._generate_summary(),
            "results": [result.to_dict() for result in self.results],
            "generated_at": datetime.utcnow().isoformat(),
        }


        os.makedirs(self.output_dir, exist_ok=True)

        report_path = os.path.join(self.output_dir, "test_report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        return report_path

    def generate_html_report(self) -> str:
        """Generate HTML test report."""
        html_template = self._get_html_template()
        summary = self._generate_summary()

        html_content = html_template.format(
            summary=json.dumps(summary),
            results=json.dumps([result.to_dict() for result in self.results]),
        )


        os.makedirs(self.output_dir, exist_ok=True)

        report_path = os.path.join(self.output_dir, "test_report.html")
        with open(report_path, "w") as f:
            f.write(html_content)

        return report_path

    def _generate_summary(self) -> builtins.dict[str, Any]:
        """Generate test summary."""
        total_tests = len(self.results)
        passed = len([r for r in self.results if r.status == TestStatus.PASSED])
        failed = len([r for r in self.results if r.status == TestStatus.FAILED])
        skipped = len([r for r in self.results if r.status == TestStatus.SKIPPED])
        errors = len([r for r in self.results if r.status == TestStatus.ERROR])

        total_time = sum(r.execution_time for r in self.results)

        return {
            "total_tests": total_tests,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "success_rate": (passed / total_tests * 100) if total_tests > 0 else 0,
            "total_execution_time": total_time,
            "average_execution_time": total_time / total_tests if total_tests > 0 else 0,
        }

    def _get_html_template(self) -> str:
        """Get HTML report template."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        .skipped {{ color: orange; }}
        .error {{ color: darkred; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Test Report</h1>
    <div id="summary" class="summary"></div>
    <div id="results"></div>

    <script>
        const summary = {summary};
        const results = {results};

        document.getElementById('summary').innerHTML = `
            <h2>Summary</h2>
            <p>Total Tests: ${{summary.total_tests}}</p>
            <p class="passed">Passed: ${{summary.passed}}</p>
            <p class="failed">Failed: ${{summary.failed}}</p>
            <p class="skipped">Skipped: ${{summary.skipped}}</p>
            <p class="error">Errors: ${{summary.errors}}</p>
            <p>Success Rate: ${{summary.success_rate.toFixed(2)}}%</p>
            <p>Total Time: ${{summary.total_execution_time.toFixed(2)}}s</p>
        `;

        let tableHtml = '<h2>Test Results</h2><table><tr><th>Test Name</th><th>Type</th><th>Status</th><th>Duration</th><th>Error</th></tr>';
        results.forEach(result => {{
            tableHtml += `<tr>
                <td>${{result.name}}</td>
                <td>${{result.test_type}}</td>
                <td class="${{result.status}}">${{result.status}}</td>
                <td>${{result.execution_time.toFixed(3)}}s</td>
                <td>${{result.error_message || ''}}</td>
            </tr>`;
        }});
        tableHtml += '</table>';

        document.getElementById('results').innerHTML = tableHtml;
    </script>
</body>
</html>
        """


class TestExecutor:
    """Executes test suites and manages test execution."""

    def __init__(self, config: TestConfiguration = None):
        self.config = config or TestConfiguration()
        self.data_manager = TestDataManager()
        self.reporter = TestReporter(self.config.output_directory)

    async def execute_suite(self, suite: TestSuite) -> builtins.list[TestResult]:
        """Execute a test suite."""
        logger.info(f"Starting execution of test suite: {suite.name}")

        # Filter tests based on configuration
        tests_to_run = suite.filter_tests(
            tags=self.config.tags_to_run, test_types=self.config.test_types_to_run
        )

        if self.config.tags_to_exclude:
            tests_to_run = [
                test
                for test in tests_to_run
                if not any(tag in test.tags for tag in self.config.tags_to_exclude)
            ]

        logger.info(f"Running {len(tests_to_run)} tests")

        try:
            # Setup suite
            await suite.setup()

            # Execute tests
            if self.config.parallel_execution and len(tests_to_run) > 1:
                results = await self._execute_parallel(tests_to_run)
            else:
                results = await self._execute_sequential(tests_to_run)

            # Add results to reporter
            for result in results:
                self.reporter.add_result(result)

            return results

        finally:
            # Teardown suite
            await suite.teardown()
            await self.data_manager.cleanup()

    async def _execute_parallel(self, tests: builtins.list[TestCase]) -> builtins.list[TestResult]:
        """Execute tests in parallel."""
        semaphore = asyncio.Semaphore(self.config.max_workers)

        async def execute_with_semaphore(test: TestCase) -> TestResult:
            async with semaphore:
                return await self._execute_single_test(test)

        tasks = [execute_with_semaphore(test) for test in tests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = TestResult(
                    test_id=tests[i].id,
                    name=tests[i].name,
                    test_type=tests[i].test_type,
                    status=TestStatus.ERROR,
                    execution_time=0.0,
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                    error_message=str(result),
                    stack_trace=traceback.format_exc(),
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)

        return processed_results

    async def _execute_sequential(
        self, tests: builtins.list[TestCase]
    ) -> builtins.list[TestResult]:
        """Execute tests sequentially."""
        results = []

        for test in tests:
            result = await self._execute_single_test(test)
            results.append(result)

            if self.config.fail_fast and result.status in [
                TestStatus.FAILED,
                TestStatus.ERROR,
            ]:
                logger.info("Fail-fast enabled, stopping execution")
                break

        return results

    async def _execute_single_test(self, test: TestCase) -> TestResult:
        """Execute a single test case."""
        logger.info(f"Executing test: {test.name}")

        started_at = datetime.utcnow()

        try:
            # Setup test
            await test.setup()

            # Execute test with timeout
            result = await asyncio.wait_for(test.execute(), timeout=self.config.timeout)

            result.started_at = started_at
            result.completed_at = datetime.utcnow()

            logger.info(f"Test {test.name} completed with status: {result.status}")
            return result

        except asyncio.TimeoutError:
            logger.error(f"Test {test.name} timed out")
            return TestResult(
                test_id=test.id,
                name=test.name,
                test_type=test.test_type,
                status=TestStatus.ERROR,
                execution_time=self.config.timeout,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                error_message="Test execution timed out",
                severity=TestSeverity.HIGH,
            )

        except Exception as e:
            logger.error(f"Test {test.name} failed with error: {e}")
            return TestResult(
                test_id=test.id,
                name=test.name,
                test_type=test.test_type,
                status=TestStatus.ERROR,
                execution_time=(datetime.utcnow() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
                stack_trace=traceback.format_exc(),
                severity=TestSeverity.HIGH,
            )

        finally:
            # Teardown test
            try:
                await test.teardown()
            except Exception as e:
                logger.warning(f"Test teardown failed: {e}")

    def generate_reports(self) -> builtins.dict[str, str]:
        """Generate test reports."""
        reports = {}

        if "json" in self.config.report_formats:
            reports["json"] = self.reporter.generate_json_report()

        if "html" in self.config.report_formats:
            reports["html"] = self.reporter.generate_html_report()

        return reports


# Utility functions and decorators
def test_case(name: str, test_type: TestType, tags: builtins.list[str] = None):
    """Decorator for creating test cases from functions."""

    def decorator(func):
        class FunctionTestCase(TestCase):
            def __init__(self):
                super().__init__(name, test_type, tags)
                self.func = func

            async def execute(self) -> TestResult:
                start_time = datetime.utcnow()

                try:
                    if asyncio.iscoroutinefunction(self.func):
                        await self.func()
                    else:
                        self.func()

                    execution_time = (datetime.utcnow() - start_time).total_seconds()

                    return TestResult(
                        test_id=self.id,
                        name=self.name,
                        test_type=self.test_type,
                        status=TestStatus.PASSED,
                        execution_time=execution_time,
                        started_at=start_time,
                        completed_at=datetime.utcnow(),
                    )

                except Exception as e:
                    execution_time = (datetime.utcnow() - start_time).total_seconds()

                    return TestResult(
                        test_id=self.id,
                        name=self.name,
                        test_type=self.test_type,
                        status=TestStatus.FAILED,
                        execution_time=execution_time,
                        started_at=start_time,
                        completed_at=datetime.utcnow(),
                        error_message=str(e),
                        stack_trace=traceback.format_exc(),
                    )

        return FunctionTestCase()

    return decorator


@asynccontextmanager
async def test_context(data_manager: TestDataManager):
    """Context manager for test execution."""
    try:
        yield data_manager
    finally:
        await data_manager.cleanup()
