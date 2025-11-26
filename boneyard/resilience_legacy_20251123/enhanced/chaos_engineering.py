"""
Chaos engineering and fault injection capabilities for resilience testing.

Ported from Marty's resilience framework to provide chaos testing
capabilities for microservices.
"""

import asyncio
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ChaosType(str, Enum):
    """Types of chaos that can be injected."""

    NETWORK_DELAY = "network_delay"
    NETWORK_FAILURE = "network_failure"
    SERVICE_UNAVAILABLE = "service_unavailable"
    HIGH_LATENCY = "high_latency"
    MEMORY_PRESSURE = "memory_pressure"
    CPU_SPIKE = "cpu_spike"
    DISK_FULL = "disk_full"
    RANDOM_ERRORS = "random_errors"
    INTERMITTENT_FAILURES = "intermittent_failures"


@dataclass
class ChaosConfig:
    """Configuration for chaos injection."""

    chaos_type: ChaosType
    probability: float = 0.3  # 30% chance by default
    duration_seconds: float = 10.0
    intensity: float = 1.0  # Scale from 0.0 to 1.0
    target_services: list[str] = field(default_factory=list)
    enabled: bool = True


class ChaosInjector:
    """Inject various types of chaos into the system."""

    def __init__(self) -> None:
        self.active_chaos: dict[str, ChaosConfig] = {}
        self.injection_history: list[dict[str, Any]] = []

    async def inject_chaos(self, config: ChaosConfig, target: str = "default") -> None:
        """Inject specified chaos into the system."""
        if not config.enabled:
            return

        if random.random() > config.probability:
            return

        self.active_chaos[target] = config
        start_time = time.time()

        self.injection_history.append(
            {
                "target": target,
                "chaos_type": config.chaos_type.value,
                "start_time": start_time,
                "duration": config.duration_seconds,
                "intensity": config.intensity,
            }
        )

        try:
            if config.chaos_type == ChaosType.NETWORK_DELAY:
                await self._inject_network_delay(config)
            elif config.chaos_type == ChaosType.NETWORK_FAILURE:
                await self._inject_network_failure(config)
            elif config.chaos_type == ChaosType.SERVICE_UNAVAILABLE:
                await self._inject_service_unavailable(config)
            elif config.chaos_type == ChaosType.HIGH_LATENCY:
                await self._inject_high_latency(config)
            elif config.chaos_type == ChaosType.RANDOM_ERRORS:
                await self._inject_random_errors(config)
            elif config.chaos_type == ChaosType.INTERMITTENT_FAILURES:
                await self._inject_intermittent_failures(config)
        finally:
            if target in self.active_chaos:
                del self.active_chaos[target]

    async def _inject_network_delay(self, config: ChaosConfig) -> None:
        """Inject network delay."""
        delay = config.intensity * 5.0  # Up to 5 seconds delay
        logger.warning("Injecting network delay of %.2fs", delay)
        await asyncio.sleep(delay)

    async def _inject_network_failure(self, config: ChaosConfig) -> None:  # noqa: ARG002
        """Inject network failure."""
        logger.warning("Injecting network failure")
        raise ConnectionError("Chaos injection: Network failure")

    async def _inject_service_unavailable(self, config: ChaosConfig) -> None:  # noqa: ARG002
        """Inject service unavailable error."""
        logger.warning("Injecting service unavailable")
        raise RuntimeError("Chaos injection: Service unavailable")

    async def _inject_high_latency(self, config: ChaosConfig) -> None:
        """Inject high latency."""
        latency = config.intensity * 10.0  # Up to 10 seconds latency
        logger.warning("Injecting high latency of %.2fs", latency)
        await asyncio.sleep(latency)

    async def _inject_random_errors(self, config: ChaosConfig) -> None:
        """Inject random errors."""
        if random.random() < config.intensity:
            error_types = [
                ValueError("Chaos injection: Random validation error"),
                RuntimeError("Chaos injection: Random runtime error"),
                ConnectionError("Chaos injection: Random connection error"),
            ]
            error = random.choice(error_types)
            logger.warning("Injecting random error: %s", error)
            raise error

    async def _inject_intermittent_failures(self, config: ChaosConfig) -> None:
        """Inject intermittent failures."""
        if random.random() < config.intensity * 0.5:  # 50% of intensity
            logger.warning("Injecting intermittent failure")
            raise RuntimeError("Chaos injection: Intermittent failure")

    def is_chaos_active(self, target: str = "default") -> bool:
        """Check if chaos is currently active for a target."""
        return target in self.active_chaos

    def get_active_chaos(self, target: str = "default") -> ChaosConfig | None:
        """Get active chaos configuration for a target."""
        return self.active_chaos.get(target)

    def clear_all_chaos(self) -> None:
        """Clear all active chaos configurations."""
        self.active_chaos.clear()

    def get_injection_history(self) -> list[dict[str, Any]]:
        """Get history of chaos injections."""
        return self.injection_history.copy()


@asynccontextmanager
async def chaos_context(
    config: ChaosConfig, target: str = "default", injector: ChaosInjector | None = None
) -> AsyncIterator[ChaosInjector]:
    """Context manager for chaos injection."""
    if injector is None:
        injector = ChaosInjector()

    try:
        await injector.inject_chaos(config, target)
        yield injector
    finally:
        # Cleanup handled by inject_chaos method
        pass


