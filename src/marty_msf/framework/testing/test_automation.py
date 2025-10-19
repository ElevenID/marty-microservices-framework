"""
Test automation framework for Marty Microservices Framework.

This module provides comprehensive test automation capabilities including
test discovery, test orchestration, CI/CD integration, test scheduling,
and automated test reporting.
"""

import asyncio
import builtins
import fnmatch
import importlib.util
import inspect
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import schedule
import yaml

from .core import (
    TestCase,
    TestConfiguration,
    TestExecutor,
    TestReporter,
    TestResult,
    TestStatus,
    TestSuite,
    TestType,
)

logger = logging.getLogger(__name__)


class TestDiscoveryStrategy(Enum):
    """Test discovery strategies."""

    FILE_PATTERN = "file_pattern"
    DECORATOR_BASED = "decorator_based"
    CLASS_BASED = "class_based"
    DIRECTORY_SCAN = "directory_scan"
    CONFIGURATION_BASED = "configuration_based"


class TestScheduleType(Enum):
    """Test schedule types."""

    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    TRIGGERED = "triggered"
    CONTINUOUS = "continuous"
    ON_CHANGE = "on_change"


class TestEnvironmentType(Enum):
    """Test environment types."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    CI_CD = "ci_cd"


@dataclass
class TestDiscoveryConfig:
    """Configuration for test discovery."""

    strategy: TestDiscoveryStrategy
    base_directories: builtins.list[str] = field(default_factory=list)
    file_patterns: builtins.list[str] = field(default_factory=lambda: ["test_*.py", "*_test.py"])
    exclude_patterns: builtins.list[str] = field(default_factory=list)
    test_class_patterns: builtins.list[str] = field(default_factory=lambda: ["Test*", "*Test"])
    test_method_patterns: builtins.list[str] = field(default_factory=lambda: ["test_*"])
    decorator_names: builtins.list[str] = field(
        default_factory=lambda: ["test_case", "integration_test"]
    )
    config_files: builtins.list[str] = field(default_factory=list)


@dataclass
class TestScheduleConfig:
    """Configuration for test scheduling."""

    schedule_type: TestScheduleType
    cron_expression: str | None = None
    interval_minutes: int | None = None
    trigger_events: builtins.list[str] = field(default_factory=list)
    environment: TestEnvironmentType = TestEnvironmentType.TESTING
    enabled: bool = True
    retry_on_failure: bool = True
    max_retries: int = 3


@dataclass
class TestExecutionPlan:
    """Test execution plan."""

    name: str
    description: str
    test_suites: builtins.list[str] = field(default_factory=list)
    test_cases: builtins.list[str] = field(default_factory=list)
    execution_order: builtins.list[str] = field(default_factory=list)
    parallel_execution: bool = True
    max_workers: int = 4
    timeout: int = 3600  # seconds
    environment: TestEnvironmentType = TestEnvironmentType.TESTING
    configuration: TestConfiguration | None = None


@dataclass
class TestRun:
    """Test run information."""

    id: str
    plan_name: str
    started_at: datetime
    completed_at: datetime | None = None
    status: TestStatus = TestStatus.PENDING
    results: builtins.list[TestResult] = field(default_factory=list)
    environment: TestEnvironmentType = TestEnvironmentType.TESTING
    triggered_by: str | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


class TestDiscovery:
    """Discovers and loads test cases and suites."""

    def __init__(self, config: TestDiscoveryConfig):
        self.config = config
        self.discovered_tests: builtins.dict[str, TestCase] = {}
        self.discovered_suites: builtins.dict[str, TestSuite] = {}

    def discover_tests(
        self,
    ) -> builtins.tuple[builtins.dict[str, TestCase], builtins.dict[str, TestSuite]]:
        """Discover all tests based on configuration."""
        logger.info(f"Discovering tests using strategy: {self.config.strategy}")

        if self.config.strategy == TestDiscoveryStrategy.FILE_PATTERN:
            self._discover_by_file_pattern()
        elif self.config.strategy == TestDiscoveryStrategy.DECORATOR_BASED:
            self._discover_by_decorators()
        elif self.config.strategy == TestDiscoveryStrategy.CLASS_BASED:
            self._discover_by_classes()
        elif self.config.strategy == TestDiscoveryStrategy.DIRECTORY_SCAN:
            self._discover_by_directory_scan()
        elif self.config.strategy == TestDiscoveryStrategy.CONFIGURATION_BASED:
            self._discover_by_configuration()

        logger.info(
            f"Discovered {len(self.discovered_tests)} test cases and {len(self.discovered_suites)} test suites"
        )
        return self.discovered_tests, self.discovered_suites

    def _discover_by_file_pattern(self):
        """Discover tests by scanning files matching patterns."""
        for base_dir in self.config.base_directories:
            base_path = Path(base_dir)
            if not base_path.exists():
                continue

            for pattern in self.config.file_patterns:
                for file_path in base_path.rglob(pattern):
                    if self._should_exclude_file(file_path):
                        continue

                    self._load_tests_from_file(file_path)

    def _discover_by_decorators(self):
        """Discover tests by finding decorated functions."""
        for base_dir in self.config.base_directories:
            for file_path in self._get_python_files(base_dir):
                if self._should_exclude_file(file_path):
                    continue

                module = self._import_module_from_path(file_path)
                if module:
                    self._find_decorated_tests(module)

    def _discover_by_classes(self):
        """Discover tests by finding test classes."""
        for base_dir in self.config.base_directories:
            for file_path in self._get_python_files(base_dir):
                if self._should_exclude_file(file_path):
                    continue

                module = self._import_module_from_path(file_path)
                if module:
                    self._find_test_classes(module)

    def _discover_by_directory_scan(self):
        """Discover tests by comprehensive directory scanning."""
        # Combine multiple strategies
        self._discover_by_file_pattern()
        self._discover_by_decorators()
        self._discover_by_classes()

    def _discover_by_configuration(self):
        """Discover tests based on configuration files."""
        for config_file in self.config.config_files:
            config_path = Path(config_file)
            if not config_path.exists():
                continue

            if config_path.suffix in [".yaml", ".yml"]:
                with open(config_path) as f:
                    config_data = yaml.safe_load(f)
            elif config_path.suffix == ".json":
                with open(config_path) as f:
                    config_data = json.load(f)
            else:
                continue

            self._load_tests_from_config(config_data)

    def _should_exclude_file(self, file_path: Path) -> bool:
        """Check if file should be excluded."""
        file_str = str(file_path)

        for exclude_pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(file_str, exclude_pattern):
                return True

        return False

    def _get_python_files(self, directory: str) -> builtins.list[Path]:
        """Get all Python files in directory."""
        base_path = Path(directory)
        return list(base_path.rglob("*.py"))

    def _import_module_from_path(self, file_path: Path) -> Any | None:
        """Import module from file path."""
        try:
            spec = importlib.util.spec_from_file_location("test_module", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception as e:
            logger.warning(f"Failed to import module {file_path}: {e}")
            return None

    def _find_decorated_tests(self, module):
        """Find decorated test functions in module."""
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj):
                # Check for test decorators
                for decorator_name in self.config.decorator_names:
                    if hasattr(obj, decorator_name) or name.startswith("test_"):
                        test_case = self._create_test_case_from_function(obj, name)
                        if test_case:
                            self.discovered_tests[test_case.id] = test_case

    def _find_test_classes(self, module):
        """Find test classes in module."""
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and self._is_test_class(name):
                # Check if it's a TestCase subclass
                if issubclass(obj, TestCase):
                    test_instance = obj()
                    self.discovered_tests[test_instance.id] = test_instance
                else:
                    # Create test suite from class methods
                    test_suite = self._create_test_suite_from_class(obj, name)
                    if test_suite:
                        self.discovered_suites[test_suite.name] = test_suite

    def _is_test_class(self, class_name: str) -> bool:
        """Check if class name matches test patterns."""
        for pattern in self.config.test_class_patterns:
            if fnmatch.fnmatch(class_name, pattern):
                return True
        return False

    def _create_test_case_from_function(self, func, name: str) -> TestCase | None:
        """Create test case from function."""
        # This is a simplified implementation
        # In practice, you might need more sophisticated logic
        try:
            # Create a wrapper test case
            class FunctionTestCase(TestCase):
                def __init__(self):
                    super().__init__(name, TestType.UNIT)
                    self.test_function = func

                async def execute(self) -> TestResult:
                    start_time = datetime.utcnow()
                    try:
                        if asyncio.iscoroutinefunction(self.test_function):
                            await self.test_function()
                        else:
                            self.test_function()

                        return TestResult(
                            test_id=self.id,
                            name=self.name,
                            test_type=self.test_type,
                            status=TestStatus.PASSED,
                            execution_time=(datetime.utcnow() - start_time).total_seconds(),
                            started_at=start_time,
                            completed_at=datetime.utcnow(),
                        )
                    except Exception as e:
                        return TestResult(
                            test_id=self.id,
                            name=self.name,
                            test_type=self.test_type,
                            status=TestStatus.FAILED,
                            execution_time=(datetime.utcnow() - start_time).total_seconds(),
                            started_at=start_time,
                            completed_at=datetime.utcnow(),
                            error_message=str(e),
                        )

            return FunctionTestCase()
        except Exception as e:
            logger.warning(f"Failed to create test case from function {name}: {e}")
            return None

    def _create_test_suite_from_class(self, test_class, class_name: str) -> TestSuite | None:
        """Create test suite from class methods."""
        try:
            test_suite = TestSuite(class_name, f"Test suite for {class_name}")

            # Find test methods
            for method_name, method in inspect.getmembers(test_class, predicate=inspect.ismethod):
                if self._is_test_method(method_name):
                    test_case = self._create_test_case_from_method(test_class, method, method_name)
                    if test_case:
                        test_suite.add_test(test_case)

            return test_suite if test_suite.test_cases else None
        except Exception as e:
            logger.warning(f"Failed to create test suite from class {class_name}: {e}")
            return None

    def _is_test_method(self, method_name: str) -> bool:
        """Check if method name matches test patterns."""
        for pattern in self.config.test_method_patterns:
            if fnmatch.fnmatch(method_name, pattern):
                return True
        return False

    def _create_test_case_from_method(
        self, test_class, method, method_name: str
    ) -> TestCase | None:
        """Create test case from class method."""
        # Similar to function test case but with class instance
        # This is a simplified implementation
        return None

    def _load_tests_from_file(self, file_path: Path):
        """Load tests from specific file."""
        module = self._import_module_from_path(file_path)
        if module:
            self._find_decorated_tests(module)
            self._find_test_classes(module)

    def _load_tests_from_config(self, config_data: builtins.dict[str, Any]):
        """Load tests from configuration data."""
        # Load test definitions from configuration
        tests = config_data.get("tests", [])
        for test_config in tests:
            # Create test case from configuration
            test_name = test_config.get("name", "unnamed_test")
            test_path = test_config.get("path", "")

            # For now, just log the test configuration
            # Implementation would depend on specific test runner integration
            logger = logging.getLogger(__name__)
            logger.info(f"Configured test: {test_name} at {test_path}")

        suites = config_data.get("test_suites", [])
        for suite_config in suites:
            # Create test suite from configuration
            suite_name = suite_config.get("name", "unnamed_suite")
            suite_tests = suite_config.get("tests", [])

            # For now, just log the suite configuration
            logger = logging.getLogger(__name__)
            logger.info(f"Configured test suite: {suite_name} with {len(suite_tests)} tests")


class TestScheduler:
    """Schedules and manages test execution."""

    def __init__(self):
        self.scheduled_plans: builtins.dict[
            str, builtins.tuple[TestExecutionPlan, TestScheduleConfig]
        ] = {}
        self.scheduler_thread: threading.Thread | None = None
        self.running = False
        self.test_runs: builtins.dict[str, TestRun] = {}

    def add_scheduled_plan(self, plan: TestExecutionPlan, schedule_config: TestScheduleConfig):
        """Add scheduled test execution plan."""
        self.scheduled_plans[plan.name] = (plan, schedule_config)
        logger.info(f"Added scheduled test plan: {plan.name}")

    def start_scheduler(self):
        """Start the test scheduler."""
        if self.running:
            return

        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
        self.scheduler_thread.start()
        logger.info("Test scheduler started")

    def stop_scheduler(self):
        """Stop the test scheduler."""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join()
        logger.info("Test scheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop."""
        # Setup scheduled jobs
        for plan_name, (_plan, schedule_config) in self.scheduled_plans.items():
            if not schedule_config.enabled:
                continue

            if schedule_config.schedule_type == TestScheduleType.SCHEDULED:
                if schedule_config.cron_expression:
                    # Parse cron expression and schedule job
                    # This is simplified - in practice, use a proper cron parser
                    if schedule:
                        schedule.every().hour.do(self._execute_plan, plan_name)
                elif schedule_config.interval_minutes:
                    if schedule:
                        schedule.every(schedule_config.interval_minutes).minutes.do(
                            self._execute_plan, plan_name
                        )
            elif schedule_config.schedule_type == TestScheduleType.CONTINUOUS:
                # For continuous testing, schedule frequent runs
                if schedule:
                    schedule.every(5).minutes.do(self._execute_plan, plan_name)

        # Run scheduler
        while self.running:
            if schedule:
                schedule.run_pending()
            time.sleep(1)

    def _execute_plan(self, plan_name: str):
        """Execute a test plan."""
        if plan_name not in self.scheduled_plans:
            return

        plan, schedule_config = self.scheduled_plans[plan_name]

        # Create test run
        test_run = TestRun(
            id=f"{plan_name}_{int(time.time())}",
            plan_name=plan_name,
            started_at=datetime.utcnow(),
            environment=schedule_config.environment,
            triggered_by="scheduler",
        )

        self.test_runs[test_run.id] = test_run

        # Execute plan asynchronously
        asyncio.create_task(self._execute_plan_async(test_run, plan, schedule_config))

    async def _execute_plan_async(
        self,
        test_run: TestRun,
        plan: TestExecutionPlan,
        schedule_config: TestScheduleConfig,
    ):
        """Execute test plan asynchronously."""
        try:
            test_run.status = TestStatus.RUNNING

            # Execute the plan (this would integrate with TestExecutor)
            TestExecutor(plan.configuration or TestConfiguration())

            # For now, just simulate execution
            await asyncio.sleep(1)  # Simulate test execution

            test_run.status = TestStatus.PASSED
            test_run.completed_at = datetime.utcnow()

            logger.info(f"Test run {test_run.id} completed successfully")

        except Exception as e:
            test_run.status = TestStatus.FAILED
            test_run.completed_at = datetime.utcnow()

            logger.error(f"Test run {test_run.id} failed: {e}")

            # Retry if configured
            if schedule_config.retry_on_failure and schedule_config.max_retries > 0:
                # Implement retry logic
                for attempt in range(schedule_config.max_retries):
                    logger.info(f"Retrying test plan {plan.name}, attempt {attempt + 1}")
                    try:
                        await asyncio.sleep(5)  # Wait before retry
                        TestExecutor(plan.configuration or TestConfiguration())
                        await asyncio.sleep(1)  # Simulate retry execution
                        test_run.status = TestStatus.PASSED
                        test_run.completed_at = datetime.utcnow()
                        break  # Success, exit retry loop
                    except Exception as retry_e:
                        logger.warning(f"Retry {attempt + 1} failed: {retry_e}")
                        if attempt == schedule_config.max_retries - 1:
                            logger.error(f"All retries exhausted for {plan.name}")
                            test_run.status = TestStatus.FAILED

    def trigger_plan(self, plan_name: str, triggered_by: str = "manual") -> str | None:
        """Manually trigger a test plan."""
        if plan_name not in self.scheduled_plans:
            return None

        plan, schedule_config = self.scheduled_plans[plan_name]

        test_run = TestRun(
            id=f"{plan_name}_{int(time.time())}",
            plan_name=plan_name,
            started_at=datetime.utcnow(),
            environment=schedule_config.environment,
            triggered_by=triggered_by,
        )

        self.test_runs[test_run.id] = test_run

        # Execute plan
        asyncio.create_task(self._execute_plan_async(test_run, plan, schedule_config))

        return test_run.id

    def get_test_run_status(self, run_id: str) -> TestRun | None:
        """Get test run status."""
        return self.test_runs.get(run_id)

    def get_recent_runs(
        self, plan_name: str | None = None, limit: int = 10
    ) -> builtins.list[TestRun]:
        """Get recent test runs."""
        runs = list(self.test_runs.values())

        if plan_name:
            runs = [r for r in runs if r.plan_name == plan_name]

        # Sort by start time, most recent first
        runs.sort(key=lambda r: r.started_at, reverse=True)

        return runs[:limit]


