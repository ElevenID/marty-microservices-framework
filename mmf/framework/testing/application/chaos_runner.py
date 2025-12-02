import asyncio
import logging
import os
import subprocess
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from typing import Any

import psutil

from mmf.framework.testing.domain.chaos import (
    ChaosExperiment,
    ChaosParameters,
    ChaosTarget,
    ChaosType,
)
from mmf.framework.testing.domain.entities import (
    TestMetrics,
    TestResult,
    TestSeverity,
    TestStatus,
    TestType,
)

logger = logging.getLogger(__name__)


class ChaosAction(ABC):
    """Abstract base class for chaos actions."""

    def __init__(self, chaos_type: ChaosType):
        self.chaos_type = chaos_type
        self.active = False
        self.cleanup_callbacks: list[Callable] = []

    @abstractmethod
    async def inject(self, targets: list[ChaosTarget], parameters: ChaosParameters) -> bool:
        """Inject chaos into targets."""

    @abstractmethod
    async def recover(self) -> bool:
        """Recover from chaos injection."""

    async def cleanup(self):
        """Clean up chaos action."""
        for callback in reversed(self.cleanup_callbacks):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.warning(f"Cleanup callback failed: {e}")

        self.cleanup_callbacks.clear()
        self.active = False

    async def _execute_command(self, command: str):
        """Execute system command."""
        process = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise Exception(f"Command failed: {command}, Error: {stderr.decode()}")


class NetworkDelayAction(ChaosAction):
    """Injects network delay."""

    def __init__(self):
        super().__init__(ChaosType.NETWORK_DELAY)
        self.original_rules: list[str] = []

    async def inject(self, targets: list[ChaosTarget], parameters: ChaosParameters) -> bool:
        """Inject network delay using tc (traffic control)."""
        try:
            delay_ms = int(parameters.custom_params.get("delay_ms", 100))
            variance_ms = int(parameters.custom_params.get("variance_ms", 10))

            for target in targets:
                if target.host and target.port:
                    # Add delay rule using tc
                    rule = "tc qdisc add dev eth0 root handle 1: prio"
                    await self._execute_command(rule)

                    rule = f"tc qdisc add dev eth0 parent 1:1 handle 10: netem delay {delay_ms}ms {variance_ms}ms"
                    await self._execute_command(rule)

                    rule = f"tc filter add dev eth0 protocol ip parent 1:0 prio 1 u32 match ip dport {target.port} 0xffff flowid 1:1"
                    await self._execute_command(rule)

                    self.original_rules.append(f"eth0:{target.port}")

                    logger.info(
                        f"Injected network delay of {delay_ms}ms for {target.service_name}:{target.port}"
                    )

            self.active = True
            return True

        except Exception as e:
            logger.error(f"Failed to inject network delay: {e}")
            return False

    async def recover(self) -> bool:
        """Remove network delay rules."""
        try:
            for _rule_id in self.original_rules:
                # Remove tc rules
                await self._execute_command("tc qdisc del dev eth0 root")

            self.original_rules.clear()
            self.active = False
            logger.info("Recovered from network delay injection")
            return True

        except Exception as e:
            logger.error(f"Failed to recover from network delay: {e}")
            return False


