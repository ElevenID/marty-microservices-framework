"""
Chaos engineering implementation for testing system resilience.

This module provides tools for introducing controlled failures and disruptions
to test the resilience and fault tolerance of distributed systems.
"""

import asyncio
import logging
import os
import random
import signal
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class ChaosType(Enum):
    """Types of chaos experiments."""

    LATENCY = "latency"
    EXCEPTION = "exception"
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_PARTITION = "network_partition"
    SERVICE_UNAVAILABLE = "service_unavailable"
    MEMORY_PRESSURE = "memory_pressure"
    CPU_STRESS = "cpu_stress"


class ExperimentStatus(Enum):
    """Status of chaos experiments."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class ChaosConfig:
    """Configuration for chaos experiments."""

    name: str
    chaos_type: ChaosType
    probability: float = 0.1  # Probability of chaos activation (0.0 to 1.0)
    enabled: bool = True
    min_delay: float = 0.1
    max_delay: float = 2.0
    exception_message: str = "Chaos engineering exception"
    exception_type: type = Exception
    resource_limit: int = 1000
    duration_seconds: float = 60.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """Result of a chaos experiment."""

    experiment_id: str
    name: str
    chaos_type: ChaosType
    status: ExperimentStatus
    start_time: float
    end_time: float | None = None
    error_count: int = 0
    success_count: int = 0
    total_operations: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Get experiment duration."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def error_rate(self) -> float:
        """Get error rate as percentage."""
        if self.total_operations == 0:
            return 0.0
        return (self.error_count / self.total_operations) * 100


class LatencyChaos:
    """Chaos for introducing artificial latency."""

    def __init__(self, config: ChaosConfig):
        self.config = config
        self._active = False

    async def inject_async(self, coro: Awaitable[T]) -> T:
        """Inject latency into async operations."""
        if self._should_activate():
            delay = random.uniform(self.config.min_delay, self.config.max_delay)
            logger.debug(f"Injecting {delay:.2f}s latency in {self.config.name}")
            await asyncio.sleep(delay)

        return await coro

    def inject_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Inject latency into sync operations."""
        if self._should_activate():
            delay = random.uniform(self.config.min_delay, self.config.max_delay)
            logger.debug(f"Injecting {delay:.2f}s latency in {self.config.name}")
            time.sleep(delay)

        return func(*args, **kwargs)

    def _should_activate(self) -> bool:
        """Check if chaos should be activated."""
        return self.config.enabled and random.random() < self.config.probability


class ExceptionChaos:
    """Chaos for introducing exceptions."""

    def __init__(self, config: ChaosConfig):
        self.config = config

    async def inject_async(self, coro: Awaitable[T]) -> T:
        """Inject exceptions into async operations."""
        if self._should_activate():
            logger.debug(f"Injecting exception in {self.config.name}")
            raise self.config.exception_type(self.config.exception_message)

        return await coro

    def inject_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Inject exceptions into sync operations."""
        if self._should_activate():
            logger.debug(f"Injecting exception in {self.config.name}")
            raise self.config.exception_type(self.config.exception_message)

        return func(*args, **kwargs)

    def _should_activate(self) -> bool:
        """Check if chaos should be activated."""
        return self.config.enabled and random.random() < self.config.probability


class ResourceExhaustionChaos:
    """Chaos for simulating resource exhaustion."""

    def __init__(self, config: ChaosConfig):
        self.config = config
        self._allocated_memory = []
        self._cpu_stress_active = False

    async def inject_async(self, coro: Awaitable[T]) -> T:
        """Inject resource exhaustion into async operations."""
        if self._should_activate():
            self.exhaust_memory(50)  # Allocate 50MB
        return await coro

    def inject_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Inject resource exhaustion into sync operations."""
        if self._should_activate():
            self.stress_cpu(0.1)  # Stress CPU for 100ms
        return func(*args, **kwargs)

    def exhaust_memory(self, size_mb: int = 100) -> None:
        """Allocate memory to simulate memory pressure."""
        if self._should_activate():
            logger.debug(f"Allocating {size_mb}MB memory in {self.config.name}")
            # Allocate memory blocks
            block = bytearray(size_mb * 1024 * 1024)
            self._allocated_memory.append(block)

    def stress_cpu(self, duration: float = 1.0) -> None:
        """Create CPU stress."""
        if self._should_activate():
            logger.debug(f"Starting CPU stress for {duration}s in {self.config.name}")
            end_time = time.time() + duration
            while time.time() < end_time:
                # Busy loop to consume CPU
                _ = sum(i * i for i in range(1000))

    def release_memory(self) -> None:
        """Release allocated memory."""
        self._allocated_memory.clear()
        logger.debug(f"Released memory in {self.config.name}")

    def _should_activate(self) -> bool:
        """Check if chaos should be activated."""
        return self.config.enabled and random.random() < self.config.probability


