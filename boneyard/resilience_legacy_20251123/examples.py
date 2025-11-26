"""
Advanced Resilience Patterns Examples

Demonstrates comprehensive usage of the resilience framework including
circuit breakers, retry mechanisms, bulkheads, timeouts, and fallbacks.
"""

import asyncio
import builtins
import random
import time
from typing import Any

from marty_msf.framework.resilience import (  # Circuit Breaker; Retry; Timeout; Fallback; Integrated Patterns
    CircuitBreaker,
    CircuitBreakerConfig,
    FunctionFallback,
    ResilienceConfig,
    RetryConfig,
    RetryStrategy,
    StaticFallback,
    initialize_resilience,
    resilience_pattern,
    retry_async,
    timeout_async,
    with_timeout,
)


# Simulated external services for examples
class ExternalAPIError(Exception):
    """Simulated external API error."""


class DatabaseError(Exception):
    """Simulated database error."""


async def unreliable_external_api(success_rate: float = 0.7) -> builtins.dict[str, Any]:
    """Simulate an unreliable external API."""
    await asyncio.sleep(random.uniform(0.1, 0.5))  # Simulate network delay

    if random.random() > success_rate:
        raise ExternalAPIError("External API temporarily unavailable")

    return {
        "status": "success",
        "data": {"user_id": random.randint(1000, 9999)},
        "timestamp": time.time(),
    }


async def slow_database_query(delay_range: tuple = (0.1, 2.0)) -> builtins.dict[str, Any]:
    """Simulate a slow database query."""
    delay = random.uniform(*delay_range)
    await asyncio.sleep(delay)

    if delay > 1.5:  # Simulate timeout-prone queries
        raise DatabaseError("Database query timeout")

    return {
        "query_result": [{"id": i, "name": f"Item {i}"} for i in range(5)],
        "execution_time": delay,
    }


def cpu_intensive_task(iterations: int = 1000000) -> int:
    """Simulate CPU-intensive work."""
    result = 0
    for i in range(iterations):
        result += i * i
    return result


# Example 1: Basic Circuit Breaker
async def example_circuit_breaker():
    """Demonstrate basic circuit breaker usage."""
    print("\n=== Circuit Breaker Example ===")

    # Configure circuit breaker
    config = CircuitBreakerConfig(
        failure_threshold=3,
        timeout_seconds=10,
        success_threshold=2,
        use_failure_rate=True,
        failure_rate_threshold=0.5,
    )

    circuit = CircuitBreaker("external_api_circuit", config)

    # Test circuit breaker behavior
    for attempt in range(10):
        try:
            result = await circuit.call(unreliable_external_api, 0.3)  # 30% success rate
            print(f"Attempt {attempt + 1}: SUCCESS - {result}")
        except Exception as e:
            print(f"Attempt {attempt + 1}: FAILED - {type(e).__name__}: {e}")

        # Show circuit state
        stats = circuit.get_stats()
        print(f"  Circuit State: {stats['state']}, Failures: {stats['failure_count']}")

        await asyncio.sleep(0.1)


# Example 2: Retry with Exponential Backoff
async def example_retry_mechanism():
    """Demonstrate retry mechanism with different strategies."""
    print("\n=== Retry Mechanism Example ===")

    # Exponential backoff retry
    exponential_config = RetryConfig(
        max_attempts=5,
        base_delay=0.5,
        max_delay=10.0,
        strategy=RetryStrategy.EXPONENTIAL,
        backoff_multiplier=2.0,
        jitter=True,
    )

    print("Exponential Backoff Retry:")
    try:
        result = await retry_async(
            unreliable_external_api,
            exponential_config,
            0.4,  # 40% success rate
        )
        print(f"SUCCESS: {result}")
    except Exception as e:
        print(f"FAILED after all retries: {e}")


# Example 3: Timeout Management
async def example_timeout_management():
    """Demonstrate timeout management."""
    print("\n=== Timeout Management Example ===")

    # Basic timeout usage
    print("Basic Timeout:")
    try:
        result = await with_timeout(
            slow_database_query,
            1.0,  # timeout_seconds
            "fast_query",  # operation
            (0.5, 0.8),  # delay_range argument to the function
        )
        print(f"SUCCESS: Query completed in {result['execution_time']:.2f}s")
    except Exception as e:
        print(f"TIMEOUT: {e}")

    # Timeout decorator
    @timeout_async(timeout_seconds=2.0, operation="decorated_query")
    async def timed_database_query():
        return await slow_database_query((1.0, 3.0))  # Longer delay range

    print("\nDecorator Timeout:")
    try:
        result = await timed_database_query()
        print(f"SUCCESS: Query completed in {result['execution_time']:.2f}s")
    except Exception as e:
        print(f"TIMEOUT: {e}")