class ServiceKillAction(ChaosAction):
    """Kills service processes."""

    def __init__(self):
        super().__init__(ChaosType.SERVICE_KILL)
        self.killed_processes: list[int] = []

    async def inject(self, targets: list[ChaosTarget], parameters: ChaosParameters) -> bool:
        """Kill target service processes."""
        try:
            kill_signal = parameters.custom_params.get("signal", "SIGTERM")

            for target in targets:
                processes = self._find_processes(target.service_name)

                for proc in processes:
                    try:
                        if kill_signal == "SIGKILL":
                            proc.kill()
                        else:
                            proc.terminate()

                        self.killed_processes.append(proc.pid)
                        logger.info(f"Killed process {proc.pid} for service {target.service_name}")

                    except psutil.NoSuchProcess:
                        logger.warning(f"Process {proc.pid} already terminated")

            self.active = True
            return True

        except Exception as e:
            logger.error(f"Failed to kill service processes: {e}")
            return False

    async def recover(self) -> bool:
        """Recovery is typically handled by orchestrator (K8s, Docker, etc.)."""
        # In real scenarios, the orchestrator should restart killed services
        self.killed_processes.clear()
        self.active = False
        logger.info("Service kill recovery completed (orchestrator should restart services)")
        return True

    def _find_processes(self, service_name: str) -> list[psutil.Process]:
        """Find processes by service name."""
        processes = []

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if service_name.lower() in proc.info["name"].lower() or any(
                    service_name.lower() in arg.lower() for arg in proc.info["cmdline"] or []
                ):
                    processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return processes


class ResourceExhaustionAction(ChaosAction):
    """Exhausts system resources."""

    def __init__(self):
        super().__init__(ChaosType.RESOURCE_EXHAUSTION)
        self.stress_processes: list[subprocess.Popen] = []
        self.stress_threads: list[threading.Thread] = []
        self.stop_stress = False

    async def inject(self, targets: list[ChaosTarget], parameters: ChaosParameters) -> bool:
        """Inject resource exhaustion."""
        try:
            resource_type = parameters.custom_params.get("resource_type", "cpu")
            intensity = parameters.intensity

            if resource_type == "cpu":
                await self._stress_cpu(intensity)
            elif resource_type == "memory":
                await self._stress_memory(intensity)
            elif resource_type == "io":
                await self._stress_io(intensity)

            self.active = True
            return True

        except Exception as e:
            logger.error(f"Failed to inject resource exhaustion: {e}")
            return False

    async def recover(self) -> bool:
        """Stop resource exhaustion."""
        try:
            self.stop_stress = True

            # Stop stress processes
            for process in self.stress_processes:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

            # Wait for stress threads to finish
            for thread in self.stress_threads:
                thread.join(timeout=5)

            self.stress_processes.clear()
            self.stress_threads.clear()
            self.stop_stress = False
            self.active = False

            logger.info("Recovered from resource exhaustion")
            return True

        except Exception as e:
            logger.error(f"Failed to recover from resource exhaustion: {e}")
            return False

    async def _stress_cpu(self, intensity: float):
        """Stress CPU resources."""
        cpu_count = psutil.cpu_count()
        threads_to_create = max(1, int(cpu_count * intensity))

        def cpu_stress():
            end_time = time.time() + 1  # Run for 1 second bursts
            while not self.stop_stress and time.time() < end_time:
                pass  # Busy loop

        for _ in range(threads_to_create):
            thread = threading.Thread(target=cpu_stress)
            thread.start()
            self.stress_threads.append(thread)

        logger.info(f"Started CPU stress with {threads_to_create} threads")

    async def _stress_memory(self, intensity: float):
        """Stress memory resources."""
        available_memory = psutil.virtual_memory().available
        memory_to_allocate = int(available_memory * intensity * 0.8)  # 80% to avoid system crash

        def memory_stress():
            try:
                # Allocate memory in chunks
                chunk_size = 1024 * 1024 * 10  # 10MB chunks
                chunks = []
                allocated = 0

                while not self.stop_stress and allocated < memory_to_allocate:
                    chunk = bytearray(min(chunk_size, memory_to_allocate - allocated))
                    chunks.append(chunk)
                    allocated += len(chunk)
                    time.sleep(0.01)  # Small delay to avoid overwhelming

                # Hold memory while stress is active
                while not self.stop_stress:
                    time.sleep(0.1)

            except MemoryError:
                logger.warning("Memory stress reached system limits")

        thread = threading.Thread(target=memory_stress)
        thread.start()
        self.stress_threads.append(thread)

        logger.info(f"Started memory stress allocating {memory_to_allocate / (1024 * 1024):.1f}MB")

    async def _stress_io(self, intensity: float):
        """Stress I/O resources."""

        def io_stress():
            with tempfile.NamedTemporaryFile(delete=False) as f:
                temp_file = f.name

            try:
                # Write/read operations based on intensity
                operations_per_second = int(100 * intensity)

                while not self.stop_stress:
                    for _ in range(operations_per_second):
                        if self.stop_stress:
                            break

                        # Write operation
                        with open(temp_file, "w") as f:
                            f.write("x" * 1024)  # 1KB write

                        # Read operation
                        with open(temp_file) as f:
                            f.read()

                    time.sleep(1)  # Wait 1 second between bursts

            finally:
                try:
                    os.unlink(temp_file)
                except OSError as cleanup_error:
                    logger.debug(
                        "Failed to clean up temporary file %s: %s",
                        temp_file,
                        cleanup_error,
                        exc_info=True,
                    )

        thread = threading.Thread(target=io_stress)
        thread.start()
        self.stress_threads.append(thread)

        logger.info("Started I/O stress")


