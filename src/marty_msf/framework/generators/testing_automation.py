"""
Service Testing and Quality Automation for Marty Microservices Framework

This module provides comprehensive testing automation, code quality analysis,
and validation tools for generated microservices.
"""

import ast
import asyncio
import builtins
import json
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import pytest
from coverage import Coverage
from mypy import api as mypy_api


class TestType(Enum):
    """Types of tests to generate and run."""

    UNIT = "unit"
    INTEGRATION = "integration"
    CONTRACT = "contract"
    PERFORMANCE = "performance"
    SECURITY = "security"
    E2E = "e2e"


class QualityMetric(Enum):
    """Code quality metrics."""

    COVERAGE = "coverage"
    COMPLEXITY = "complexity"
    MAINTAINABILITY = "maintainability"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"


@dataclass
class TestResult:
    """Result of a test execution."""

    test_type: TestType
    passed: bool
    total_tests: int
    failed_tests: int
    skipped_tests: int
    duration: float
    coverage: float | None = None
    errors: builtins.list[str] = field(default_factory=list)
    warnings: builtins.list[str] = field(default_factory=list)


@dataclass
class QualityReport:
    """Code quality analysis report."""

    metric: QualityMetric
    score: float
    max_score: float
    details: builtins.dict[str, Any] = field(default_factory=dict)
    recommendations: builtins.list[str] = field(default_factory=list)
    issues: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)


@dataclass
class ServiceValidationResult:
    """Complete validation result for a service."""

    service_name: str
    passed: bool
    test_results: builtins.list[TestResult] = field(default_factory=list)
    quality_reports: builtins.list[QualityReport] = field(default_factory=list)
    overall_score: float = 0.0
    recommendations: builtins.list[str] = field(default_factory=list)
    errors: builtins.list[str] = field(default_factory=list)


