"""
Outbound call resilience patterns.

Ported from Marty's resilience framework to provide resilient
outbound call capabilities for microservices.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .advanced_retry import AdvancedRetryConfig, async_retry_with_advanced_policy
from .enhanced_circuit_breaker import EnhancedCircuitBreakerConfig, get_circuit_breaker

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def async_call_with_resilience(
    func: Callable[..., Awaitable[T]],
    *args,
    retry_config: AdvancedRetryConfig | None = None,
    circuit_breaker_config: EnhancedCircuitBreakerConfig | None = None,
    circuit_breaker_name: str = "default",
    **kwargs,
) -> T:
    """Execute an async function with comprehensive resilience patterns."""
    # Set up default configurations
    if retry_config is None:
        retry_config = AdvancedRetryConfig()

    # Create circuit breaker if config provided
    circuit_breaker = None
    if circuit_breaker_config is not None:

        circuit_breaker = get_circuit_breaker(circuit_breaker_name, circuit_breaker_config)

    async def resilient_call() -> T:
        """Execute the call with circuit breaker protection if enabled."""
        if circuit_breaker:
            return await circuit_breaker.call(func, *args, **kwargs)
        else:
            return await func(*args, **kwargs)

    # Execute with retry policy
    retry_result = await async_retry_with_advanced_policy(resilient_call, config=retry_config)

    if retry_result.success:
        return retry_result.result
    else:
        # Re-raise the last exception
        if retry_result.last_exception:
            raise retry_result.last_exception
        else:
            raise RuntimeError("Call failed without specific exception")