class ChaosActionFactory:
    """Factory for creating chaos actions."""

    _actions = {
        ChaosType.NETWORK_DELAY: NetworkDelayAction,
        ChaosType.SERVICE_KILL: ServiceKillAction,
        ChaosType.RESOURCE_EXHAUSTION: ResourceExhaustionAction,
    }

    @classmethod
    def create_action(cls, chaos_type: ChaosType) -> ChaosAction:
        """Create chaos action by type."""
        action_class = cls._actions.get(chaos_type)
        if not action_class:
            raise ValueError(f"Unsupported chaos type: {chaos_type}")

        return action_class()


class SteadyStateProbe:
    """Probe for checking system steady state."""

    def __init__(self, name: str, probe_func: Callable, tolerance: dict[str, Any]):
        self.name = name
        self.probe_func = probe_func
        self.tolerance = tolerance

    async def check(self) -> tuple[bool, Any]:
        """Check probe and return success status and value."""
        try:
            if asyncio.iscoroutinefunction(self.probe_func):
                value = await self.probe_func()
            else:
                value = self.probe_func()

            # Check against tolerance
            is_valid = self._validate_tolerance(value)
            return is_valid, value

        except Exception as e:
            logger.error(f"Probe {self.name} failed: {e}")
            return False, None

    def _validate_tolerance(self, value: Any) -> bool:
        """Validate value against tolerance."""
        if "min" in self.tolerance:
            if value < self.tolerance["min"]:
                return False

        if "max" in self.tolerance:
            if value > self.tolerance["max"]:
                return False

        if "equals" in self.tolerance:
            if value != self.tolerance["equals"]:
                return False

        if "range" in self.tolerance:
            min_val, max_val = self.tolerance["range"]
            if not (min_val <= value <= max_val):
                return False

        return True


