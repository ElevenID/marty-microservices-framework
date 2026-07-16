"""
Resilience Application Services.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from mmf.framework.resilience.domain.config import ResilienceConfig, ResilienceStrategy
from mmf.framework.resilience.domain.exceptions import (
    BulkheadError,
    CircuitBreakerError,
    ResilienceTimeoutError,
)
from mmf.framework.resilience.domain.ports import (
    ResilienceManagerPort,
    ResilienceMetrics,
)
from mmf.framework.resilience.infrastructure.adapters.bulkhead import (
    BulkheadManager,
    get_bulkhead_manager,
)
from mmf.framework.resilience.infrastructure.adapters.circuit_breaker import (
    CircuitBreaker,
    get_circuit_breaker,
)
from mmf.framework.resilience.infrastructure.adapters.retry import retry_async

T = TypeVar("T")
logger = logging.getLogger(__name__)


class ResilienceManager(ResilienceManagerPort):
    """
    Unified resilience manager that automatically applies circuit breakers,
    retries, and timeouts.
    """

    def __init__(self, config: ResilienceConfig | None = None):
        self.config = config or ResilienceConfig()
        self._metrics = ResilienceMetrics()
        self._bulkhead_manager: BulkheadManager = get_bulkhead_manager()

    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        strategy: ResilienceStrategy = ResilienceStrategy.INTERNAL_SERVICE,
        operation_name: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a function with resilience patterns applied."""
        start_time = time.time()
        op_name = operation_name or getattr(func, "__name__", "unknown_operation")

        # In a real implementation, we would select config based on strategy
        # For now, we use the global config
        effective_config = self.config

        try:
            # 1. Timeout (outermost)
            if effective_config.timeout_enabled:

                async def timeout_wrapper() -> Any:
                    try:
                        return await asyncio.wait_for(
                            self._execute_inner(func, op_name, effective_config, *args, **kwargs),
                            timeout=effective_config.timeout.seconds,
                        )
                    except asyncio.TimeoutError as e:
                        self._metrics.timeout_count += 1
                        raise ResilienceTimeoutError(
                            f"Operation {op_name} timed out after {effective_config.timeout.seconds}s"
                        ) from e

                result = await timeout_wrapper()
            else:
                result = await self._execute_inner(func, op_name, effective_config, *args, **kwargs)

            # Update metrics
            duration = time.time() - start_time
            self._metrics.successful_calls += 1
            self._metrics.total_calls += 1
            self._metrics.last_success_time = time.time()
            # Simple average calculation
            n = self._metrics.successful_calls
            self._metrics.average_response_time = (
                self._metrics.average_response_time * (n - 1) + duration
            ) / n

            return result

        except Exception:
            self._metrics.failed_calls += 1
            self._metrics.total_calls += 1
            self._metrics.last_failure_time = time.time()
            raise

    async def _execute_inner(
        self,
        func: Callable[..., Any],
        op_name: str,
        config: ResilienceConfig,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute inner layers: Retry -> Circuit Breaker -> Bulkhead -> Function."""

        # We build the execution chain from inside out

        # 4. The actual function execution
        async def actual_execution() -> Any:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        current_func = actual_execution

        # 3. Bulkhead
        if config.bulkhead_enabled:
            bulkhead = self._bulkhead_manager.get_bulkhead(op_name)
            if not bulkhead:
                bulkhead = self._bulkhead_manager.create_bulkhead(op_name, config.bulkhead)

            func_to_isolate = current_func

            async def bulkhead_wrapper() -> Any:
                try:
                    return await bulkhead.execute_async(func_to_isolate)  # type: ignore
                except BulkheadError:
                    self._metrics.bulkhead_rejected_count += 1
                    raise

            current_func = bulkhead_wrapper

        # 2. Circuit Breaker
        if config.circuit_breaker_enabled:
            circuit = get_circuit_breaker(op_name, config.circuit_breaker)

            func_to_protect = current_func

            async def circuit_wrapper() -> Any:
                try:
                    return await circuit.call(func_to_protect)
                except CircuitBreakerError:
                    self._metrics.circuit_breaker_open_count += 1
                    raise

            current_func = circuit_wrapper

        # 1. Retry
        if config.retry_enabled:
            func_to_retry = current_func

            async def retry_wrapper() -> Any:
                try:
                    return await retry_async(func_to_retry, config=config.retry)
                except Exception:
                    self._metrics.retry_count += (
                        1  # This counts failed retry sequences, not individual retries
                    )
                    raise

            current_func = retry_wrapper

        return await current_func()

    def get_metrics(self) -> ResilienceMetrics:
        """Get current metrics."""
        return self._metrics