class ResilienceTestSuite:
    """Test suite for resilience patterns with chaos engineering."""

    def __init__(self, injector: ChaosInjector | None = None):
        self.injector = injector or ChaosInjector()
        self.test_results: list[dict[str, Any]] = []

    async def test_network_resilience(
        self, target_function: Callable[..., Awaitable[Any]], *args, **kwargs
    ) -> dict[str, Any]:
        """Test network resilience with various network chaos scenarios."""
        scenarios = [
            ChaosConfig(ChaosType.NETWORK_DELAY, intensity=0.3),
            ChaosConfig(ChaosType.NETWORK_DELAY, intensity=0.7),
            ChaosConfig(ChaosType.NETWORK_FAILURE, probability=0.5),
        ]

        results = {}
        for i, scenario in enumerate(scenarios):
            scenario_name = f"network_scenario_{i}"
            try:
                start_time = time.time()

                async with chaos_context(scenario, injector=self.injector):
                    result = await target_function(*args, **kwargs)

                execution_time = time.time() - start_time
                results[scenario_name] = {
                    "success": True,
                    "execution_time": execution_time,
                    "result": result,
                    "chaos_config": scenario,
                }
            except Exception as e:  # noqa: BLE001
                execution_time = time.time() - start_time
                results[scenario_name] = {
                    "success": False,
                    "execution_time": execution_time,
                    "error": str(e),
                    "chaos_config": scenario,
                }

        return results

    async def test_latency_resilience(
        self,
        target_function: Callable[..., Awaitable[Any]],
        *args,
        max_acceptable_latency: float = 5.0,
        **kwargs,
    ) -> dict[str, Any]:
        """Test latency resilience with high latency scenarios."""
        scenarios = [
            ChaosConfig(ChaosType.HIGH_LATENCY, intensity=0.2),
            ChaosConfig(ChaosType.HIGH_LATENCY, intensity=0.5),
            ChaosConfig(ChaosType.HIGH_LATENCY, intensity=0.8),
        ]

        results = {}
        for i, scenario in enumerate(scenarios):
            scenario_name = f"latency_scenario_{i}"
            try:
                start_time = time.time()

                async with chaos_context(scenario, injector=self.injector):
                    result = await target_function(*args, **kwargs)

                execution_time = time.time() - start_time
                within_acceptable_latency = execution_time <= max_acceptable_latency

                results[scenario_name] = {
                    "success": True,
                    "execution_time": execution_time,
                    "within_acceptable_latency": within_acceptable_latency,
                    "result": result,
                    "chaos_config": scenario,
                }
            except Exception as e:  # noqa: BLE001
                execution_time = time.time() - start_time
                results[scenario_name] = {
                    "success": False,
                    "execution_time": execution_time,
                    "error": str(e),
                    "chaos_config": scenario,
                }

        return results

    async def test_error_resilience(
        self, target_function: Callable[..., Awaitable[Any]], *args, **kwargs
    ) -> dict[str, Any]:
        """Test error resilience with various error scenarios."""
        scenarios = [
            ChaosConfig(ChaosType.RANDOM_ERRORS, intensity=0.3),
            ChaosConfig(ChaosType.INTERMITTENT_FAILURES, intensity=0.5),
            ChaosConfig(ChaosType.SERVICE_UNAVAILABLE, probability=0.3),
        ]

        results = {}
        for i, scenario in enumerate(scenarios):
            scenario_name = f"error_scenario_{i}"
            try:
                start_time = time.time()

                async with chaos_context(scenario, injector=self.injector):
                    result = await target_function(*args, **kwargs)

                execution_time = time.time() - start_time
                results[scenario_name] = {
                    "success": True,
                    "execution_time": execution_time,
                    "result": result,
                    "chaos_config": scenario,
                }
            except Exception as e:  # noqa: BLE001
                execution_time = time.time() - start_time
                results[scenario_name] = {
                    "success": False,
                    "execution_time": execution_time,
                    "error": str(e),
                    "chaos_config": scenario,
                }

        return results

    async def run_comprehensive_test(
        self, target_function: Callable[..., Awaitable[Any]], *args, **kwargs
    ) -> dict[str, Any]:
        """Run comprehensive resilience tests."""
        test_start = time.time()

        network_results = await self.test_network_resilience(target_function, *args, **kwargs)
        latency_results = await self.test_latency_resilience(target_function, *args, **kwargs)
        error_results = await self.test_error_resilience(target_function, *args, **kwargs)

        total_time = time.time() - test_start

        comprehensive_results = {
            "network_resilience": network_results,
            "latency_resilience": latency_results,
            "error_resilience": error_results,
            "total_test_time": total_time,
            "injection_history": self.injector.get_injection_history(),
        }

        self.test_results.append(comprehensive_results)
        return comprehensive_results

    def get_test_summary(self) -> dict[str, Any]:
        """Get summary of all test results."""
        if not self.test_results:
            return {"message": "No tests run yet"}

        total_tests = 0
        successful_tests = 0

        for test_result in self.test_results:
            for category in ["network_resilience", "latency_resilience", "error_resilience"]:
                if category in test_result:
                    for scenario_result in test_result[category].values():
                        total_tests += 1
                        if scenario_result.get("success", False):
                            successful_tests += 1

        success_rate = successful_tests / total_tests if total_tests > 0 else 0

        return {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": total_tests - successful_tests,
            "success_rate": success_rate,
            "test_runs": len(self.test_results),
        }
