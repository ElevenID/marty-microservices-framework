import builtins
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from .enums import TestType, TestStatus, TestSeverity

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
    custom_metrics: dict[str, Any] = field(default_factory=dict)

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
    artifacts: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    severity: TestSeverity = TestSeverity.MEDIUM

    def to_dict(self) -> dict[str, Any]:
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
    report_formats: list[str] = field(default_factory=lambda: ["json", "html"])
    output_directory: str = "./test_results"
    log_level: str = "INFO"
    tags_to_run: list[str] = field(default_factory=list)
    tags_to_exclude: list[str] = field(default_factory=list)
    test_types_to_run: list[TestType] = field(default_factory=list)