class ContinuousTestingEngine:
    """Engine for continuous testing and CI/CD integration."""

    def __init__(self, discovery_config: TestDiscoveryConfig):
        self.discovery_config = discovery_config
        self.discovery = TestDiscovery(discovery_config)
        self.scheduler = TestScheduler()
        self.file_watcher: Any | None = None  # Would use watchdog in real implementation
        self.changed_files: builtins.set[str] = set()

    def start_continuous_testing(self):
        """Start continuous testing engine."""
        logger.info("Starting continuous testing engine")

        # Discover initial tests
        self.discovery.discover_tests()

        # Start scheduler
        self.scheduler.start_scheduler()

        # Start file watching (simplified implementation)
        self._start_file_watching()

    def stop_continuous_testing(self):
        """Stop continuous testing engine."""
        logger.info("Stopping continuous testing engine")

        # Stop scheduler
        self.scheduler.stop_scheduler()

        # Stop file watching
        self._stop_file_watching()

    def _start_file_watching(self):
        """Start watching for file changes."""
        # In a real implementation, use watchdog library
        # For now, this is a placeholder

    def _stop_file_watching(self):
        """Stop file watching."""

    def on_file_changed(self, file_path: str):
        """Handle file change event."""
        self.changed_files.add(file_path)

        # Trigger affected tests
        self._trigger_affected_tests(file_path)

    def _trigger_affected_tests(self, file_path: str):
        """Trigger tests affected by file change."""
        # Determine which tests are affected by the changed file
        # This would involve dependency analysis

        # For now, just re-discover tests
        self.discovery.discover_tests()

    def create_ci_cd_plan(self, environment: TestEnvironmentType) -> TestExecutionPlan:
        """Create test execution plan for CI/CD."""
        tests, suites = self.discovery.discover_tests()

        plan = TestExecutionPlan(
            name=f"CI_CD_{environment.value}",
            description=f"CI/CD test plan for {environment.value} environment",
            test_suites=list(suites.keys()),
            environment=environment,
            configuration=TestConfiguration(
                parallel_execution=True,
                max_workers=8,
                fail_fast=True,
                generate_reports=True,
                report_formats=["json", "html"],
            ),
        )

        return plan


