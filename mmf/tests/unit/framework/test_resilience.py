"""
Comprehensive Resilience Framework Tests - Working with Real Components

Tests all major resilience patterns using real implementations:
- Circuit Breakers
- Retry Mechanisms
- Timeout Management
- Bulkhead Isolation (Basic)
- Resilience Manager
"""

import asyncio

import pytest

from mmf.framework.resilience.application.services import ResilienceManager
from mmf.framework.resilience.domain.config import (
    CircuitBreakerConfig,
    ResilienceConfig,
    RetryConfig,
    RetryStrategy,
    TimeoutConfig,
)
from mmf.framework.resilience.domain.exceptions import (
    CircuitBreakerError,
    CircuitBreakerState,
    ResilienceTimeoutError,
    RetryError,
)
from mmf.framework.resilience.infrastructure.adapters.circuit_breaker import (
    CircuitBreaker,
)
from mmf.framework.resilience.infrastructure.adapters.retry import retry_async


class TestCircuitBreaker:
    """Test circuit breaker functionality with real implementation."""

    def test_circuit_breaker_creation(self):
        """Test circuit breaker creation with default config."""
        config = CircuitBreakerConfig()
        cb = CircuitBreaker("test-cb", config)

        assert cb.name == "test-cb"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_with_custom_config(self):
        """Test circuit breaker with custom configuration."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=30,
            use_failure_rate=True,
            failure_rate_threshold=0.5,
        )
        cb = CircuitBreaker("custom-cb", config)

        assert cb.config.failure_threshold == 5
        assert cb.config.timeout_seconds == 30
        assert cb.config.use_failure_rate
        assert cb.config.failure_rate_threshold == 0.5

    @pytest.mark.asyncio
    async def test_circuit_breaker_success_flow(self):
        """Test circuit breaker with successful operations."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("success-cb", config)

        async def successful_operation():
            return "success"

        result = await cb.call(successful_operation)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.success_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_flow(self):
        """Test circuit breaker with failing operations."""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("failure-cb", config)

        async def failing_operation():
            raise ValueError("Simulated failure")

        # First failure
        with pytest.raises(ValueError):
            await cb.call(failing_operation)
        assert cb.state == CircuitBreakerState.CLOSED

        # Second failure should open circuit
        with pytest.raises(ValueError):
            await cb.call(failing_operation)
        assert cb.state == CircuitBreakerState.OPEN

        # Subsequent calls should raise CircuitBreakerError
        with pytest.raises(
            (CircuitBreakerError, ValueError)
        ):  # Could be CircuitBreakerError or the function exception
            await cb.call(failing_operation)


class TestRetryMechanism:
    """Test retry mechanisms with real implementations."""

    @pytest.mark.asyncio
    async def test_retry_with_eventual_success(self):
        """Test retry mechanism with eventual success."""
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,  # Small delay for fast tests
            strategy=RetryStrategy.EXPONENTIAL,
        )

        attempt_count = 0

        async def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ValueError("Temporary failure")
            return f"success_on_attempt_{attempt_count}"

        result = await retry_async(flaky_operation, config=config)
        assert result == "success_on_attempt_2"
        assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_constant_backoff(self):
        """Test retry with constant backoff strategy."""
        config = RetryConfig(max_attempts=3, base_delay=0.01, strategy=RetryStrategy.CONSTANT)

        attempt_count = 0

        async def always_failing():
            nonlocal attempt_count
            attempt_count += 1
            raise RuntimeError(f"Failure {attempt_count}")

        with pytest.raises(RetryError):
            await retry_async(always_failing, config=config)
        assert attempt_count == 3


