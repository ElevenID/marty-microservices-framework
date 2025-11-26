"""
Mutation Testing and Quality Gates for Marty Microservices Framework

This module implements comprehensive mutation testing capabilities including
code mutation, test effectiveness measurement, quality gate automation,
and comprehensive reporting for microservices code quality validation.
"""

import ast
import asyncio
import builtins
import copy
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# For code analysis and mutation
import coverage


class MutationType(Enum):
    """Types of code mutations."""

    ARITHMETIC_OPERATOR = "arithmetic_operator"
    RELATIONAL_OPERATOR = "relational_operator"
    CONDITIONAL_OPERATOR = "conditional_operator"
    LOGICAL_OPERATOR = "logical_operator"
    ASSIGNMENT_OPERATOR = "assignment_operator"
    UNARY_OPERATOR = "unary_operator"
    STATEMENT_DELETION = "statement_deletion"
    CONSTANT_REPLACEMENT = "constant_replacement"
    VARIABLE_REPLACEMENT = "variable_replacement"
    RETURN_VALUE_REPLACEMENT = "return_value_replacement"
    EXCEPTION_HANDLING = "exception_handling"
    LOOP_BOUNDARY = "loop_boundary"


class MutationStatus(Enum):
    """Status of mutation testing."""

    KILLED = "killed"  # Test detected the mutation
    SURVIVED = "survived"  # Test did not detect the mutation
    TIMEOUT = "timeout"  # Test timed out
    ERROR = "error"  # Error during mutation execution
    SKIPPED = "skipped"  # Mutation was skipped


class QualityGateType(Enum):
    """Types of quality gates."""

    MUTATION_SCORE = "mutation_score"
    CODE_COVERAGE = "code_coverage"
    TEST_PASS_RATE = "test_pass_rate"
    COMPLEXITY_THRESHOLD = "complexity_threshold"
    DUPLICATION_THRESHOLD = "duplication_threshold"
    SECURITY_VULNERABILITIES = "security_vulnerabilities"
    PERFORMANCE_DEGRADATION = "performance_degradation"