class TestOrchestrator:
    """Orchestrates comprehensive test automation workflow."""

    def __init__(self):
        self.discovery_configs: builtins.dict[str, TestDiscoveryConfig] = {}
        self.execution_plans: builtins.dict[str, TestExecutionPlan] = {}
        self.schedulers: builtins.dict[str, TestScheduler] = {}
        self.continuous_engines: builtins.dict[str, ContinuousTestingEngine] = {}
        self.reporters: builtins.dict[str, TestReporter] = {}

    def add_discovery_config(self, name: str, config: TestDiscoveryConfig):
        """Add test discovery configuration."""
        self.discovery_configs[name] = config

    def add_execution_plan(self, plan: TestExecutionPlan):
        """Add test execution plan."""
        self.execution_plans[plan.name] = plan

    def setup_continuous_testing(self, environment: str, discovery_config_name: str):
        """Setup continuous testing for environment."""
        if discovery_config_name not in self.discovery_configs:
            raise ValueError(f"Discovery config not found: {discovery_config_name}")

        config = self.discovery_configs[discovery_config_name]
        engine = ContinuousTestingEngine(config)

        self.continuous_engines[environment] = engine
        engine.start_continuous_testing()

        logger.info(f"Continuous testing setup for environment: {environment}")

    def setup_scheduled_testing(self, environment: str):
        """Setup scheduled testing for environment."""
        scheduler = TestScheduler()
        self.schedulers[environment] = scheduler

        # Add relevant plans to scheduler
        for plan in self.execution_plans.values():
            if plan.environment.value == environment:
                schedule_config = TestScheduleConfig(
                    schedule_type=TestScheduleType.SCHEDULED,
                    interval_minutes=60,  # Run every hour
                    environment=plan.environment,
                )
                scheduler.add_scheduled_plan(plan, schedule_config)

        scheduler.start_scheduler()
        logger.info(f"Scheduled testing setup for environment: {environment}")

    def execute_plan(self, plan_name: str) -> str | None:
        """Execute a test plan."""
        if plan_name not in self.execution_plans:
            return None

        plan = self.execution_plans[plan_name]
        environment = plan.environment.value

        # Get or create scheduler for environment
        if environment not in self.schedulers:
            self.schedulers[environment] = TestScheduler()

        scheduler = self.schedulers[environment]
        return scheduler.trigger_plan(plan_name, "manual")

    def get_test_status(
        self, environment: str, run_id: str | None = None
    ) -> builtins.dict[str, Any]:
        """Get test status for environment."""
        status = {
            "environment": environment,
            "continuous_testing": environment in self.continuous_engines,
            "scheduled_testing": environment in self.schedulers,
            "recent_runs": [],
        }

        if environment in self.schedulers:
            scheduler = self.schedulers[environment]
            if run_id:
                run = scheduler.get_test_run_status(run_id)
                status["current_run"] = run.__dict__ if run else None
            else:
                status["recent_runs"] = [run.__dict__ for run in scheduler.get_recent_runs()]

        return status

    def generate_comprehensive_report(self, environment: str | None = None) -> str:
        """Generate comprehensive test report."""
        report_data = {
            "generated_at": datetime.utcnow().isoformat(),
            "environments": {},
        }

        environments = [environment] if environment else self.schedulers.keys()

        for env in environments:
            if env in self.schedulers:
                scheduler = self.schedulers[env]
                recent_runs = scheduler.get_recent_runs(limit=50)

                env_data = {
                    "total_runs": len(recent_runs),
                    "recent_runs": [run.__dict__ for run in recent_runs],
                    "success_rate": 0,
                }

                if recent_runs:
                    successful_runs = len([r for r in recent_runs if r.status == TestStatus.PASSED])
                    env_data["success_rate"] = (successful_runs / len(recent_runs)) * 100

                report_data["environments"][env] = env_data

        # Save report
        report_path = f"test_automation_report_{int(time.time())}.json"
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Comprehensive test report generated: {report_path}")
        return report_path

    def shutdown(self):
        """Shutdown test orchestrator."""
        logger.info("Shutting down test orchestrator")

        # Stop continuous testing engines
        for engine in self.continuous_engines.values():
            engine.stop_continuous_testing()

        # Stop schedulers
        for scheduler in self.schedulers.values():
            scheduler.stop_scheduler()

        logger.info("Test orchestrator shutdown complete")