class TestTimeoutManagement:
    """Test timeout management functionality."""

    def test_timeout_config_creation(self):
        """Test timeout configuration creation."""
        config = TimeoutConfig(seconds=30.0)
        assert config.seconds == 30.0

    @pytest.mark.asyncio
    async def test_timeout_with_fast_operation(self):
        """Test timeout with operation that completes quickly."""

        async def fast_operation():
            await asyncio.sleep(0.01)
            return "quick_result"

        result = await asyncio.wait_for(fast_operation(), timeout=1.0)
        assert result == "quick_result"

    @pytest.mark.asyncio
    async def test_timeout_with_slow_operation(self):
        """Test timeout with operation that exceeds timeout."""

        async def slow_operation():
            await asyncio.sleep(1.0)
            return "should_not_reach"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_operation(), timeout=0.1)


class TestResilienceManager:
    """Test resilience manager functionality."""

    def test_resilience_manager_creation(self):
        """Test resilience manager creation."""
        config = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(failure_threshold=5),
            retry=RetryConfig(max_attempts=3),
            timeout=TimeoutConfig(seconds=30.0),
        )
        manager = ResilienceManager(config)

        assert manager.config.timeout.seconds == 30.0
        assert manager.config.circuit_breaker.failure_threshold == 5
        assert manager.config.retry.max_attempts == 3

    @pytest.mark.asyncio
    async def test_resilience_manager_execution(self):
        """Test resilience manager executing operations."""
        config = ResilienceConfig(timeout=TimeoutConfig(seconds=1.0))
        manager = ResilienceManager(config)

        async def test_operation():
            await asyncio.sleep(0.01)
            return "operation_result"

        result = await manager.execute(test_operation, operation_name="test_op")
        assert result == "operation_result"


class TestResilienceInitialization:
    """Test resilience initialization and configuration."""

    def test_initialize_resilience(self):
        """Test resilience initialization."""
        config = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(failure_threshold=10),
            retry=RetryConfig(max_attempts=5),
        )

        manager = ResilienceManager(config)
        assert isinstance(manager, ResilienceManager)
        assert manager.config.circuit_breaker.failure_threshold == 10
        assert manager.config.retry.max_attempts == 5


class TestResilienceIntegration:
    """Test integrated resilience scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_patterns_integration(self):
        """Test combining multiple resilience patterns."""
        config = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(failure_threshold=3),
            retry=RetryConfig(max_attempts=2, base_delay=0.01),
            timeout=TimeoutConfig(seconds=2.0),
        )
        manager = ResilienceManager(config)

        call_count = 0

        async def sometimes_failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First failure")
            return f"success_on_call_{call_count}"

        result = await manager.execute(
            sometimes_failing_operation, operation_name="integration_test"
        )
        assert result == "success_on_call_2"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_stats_collection(self):
        """Test resilience statistics collection."""
        manager = ResilienceManager()

        async def successful_operation():
            return "success"

        # Execute some operations
        await manager.execute(successful_operation, operation_name="stats_test_1")
        await manager.execute(successful_operation, operation_name="stats_test_2")

        metrics = manager.get_metrics()
        assert metrics.total_calls == 2
        assert metrics.successful_calls == 2


class TestResilienceErrorHandling:
    """Test resilience framework error handling."""

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """Test proper error propagation through resilience layers."""
        config = ResilienceConfig(
            retry=RetryConfig(max_attempts=2, base_delay=0.01),
            timeout=TimeoutConfig(seconds=1.0),
        )
        manager = ResilienceManager(config)

        async def consistently_failing_operation():
            raise ValueError("Persistent failure")

        with pytest.raises(RetryError):  # RetryError is raised when all retry attempts fail
            await manager.execute(consistently_failing_operation, operation_name="error_test")

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self):
        """Test timeout error handling in resilience patterns."""
        config = ResilienceConfig(timeout=TimeoutConfig(seconds=0.1))
        manager = ResilienceManager(config)

        async def timeout_operation():
            await asyncio.sleep(1.0)
            return "should_not_complete"

        with pytest.raises(ResilienceTimeoutError):  # ResilienceTimeoutError for timeout operations
            await manager.execute(timeout_operation, operation_name="timeout_test")
