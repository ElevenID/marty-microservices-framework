"""
Enhanced CI/CD Pipeline Framework for Marty Microservices Framework

Provides comprehensive CI/CD capabilities including:
- Multi-stage pipeline orchestration
- Automated testing frameworks with parallel execution
- Security scanning and vulnerability assessment
- Quality gates and approval workflows
- Artifact management and versioning
- Integration with deployment strategies
- Pipeline analytics and reporting
"""

import asyncio
import builtins
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PipelineStage(Enum):
    """CI/CD pipeline stage types"""

    SOURCE = "source"
    BUILD = "build"
    TEST = "test"
    SECURITY_SCAN = "security_scan"
    QUALITY_GATE = "quality_gate"
    PACKAGE = "package"
    DEPLOY = "deploy"
    INTEGRATION_TEST = "integration_test"
    PERFORMANCE_TEST = "performance_test"
    APPROVAL = "approval"
    NOTIFICATION = "notification"


class TestType(Enum):
    """Test execution types"""

    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    PERFORMANCE = "performance"
    SECURITY = "security"
    SMOKE = "smoke"
    CONTRACT = "contract"
    CHAOS = "chaos"


class SecurityScanType(Enum):
    """Security scan types"""

    SAST = "sast"  # Static Application Security Testing
    DAST = "dast"  # Dynamic Application Security Testing
    DEPENDENCY = "dependency"
    CONTAINER = "container"
    INFRASTRUCTURE = "infrastructure"
    SECRETS = "secrets"
    COMPLIANCE = "compliance"