class NetworkPartitionChaos:
    """Chaos for simulating network partitions."""

    def __init__(self, config: ChaosConfig):
        self.config = config
        self._blocked_hosts = set()

    async def inject_async(self, coro: Awaitable[T]) -> T:
        """Inject network partition into async operations."""
        # Network partition chaos is typically handled at connection level
        return await coro

    def inject_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Inject network partition into sync operations."""
        # Network partition chaos is typically handled at connection level
        return func(*args, **kwargs)

    def block_host(self, host: str) -> None:
        """Block connections to a specific host."""
        if self._should_activate():
            logger.debug(f"Blocking host {host} in {self.config.name}")
            self._blocked_hosts.add(host)

    def unblock_host(self, host: str) -> None:
        """Unblock connections to a host."""
        self._blocked_hosts.discard(host)
        logger.debug(f"Unblocked host {host} in {self.config.name}")

    def is_host_blocked(self, host: str) -> bool:
        """Check if a host is blocked."""
        return host in self._blocked_hosts

    def clear_blocks(self) -> None:
        """Clear all host blocks."""
        self._blocked_hosts.clear()
        logger.debug(f"Cleared all blocks in {self.config.name}")

    def _should_activate(self) -> bool:
        """Check if chaos should be activated."""
        return self.config.enabled and random.random() < self.config.probability


class ChaosExperiment:
    """Manages a complete chaos engineering experiment."""

    def __init__(self, config: ChaosConfig):
        self.config = config
        self.result = ExperimentResult(
            experiment_id=f"{config.name}_{int(time.time())}",
            name=config.name,
            chaos_type=config.chaos_type,
            status=ExperimentStatus.CREATED,
            start_time=time.time(),
        )
        self._chaos_injector = self._create_chaos_injector()
        self._running = False

    def _create_chaos_injector(self):
        """Create the appropriate chaos injector."""
        if self.config.chaos_type == ChaosType.LATENCY:
            return LatencyChaos(self.config)
        elif self.config.chaos_type == ChaosType.EXCEPTION:
            return ExceptionChaos(self.config)
        elif self.config.chaos_type == ChaosType.RESOURCE_EXHAUSTION:
            return ResourceExhaustionChaos(self.config)
        elif self.config.chaos_type == ChaosType.NETWORK_PARTITION:
            return NetworkPartitionChaos(self.config)
        else:
            raise ValueError(f"Unsupported chaos type: {self.config.chaos_type}")

    def start(self) -> None:
        """Start the chaos experiment."""
        self._running = True
        self.result.status = ExperimentStatus.RUNNING
        self.result.start_time = time.time()
        logger.info(f"Started chaos experiment: {self.config.name}")

    def stop(self) -> None:
        """Stop the chaos experiment."""
        self._running = False
        self.result.status = ExperimentStatus.COMPLETED
        self.result.end_time = time.time()
        logger.info(f"Stopped chaos experiment: {self.config.name}")

        # Cleanup resources based on chaos type
        if self.config.chaos_type == ChaosType.RESOURCE_EXHAUSTION:
            self._chaos_injector.release_memory()
        elif self.config.chaos_type == ChaosType.NETWORK_PARTITION:
            self._chaos_injector.clear_blocks()

    def abort(self) -> None:
        """Abort the chaos experiment."""
        self._running = False
        self.result.status = ExperimentStatus.ABORTED
        self.result.end_time = time.time()
        logger.warning(f"Aborted chaos experiment: {self.config.name}")

    def record_operation(self, success: bool) -> None:
        """Record the result of an operation."""
        self.result.total_operations += 1
        if success:
            self.result.success_count += 1
        else:
            self.result.error_count += 1

    async def inject_async(self, coro: Awaitable[T]) -> T:
        """Inject chaos into async operations."""
        if not self._running:
            return await coro

        try:
            result = await self._chaos_injector.inject_async(coro)
            self.record_operation(True)
            return result
        except Exception:
            self.record_operation(False)
            raise

    def inject_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Inject chaos into sync operations."""
        if not self._running:
            return func(*args, **kwargs)

        try:
            result = self._chaos_injector.inject_sync(func, *args, **kwargs)
            self.record_operation(True)
            return result
        except Exception:
            self.record_operation(False)
            raise


