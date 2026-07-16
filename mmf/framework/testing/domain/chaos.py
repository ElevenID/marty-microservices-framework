import builtins
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChaosType(Enum):
    """Types of chaos experiments."""

    NETWORK_DELAY = "network_delay"
    NETWORK_LOSS = "network_loss"
    NETWORK_PARTITION = "network_partition"
    SERVICE_KILL = "service_kill"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DISK_FAILURE = "disk_failure"
    CPU_STRESS = "cpu_stress"
    MEMORY_STRESS = "memory_stress"
    IO_STRESS = "io_stress"
    DNS_FAILURE = "dns_failure"
    TIME_DRIFT = "time_drift"
    DEPENDENCY_FAILURE = "dependency_failure"


class ChaosScope(Enum):
    """Scope of chaos experiments."""

    SINGLE_INSTANCE = "single_instance"
    MULTIPLE_INSTANCES = "multiple_instances"
    ENTIRE_SERVICE = "entire_service"
    RANDOM_SELECTION = "random_selection"
    PERCENTAGE_BASED = "percentage_based"


class ExperimentPhase(Enum):
    """Phases of chaos experiment."""

    STEADY_STATE = "steady_state"
    INJECTION = "injection"
    RECOVERY = "recovery"
    VERIFICATION = "verification"


@dataclass
class ChaosTarget:
    """Target for chaos experiment."""

    service_name: str
    instance_id: str | None = None
    host: str | None = None
    port: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChaosParameters:
    """Parameters for chaos experiment."""

    duration: int  # seconds
    intensity: float = 1.0  # 0.0 to 1.0
    delay_before: int = 0  # seconds
    delay_after: int = 0  # seconds
    custom_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SteadyStateHypothesis:
    """Hypothesis about system steady state."""

    title: str
    description: str
    probes: list[Callable] = field(default_factory=list)
    tolerance: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChaosExperiment:
    """Chaos engineering experiment definition."""

    title: str
    description: str
    chaos_type: ChaosType
    targets: list[ChaosTarget]
    parameters: ChaosParameters
    steady_state_hypothesis: SteadyStateHypothesis
    scope: ChaosScope = ChaosScope.SINGLE_INSTANCE
    rollback_strategy: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
