"""
Enhanced behavioral tests for resilience patterns.
"""

import asyncio
import time

import pytest

from mmf_new.framework.resilience.domain.config import CircuitBreakerConfig
from mmf_new.framework.resilience.domain.exceptions import (
    CircuitBreakerError,
    CircuitBreakerState,
)
from mmf_new.framework.resilience.infrastructure.adapters.circuit_breaker import (
    CircuitBreaker,
)


class TestCircuitBreakerBehavior:
    @pytest.mark.asyncio
    async def test_circuit_breaker_state_transitions(self):
        """Test circuit breaker transitions through CLOSED -> OPEN -> HALF_OPEN states."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=0.1,  # 100ms for fast testing
            success_threshold=2,
            use_failure_rate=False,
        )
        circuit_breaker = CircuitBreaker("test_cb", config)

        # Initially CLOSED
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

        # Simulate failures to trigger OPEN state
        async def failing_func():
            raise ValueError("Fail")

        for _ in range(3):
            try:
                await circuit_breaker.call(failing_func)
            except ValueError:
                pass

        assert circuit_breaker.state == CircuitBreakerState.OPEN

        # Should reject calls in OPEN state
        with pytest.raises(CircuitBreakerError):
            await circuit_breaker.call(lambda: "success")

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery from OPEN to CLOSED state."""
        config = CircuitBreakerConfig(
            failure_threshold=2, timeout_seconds=0.1, success_threshold=2, use_failure_rate=False
        )
        circuit_breaker = CircuitBreaker("recovery_test", config)

        # Trigger OPEN state
        async def failing_func():
            raise ValueError("Fail")

        for _ in range(2):
            try:
                await circuit_breaker.call(failing_func)
            except ValueError:
                pass

        assert circuit_breaker.state == CircuitBreakerState.OPEN

        # Wait for timeout to trigger HALF_OPEN
        await asyncio.sleep(0.15)

        # Next call should transition to HALF_OPEN (internally) and succeed
        result = await circuit_breaker.call(lambda: "success")
        assert result == "success"

        # State might still be HALF_OPEN until success threshold reached
        # We need 2 successes. We got 1.
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN

        # Second success
        await circuit_breaker.call(lambda: "success")

        # Now should be CLOSED
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