class ChaosMonkey:
    """Central manager for chaos engineering experiments."""

    def __init__(self):
        self._experiments: dict[str, ChaosExperiment] = {}
        self._lock = threading.Lock()

    def register_experiment(self, config: ChaosConfig) -> str:
        """Register a new chaos experiment."""
        with self._lock:
            experiment = ChaosExperiment(config)
            self._experiments[config.name] = experiment
            return experiment.result.experiment_id

    def start_experiment(self, name: str) -> bool:
        """Start a chaos experiment by name."""
        with self._lock:
            experiment = self._experiments.get(name)
            if experiment:
                experiment.start()
                return True
            return False

    def stop_experiment(self, name: str) -> bool:
        """Stop a chaos experiment by name."""
        with self._lock:
            experiment = self._experiments.get(name)
            if experiment:
                experiment.stop()
                return True
            return False

    def abort_experiment(self, name: str) -> bool:
        """Abort a chaos experiment by name."""
        with self._lock:
            experiment = self._experiments.get(name)
            if experiment:
                experiment.abort()
                return True
            return False

    def get_experiment(self, name: str) -> ChaosExperiment | None:
        """Get a chaos experiment by name."""
        with self._lock:
            return self._experiments.get(name)

    def get_all_results(self) -> dict[str, ExperimentResult]:
        """Get results for all experiments."""
        with self._lock:
            return {name: experiment.result for name, experiment in self._experiments.items()}

    def cleanup_completed(self) -> None:
        """Remove completed experiments."""
        with self._lock:
            completed = [
                name
                for name, exp in self._experiments.items()
                if exp.result.status in [ExperimentStatus.COMPLETED, ExperimentStatus.ABORTED]
            ]
            for name in completed:
                del self._experiments[name]

    def emergency_stop_all(self) -> None:
        """Emergency stop all running experiments."""
        with self._lock:
            for experiment in self._experiments.values():
                if experiment.result.status == ExperimentStatus.RUNNING:
                    experiment.abort()
            logger.warning("Emergency stopped all chaos experiments")


# Decorators for chaos injection
def with_chaos(chaos_config: ChaosConfig):
    """Decorator for injecting chaos into functions."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            experiment = ChaosExperiment(chaos_config)
            if chaos_config.enabled:
                experiment.start()
                try:
                    return experiment.inject_sync(func, *args, **kwargs)
                finally:
                    experiment.stop()
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


def with_async_chaos(chaos_config: ChaosConfig):
    """Decorator for injecting chaos into async functions."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args, **kwargs) -> T:
            experiment = ChaosExperiment(chaos_config)
            if chaos_config.enabled:
                experiment.start()
                try:
                    return await experiment.inject_async(func(*args, **kwargs))
                finally:
                    experiment.stop()
            else:
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# Global chaos monkey instance
default_chaos_monkey = ChaosMonkey()


def create_latency_chaos(name: str, probability: float = 0.1, max_delay: float = 2.0) -> str:
    """Create and register a latency chaos experiment."""
    config = ChaosConfig(
        name=name, chaos_type=ChaosType.LATENCY, probability=probability, max_delay=max_delay
    )
    return default_chaos_monkey.register_experiment(config)


def create_exception_chaos(
    name: str, probability: float = 0.1, exception_type: type = Exception
) -> str:
    """Create and register an exception chaos experiment."""
    config = ChaosConfig(
        name=name,
        chaos_type=ChaosType.EXCEPTION,
        probability=probability,
        exception_type=exception_type,
    )
    return default_chaos_monkey.register_experiment(config)


# Utility functions for enabling/disabling chaos based on environment
def is_chaos_enabled() -> bool:
    """Check if chaos engineering is enabled via environment variable."""
    return os.getenv("CHAOS_ENABLED", "false").lower() in ["true", "1", "yes"]


def setup_emergency_stop() -> None:
    """Setup emergency stop signal handler."""

    def emergency_handler(signum, frame):
        logger.critical("Emergency stop signal received - stopping all chaos experiments")
        default_chaos_monkey.emergency_stop_all()

    signal.signal(signal.SIGUSR1, emergency_handler)