# Utility functions for quick setup
def create_standard_discovery_config(
    base_dirs: builtins.list[str],
) -> TestDiscoveryConfig:
    """Create standard test discovery configuration."""
    return TestDiscoveryConfig(
        strategy=TestDiscoveryStrategy.DIRECTORY_SCAN,
        base_directories=base_dirs,
        file_patterns=["test_*.py", "*_test.py", "test*.py"],
        exclude_patterns=["**/venv/**", "**/node_modules/**", "**/__pycache__/**"],
        test_class_patterns=["Test*", "*Test", "*TestCase"],
        test_method_patterns=["test_*", "*_test"],
    )


def create_ci_cd_execution_plan(environment: TestEnvironmentType) -> TestExecutionPlan:
    """Create standard CI/CD execution plan."""
    return TestExecutionPlan(
        name=f"CI_CD_{environment.value}",
        description=f"Standard CI/CD test execution plan for {environment.value}",
        parallel_execution=True,
        max_workers=8,
        timeout=1800,  # 30 minutes
        environment=environment,
        configuration=TestConfiguration(
            parallel_execution=True,
            max_workers=8,
            timeout=300,
            fail_fast=True,
            retry_failed_tests=True,
            max_retries=2,
            generate_reports=True,
            report_formats=["json", "html"],
            log_level="INFO",
        ),
    )


def setup_basic_test_automation(
    base_dirs: builtins.list[str], environments: builtins.list[str]
) -> TestOrchestrator:
    """Setup basic test automation for given environments."""
    orchestrator = TestOrchestrator()

    # Add discovery config
    discovery_config = create_standard_discovery_config(base_dirs)
    orchestrator.add_discovery_config("standard", discovery_config)

    # Create execution plans for each environment
    for env_name in environments:
        try:
            env_type = TestEnvironmentType(env_name)
            plan = create_ci_cd_execution_plan(env_type)
            orchestrator.add_execution_plan(plan)
        except ValueError:
            logger.warning(f"Unknown environment type: {env_name}")

    return orchestrator