class ChaosRunner:
    """Executes chaos experiments."""

    def __init__(self, experiment: ChaosExperiment):
        self.experiment = experiment
        self.action: ChaosAction | None = None
        self.steady_state_probes: list[SteadyStateProbe] = []

        # Setup steady state probes
        for probe_func in experiment.steady_state_hypothesis.probes:
            probe = SteadyStateProbe(
                name=f"{experiment.title}_probe",
                probe_func=probe_func,
                tolerance=experiment.steady_state_hypothesis.tolerance,
            )
            self.steady_state_probes.append(probe)

    async def run(self) -> TestResult:
        """Execute chaos experiment."""
        start_time = datetime.utcnow()
        experiment_log = []
        test_id = f"chaos-{int(time.time())}"

        try:
            # Phase 1: Verify steady state before experiment
            experiment_log.append("Phase 1: Checking steady state before experiment")
            steady_state_before = await self._check_steady_state()

            if not steady_state_before:
                raise Exception("System not in steady state before experiment")

            experiment_log.append("✓ System in steady state")

            # Phase 2: Inject chaos
            experiment_log.append("Phase 2: Injecting chaos")
            self.action = ChaosActionFactory.create_action(self.experiment.chaos_type)

            # Wait before injection if specified
            if self.experiment.parameters.delay_before > 0:
                await asyncio.sleep(self.experiment.parameters.delay_before)

            injection_success = await self.action.inject(
                self.experiment.targets, self.experiment.parameters
            )

            if not injection_success:
                raise Exception("Failed to inject chaos")

            experiment_log.append(f"✓ Chaos injected: {self.experiment.chaos_type.value}")

            # Phase 3: Monitor during chaos
            experiment_log.append("Phase 3: Monitoring during chaos injection")

            # Run chaos for specified duration
            monitoring_interval = 5  # Check every 5 seconds
            monitoring_duration = self.experiment.parameters.duration
            monitoring_cycles = max(1, monitoring_duration // monitoring_interval)

            steady_state_violations = 0

            for cycle in range(monitoring_cycles):
                await asyncio.sleep(monitoring_interval)

                steady_state_during = await self._check_steady_state()
                if not steady_state_during:
                    steady_state_violations += 1
                    experiment_log.append(f"! Steady state violation at cycle {cycle + 1}")

            # Phase 4: Recover from chaos
            experiment_log.append("Phase 4: Recovering from chaos")

            recovery_success = await self.action.recover()
            if not recovery_success:
                experiment_log.append("! Recovery failed, manual intervention may be required")
            else:
                experiment_log.append("✓ Recovery completed")

            # Wait after recovery if specified
            if self.experiment.parameters.delay_after > 0:
                await asyncio.sleep(self.experiment.parameters.delay_after)

            # Phase 5: Verify steady state after experiment
            experiment_log.append("Phase 5: Checking steady state after experiment")

            # Give system time to stabilize
            await asyncio.sleep(10)

            steady_state_after = await self._check_steady_state()

            if steady_state_after:
                experiment_log.append("✓ System returned to steady state")
            else:
                experiment_log.append("! System did not return to steady state")

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            # Determine experiment result
            if steady_state_before and steady_state_after:
                if steady_state_violations == 0:
                    status = TestStatus.PASSED
                    severity = TestSeverity.LOW
                    message = "Chaos experiment passed: system maintained resilience"
                else:
                    status = TestStatus.PASSED
                    severity = TestSeverity.MEDIUM
                    message = f"Chaos experiment passed with {steady_state_violations} steady state violations"
            else:
                status = TestStatus.FAILED
                severity = TestSeverity.HIGH
                message = "Chaos experiment failed: system did not recover properly"

            return TestResult(
                test_id=test_id,
                name=f"Chaos Test: {self.experiment.title}",
                test_type=TestType.CHAOS,
                status=status,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                error_message=message if status == TestStatus.FAILED else None,
                severity=severity,
                metrics=TestMetrics(
                    execution_time=execution_time,
                    custom_metrics={
                        "chaos_type": self.experiment.chaos_type.value,
                        "chaos_duration": self.experiment.parameters.duration,
                        "steady_state_violations": steady_state_violations,
                        "monitoring_cycles": monitoring_cycles,
                        "recovery_success": recovery_success,
                    },
                ),
                artifacts={"experiment_log": experiment_log},
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            experiment_log.append(f"✗ Experiment failed: {e!s}")

            return TestResult(
                test_id=test_id,
                name=f"Chaos Test: {self.experiment.title}",
                test_type=TestType.CHAOS,
                status=TestStatus.ERROR,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                error_message=str(e),
                severity=TestSeverity.CRITICAL,
                artifacts={"experiment_log": experiment_log},
            )

        finally:
            # Ensure cleanup
            if self.action:
                await self.action.cleanup()

    async def _check_steady_state(self) -> bool:
        """Check all steady state probes."""
        if not self.steady_state_probes:
            return True  # No probes means steady state by default

        results = []

        for probe in self.steady_state_probes:
            is_valid, value = await probe.check()
            results.append(is_valid)

            if not is_valid:
                logger.warning(f"Steady state probe failed: {probe.name}, value: {value}")

        return all(results)