# Example 4: Fallback Strategies
async def example_fallback_strategies():
    """Demonstrate fallback strategies."""
    print("\n=== Fallback Strategies Example ===")

    # Create a simple fallback manager for this example
    class SimpleFallbackManager:
        def __init__(self):
            self.strategies = {}

        def register_fallback(self, strategy):
            self.strategies[strategy.name] = strategy

        async def execute_with_fallback(self, func, strategy_name, *args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if strategy_name in self.strategies:
                    return await self.strategies[strategy_name].execute_fallback(e, *args, **kwargs)
                raise

    manager = SimpleFallbackManager()

    # Static fallback
    static_fallback = StaticFallback(
        "static_response", {"status": "fallback", "data": {"cached": True}}
    )
    manager.register_fallback(static_fallback)

    # Function fallback
    async def fallback_function(*args, **kwargs):
        return {"status": "fallback", "source": "function", "args": args}

    function_fallback = FunctionFallback("function_response", fallback_function)
    manager.register_fallback(function_fallback)

    # Test fallback strategies
    async def unreliable_user_service(user_id: int):
        # Always fail to trigger fallback
        raise ExternalAPIError("User service unavailable")

    try:
        result = await manager.execute_with_fallback(
            unreliable_user_service, "static_response", user_id=123
        )
        print(f"Fallback result: {result}")
    except Exception as e:
        print(f"All fallbacks failed: {e}")


# Example 5: Integrated Resilience Patterns
async def example_integrated_patterns():
    """Demonstrate integrated resilience patterns."""
    print("\n=== Integrated Resilience Patterns Example ===")

    # Configure comprehensive resilience
    config = ResilienceConfig(
        circuit_breaker_config=CircuitBreakerConfig(
            failure_threshold=2,
            timeout_seconds=15,
            use_failure_rate=True,
            failure_rate_threshold=0.4,
        ),
        retry_config=RetryConfig(
            max_attempts=3, base_delay=1.0, strategy=RetryStrategy.EXPONENTIAL
        ),
        timeout_seconds=5.0,
    )

    manager = initialize_resilience(config)

    # Decorated function with patterns
    @resilience_pattern(config, "comprehensive_service")
    async def resilient_service_call():
        return await unreliable_external_api(0.3)  # Low success rate

    # Test integrated patterns
    results = []
    for i in range(5):
        try:
            result = await resilient_service_call()
            results.append(("SUCCESS", result))
            print(f"Call {i + 1}: SUCCESS")
        except Exception as e:
            results.append(("FAILED", str(e)))
            print(f"Call {i + 1}: FAILED - {e}")

        await asyncio.sleep(0.5)

    # Show comprehensive stats
    stats = manager.get_stats()
    print("\nResilience Stats:")
    print(f"  Total operations: {stats['total_operations']}")
    print(f"  Success rate: {stats['success_rate']:.2%}")
    print(f"  Pattern usage: {stats['pattern_usage']}")


# Example 6: Real-world Service Integration
async def example_service_integration():
    """Demonstrate real-world service integration patterns."""
    print("\n=== Service Integration Example ===")

    class UserService:
        """Example service with resilience patterns."""

        def __init__(self):
            # Configure different patterns for different operations
            self.fast_config = ResilienceConfig(
                circuit_breaker_config=CircuitBreakerConfig(failure_threshold=2),
                retry_config=RetryConfig(max_attempts=2, base_delay=0.1),
                timeout_seconds=2.0,
            )

        @resilience_pattern(operation_name="get_user_profile")
        async def get_user_profile(self, user_id: int) -> builtins.dict[str, Any]:
            """Fast user profile lookup."""
            return await unreliable_external_api(0.8)

        @timeout_async(timeout_seconds=5.0, operation="generate_report")
        async def generate_user_report(self, user_id: int) -> builtins.dict[str, Any]:
            """Slow report generation."""
            await asyncio.sleep(random.uniform(1.0, 3.0))
            return {"report": f"Report for user {user_id}", "pages": 50}

    # Test service integration
    service = UserService()

    # Run multiple operations concurrently
    tasks = [
        service.get_user_profile(1),
        service.get_user_profile(2),
        service.generate_user_report(1),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    operation_names = [
        "get_user_profile(1)",
        "get_user_profile(2)",
        "generate_user_report(1)",
    ]

    for operation, result in zip(operation_names, results, strict=False):
        if isinstance(result, Exception):
            print(f"{operation}: FAILED - {type(result).__name__}")
        else:
            print(f"{operation}: SUCCESS")


async def main():
    """Run all resilience pattern examples."""
    print("Advanced Resilience Patterns Examples")
    print("=" * 50)

    examples = [
        example_circuit_breaker,
        example_retry_mechanism,
        example_timeout_management,
        example_fallback_strategies,
        example_integrated_patterns,
        example_service_integration,
    ]

    for example in examples:
        try:
            await example()
        except Exception as e:
            print(f"Example failed: {e}")

        print("\n" + "-" * 50)
        await asyncio.sleep(1)  # Brief pause between examples


if __name__ == "__main__":
    asyncio.run(main())
