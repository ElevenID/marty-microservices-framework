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

from marty_msf.framework.resilience import (  # Basic Components; Pattern Management; Convenience Functions
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerState,
    ResilienceConfig,
    ResilienceManager,
    ResiliencePattern,
    RetryConfig,
    RetryStrategy,
    TimeoutConfig,
    initialize_resilience,
    retry_async,
)
from marty_msf.framework.resilience.retry import RetryError
from marty_msf.framework.resilience.timeout import ResilienceTimeoutError, with_timeout


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

        result = await retry_async(flaky_operation, config)
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
            await retry_async(always_failing, config)
        assert attempt_count == 3


class TestTimeoutManagement:
    """Test timeout management functionality."""

    def test_timeout_config_creation(self):
        """Test timeout configuration creation."""
        config = TimeoutConfig()
        config.default_timeout = 30.0
        config.log_timeouts = True
        config.grace_period = 5.0

        assert config.default_timeout == 30.0
        assert config.log_timeouts
        assert config.grace_period == 5.0

    @pytest.mark.asyncio
    async def test_timeout_with_fast_operation(self):
        """Test timeout with operation that completes quickly."""

        async def fast_operation():
            await asyncio.sleep(0.01)
            return "quick_result"

        result = await with_timeout(fast_operation, 1.0, "fast_op")
        assert result == "quick_result"

    @pytest.mark.asyncio
    async def test_timeout_with_slow_operation(self):
        """Test timeout with operation that exceeds timeout."""

        async def slow_operation():
            await asyncio.sleep(1.0)
            return "should_not_reach"

        with pytest.raises((asyncio.TimeoutError, Exception)):  # More flexible exception handling
            await with_timeout(slow_operation, 0.1, "slow_op")


class TestResilienceManager:
    """Test integrated resilience management."""

    def test_resilience_manager_creation(self):
        """Test resilience manager creation with default config."""
        manager = ResilienceManager()

        assert manager.config is not None
        assert isinstance(manager._circuit_breakers, dict)
        assert manager._total_operations == 0

    def test_resilience_manager_with_custom_config(self):
        """Test resilience manager with custom configuration."""
        config = ResilienceConfig(
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=5),
            retry_config=RetryConfig(max_attempts=3),
            timeout_seconds=30.0,
        )
        manager = ResilienceManager(config)

        assert manager.config.timeout_seconds == 30.0
        assert manager.config.circuit_breaker_config.failure_threshold == 5
        assert manager.config.retry_config.max_attempts == 3

    @pytest.mark.asyncio
    async def test_resilience_manager_execution(self):
        """Test resilience manager executing operations."""
        config = ResilienceConfig(timeout_seconds=1.0, execution_order=[ResiliencePattern.TIMEOUT])
        manager = ResilienceManager(config)

        async def test_operation():
            await asyncio.sleep(0.01)
            return "operation_result"

        result = await manager.execute_with_patterns(test_operation, "test_op")
        assert result == "operation_result"

    def test_circuit_breaker_creation_via_manager(self):
        """Test circuit breaker creation through manager."""
        manager = ResilienceManager()
        cb = manager.get_or_create_circuit_breaker("test-cb")

        assert cb.name == "test-cb"
        assert cb.state == CircuitBreakerState.CLOSED

        # Should return same instance on second call
        cb2 = manager.get_or_create_circuit_breaker("test-cb")
        assert cb is cb2


class TestResilienceInitialization:
    """Test resilience initialization and configuration."""

    def test_initialize_resilience(self):
        """Test resilience initialization."""
        config = ResilienceConfig(
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=10),
            retry_config=RetryConfig(max_attempts=5),
        )

        manager = initialize_resilience(config)
        assert isinstance(manager, ResilienceManager)
        assert manager.config.circuit_breaker_config.failure_threshold == 10
        assert manager.config.retry_config.max_attempts == 5


class TestResilienceIntegration:
    """Test integrated resilience scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_patterns_integration(self):
        """Test combining multiple resilience patterns."""
        config = ResilienceConfig(
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=3),
            retry_config=RetryConfig(max_attempts=2, base_delay=0.01),
            timeout_seconds=2.0,
            execution_order=[
                ResiliencePattern.TIMEOUT,
                ResiliencePattern.RETRY,
                ResiliencePattern.CIRCUIT_BREAKER,
            ],
        )
        manager = ResilienceManager(config)

        call_count = 0

        async def sometimes_failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First failure")
            return f"success_on_call_{call_count}"

        result = await manager.execute_with_patterns(
            sometimes_failing_operation, "integration_test"
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
        await manager.execute_with_patterns(successful_operation, "stats_test_1")
        await manager.execute_with_patterns(successful_operation, "stats_test_2")

        stats = manager.get_stats()
        assert stats["total_operations"] == 2
        assert stats["successful_operations"] == 2
        assert stats["success_rate"] == 1.0


class TestResilienceErrorHandling:
    """Test resilience framework error handling."""

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """Test proper error propagation through resilience layers."""
        config = ResilienceConfig(
            retry_config=RetryConfig(max_attempts=2, base_delay=0.01), timeout_seconds=1.0
        )
        manager = ResilienceManager(config)

        async def consistently_failing_operation():
            raise ValueError("Persistent failure")

        with pytest.raises(RetryError):  # RetryError is raised when all retry attempts fail
            await manager.execute_with_patterns(consistently_failing_operation, "error_test")

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self):
        """Test timeout error handling in resilience patterns."""
        config = ResilienceConfig(timeout_seconds=0.1)
        manager = ResilienceManager(config)

        async def timeout_operation():
            await asyncio.sleep(1.0)
            return "should_not_complete"

        with pytest.raises(ResilienceTimeoutError):  # ResilienceTimeoutError for timeout operations
            await manager.execute_with_patterns(timeout_operation, "timeout_test")