class QualityGateStatus(Enum):
    """Quality gate evaluation status."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class MutationOperator:
    """Defines a mutation operator."""

    name: str
    mutation_type: MutationType
    description: str
    apply_function: Callable[[ast.AST], builtins.list[ast.AST]]

    # Configuration
    enabled: bool = True
    weight: float = 1.0

    # Metadata
    tags: builtins.list[str] = field(default_factory=list)


@dataclass
class Mutant:
    """Represents a code mutant."""

    mutant_id: str
    original_file: str
    line_number: int
    column_number: int

    # Mutation details
    mutation_type: MutationType
    operator_name: str
    original_code: str
    mutated_code: str

    # Execution results
    status: MutationStatus = MutationStatus.SKIPPED
    killing_test: str | None = None
    execution_time: float | None = None
    error_message: str | None = None

    # Coverage information
    covered_by_tests: builtins.list[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: datetime | None = None


@dataclass
class MutationTestResult:
    """Results of mutation testing."""

    session_id: str
    target_files: builtins.list[str]

    # Overall statistics
    total_mutants: int = 0
    killed_mutants: int = 0
    survived_mutants: int = 0
    timeout_mutants: int = 0
    error_mutants: int = 0

    # Mutation score
    mutation_score: float = 0.0

    # Detailed results
    mutants: builtins.list[Mutant] = field(default_factory=list)

    # Coverage information
    original_coverage: builtins.dict[str, Any] = field(default_factory=dict)

    # Performance metrics
    execution_time: float = 0.0

    # Quality metrics
    test_effectiveness: builtins.dict[str, Any] = field(default_factory=dict)

    # Timestamps
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


@dataclass
class QualityGate:
    """Defines a quality gate."""

    gate_id: str
    name: str
    gate_type: QualityGateType

    # Thresholds
    threshold_value: float
    warning_threshold: float | None = None

    # Configuration
    enabled: bool = True
    blocking: bool = True  # Whether failure blocks deployment

    # Evaluation function
    evaluation_function: Callable | None = None

    # Metadata
    description: str = ""
    tags: builtins.list[str] = field(default_factory=list)


@dataclass
class QualityGateResult:
    """Result of quality gate evaluation."""

    gate_id: str
    status: QualityGateStatus

    # Values
    actual_value: float
    threshold_value: float

    # Details
    message: str = ""
    details: builtins.dict[str, Any] = field(default_factory=dict)

    # Timestamps
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CodeMutator(ABC):
    """Abstract base class for code mutators."""

    @abstractmethod
    def can_mutate(self, node: ast.AST) -> bool:
        """Check if node can be mutated."""

    @abstractmethod
    def mutate(self, node: ast.AST) -> builtins.list[ast.AST]:
        """Generate mutations for the node."""


class ArithmeticOperatorMutator(CodeMutator):
    """Mutates arithmetic operators."""

    OPERATOR_REPLACEMENTS = {
        ast.Add: [ast.Sub, ast.Mult, ast.Div],
        ast.Sub: [ast.Add, ast.Mult, ast.Div],
        ast.Mult: [ast.Add, ast.Sub, ast.Div],
        ast.Div: [ast.Add, ast.Sub, ast.Mult],
        ast.Mod: [ast.Mult, ast.Div],
        ast.Pow: [ast.Mult, ast.Div],
        ast.FloorDiv: [ast.Div, ast.Mult],
    }

    def can_mutate(self, node: ast.AST) -> bool:
        """Check if node is a binary operation with arithmetic operator."""
        return isinstance(node, ast.BinOp) and type(node.op) in self.OPERATOR_REPLACEMENTS

    def mutate(self, node: ast.AST) -> builtins.list[ast.AST]:
        """Generate arithmetic operator mutations."""
        mutations = []

        if isinstance(node, ast.BinOp):
            original_op = type(node.op)
            replacements = self.OPERATOR_REPLACEMENTS.get(original_op, [])

            for replacement_op in replacements:
                mutated_node = copy.deepcopy(node)
                mutated_node.op = replacement_op()
                mutations.append(mutated_node)

        return mutations


class RelationalOperatorMutator(CodeMutator):
    """Mutates relational operators."""

    OPERATOR_REPLACEMENTS = {
        ast.Eq: [ast.NotEq, ast.Lt, ast.Gt, ast.LtE, ast.GtE],
        ast.NotEq: [ast.Eq, ast.Lt, ast.Gt, ast.LtE, ast.GtE],
        ast.Lt: [ast.Eq, ast.NotEq, ast.Gt, ast.LtE, ast.GtE],
        ast.Gt: [ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.GtE],
        ast.LtE: [ast.Eq, ast.NotEq, ast.Lt, ast.Gt, ast.GtE],
        ast.GtE: [ast.Eq, ast.NotEq, ast.Lt, ast.Gt, ast.LtE],
        ast.Is: [ast.IsNot],
        ast.IsNot: [ast.Is],
        ast.In: [ast.NotIn],
        ast.NotIn: [ast.In],
    }

    def can_mutate(self, node: ast.AST) -> bool:
        """Check if node is a comparison with relational operator."""
        return (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and type(node.ops[0]) in self.OPERATOR_REPLACEMENTS
        )

    def mutate(self, node: ast.AST) -> builtins.list[ast.AST]:
        """Generate relational operator mutations."""
        mutations = []

        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            original_op = type(node.ops[0])
            replacements = self.OPERATOR_REPLACEMENTS.get(original_op, [])

            for replacement_op in replacements:
                mutated_node = copy.deepcopy(node)
                mutated_node.ops = [replacement_op()]
                mutations.append(mutated_node)

        return mutations


class LogicalOperatorMutator(CodeMutator):
    """Mutates logical operators."""

    def can_mutate(self, node: ast.AST) -> bool:
        """Check if node is a boolean operation."""
        return isinstance(node, ast.BoolOp)

    def mutate(self, node: ast.AST) -> builtins.list[ast.AST]:
        """Generate logical operator mutations."""
        mutations = []

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                # Replace AND with OR
                mutated_node = copy.deepcopy(node)
                mutated_node.op = ast.Or()
                mutations.append(mutated_node)

            elif isinstance(node.op, ast.Or):
                # Replace OR with AND
                mutated_node = copy.deepcopy(node)
                mutated_node.op = ast.And()
                mutations.append(mutated_node)

        return mutations


class ConstantReplacementMutator(CodeMutator):
    """Mutates constants."""

    def can_mutate(self, node: ast.AST) -> bool:
        """Check if node is a constant."""
        return isinstance(node, ast.Constant | ast.Num | ast.Str | ast.NameConstant)

    def mutate(self, node: ast.AST) -> builtins.list[ast.AST]:
        """Generate constant mutations."""
        mutations = []

        if isinstance(node, ast.Constant):
            value = node.value

            if isinstance(value, int | float):
                # Numeric mutations
                mutations.extend(
                    [
                        ast.Constant(value=0),
                        ast.Constant(value=1),
                        ast.Constant(value=-1),
                        ast.Constant(value=value + 1)
                        if isinstance(value, int)
                        else ast.Constant(value=value + 0.1),
                        ast.Constant(value=value - 1)
                        if isinstance(value, int)
                        else ast.Constant(value=value - 0.1),
                    ]
                )

            elif isinstance(value, str):
                # String mutations
                mutations.extend(
                    [
                        ast.Constant(value=""),
                        ast.Constant(value="mutated"),
                        ast.Constant(value=value + "_mutated"),
                    ]
                )

            elif isinstance(value, bool):
                # Boolean mutations
                mutations.append(ast.Constant(value=not value))

        return mutations


class StatementDeletionMutator(CodeMutator):
    """Deletes statements."""

    def can_mutate(self, node: ast.AST) -> bool:
        """Check if node is a deletable statement."""
        return isinstance(node, ast.Expr | ast.Assign | ast.AnnAssign | ast.AugAssign)

    def mutate(self, node: ast.AST) -> builtins.list[ast.AST]:
        """Generate statement deletion mutations."""
        # Return pass statement to replace the deleted statement
        return [ast.Pass()]


class MutationEngine:
    """Engine for generating and applying code mutations."""

    def __init__(self):
        """Initialize mutation engine."""
        self.mutators: builtins.list[CodeMutator] = [
            ArithmeticOperatorMutator(),
            RelationalOperatorMutator(),
            LogicalOperatorMutator(),
            ConstantReplacementMutator(),
            StatementDeletionMutator(),
        ]

        # Configuration
        self.max_mutants_per_file = 1000
        self.max_mutants_per_line = 10

        # Statistics
        self.mutation_stats = defaultdict(int)

    def add_mutator(self, mutator: CodeMutator):
        """Add custom mutator."""
        self.mutators.append(mutator)

    def generate_mutants(self, source_file: str) -> builtins.list[Mutant]:
        """Generate mutants for source file."""
        try:
            with open(source_file) as f:
                source_code = f.read()

            tree = ast.parse(source_code)
            mutants = []

            for node in ast.walk(tree):
                # Limit mutants per file
                if len(mutants) >= self.max_mutants_per_file:
                    break

                line_mutants = 0

                for mutator in self.mutators:
                    if mutator.can_mutate(node):
                        mutations = mutator.mutate(node)

                        for mutation in mutations:
                            # Limit mutants per line
                            if line_mutants >= self.max_mutants_per_line:
                                break

                            mutant = self._create_mutant(source_file, node, mutation, mutator)

                            if mutant:
                                mutants.append(mutant)
                                line_mutants += 1
                                self.mutation_stats[mutator.__class__.__name__] += 1

            logging.info(f"Generated {len(mutants)} mutants for {source_file}")
            return mutants

        except Exception as e:
            logging.exception(f"Failed to generate mutants for {source_file}: {e}")
            return []

    def _create_mutant(
        self,
        source_file: str,
        original_node: ast.AST,
        mutated_node: ast.AST,
        mutator: CodeMutator,
    ) -> Mutant | None:
        """Create mutant from AST nodes."""
        try:
            # Get line and column information
            line_number = getattr(original_node, "lineno", 0)
            column_number = getattr(original_node, "col_offset", 0)

            # Generate code representations
            original_code = ast.unparse(original_node)
            mutated_code = ast.unparse(mutated_node)

            # Skip if codes are identical
            if original_code == mutated_code:
                return None

            # Determine mutation type
            mutation_type = MutationType.ARITHMETIC_OPERATOR  # Default
            if isinstance(mutator, ArithmeticOperatorMutator):
                mutation_type = MutationType.ARITHMETIC_OPERATOR
            elif isinstance(mutator, RelationalOperatorMutator):
                mutation_type = MutationType.RELATIONAL_OPERATOR
            elif isinstance(mutator, LogicalOperatorMutator):
                mutation_type = MutationType.LOGICAL_OPERATOR
            elif isinstance(mutator, ConstantReplacementMutator):
                mutation_type = MutationType.CONSTANT_REPLACEMENT
            elif isinstance(mutator, StatementDeletionMutator):
                mutation_type = MutationType.STATEMENT_DELETION

            mutant = Mutant(
                mutant_id=str(uuid.uuid4()),
                original_file=source_file,
                line_number=line_number,
                column_number=column_number,
                mutation_type=mutation_type,
                operator_name=mutator.__class__.__name__,
                original_code=original_code,
                mutated_code=mutated_code,
            )

            return mutant

        except Exception as e:
            logging.warning(f"Failed to create mutant: {e}")
            return None

    def apply_mutant(self, mutant: Mutant, target_dir: str) -> str:
        """Apply mutant to create mutated source file."""
        try:
            # Read original file
            with open(mutant.original_file) as f:
                f.readlines()

            # Parse and mutate the AST
            with open(mutant.original_file) as f:
                source_code = f.read()

            tree = ast.parse(source_code)

            # Find and replace the target node
            mutated_tree = self._apply_mutation_to_tree(tree, mutant)

            # Generate mutated source code
            mutated_source = ast.unparse(mutated_tree)

            # Write mutated file
            mutated_file_path = os.path.join(
                target_dir,
                f"mutant_{mutant.mutant_id}_{os.path.basename(mutant.original_file)}",
            )

            with open(mutated_file_path, "w") as f:
                f.write(mutated_source)

            return mutated_file_path

        except Exception as e:
            logging.exception(f"Failed to apply mutant {mutant.mutant_id}: {e}")
            raise

    def _apply_mutation_to_tree(self, tree: ast.AST, mutant: Mutant) -> ast.AST:
        """Apply mutation to AST tree."""
        # This is a simplified implementation
        # In practice, you'd need more sophisticated node matching

        class MutationApplier(ast.NodeTransformer):
            def __init__(self, target_line: int, target_col: int, mutated_code: str):
                self.target_line = target_line
                self.target_col = target_col
                self.mutated_code = mutated_code
                self.applied = False

            def visit(self, node):
                if (
                    not self.applied
                    and hasattr(node, "lineno")
                    and hasattr(node, "col_offset")
                    and node.lineno == self.target_line
                    and node.col_offset == self.target_col
                ):
                    # Parse the mutated code and return the new node
                    try:
                        mutated_node = ast.parse(self.mutated_code, mode="eval").body
                        self.applied = True
                        return mutated_node
                    except Exception:
                        logging.debug(
                            "Failed to parse mutated code for mutation %s",
                            mutant.mutant_id,
                            exc_info=True,
                        )

                return self.generic_visit(node)

        applier = MutationApplier(mutant.line_number, mutant.column_number, mutant.mutated_code)

        return applier.visit(tree)


class TestRunner:
    """Runs tests against mutated code."""

    def __init__(self, test_command: str = "python -m pytest"):
        """Initialize test runner."""
        self.test_command = test_command
        self.timeout = 300  # 5 minutes default timeout

    async def run_tests(
        self, test_directory: str, mutated_file: str = None
    ) -> builtins.tuple[bool, str, float]:
        """Run tests and return success, output, and execution time."""
        start_time = time.time()

        try:
            # Build test command
            cmd = self.test_command.split()
            if test_directory:
                cmd.append(test_directory)

            # Add coverage options if needed
            cmd.extend(["--tb=short", "-q"])

            # Run tests
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(mutated_file) if mutated_file else None,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)

                execution_time = time.time() - start_time
                output = stdout.decode() + stderr.decode()
                success = process.returncode == 0

                return success, output, execution_time

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                execution_time = time.time() - start_time
                return False, "Test execution timed out", execution_time

        except Exception as e:
            execution_time = time.time() - start_time
            return False, f"Test execution error: {e}", execution_time


class MutationTester:
    """Main mutation testing coordinator."""

    def __init__(
        self,
        source_directories: builtins.list[str],
        test_directories: builtins.list[str],
        test_command: str = "python -m pytest",
    ):
        """Initialize mutation tester."""
        self.source_directories = source_directories
        self.test_directories = test_directories

        self.mutation_engine = MutationEngine()
        self.test_runner = TestRunner(test_command)

        # Configuration
        self.parallel_execution = True
        self.max_workers = 4

        # Results storage
        self.results: builtins.dict[str, MutationTestResult] = {}

        # Coverage tracking
        self.coverage_data = {}

    async def run_mutation_testing(self, session_id: str = None) -> MutationTestResult:
        """Run complete mutation testing session."""
        if not session_id:
            session_id = str(uuid.uuid4())

        logging.info(f"Starting mutation testing session: {session_id}")
        start_time = time.time()

        # Initialize result
        result = MutationTestResult(session_id=session_id, target_files=[])

        try:
            # Collect source files
            source_files = self._collect_source_files()
            result.target_files = source_files

            # Run original tests to ensure they pass
            logging.info("Running original tests...")
            (
                original_test_success,
                original_output,
                _,
            ) = await self.test_runner.run_tests(
                self.test_directories[0] if self.test_directories else "."
            )

            if not original_test_success:
                raise Exception(f"Original tests failed: {original_output}")

            # Collect coverage information
            await self._collect_coverage_info(result)

            # Generate mutants
            logging.info("Generating mutants...")
            all_mutants = []
            for source_file in source_files:
                mutants = self.mutation_engine.generate_mutants(source_file)
                all_mutants.extend(mutants)

            result.total_mutants = len(all_mutants)
            logging.info(f"Generated {result.total_mutants} mutants")

            # Execute mutation testing
            if self.parallel_execution:
                await self._run_parallel_mutation_testing(all_mutants, result)
            else:
                await self._run_sequential_mutation_testing(all_mutants, result)

            # Calculate final metrics
            self._calculate_mutation_metrics(result)

            result.execution_time = time.time() - start_time
            result.completed_at = datetime.now(timezone.utc)

            # Store results
            self.results[session_id] = result

            logging.info(f"Mutation testing completed. Score: {result.mutation_score:.2%}")
            return result

        except Exception as e:
            logging.exception(f"Mutation testing failed: {e}")
            result.execution_time = time.time() - start_time
            result.completed_at = datetime.now(timezone.utc)
            return result

    def _collect_source_files(self) -> builtins.list[str]:
        """Collect Python source files from directories."""
        source_files = []

        for directory in self.source_directories:
            for root, _dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith(".py") and not file.startswith("test_"):
                        source_files.append(os.path.join(root, file))

        return source_files

    async def _collect_coverage_info(self, result: MutationTestResult):
        """Collect code coverage information."""
        try:
            # Run tests with coverage
            cov = coverage.Coverage()
            cov.start()

            # This is simplified - in practice you'd run tests with coverage
            test_success, _, _ = await self.test_runner.run_tests(
                self.test_directories[0] if self.test_directories else "."
            )

            cov.stop()
            cov.save()

            # Get coverage data
            result.original_coverage = {
                "line_coverage": cov.report(),
                "files": list(cov.get_data().measured_files()),
            }

        except Exception as e:
            logging.warning(f"Failed to collect coverage info: {e}")

    async def _run_parallel_mutation_testing(
        self, mutants: builtins.list[Mutant], result: MutationTestResult
    ):
        """Run mutation testing in parallel."""
        semaphore = asyncio.Semaphore(self.max_workers)

        async def test_mutant(mutant: Mutant):
            async with semaphore:
                await self._test_single_mutant(mutant, result)

        tasks = [test_mutant(mutant) for mutant in mutants]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_sequential_mutation_testing(
        self, mutants: builtins.list[Mutant], result: MutationTestResult
    ):
        """Run mutation testing sequentially."""
        for mutant in mutants:
            await self._test_single_mutant(mutant, result)

    async def _test_single_mutant(self, mutant: Mutant, result: MutationTestResult):
        """Test a single mutant."""
        try:
            # Create temporary directory for mutated code
            with tempfile.TemporaryDirectory() as temp_dir:
                # Apply mutation
                mutated_file = self.mutation_engine.apply_mutant(mutant, temp_dir)

                # Copy original file to temp location for testing
                temp_source_dir = os.path.join(temp_dir, "src")
                os.makedirs(temp_source_dir, exist_ok=True)

                # Copy source structure
                shutil.copy2(
                    mutant.original_file,
                    os.path.join(temp_source_dir, os.path.basename(mutant.original_file)),
                )

                # Replace with mutated version
                shutil.copy2(
                    mutated_file,
                    os.path.join(temp_source_dir, os.path.basename(mutant.original_file)),
                )

                # Run tests
                mutant.executed_at = datetime.now(timezone.utc)

                (
                    test_success,
                    test_output,
                    execution_time,
                ) = await self.test_runner.run_tests(
                    self.test_directories[0] if self.test_directories else ".",
                    temp_source_dir,
                )

                mutant.execution_time = execution_time

                # Determine mutant status
                if "timeout" in test_output.lower():
                    mutant.status = MutationStatus.TIMEOUT
                    result.timeout_mutants += 1
                elif not test_success:
                    mutant.status = MutationStatus.KILLED
                    result.killed_mutants += 1
                    # Parse test output to find killing test
                    mutant.killing_test = self._extract_failing_test(test_output)
                else:
                    mutant.status = MutationStatus.SURVIVED
                    result.survived_mutants += 1

                result.mutants.append(mutant)

        except Exception as e:
            mutant.status = MutationStatus.ERROR
            mutant.error_message = str(e)
            result.error_mutants += 1
            result.mutants.append(mutant)

            logging.warning(f"Error testing mutant {mutant.mutant_id}: {e}")

    def _extract_failing_test(self, test_output: str) -> str | None:
        """Extract the name of the failing test from output."""
        lines = test_output.split("\n")
        for line in lines:
            if "::" in line and "FAILED" in line:
                return line.split()[0]
        return None

    def _calculate_mutation_metrics(self, result: MutationTestResult):
        """Calculate mutation testing metrics."""
        if result.total_mutants > 0:
            # Basic mutation score
            result.mutation_score = result.killed_mutants / result.total_mutants

            # Test effectiveness analysis
            test_kills = defaultdict(int)
            for mutant in result.mutants:
                if mutant.killing_test:
                    test_kills[mutant.killing_test] += 1

            result.test_effectiveness = {
                "tests_that_kill_mutants": len(test_kills),
                "test_kill_distribution": dict(test_kills),
                "average_kills_per_test": sum(test_kills.values()) / len(test_kills)
                if test_kills
                else 0,
            }


class QualityGateEngine:
    """Engine for evaluating quality gates."""

    def __init__(self):
        """Initialize quality gate engine."""
        self.gates: builtins.dict[str, QualityGate] = {}

        # Default gates
        self._register_default_gates()

    def _register_default_gates(self):
        """Register default quality gates."""
        # Mutation score gate
        self.register_gate(
            QualityGate(
                gate_id="mutation_score",
                name="Mutation Score",
                gate_type=QualityGateType.MUTATION_SCORE,
                threshold_value=0.80,
                warning_threshold=0.70,
                description="Minimum mutation testing score",
            )
        )

        # Code coverage gate
        self.register_gate(
            QualityGate(
                gate_id="code_coverage",
                name="Code Coverage",
                gate_type=QualityGateType.CODE_COVERAGE,
                threshold_value=0.90,
                warning_threshold=0.80,
                description="Minimum code coverage percentage",
            )
        )

        # Test pass rate gate
        self.register_gate(
            QualityGate(
                gate_id="test_pass_rate",
                name="Test Pass Rate",
                gate_type=QualityGateType.TEST_PASS_RATE,
                threshold_value=1.00,
                warning_threshold=0.95,
                description="Minimum test pass rate",
            )
        )

    def register_gate(self, gate: QualityGate):
        """Register quality gate."""
        self.gates[gate.gate_id] = gate
        logging.info(f"Registered quality gate: {gate.name}")

    def evaluate_gates(self, metrics: builtins.dict[str, Any]) -> builtins.list[QualityGateResult]:
        """Evaluate all enabled quality gates."""
        results = []

        for gate in self.gates.values():
            if gate.enabled:
                result = self._evaluate_single_gate(gate, metrics)
                results.append(result)

        return results

    def _evaluate_single_gate(
        self, gate: QualityGate, metrics: builtins.dict[str, Any]
    ) -> QualityGateResult:
        """Evaluate single quality gate."""
        # Get actual value based on gate type
        actual_value = self._extract_metric_value(gate.gate_type, metrics)

        # Determine status
        if actual_value >= gate.threshold_value:
            status = QualityGateStatus.PASSED
            message = f"✅ {gate.name} passed ({actual_value:.2%} >= {gate.threshold_value:.2%})"
        elif gate.warning_threshold and actual_value >= gate.warning_threshold:
            status = QualityGateStatus.WARNING
            message = f"⚠️ {gate.name} warning ({actual_value:.2%} >= {gate.warning_threshold:.2%} but < {gate.threshold_value:.2%})"
        else:
            status = QualityGateStatus.FAILED
            message = f"❌ {gate.name} failed ({actual_value:.2%} < {gate.threshold_value:.2%})"

        return QualityGateResult(
            gate_id=gate.gate_id,
            status=status,
            actual_value=actual_value,
            threshold_value=gate.threshold_value,
            message=message,
            details={"gate_type": gate.gate_type.value, "blocking": gate.blocking},
        )

    def _extract_metric_value(
        self, gate_type: QualityGateType, metrics: builtins.dict[str, Any]
    ) -> float:
        """Extract metric value based on gate type."""
        if gate_type == QualityGateType.MUTATION_SCORE:
            return metrics.get("mutation_score", 0.0)
        if gate_type == QualityGateType.CODE_COVERAGE:
            return metrics.get("code_coverage", 0.0)
        if gate_type == QualityGateType.TEST_PASS_RATE:
            return metrics.get("test_pass_rate", 0.0)
        return 0.0

    def is_deployment_blocked(self, results: builtins.list[QualityGateResult]) -> bool:
        """Check if deployment should be blocked based on gate results."""
        for result in results:
            gate = self.gates[result.gate_id]
            if gate.blocking and result.status == QualityGateStatus.FAILED:
                return True
        return False


class QualityReporter:
    """Generates quality reports."""

    def __init__(self, output_directory: str = "./quality_reports"):
        """Initialize quality reporter."""
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)

    def generate_mutation_report(self, result: MutationTestResult) -> str:
        """Generate mutation testing report."""
        report_file = self.output_directory / f"mutation_report_{result.session_id}.html"

        # Generate HTML report
        html_content = self._generate_mutation_html_report(result)

        with open(report_file, "w") as f:
            f.write(html_content)

        # Also generate JSON report
        json_file = self.output_directory / f"mutation_report_{result.session_id}.json"
        self._generate_mutation_json_report(result, json_file)

        logging.info(f"Generated mutation testing report: {report_file}")
        return str(report_file)

    def generate_quality_gates_report(self, gate_results: builtins.list[QualityGateResult]) -> str:
        """Generate quality gates report."""
        report_file = (
            self.output_directory / f"quality_gates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )

        html_content = self._generate_quality_gates_html_report(gate_results)

        with open(report_file, "w") as f:
            f.write(html_content)

        logging.info(f"Generated quality gates report: {report_file}")
        return str(report_file)

    def _generate_mutation_html_report(self, result: MutationTestResult) -> str:
        """Generate HTML mutation testing report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Mutation Testing Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; }}
                .metrics {{ display: flex; gap: 20px; margin: 20px 0; }}
                .metric {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; flex: 1; }}
                .mutants {{ margin-top: 20px; }}
                .mutant {{ border: 1px solid #dee2e6; margin: 10px 0; padding: 15px; border-radius: 5px; }}
                .killed {{ background-color: #d4edda; }}
                .survived {{ background-color: #f8d7da; }}
                .error {{ background-color: #fff3cd; }}
                .timeout {{ background-color: #cce7ff; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Mutation Testing Report</h1>
                <p><strong>Session ID:</strong> {result.session_id}</p>
                <p><strong>Started:</strong> {result.started_at}</p>
                <p><strong>Completed:</strong> {result.completed_at}</p>
                <p><strong>Execution Time:</strong> {result.execution_time:.2f} seconds</p>
            </div>

            <div class="metrics">
                <div class="metric">
                    <h3>Mutation Score</h3>
                    <h2>{result.mutation_score:.2%}</h2>
                </div>
                <div class="metric">
                    <h3>Total Mutants</h3>
                    <h2>{result.total_mutants}</h2>
                </div>
                <div class="metric">
                    <h3>Killed</h3>
                    <h2>{result.killed_mutants}</h2>
                </div>
                <div class="metric">
                    <h3>Survived</h3>
                    <h2>{result.survived_mutants}</h2>
                </div>
            </div>

            <div class="mutants">
                <h2>Mutant Details</h2>
        """

        for mutant in result.mutants[:50]:  # Show first 50 mutants
            status_class = mutant.status.value
            html += f"""
                <div class="mutant {status_class}">
                    <strong>{mutant.operator_name}</strong> - {mutant.mutation_type.value}<br>
                    <strong>File:</strong> {mutant.original_file}:{mutant.line_number}<br>
                    <strong>Status:</strong> {mutant.status.value}<br>
                    <strong>Original:</strong> <code>{mutant.original_code}</code><br>
                    <strong>Mutated:</strong> <code>{mutant.mutated_code}</code><br>
                    {f"<strong>Killing Test:</strong> {mutant.killing_test}<br>" if mutant.killing_test else ""}
                </div>
            """

        html += """
            </div>
        </body>
        </html>
        """

        return html

    def _generate_mutation_json_report(self, result: MutationTestResult, output_file: Path):
        """Generate JSON mutation testing report."""
        report_data = {
            "session_id": result.session_id,
            "target_files": result.target_files,
            "total_mutants": result.total_mutants,
            "killed_mutants": result.killed_mutants,
            "survived_mutants": result.survived_mutants,
            "timeout_mutants": result.timeout_mutants,
            "error_mutants": result.error_mutants,
            "mutation_score": result.mutation_score,
            "execution_time": result.execution_time,
            "test_effectiveness": result.test_effectiveness,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "mutants": [
                {
                    "mutant_id": mutant.mutant_id,
                    "file": mutant.original_file,
                    "line": mutant.line_number,
                    "column": mutant.column_number,
                    "mutation_type": mutant.mutation_type.value,
                    "operator": mutant.operator_name,
                    "original_code": mutant.original_code,
                    "mutated_code": mutant.mutated_code,
                    "status": mutant.status.value,
                    "killing_test": mutant.killing_test,
                    "execution_time": mutant.execution_time,
                    "error_message": mutant.error_message,
                }
                for mutant in result.mutants
            ],
        }

        with open(output_file, "w") as f:
            json.dump(report_data, f, indent=2)

    def _generate_quality_gates_html_report(
        self, gate_results: builtins.list[QualityGateResult]
    ) -> str:
        """Generate HTML quality gates report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Quality Gates Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; }}
                .gate {{ border: 1px solid #dee2e6; margin: 10px 0; padding: 15px; border-radius: 5px; }}
                .passed {{ background-color: #d4edda; }}
                .failed {{ background-color: #f8d7da; }}
                .warning {{ background-color: #fff3cd; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Quality Gates Report</h1>
                <p><strong>Generated:</strong> {datetime.now()}</p>
                <p><strong>Total Gates:</strong> {len(gate_results)}</p>
            </div>
        """

        for result in gate_results:
            status_class = result.status.value
            html += f"""
                <div class="gate {status_class}">
                    <h3>{result.gate_id}</h3>
                    <p>{result.message}</p>
                    <p><strong>Actual Value:</strong> {result.actual_value:.2%}</p>
                    <p><strong>Threshold:</strong> {result.threshold_value:.2%}</p>
                </div>
            """

        html += """
        </body>
        </html>
        """

        return html


def create_mutation_testing_platform(
    source_directories: builtins.list[str],
    test_directories: builtins.list[str],
    test_command: str = "python -m pytest",
) -> builtins.dict[str, Any]:
    """Create mutation testing platform."""
    mutation_tester = MutationTester(source_directories, test_directories, test_command)
    quality_gate_engine = QualityGateEngine()
    reporter = QualityReporter()

    return {
        "mutation_tester": mutation_tester,
        "quality_gate_engine": quality_gate_engine,
        "reporter": reporter,
    }