class PipelineStatus(Enum):
    """Pipeline execution status"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    MANUAL_APPROVAL = "manual_approval"


class ArtifactType(Enum):
    """Build artifact types"""

    CONTAINER_IMAGE = "container_image"
    BINARY = "binary"
    LIBRARY = "library"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    TEST_RESULTS = "test_results"
    SECURITY_REPORT = "security_report"
    COVERAGE_REPORT = "coverage_report"


@dataclass
class TestConfiguration:
    """Test execution configuration"""

    name: str
    test_type: TestType

    # Execution settings
    command: str = ""
    working_directory: str = "."
    environment_variables: builtins.dict[str, str] = field(default_factory=dict)

    # Test framework settings
    framework: str = "pytest"  # pytest, jest, junit, etc.
    test_paths: builtins.list[str] = field(default_factory=list)
    coverage_enabled: bool = True
    coverage_threshold: float = 0.8

    # Parallel execution
    parallel_enabled: bool = False
    max_parallel_jobs: int = 4

    # Timeout and retries
    timeout: int = 600  # 10 minutes
    retries: int = 0

    # Reporting
    junit_output: str = ""
    coverage_output: str = ""

    def to_dict(self) -> builtins.dict[str, Any]:
        return {**asdict(self), "test_type": self.test_type.value}


@dataclass
class SecurityScanConfiguration:
    """Security scan configuration"""

    name: str
    scan_type: SecurityScanType

    # Scanner settings
    scanner_tool: str = ""  # sonar, snyk, clair, etc.
    scanner_version: str = "latest"

    # Scan configuration
    scan_paths: builtins.list[str] = field(default_factory=list)
    exclude_paths: builtins.list[str] = field(default_factory=list)

    # Thresholds
    fail_on_critical: bool = True
    fail_on_high: bool = True
    fail_on_medium: bool = False
    max_vulnerabilities: int = 0

    # Output settings
    report_format: str = "json"
    report_output: str = ""

    # Tool-specific configuration
    tool_config: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {**asdict(self), "scan_type": self.scan_type.value}


@dataclass
class QualityGate:
    """Quality gate configuration"""

    name: str
    description: str = ""

    # Quality metrics
    code_coverage_threshold: float = 0.8
    test_success_rate_threshold: float = 1.0
    security_score_threshold: float = 0.9

    # Performance thresholds
    build_time_threshold: int = 600  # 10 minutes
    test_time_threshold: int = 300  # 5 minutes

    # Custom quality checks
    custom_checks: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)

    # Enforcement
    blocking: bool = True
    approval_required: bool = False

    def to_dict(self) -> builtins.dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineArtifact:
    """Pipeline build artifact"""

    name: str
    artifact_type: ArtifactType

    # Artifact details
    version: str = "latest"
    file_path: str = ""
    download_url: str = ""

    # Metadata
    size_bytes: int = 0
    checksum: str = ""
    content_type: str = ""

    # Lifecycle
    created_at: datetime | None = None
    expires_at: datetime | None = None

    # Storage
    storage_backend: str = "local"  # local, s3, gcs, azure, registry
    storage_location: str = ""

    # Tags and labels
    tags: builtins.dict[str, str] = field(default_factory=dict)
    labels: builtins.dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "artifact_type": self.artifact_type.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class PipelineStageDefinition:
    """Pipeline stage definition"""

    name: str
    stage_type: PipelineStage

    # Dependencies
    depends_on: builtins.list[str] = field(default_factory=list)

    # Execution settings
    enabled: bool = True
    allow_failure: bool = False
    timeout: int = 1800  # 30 minutes
    retries: int = 0

    # Conditional execution
    conditions: builtins.list[str] = field(default_factory=list)

    # Stage-specific configuration
    test_config: TestConfiguration | None = None
    security_scan_config: SecurityScanConfiguration | None = None
    quality_gate: QualityGate | None = None

    # Custom command execution
    commands: builtins.list[str] = field(default_factory=list)
    environment: builtins.dict[str, str] = field(default_factory=dict)
    working_directory: str = "."

    # Artifacts
    input_artifacts: builtins.list[str] = field(default_factory=list)
    output_artifacts: builtins.list[str] = field(default_factory=list)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "stage_type": self.stage_type.value,
            "test_config": self.test_config.to_dict() if self.test_config else None,
            "security_scan_config": self.security_scan_config.to_dict()
            if self.security_scan_config
            else None,
            "quality_gate": self.quality_gate.to_dict() if self.quality_gate else None,
        }


@dataclass
class PipelineDefinition:
    """Complete pipeline definition"""

    name: str
    description: str

    # Pipeline configuration
    triggers: builtins.list[str] = field(
        default_factory=list
    )  # push, pull_request, schedule, manual
    branches: builtins.list[str] = field(default_factory=list)  # main, develop, feature/*

    # Stages
    stages: builtins.list[PipelineStageDefinition] = field(default_factory=list)

    # Global settings
    timeout: int = 3600  # 1 hour
    concurrent_builds: int = 1

    # Environment
    environment_variables: builtins.dict[str, str] = field(default_factory=dict)
    secrets: builtins.list[str] = field(default_factory=list)

    # Notifications
    notification_channels: builtins.list[str] = field(default_factory=list)

    # Artifact management
    artifact_retention_days: int = 30
    artifact_storage: str = "local"

    # Integration settings
    deployment_integration: bool = True
    deployment_strategy: str = "rolling"

    def to_dict(self) -> builtins.dict[str, Any]:
        return {**asdict(self), "stages": [stage.to_dict() for stage in self.stages]}


@dataclass
class PipelineExecution:
    """Pipeline execution tracking"""

    execution_id: str
    pipeline_name: str
    started_at: datetime

    # Trigger information
    trigger_type: str = "manual"
    trigger_source: str = ""
    commit_sha: str = ""
    branch: str = "main"

    # Execution state
    status: PipelineStatus = PipelineStatus.PENDING
    current_stage: str = ""
    completed_stages: builtins.list[str] = field(default_factory=list)
    failed_stages: builtins.list[str] = field(default_factory=list)
    skipped_stages: builtins.list[str] = field(default_factory=list)

    # Results
    artifacts: builtins.list[PipelineArtifact] = field(default_factory=list)
    test_results: builtins.dict[str, Any] = field(default_factory=dict)
    security_results: builtins.dict[str, Any] = field(default_factory=dict)
    quality_results: builtins.dict[str, Any] = field(default_factory=dict)

    # Timing
    completed_at: datetime | None = None
    duration: float | None = None

    # Error handling
    error_message: str | None = None
    failure_reason: str | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


class TestRunner:
    """
    Test execution engine with support for multiple frameworks

    Features:
    - Multi-framework support (pytest, jest, junit, etc.)
    - Parallel test execution
    - Coverage reporting
    - Test result aggregation
    """

    def __init__(self):
        self.test_results: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Test framework configurations
        self.framework_configs = {
            "pytest": {
                "command_template": "python -m pytest {paths} --junitxml={junit_output} --cov={coverage_paths} --cov-report=xml:{coverage_output}",
                "default_paths": ["tests/"],
                "coverage_file": "coverage.xml",
            },
            "jest": {
                "command_template": "npm test -- --coverage --testResultsProcessor=jest-junit",
                "default_paths": ["src/", "tests/"],
                "coverage_file": "coverage/lcov.info",
            },
            "junit": {
                "command_template": "mvn test -Dmaven.test.failure.ignore=true",
                "default_paths": ["src/test/"],
                "coverage_file": "target/site/jacoco/jacoco.xml",
            },
        }

    async def execute_tests(
        self, execution_id: str, test_config: TestConfiguration
    ) -> builtins.dict[str, Any]:
        """Execute test suite"""

        result = {
            "test_name": test_config.name,
            "test_type": test_config.test_type.value,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "coverage_percentage": 0.0,
            "duration": 0.0,
            "output": "",
            "error_message": None,
        }

        try:
            print(f"🧪 Running {test_config.test_type.value} tests: {test_config.name}")

            # Build test command
            test_command = self._build_test_command(test_config)

            # Execute tests
            start_time = datetime.now()

            if test_config.parallel_enabled:
                test_result = await self._execute_parallel_tests(test_config, test_command)
            else:
                test_result = await self._execute_sequential_tests(test_config, test_command)

            end_time = datetime.now()
            result["duration"] = (end_time - start_time).total_seconds()

            # Parse test results
            if test_result["returncode"] == 0:
                result["status"] = "passed"
                print(f"✅ Tests passed: {test_config.name}")
            else:
                result["status"] = "failed"
                result["error_message"] = test_result["stderr"]
                print(f"❌ Tests failed: {test_config.name}")

            result["output"] = test_result["stdout"]

            # Parse test metrics
            await self._parse_test_results(result, test_config)

            # Check coverage threshold
            if (
                test_config.coverage_enabled
                and result["coverage_percentage"] < test_config.coverage_threshold
            ):
                result["status"] = "failed"
                result["error_message"] = (
                    f"Coverage {result['coverage_percentage']:.1f}% below threshold {test_config.coverage_threshold * 100:.1f}%"
                )

        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
            print(f"❌ Test execution error: {e}")

        finally:
            result["completed_at"] = datetime.now().isoformat()
            self.test_results[execution_id] = self.test_results.get(execution_id, {})
            self.test_results[execution_id][test_config.name] = result

        return result

    def _build_test_command(self, test_config: TestConfiguration) -> str:
        """Build test execution command"""

        if test_config.command:
            return test_config.command

        framework_config = self.framework_configs.get(test_config.framework, {})
        command_template = framework_config.get("command_template", test_config.command)

        # Build paths
        test_paths = test_config.test_paths or framework_config.get("default_paths", [])
        paths_str = " ".join(test_paths)

        # Build coverage paths (usually source directories)
        coverage_paths = [path for path in test_paths if "src" in path or "lib" in path]
        if not coverage_paths:
            coverage_paths = ["src/"]
        coverage_paths_str = ",".join(coverage_paths)

        # Set output files
        junit_output = test_config.junit_output or f"test-results-{test_config.name}.xml"
        coverage_output = test_config.coverage_output or framework_config.get(
            "coverage_file", "coverage.xml"
        )

        # Format command
        command = command_template.format(
            paths=paths_str,
            junit_output=junit_output,
            coverage_paths=coverage_paths_str,
            coverage_output=coverage_output,
        )

        return command

    async def _execute_sequential_tests(
        self, test_config: TestConfiguration, command: str
    ) -> builtins.dict[str, Any]:
        """Execute tests sequentially"""

        try:
            # Set up environment
            env = os.environ.copy()
            env.update(test_config.environment_variables)

            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=test_config.working_directory,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=test_config.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "returncode": -1,
                    "stdout": "",
                    "stderr": "Test execution timed out",
                }

            return {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
            }

        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e)}

    async def _execute_parallel_tests(
        self, test_config: TestConfiguration, base_command: str
    ) -> builtins.dict[str, Any]:
        """Execute tests in parallel"""

        try:
            # Split test paths for parallel execution
            test_paths = test_config.test_paths
            if not test_paths:
                test_paths = ["tests/"]

            # Create parallel commands
            parallel_commands = []
            for i, path in enumerate(test_paths):
                if i >= test_config.max_parallel_jobs:
                    break

                # Modify command for this specific path
                path_command = base_command.replace(" ".join(test_config.test_paths), path)
                path_command += f" --junitxml=test-results-{i}.xml"
                parallel_commands.append(path_command)

            # Execute parallel tasks
            tasks = []
            for command in parallel_commands:
                task = self._execute_sequential_tests(test_config, command)
                tasks.append(task)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Aggregate results
            combined_stdout = []
            combined_stderr = []
            final_returncode = 0

            for result in results:
                if isinstance(result, Exception):
                    combined_stderr.append(str(result))
                    final_returncode = -1
                else:
                    combined_stdout.append(result["stdout"])
                    combined_stderr.append(result["stderr"])
                    if result["returncode"] != 0:
                        final_returncode = result["returncode"]

            return {
                "returncode": final_returncode,
                "stdout": "\n".join(combined_stdout),
                "stderr": "\n".join(combined_stderr),
            }

        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e)}

    async def _parse_test_results(
        self, result: builtins.dict[str, Any], test_config: TestConfiguration
    ):
        """Parse test execution results"""

        # Mock test result parsing - in production would parse actual JUnit XML
        # and coverage reports

        # Simulate test metrics
        if result["status"] == "passed":
            result["total_tests"] = 150
            result["passed_tests"] = 150
            result["failed_tests"] = 0
            result["skipped_tests"] = 0
            result["coverage_percentage"] = 0.85  # 85% coverage
        else:
            result["total_tests"] = 150
            result["passed_tests"] = 145
            result["failed_tests"] = 5
            result["skipped_tests"] = 0
            result["coverage_percentage"] = 0.75  # 75% coverage

        # Add test type specific metrics
        if test_config.test_type == TestType.PERFORMANCE:
            result["performance_metrics"] = {
                "avg_response_time": 125.5,
                "p95_response_time": 250.0,
                "throughput": 1500.0,
                "error_rate": 0.02,
            }
        elif test_config.test_type == TestType.SECURITY:
            result["security_metrics"] = {
                "vulnerabilities_found": 2,
                "critical_vulnerabilities": 0,
                "high_vulnerabilities": 1,
                "medium_vulnerabilities": 1,
            }


class SecurityScanner:
    """
    Security scanning engine with support for multiple scan types

    Features:
    - SAST (Static Application Security Testing)
    - DAST (Dynamic Application Security Testing)
    - Dependency vulnerability scanning
    - Container image scanning
    - Infrastructure security scanning
    """

    def __init__(self):
        self.scan_results: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Scanner tool configurations
        self.scanner_configs = {
            "sonar": {
                "command_template": "sonar-scanner -Dsonar.projectKey={project_key} -Dsonar.sources={sources}",
                "supported_types": [SecurityScanType.SAST],
            },
            "snyk": {
                "command_template": "snyk test --json",
                "supported_types": [
                    SecurityScanType.DEPENDENCY,
                    SecurityScanType.CONTAINER,
                ],
            },
            "clair": {
                "command_template": "clair-scanner --ip localhost {image}",
                "supported_types": [SecurityScanType.CONTAINER],
            },
            "bandit": {
                "command_template": "bandit -r {paths} -f json",
                "supported_types": [SecurityScanType.SAST],
            },
            "semgrep": {
                "command_template": "semgrep --config=auto {paths} --json",
                "supported_types": [SecurityScanType.SAST],
            },
        }

    async def execute_security_scan(
        self, execution_id: str, scan_config: SecurityScanConfiguration
    ) -> builtins.dict[str, Any]:
        """Execute security scan"""

        result = {
            "scan_name": scan_config.name,
            "scan_type": scan_config.scan_type.value,
            "scanner_tool": scan_config.scanner_tool,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "vulnerabilities": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0,
            },
            "total_vulnerabilities": 0,
            "duration": 0.0,
            "report_path": "",
            "output": "",
            "error_message": None,
        }

        try:
            print(f"🔒 Running {scan_config.scan_type.value} security scan: {scan_config.name}")

            # Build scan command
            scan_command = self._build_scan_command(scan_config)

            # Execute scan
            start_time = datetime.now()
            scan_result = await self._execute_scan_command(scan_config, scan_command)
            end_time = datetime.now()

            result["duration"] = (end_time - start_time).total_seconds()
            result["output"] = scan_result["stdout"]

            # Parse scan results
            if scan_result["returncode"] == 0:
                result["status"] = "completed"
                print(f"✅ Security scan completed: {scan_config.name}")
            # Some security scanners return non-zero when vulnerabilities are found
            elif "vulnerabilities found" in scan_result["stderr"].lower():
                result["status"] = "completed"
                print(f"⚠️ Security scan completed with findings: {scan_config.name}")
            else:
                result["status"] = "failed"
                result["error_message"] = scan_result["stderr"]
                print(f"❌ Security scan failed: {scan_config.name}")

            # Parse vulnerability results
            await self._parse_vulnerability_results(result, scan_config, scan_result)

            # Check thresholds
            if self._check_security_thresholds(result, scan_config):
                result["status"] = "failed"
                result["error_message"] = "Security scan thresholds exceeded"

            # Generate report
            report_path = await self._generate_security_report(result, scan_config)
            result["report_path"] = report_path

        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
            print(f"❌ Security scan error: {e}")

        finally:
            result["completed_at"] = datetime.now().isoformat()
            self.scan_results[execution_id] = self.scan_results.get(execution_id, {})
            self.scan_results[execution_id][scan_config.name] = result

        return result

    def _build_scan_command(self, scan_config: SecurityScanConfiguration) -> str:
        """Build security scan command"""

        if not scan_config.scanner_tool:
            # Auto-select scanner based on scan type
            scan_config.scanner_tool = self._auto_select_scanner(scan_config.scan_type)

        scanner_config = self.scanner_configs.get(scan_config.scanner_tool, {})
        command_template = scanner_config.get("command_template", "")

        if not command_template:
            raise ValueError(f"No command template for scanner: {scan_config.scanner_tool}")

        # Build scan paths
        scan_paths = scan_config.scan_paths or ["."]
        paths_str = " ".join(scan_paths)

        # Format command based on scanner type
        if scan_config.scanner_tool == "sonar":
            command = command_template.format(
                project_key=f"marty-{scan_config.name}", sources=paths_str
            )
        elif scan_config.scanner_tool in ["bandit", "semgrep"]:
            command = command_template.format(paths=paths_str)
        elif scan_config.scanner_tool == "clair":
            # For container scanning, paths would be image names
            image_name = scan_paths[0] if scan_paths else "app:latest"
            command = command_template.format(image=image_name)
        else:
            command = command_template

        # Add output format
        if scan_config.report_format and "--json" not in command:
            if scan_config.report_format == "json":
                command += " --json"
            elif scan_config.report_format == "xml":
                command += " --xml"

        return command

    def _auto_select_scanner(self, scan_type: SecurityScanType) -> str:
        """Auto-select appropriate scanner for scan type"""

        scanner_mapping = {
            SecurityScanType.SAST: "semgrep",
            SecurityScanType.DEPENDENCY: "snyk",
            SecurityScanType.CONTAINER: "clair",
            SecurityScanType.SECRETS: "semgrep",
            SecurityScanType.COMPLIANCE: "sonar",
        }

        return scanner_mapping.get(scan_type, "semgrep")

    async def _execute_scan_command(
        self, scan_config: SecurityScanConfiguration, command: str
    ) -> builtins.dict[str, Any]:
        """Execute security scan command"""

        try:
            # Set up environment
            env = os.environ.copy()
            env.update(scan_config.tool_config.get("environment", {}))

            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=".",
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=600,  # 10 minutes for security scans
                )
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "returncode": -1,
                    "stdout": "",
                    "stderr": "Security scan timed out",
                }

            return {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
            }

        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e)}

    async def _parse_vulnerability_results(
        self,
        result: builtins.dict[str, Any],
        scan_config: SecurityScanConfiguration,
        scan_result: builtins.dict[str, Any],
    ):
        """Parse vulnerability scan results"""

        # Mock vulnerability parsing - in production would parse actual scanner output

        # Simulate findings based on scan type
        if scan_config.scan_type == SecurityScanType.SAST:
            result["vulnerabilities"] = {
                "critical": 0,
                "high": 2,
                "medium": 5,
                "low": 8,
                "info": 3,
            }
        elif scan_config.scan_type == SecurityScanType.DEPENDENCY:
            result["vulnerabilities"] = {
                "critical": 1,
                "high": 3,
                "medium": 7,
                "low": 12,
                "info": 5,
            }
        elif scan_config.scan_type == SecurityScanType.CONTAINER:
            result["vulnerabilities"] = {
                "critical": 0,
                "high": 1,
                "medium": 3,
                "low": 6,
                "info": 2,
            }
        else:
            result["vulnerabilities"] = {
                "critical": 0,
                "high": 1,
                "medium": 2,
                "low": 4,
                "info": 1,
            }

        result["total_vulnerabilities"] = sum(result["vulnerabilities"].values())

        # Add detailed findings
        result["findings"] = [
            {
                "id": f"VULN-{i + 1:03d}",
                "severity": "high" if i < 2 else "medium",
                "title": f"Sample vulnerability {i + 1}",
                "description": f"Description for vulnerability {i + 1}",
                "file": f"src/file{i + 1}.py",
                "line": (i + 1) * 10,
                "cwe": f"CWE-{200 + i}",
                "confidence": "high",
            }
            for i in range(min(5, result["total_vulnerabilities"]))
        ]

    def _check_security_thresholds(
        self, result: builtins.dict[str, Any], scan_config: SecurityScanConfiguration
    ) -> bool:
        """Check if vulnerabilities exceed configured thresholds"""

        vulnerabilities = result["vulnerabilities"]

        if scan_config.fail_on_critical and vulnerabilities["critical"] > 0:
            return True

        if scan_config.fail_on_high and vulnerabilities["high"] > 0:
            return True

        if scan_config.fail_on_medium and vulnerabilities["medium"] > 0:
            return True

        if result["total_vulnerabilities"] > scan_config.max_vulnerabilities:
            return True

        return False

    async def _generate_security_report(
        self, result: builtins.dict[str, Any], scan_config: SecurityScanConfiguration
    ) -> str:
        """Generate security scan report"""

        report_filename = scan_config.report_output or f"security-report-{scan_config.name}.json"

        report_data = {
            "scan_info": {
                "name": scan_config.name,
                "type": scan_config.scan_type.value,
                "scanner": scan_config.scanner_tool,
                "timestamp": result["started_at"],
                "duration": result["duration"],
            },
            "summary": {
                "total_vulnerabilities": result["total_vulnerabilities"],
                "by_severity": result["vulnerabilities"],
                "status": result["status"],
            },
            "findings": result.get("findings", []),
        }

        try:
            with open(report_filename, "w") as f:
                json.dump(report_data, f, indent=2)

            print(f"📄 Security report generated: {report_filename}")
            return report_filename

        except Exception as e:
            print(f"⚠️ Failed to generate security report: {e}")
            return ""


class QualityGateEngine:
    """
    Quality gate evaluation engine

    Features:
    - Multi-metric quality evaluation
    - Configurable thresholds
    - Custom quality checks
    - Approval workflow integration
    """

    def __init__(self):
        self.quality_results: builtins.dict[str, builtins.dict[str, Any]] = {}

    async def evaluate_quality_gate(
        self,
        execution_id: str,
        quality_gate: QualityGate,
        execution_context: builtins.dict[str, Any],
    ) -> builtins.dict[str, Any]:
        """Evaluate quality gate criteria"""

        result = {
            "gate_name": quality_gate.name,
            "status": "evaluating",
            "started_at": datetime.now().isoformat(),
            "passed": False,
            "blocking": quality_gate.blocking,
            "approval_required": quality_gate.approval_required,
            "checks": {},
            "overall_score": 0.0,
            "error_message": None,
        }

        try:
            print(f"🚦 Evaluating quality gate: {quality_gate.name}")

            total_checks = 0
            passed_checks = 0

            # Code coverage check
            if "test_results" in execution_context:
                coverage_check = self._check_code_coverage(
                    execution_context["test_results"],
                    quality_gate.code_coverage_threshold,
                )
                result["checks"]["code_coverage"] = coverage_check
                total_checks += 1
                if coverage_check["passed"]:
                    passed_checks += 1

            # Test success rate check
            if "test_results" in execution_context:
                test_success_check = self._check_test_success_rate(
                    execution_context["test_results"],
                    quality_gate.test_success_rate_threshold,
                )
                result["checks"]["test_success_rate"] = test_success_check
                total_checks += 1
                if test_success_check["passed"]:
                    passed_checks += 1

            # Security score check
            if "security_results" in execution_context:
                security_check = self._check_security_score(
                    execution_context["security_results"],
                    quality_gate.security_score_threshold,
                )
                result["checks"]["security_score"] = security_check
                total_checks += 1
                if security_check["passed"]:
                    passed_checks += 1

            # Performance checks
            build_time_check = self._check_build_time(
                execution_context.get("build_duration", 0),
                quality_gate.build_time_threshold,
            )
            result["checks"]["build_time"] = build_time_check
            total_checks += 1
            if build_time_check["passed"]:
                passed_checks += 1

            # Custom checks
            for custom_check in quality_gate.custom_checks:
                check_result = await self._execute_custom_check(custom_check, execution_context)
                result["checks"][custom_check["name"]] = check_result
                total_checks += 1
                if check_result["passed"]:
                    passed_checks += 1

            # Calculate overall score
            result["overall_score"] = passed_checks / total_checks if total_checks > 0 else 0.0

            # Determine if gate passes
            result["passed"] = passed_checks == total_checks

            if result["passed"]:
                result["status"] = "passed"
                print(f"✅ Quality gate passed: {quality_gate.name}")
            elif quality_gate.blocking:
                result["status"] = "failed"
                print(f"❌ Quality gate failed (blocking): {quality_gate.name}")
            else:
                result["status"] = "warning"
                print(f"⚠️ Quality gate failed (non-blocking): {quality_gate.name}")

            # Check if manual approval is required
            if quality_gate.approval_required and not result["passed"]:
                result["status"] = "manual_approval_required"
                print(f"⏸️ Manual approval required for quality gate: {quality_gate.name}")

        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
            print(f"❌ Quality gate evaluation error: {e}")

        finally:
            result["completed_at"] = datetime.now().isoformat()
            self.quality_results[execution_id] = self.quality_results.get(execution_id, {})
            self.quality_results[execution_id][quality_gate.name] = result

        return result

    def _check_code_coverage(
        self, test_results: builtins.dict[str, Any], threshold: float
    ) -> builtins.dict[str, Any]:
        """Check code coverage threshold"""

        # Extract coverage from test results
        coverage_values = []
        for _test_name, test_result in test_results.items():
            if "coverage_percentage" in test_result:
                coverage_values.append(test_result["coverage_percentage"])

        if not coverage_values:
            return {
                "name": "code_coverage",
                "passed": False,
                "actual_value": 0.0,
                "threshold": threshold,
                "message": "No coverage data found",
            }

        # Calculate average coverage
        avg_coverage = sum(coverage_values) / len(coverage_values)

        return {
            "name": "code_coverage",
            "passed": avg_coverage >= threshold,
            "actual_value": avg_coverage,
            "threshold": threshold,
            "message": f"Coverage: {avg_coverage:.1%} (threshold: {threshold:.1%})",
        }

    def _check_test_success_rate(
        self, test_results: builtins.dict[str, Any], threshold: float
    ) -> builtins.dict[str, Any]:
        """Check test success rate threshold"""

        total_tests = 0
        passed_tests = 0

        for _test_name, test_result in test_results.items():
            if "total_tests" in test_result and "passed_tests" in test_result:
                total_tests += test_result["total_tests"]
                passed_tests += test_result["passed_tests"]

        if total_tests == 0:
            return {
                "name": "test_success_rate",
                "passed": False,
                "actual_value": 0.0,
                "threshold": threshold,
                "message": "No test results found",
            }

        success_rate = passed_tests / total_tests

        return {
            "name": "test_success_rate",
            "passed": success_rate >= threshold,
            "actual_value": success_rate,
            "threshold": threshold,
            "message": f"Test success rate: {success_rate:.1%} ({passed_tests}/{total_tests})",
        }

    def _check_security_score(
        self, security_results: builtins.dict[str, Any], threshold: float
    ) -> builtins.dict[str, Any]:
        """Check security score threshold"""

        # Calculate security score based on vulnerability counts
        total_vulnerabilities = 0
        critical_vulnerabilities = 0
        high_vulnerabilities = 0

        for _scan_name, scan_result in security_results.items():
            if "vulnerabilities" in scan_result:
                vulns = scan_result["vulnerabilities"]
                total_vulnerabilities += vulns.get("total", 0)
                critical_vulnerabilities += vulns.get("critical", 0)
                high_vulnerabilities += vulns.get("high", 0)

        # Simple security score calculation
        # Score = 1.0 - (critical * 0.3 + high * 0.2) / max(total, 1)
        if total_vulnerabilities == 0:
            security_score = 1.0
        else:
            penalty = (
                critical_vulnerabilities * 0.3 + high_vulnerabilities * 0.2
            ) / total_vulnerabilities
            security_score = max(0.0, 1.0 - penalty)

        return {
            "name": "security_score",
            "passed": security_score >= threshold,
            "actual_value": security_score,
            "threshold": threshold,
            "message": f"Security score: {security_score:.1%} (critical: {critical_vulnerabilities}, high: {high_vulnerabilities})",
        }

    def _check_build_time(self, build_duration: float, threshold: int) -> builtins.dict[str, Any]:
        """Check build time threshold"""

        return {
            "name": "build_time",
            "passed": build_duration <= threshold,
            "actual_value": build_duration,
            "threshold": threshold,
            "message": f"Build time: {build_duration:.1f}s (threshold: {threshold}s)",
        }

    async def _execute_custom_check(
        self,
        custom_check: builtins.dict[str, Any],
        execution_context: builtins.dict[str, Any],
    ) -> builtins.dict[str, Any]:
        """Execute custom quality check"""

        check_name = custom_check.get("name", "custom_check")
        check_type = custom_check.get("type", "generic")

        # Mock custom check execution
        await asyncio.sleep(0.1)  # Simulate check execution

        # Simulate different check types
        if check_type == "performance":
            # Performance regression check
            current_response_time = execution_context.get("avg_response_time", 100)
            threshold = custom_check.get("threshold", 200)

            return {
                "name": check_name,
                "passed": current_response_time <= threshold,
                "actual_value": current_response_time,
                "threshold": threshold,
                "message": f"Response time: {current_response_time}ms (threshold: {threshold}ms)",
            }

        if check_type == "complexity":
            # Code complexity check
            complexity_score = execution_context.get("complexity_score", 5.0)
            threshold = custom_check.get("threshold", 10.0)

            return {
                "name": check_name,
                "passed": complexity_score <= threshold,
                "actual_value": complexity_score,
                "threshold": threshold,
                "message": f"Complexity score: {complexity_score} (threshold: {threshold})",
            }

        # Generic check - always pass for demo
        return {
            "name": check_name,
            "passed": True,
            "actual_value": 1.0,
            "threshold": 1.0,
            "message": f"Custom check {check_name} passed",
        }


# Example usage and demo
async def main():
    """Example usage of CI/CD pipeline framework"""

    print("=== Enhanced CI/CD Pipeline Demo ===")

    # Initialize components
    test_runner = TestRunner()
    security_scanner = SecurityScanner()
    quality_gate_engine = QualityGateEngine()

    # Create test configurations
    unit_test_config = TestConfiguration(
        name="unit_tests",
        test_type=TestType.UNIT,
        framework="pytest",
        test_paths=["tests/unit/"],
        coverage_enabled=True,
        coverage_threshold=0.8,
        parallel_enabled=True,
    )

    integration_test_config = TestConfiguration(
        name="integration_tests",
        test_type=TestType.INTEGRATION,
        framework="pytest",
        test_paths=["tests/integration/"],
        coverage_enabled=True,
        coverage_threshold=0.7,
    )

    # Create security scan configurations
    sast_scan_config = SecurityScanConfiguration(
        name="static_analysis",
        scan_type=SecurityScanType.SAST,
        scanner_tool="semgrep",
        scan_paths=["src/"],
        fail_on_critical=True,
        fail_on_high=True,
    )

    dependency_scan_config = SecurityScanConfiguration(
        name="dependency_check",
        scan_type=SecurityScanType.DEPENDENCY,
        scanner_tool="snyk",
        fail_on_critical=True,
        max_vulnerabilities=10,
    )

    # Create quality gate
    quality_gate = QualityGate(
        name="release_gate",
        description="Quality gate for release builds",
        code_coverage_threshold=0.8,
        test_success_rate_threshold=1.0,
        security_score_threshold=0.9,
        build_time_threshold=600,
        custom_checks=[{"name": "performance_check", "type": "performance", "threshold": 200}],
        blocking=True,
    )

    # Execute pipeline stages
    execution_id = f"exec_{int(datetime.now().timestamp())}"

    print("\n🧪 Running Tests")

    # Execute unit tests
    unit_test_result = await test_runner.execute_tests(execution_id, unit_test_config)
    print(
        f"Unit tests: {unit_test_result['status']} - {unit_test_result['passed_tests']}/{unit_test_result['total_tests']} passed"
    )

    # Execute integration tests
    integration_test_result = await test_runner.execute_tests(execution_id, integration_test_config)
    print(
        f"Integration tests: {integration_test_result['status']} - {integration_test_result['passed_tests']}/{integration_test_result['total_tests']} passed"
    )

    print("\n🔒 Running Security Scans")

    # Execute SAST scan
    sast_result = await security_scanner.execute_security_scan(execution_id, sast_scan_config)
    print(
        f"SAST scan: {sast_result['status']} - {sast_result['total_vulnerabilities']} vulnerabilities found"
    )

    # Execute dependency scan
    dependency_result = await security_scanner.execute_security_scan(
        execution_id, dependency_scan_config
    )
    print(
        f"Dependency scan: {dependency_result['status']} - {dependency_result['total_vulnerabilities']} vulnerabilities found"
    )

    print("\n🚦 Evaluating Quality Gate")

    # Prepare execution context
    execution_context = {
        "test_results": {
            "unit_tests": unit_test_result,
            "integration_tests": integration_test_result,
        },
        "security_results": {"sast": sast_result, "dependency": dependency_result},
        "build_duration": 350.5,  # 5.8 minutes
        "avg_response_time": 150,  # 150ms
    }

    # Evaluate quality gate
    quality_result = await quality_gate_engine.evaluate_quality_gate(
        execution_id, quality_gate, execution_context
    )

    print(
        f"Quality gate: {quality_result['status']} - Score: {quality_result['overall_score']:.1%}"
    )

    # Show detailed results
    print("\n📊 Detailed Results")
    for check_name, check_result in quality_result["checks"].items():
        status = "✅" if check_result["passed"] else "❌"
        print(f"  {status} {check_name}: {check_result['message']}")

    # Pipeline summary
    print("\n🎯 Pipeline Summary")
    print(f"Execution ID: {execution_id}")
    print(
        f"Total test coverage: {(unit_test_result['coverage_percentage'] + integration_test_result['coverage_percentage']) / 2:.1%}"
    )
    print(
        f"Total vulnerabilities: {sast_result['total_vulnerabilities'] + dependency_result['total_vulnerabilities']}"
    )
    print(f"Quality gate status: {quality_result['status']}")


if __name__ == "__main__":
    asyncio.run(main())