class TestGenerator:
    """Generates test files for microservices."""

    def __init__(self, framework_root: Path):
        """Initialize the test generator."""
        self.framework_root = framework_root
        self.test_templates_dir = framework_root / "test_templates"
        self.test_templates_dir.mkdir(exist_ok=True)

    def generate_unit_tests(
        self, service_dir: Path, service_config: builtins.dict[str, Any]
    ) -> builtins.list[Path]:
        """Generate unit tests for a service."""
        test_files = []
        tests_dir = service_dir / "tests" / "unit"
        tests_dir.mkdir(parents=True, exist_ok=True)

        # Generate test_service.py
        service_test = self._generate_service_unit_test(service_config)
        test_file = tests_dir / f"test_{service_config['service_package']}_service.py"
        test_file.write_text(service_test, encoding="utf-8")
        test_files.append(test_file)

        # Generate test_config.py
        config_test = self._generate_config_unit_test(service_config)
        test_file = tests_dir / "test_config.py"
        test_file.write_text(config_test, encoding="utf-8")
        test_files.append(test_file)

        # Generate test fixtures
        conftest = self._generate_conftest(service_config)
        test_file = tests_dir / "conftest.py"
        test_file.write_text(conftest, encoding="utf-8")
        test_files.append(test_file)

        return test_files

    def generate_integration_tests(
        self, service_dir: Path, service_config: builtins.dict[str, Any]
    ) -> builtins.list[Path]:
        """Generate integration tests for a service."""
        test_files = []
        tests_dir = service_dir / "tests" / "integration"
        tests_dir.mkdir(parents=True, exist_ok=True)

        # Generate infrastructure integration tests
        if service_config.get("use_database"):
            db_test = self._generate_database_integration_test(service_config)
            test_file = tests_dir / "test_database_integration.py"
            test_file.write_text(db_test, encoding="utf-8")
            test_files.append(test_file)

        if service_config.get("use_cache"):
            cache_test = self._generate_cache_integration_test(service_config)
            test_file = tests_dir / "test_cache_integration.py"
            test_file.write_text(cache_test, encoding="utf-8")
            test_files.append(test_file)

        if service_config.get("use_messaging"):
            messaging_test = self._generate_messaging_integration_test(service_config)
            test_file = tests_dir / "test_messaging_integration.py"
            test_file.write_text(messaging_test, encoding="utf-8")
            test_files.append(test_file)

        return test_files

    def generate_contract_tests(
        self, service_dir: Path, service_config: builtins.dict[str, Any]
    ) -> builtins.list[Path]:
        """Generate contract tests for API interfaces."""
        test_files = []
        tests_dir = service_dir / "tests" / "contract"
        tests_dir.mkdir(parents=True, exist_ok=True)

        if service_config.get("has_grpc"):
            grpc_test = self._generate_grpc_contract_test(service_config)
            test_file = tests_dir / "test_grpc_contract.py"
            test_file.write_text(grpc_test, encoding="utf-8")
            test_files.append(test_file)

        if service_config.get("has_rest"):
            rest_test = self._generate_rest_contract_test(service_config)
            test_file = tests_dir / "test_rest_contract.py"
            test_file.write_text(rest_test, encoding="utf-8")
            test_files.append(test_file)

        return test_files

    def generate_performance_tests(
        self, service_dir: Path, service_config: builtins.dict[str, Any]
    ) -> builtins.list[Path]:
        """Generate performance tests."""
        test_files = []
        tests_dir = service_dir / "tests" / "performance"
        tests_dir.mkdir(parents=True, exist_ok=True)

        perf_test = self._generate_performance_test(service_config)
        test_file = tests_dir / "test_performance.py"
        test_file.write_text(perf_test, encoding="utf-8")
        test_files.append(test_file)

        return test_files

    def _generate_service_unit_test(self, config: builtins.dict[str, Any]) -> str:
        """Generate unit test for the main service."""
        return f'''"""
Unit tests for {config["service_name"]} service.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.{config["service_package"]}_service import {config["service_class"]}Service


class Test{config["service_class"]}Service:
    """Test cases for {config["service_class"]}Service."""

    @pytest.fixture
    def service_config(self):
        """Mock service configuration."""
        return Mock()

    @pytest.fixture
    def service(self, service_config):
        """Create service instance for testing."""
        return {config["service_class"]}Service(service_config)

    def test_service_initialization(self, service):
        """Test service initialization."""
        assert service is not None
        assert hasattr(service, 'config')

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """Test service health check."""
        result = await service.health_check()
        assert isinstance(result, bool)

    {"@pytest.mark.asyncio" if config.get("has_grpc") else ""}
    {"async " if config.get("has_grpc") else ""}def test_service_startup(self, service):
        """Test service startup process."""
        {"await " if config.get("has_grpc") else ""}service.start()
        # Add assertions based on your service logic

    {"@pytest.mark.asyncio" if config.get("has_grpc") else ""}
    {"async " if config.get("has_grpc") else ""}def test_service_shutdown(self, service):
        """Test service shutdown process."""
        {"await " if config.get("has_grpc") else ""}service.stop()
        # Add assertions based on your service logic
'''

    def _generate_config_unit_test(self, config: builtins.dict[str, Any]) -> str:
        """Generate unit test for configuration."""
        return f'''"""
Unit tests for {config["service_name"]} configuration.
"""

import pytest
import os
from app.core.config import {config["service_class"]}Config


class Test{config["service_class"]}Config:
    """Test cases for service configuration."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = {config["service_class"]}Config()
        assert config.service_name == "{config["service_name"]}"
        assert config.version == "{config.get("service_version", "1.0.0")}"

    def test_config_from_environment(self):
        """Test configuration loading from environment."""
        os.environ["MARTY_SERVICE_NAME"] = "test-service"
        os.environ["MARTY_DEBUG"] = "true"

        config = {config["service_class"]}Config()
        assert config.debug is True

        # Cleanup
        del os.environ["MARTY_SERVICE_NAME"]
        del os.environ["MARTY_DEBUG"]

    def test_config_validation(self):
        """Test configuration validation."""
        # Test invalid port
        with pytest.raises(ValueError):
            {config["service_class"]}Config(grpc_port=-1)

        # Test invalid host
        with pytest.raises(ValueError):
            {config["service_class"]}Config(host="")
'''

    def _generate_conftest(self, config: builtins.dict[str, Any]) -> str:
        """Generate pytest configuration and fixtures."""
        triple_quote = '"""'
        docstring_database = (
            f"    {triple_quote}Mock database connection.{triple_quote}"
            if config.get("use_database")
            else ""
        )
        docstring_cache = (
            f"    {triple_quote}Mock cache connection.{triple_quote}"
            if config.get("use_cache")
            else ""
        )
        docstring_messaging = (
            f"    {triple_quote}Mock message queue.{triple_quote}"
            if config.get("use_messaging")
            else ""
        )

        return f'''"""
Pytest configuration and shared fixtures for {config["service_name"]}.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Mock service configuration."""
    config = Mock()
    config.service_name = "{config["service_name"]}"
    config.version = "{config.get("service_version", "1.0.0")}"
    config.debug = True
    config.host = "localhost"
    config.grpc_port = {config.get("grpc_port", 50051)}
    config.http_port = {config.get("http_port", 8000)}
    return config


{"@pytest.fixture" if config.get("use_database") else "# Database fixture disabled"}
{"def mock_database():" if config.get("use_database") else "# def mock_database():"}
{docstring_database}
{"    return AsyncMock()" if config.get("use_database") else ""}


{"@pytest.fixture" if config.get("use_cache") else "# Cache fixture disabled"}
{"def mock_cache():" if config.get("use_cache") else "# def mock_cache():"}
{docstring_cache}
{"    return AsyncMock()" if config.get("use_cache") else ""}


{"@pytest.fixture" if config.get("use_messaging") else "# Messaging fixture disabled"}
{"def mock_message_queue():" if config.get("use_messaging") else "# def mock_message_queue():"}
{docstring_messaging}
{"    return AsyncMock()" if config.get("use_messaging") else ""}
'''

    def _generate_database_integration_test(self, config: builtins.dict[str, Any]) -> str:
        """Generate database integration test."""
        return f'''"""
Database integration tests for {config["service_name"]}.
"""

import pytest
from marty_msf.framework.database import DatabaseManager


@pytest.mark.integration
class TestDatabaseIntegration:
    """Database integration test cases."""

    @pytest.fixture(scope="class")
    async def db_manager(self):
        """Setup database manager for testing."""
        manager = DatabaseManager({{
            "database_url": "sqlite:///test_{config["service_package"]}.db",
            "echo": False
        }})
        await manager.initialize()
        yield manager
        await manager.close()

    @pytest.mark.asyncio
    async def test_database_connection(self, db_manager):
        """Test database connectivity."""
        assert await db_manager.health_check() is True

    @pytest.mark.asyncio
    async def test_database_operations(self, db_manager):
        """Test basic database operations."""
        # Add your database operation tests here
        pass
'''

    def _generate_cache_integration_test(self, config: builtins.dict[str, Any]) -> str:
        """Generate cache integration test."""
        return f'''"""
Cache integration tests for {config["service_name"]}.
"""

import pytest
from marty_msf.framework.cache.manager import CacheManager


@pytest.mark.integration
class TestCacheIntegration:
    """Cache integration test cases."""

    @pytest.fixture(scope="class")
    async def cache_manager(self):
        """Setup cache manager for testing."""
        manager = CacheManager({{
            "backend": "memory",
            "default_ttl": 300
        }})
        await manager.initialize()
        yield manager
        await manager.close()

    @pytest.mark.asyncio
    async def test_cache_operations(self, cache_manager):
        """Test basic cache operations."""
        # Set a value
        await cache_manager.set("test_key", "test_value")

        # Get the value
        value = await cache_manager.get("test_key")
        assert value == "test_value"

        # Delete the value
        await cache_manager.delete("test_key")

        # Verify deletion
        value = await cache_manager.get("test_key")
        assert value is None
'''

    def _generate_messaging_integration_test(self, config: builtins.dict[str, Any]) -> str:
        """Generate messaging integration test."""
        return f'''"""
Messaging integration tests for {config["service_name"]}.
"""

import pytest
import asyncio
from marty_msf.framework.messaging import MessageQueue


@pytest.mark.integration
class TestMessagingIntegration:
    """Messaging integration test cases."""

    @pytest.fixture(scope="class")
    async def message_queue(self):
        """Setup message queue for testing."""
        queue = MessageQueue({{
            "backend": "memory",
            "queue_name": "test_queue"
        }})
        await queue.initialize()
        yield queue
        await queue.close()

    @pytest.mark.asyncio
    async def test_message_operations(self, message_queue):
        """Test basic message operations."""
        # Send a message
        await message_queue.send("test_message")

        # Receive the message
        message = await message_queue.receive(timeout=1.0)
        assert message == "test_message"
'''

    def _generate_grpc_contract_test(self, config: builtins.dict[str, Any]) -> str:
        """Generate gRPC contract test."""
        return f'''"""
gRPC contract tests for {config["service_name"]}.
"""

import pytest
import grpc
from grpc_testing import server_from_dictionary, strict_real_time


@pytest.mark.contract
class TestGRPCContract:
    """gRPC contract test cases."""

    @pytest.fixture
    def grpc_server(self):
        """Setup gRPC test server."""
        # Add your gRPC service implementation here
        services = {{
            # 'your_service': YourServiceImplementation()
        }}
        return server_from_dictionary(services, strict_real_time())

    def test_grpc_service_methods(self, grpc_server):
        """Test gRPC service method contracts."""
        # Add your contract tests here
        pass
'''

    def _generate_rest_contract_test(self, config: builtins.dict[str, Any]) -> str:
        """Generate REST contract test."""
        return f'''"""
REST API contract tests for {config["service_name"]}.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.mark.contract
class TestRESTContract:
    """REST API contract test cases."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint contract."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_api_endpoints(self, client):
        """Test API endpoint contracts."""
        # Add your API contract tests here
        pass
'''

    def _generate_performance_test(self, config: builtins.dict[str, Any]) -> str:
        """Generate performance test."""
        return f'''"""
Performance tests for {config["service_name"]}.
"""

import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor


@pytest.mark.performance
class TestPerformance:
    """Performance test cases."""

    @pytest.mark.asyncio
    async def test_service_startup_time(self):
        """Test service startup performance."""
        start_time = time.time()

        # Add service startup logic here
        await asyncio.sleep(0.1)  # Simulate startup

        startup_time = time.time() - start_time
        assert startup_time < 2.0  # Should start within 2 seconds

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test concurrent request handling."""
        async def make_request():
            # Simulate a request
            await asyncio.sleep(0.01)
            return True

        # Test 100 concurrent requests
        tasks = [make_request() for _ in range(100)]
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        duration = time.time() - start_time

        assert all(results)
        assert duration < 1.0  # Should handle 100 requests within 1 second

    def test_memory_usage(self):
        """Test memory usage patterns."""
        # Add memory usage tests here
        pass
'''


class QualityAnalyzer:
    """Analyzes code quality metrics."""

    def __init__(self, framework_root: Path):
        """Initialize the quality analyzer."""
        self.framework_root = framework_root

    def analyze_coverage(self, service_dir: Path) -> QualityReport:
        """Analyze test coverage."""
        cov = Coverage(source=[str(service_dir / "app")])
        cov.start()

        # Run tests with coverage
        pytest_args = [str(service_dir / "tests"), "--tb=short", "-v"]

        pytest.main(pytest_args)
        cov.stop()
        cov.save()

        # Get coverage data
        total_lines = 0
        covered_lines = 0

        for filename in cov.get_data().measured_files():
            analysis = cov.analysis2(filename)
            total_lines += len(analysis[1]) + len(analysis[2])
            covered_lines += len(analysis[1])

        coverage_percentage = (covered_lines / total_lines * 100) if total_lines > 0 else 0

        return QualityReport(
            metric=QualityMetric.COVERAGE,
            score=coverage_percentage,
            max_score=100.0,
            details={
                "total_lines": total_lines,
                "covered_lines": covered_lines,
                "uncovered_lines": total_lines - covered_lines,
            },
            recommendations=[
                "Add tests for uncovered code paths"
                if coverage_percentage < 80
                else "Maintain current coverage level"
            ],
        )

    def analyze_style(self, service_dir: Path) -> QualityReport:
        """Analyze code style with Ruff."""
        issues = []

        try:
            # Run Ruff check
            result = subprocess.run(
                ["ruff", "check", str(service_dir / "app"), "--output-format=json"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.stdout:
                ruff_issues = json.loads(result.stdout)
                issues.extend(ruff_issues)

        except Exception as e:
            issues.append({"error": str(e)})

        # Calculate style score (inverse of issues)
        max_issues = 100  # Assume max 100 issues for scoring
        style_score = max(0, (max_issues - len(issues)) / max_issues * 100)

        return QualityReport(
            metric=QualityMetric.STYLE,
            score=style_score,
            max_score=100.0,
            details={"issue_count": len(issues)},
            issues=issues,
            recommendations=[
                "Fix style issues found by Ruff" if issues else "Code style is excellent"
            ],
        )

    def analyze_type_safety(self, service_dir: Path) -> QualityReport:
        """Analyze type safety with MyPy."""
        try:
            result = mypy_api.run(
                [
                    str(service_dir / "app"),
                    "--json-report",
                    str(service_dir / "mypy-report"),
                    "--no-error-summary",
                ]
            )

            stdout, stderr, exit_code = result

            # Parse MyPy output
            issues = []
            if stderr:
                for line in stderr.split("\n"):
                    if line.strip() and ":" in line:
                        issues.append({"message": line.strip()})

            # Calculate type safety score
            type_score = max(0, 100 - len(issues) * 2)  # Deduct 2 points per issue

            return QualityReport(
                metric=QualityMetric.SECURITY,
                score=type_score,
                max_score=100.0,
                details={"type_issues": len(issues)},
                issues=issues,
                recommendations=[
                    "Add type hints to improve type safety"
                    if issues
                    else "Type safety is excellent"
                ],
            )

        except Exception as e:
            return QualityReport(
                metric=QualityMetric.SECURITY,
                score=0.0,
                max_score=100.0,
                details={"error": str(e)},
                recommendations=["Fix MyPy analysis errors"],
            )

    def analyze_complexity(self, service_dir: Path) -> QualityReport:
        """Analyze code complexity."""
        complexity_issues = []
        total_complexity = 0
        function_count = 0

        # Analyze Python files
        for py_file in (service_dir / "app").rglob("*.py"):
            try:
                with open(py_file, encoding="utf-8") as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        complexity = self._calculate_cyclomatic_complexity(node)
                        total_complexity += complexity
                        function_count += 1

                        if complexity > 10:  # High complexity threshold
                            complexity_issues.append(
                                {
                                    "file": str(py_file.relative_to(service_dir)),
                                    "function": node.name,
                                    "complexity": complexity,
                                    "line": node.lineno,
                                }
                            )

            except Exception as e:
                complexity_issues.append(
                    {"file": str(py_file.relative_to(service_dir)), "error": str(e)}
                )

        avg_complexity = total_complexity / function_count if function_count > 0 else 0
        complexity_score = max(0, 100 - avg_complexity * 5)  # Deduct 5 points per complexity unit

        return QualityReport(
            metric=QualityMetric.COMPLEXITY,
            score=complexity_score,
            max_score=100.0,
            details={
                "average_complexity": avg_complexity,
                "total_functions": function_count,
                "high_complexity_functions": len(complexity_issues),
            },
            issues=complexity_issues,
            recommendations=[
                "Refactor complex functions"
                if complexity_issues
                else "Code complexity is manageable"
            ],
        )

    def _calculate_cyclomatic_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity for a function."""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            if (
                isinstance(child, ast.If | ast.While | ast.For | ast.AsyncFor)
                or isinstance(child, ast.ExceptHandler)
                or isinstance(child, ast.With | ast.AsyncWith)
            ):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity


class ServiceTestRunner:
    """Runs tests and generates quality reports."""

    def __init__(self, framework_root: Path):
        """Initialize the test runner."""
        self.framework_root = framework_root
        self.test_generator = TestGenerator(framework_root)
        self.quality_analyzer = QualityAnalyzer(framework_root)

    async def validate_service(
        self, service_dir: Path, service_config: builtins.dict[str, Any]
    ) -> ServiceValidationResult:
        """Complete service validation."""
        service_name = service_config["service_name"]
        result = ServiceValidationResult(service_name=service_name, passed=False)

        try:
            # Generate tests if they don't exist
            await self._ensure_tests_exist(service_dir, service_config)

            # Run tests
            test_results = await self._run_all_tests(service_dir)
            result.test_results = test_results

            # Analyze quality
            quality_reports = await self._analyze_quality(service_dir)
            result.quality_reports = quality_reports

            # Calculate overall score
            result.overall_score = self._calculate_overall_score(test_results, quality_reports)

            # Generate recommendations
            result.recommendations = self._generate_recommendations(test_results, quality_reports)

            # Determine if validation passed
            result.passed = (
                all(test.passed for test in test_results)
                and result.overall_score >= 70.0  # 70% threshold
            )

        except Exception as e:
            result.errors.append(str(e))

        return result

    async def _ensure_tests_exist(
        self, service_dir: Path, service_config: builtins.dict[str, Any]
    ) -> None:
        """Ensure test files exist for the service."""
        tests_dir = service_dir / "tests"

        if not tests_dir.exists() or not any(tests_dir.iterdir()):
            # Generate tests
            self.test_generator.generate_unit_tests(service_dir, service_config)
            self.test_generator.generate_integration_tests(service_dir, service_config)
            self.test_generator.generate_contract_tests(service_dir, service_config)
            self.test_generator.generate_performance_tests(service_dir, service_config)

    async def _run_all_tests(self, service_dir: Path) -> builtins.list[TestResult]:
        """Run all test types."""
        test_results = []

        # Run unit tests
        unit_result = await self._run_test_type(service_dir, TestType.UNIT)
        test_results.append(unit_result)

        # Run integration tests
        integration_result = await self._run_test_type(service_dir, TestType.INTEGRATION)
        test_results.append(integration_result)

        # Run contract tests
        contract_result = await self._run_test_type(service_dir, TestType.CONTRACT)
        test_results.append(contract_result)

        # Run performance tests
        performance_result = await self._run_test_type(service_dir, TestType.PERFORMANCE)
        test_results.append(performance_result)

        return test_results

    async def _run_test_type(self, service_dir: Path, test_type: TestType) -> TestResult:
        """Run a specific type of test."""
        test_dir = service_dir / "tests" / test_type.value

        if not test_dir.exists():
            return TestResult(
                test_type=test_type,
                passed=True,
                total_tests=0,
                failed_tests=0,
                skipped_tests=0,
                duration=0.0,
            )

        # Run pytest
        pytest_args = [
            str(test_dir),
            "-v",
            "--tb=short",
            f"-m {test_type.value}" if test_type != TestType.UNIT else "",
            "--json-report",
            "--json-report-file=" + str(service_dir / f"{test_type.value}_report.json"),
        ]

        # Filter out empty arguments
        pytest_args = [arg for arg in pytest_args if arg]

        start_time = asyncio.get_event_loop().time()
        exit_code = pytest.main(pytest_args)
        duration = asyncio.get_event_loop().time() - start_time

        # Parse results
        report_file = service_dir / f"{test_type.value}_report.json"
        if report_file.exists():
            try:
                with open(report_file, encoding="utf-8") as f:
                    report = json.load(f)

                return TestResult(
                    test_type=test_type,
                    passed=exit_code == 0,
                    total_tests=report.get("summary", {}).get("total", 0),
                    failed_tests=report.get("summary", {}).get("failed", 0),
                    skipped_tests=report.get("summary", {}).get("skipped", 0),
                    duration=duration,
                )

            except Exception as e:
                return TestResult(
                    test_type=test_type,
                    passed=False,
                    total_tests=0,
                    failed_tests=0,
                    skipped_tests=0,
                    duration=duration,
                    errors=[str(e)],
                )

        return TestResult(
            test_type=test_type,
            passed=exit_code == 0,
            total_tests=1,  # Assume at least one test ran
            failed_tests=1 if exit_code != 0 else 0,
            skipped_tests=0,
            duration=duration,
        )

    async def _analyze_quality(self, service_dir: Path) -> builtins.list[QualityReport]:
        """Analyze code quality."""
        reports = []

        # Coverage analysis
        coverage_report = self.quality_analyzer.analyze_coverage(service_dir)
        reports.append(coverage_report)

        # Style analysis
        style_report = self.quality_analyzer.analyze_style(service_dir)
        reports.append(style_report)

        # Type safety analysis
        type_report = self.quality_analyzer.analyze_type_safety(service_dir)
        reports.append(type_report)

        # Complexity analysis
        complexity_report = self.quality_analyzer.analyze_complexity(service_dir)
        reports.append(complexity_report)

        return reports

    def _calculate_overall_score(
        self,
        test_results: builtins.list[TestResult],
        quality_reports: builtins.list[QualityReport],
    ) -> float:
        """Calculate overall quality score."""
        # Test score (40% weight)
        test_score = 0.0
        if test_results:
            passed_tests = sum(1 for test in test_results if test.passed)
            test_score = (passed_tests / len(test_results)) * 100

        # Quality score (60% weight)
        quality_score = 0.0
        if quality_reports:
            total_score = sum(report.score for report in quality_reports)
            quality_score = total_score / len(quality_reports)

        return (test_score * 0.4) + (quality_score * 0.6)

    def _generate_recommendations(
        self,
        test_results: builtins.list[TestResult],
        quality_reports: builtins.list[QualityReport],
    ) -> builtins.list[str]:
        """Generate improvement recommendations."""
        recommendations = []

        # Test recommendations
        for test in test_results:
            if not test.passed:
                recommendations.append(f"Fix failing {test.test_type.value} tests")
            if test.total_tests == 0:
                recommendations.append(f"Add {test.test_type.value} tests")

        # Quality recommendations
        for report in quality_reports:
            recommendations.extend(report.recommendations)

        return recommendations


def create_test_automation_config(service_dir: Path) -> None:
    """Create test automation configuration files."""
    # pytest.ini
    pytest_config = """[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests
    integration: Integration tests
    contract: Contract tests
    performance: Performance tests
    security: Security tests
    e2e: End-to-end tests
addopts =
    --strict-markers
    --disable-warnings
    --tb=short
    -v
"""
    (service_dir / "pytest.ini").write_text(pytest_config, encoding="utf-8")

    # Coverage configuration
    coverage_config = """[run]
source = app
omit =
    */tests/*
    */conftest.py
    */__init__.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:

[html]
directory = htmlcov
"""
    (service_dir / ".coveragerc").write_text(coverage_config, encoding="utf-8")

    # MyPy configuration
    mypy_config = """[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
disallow_untyped_decorators = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
warn_unreachable = True
strict_equality = True
"""
    (service_dir / "mypy.ini").write_text(mypy_config, encoding="utf-8")
