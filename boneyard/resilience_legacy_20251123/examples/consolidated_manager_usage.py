"""Consolidated Resilience Manager Usage Examples

This module demonstrates how to use the new ConsolidatedResilienceManager
to replace fragmented resilience implementations with a unified approach.
"""

import asyncio
import logging
import random
from typing import Any

# Import the new consolidated resilience manager
from marty_msf.framework.resilience import (
    ConsolidatedResilienceConfig,
    ConsolidatedResilienceManager,
    ResilienceStrategy,
    create_resilience_manager_with_defaults,
    get_resilience_manager,
    resilient_database_call,
    resilient_external_call,
    resilient_internal_call,
)

# Import configuration layer for proper integration
# from marty_msf.framework.config import get_unified_config, UnifiedConfigurationManager

logger = logging.getLogger(__name__)


# Example 1: Using the global instance with strategy-specific helpers
async def example_service_calls():
    """Demonstrate using convenience functions for different call types."""

    # Internal service call with default internal service strategy
    async def fetch_user_profile(user_id: str) -> dict[str, Any]:
        # Simulate internal service call
        await asyncio.sleep(0.1)
        return {"user_id": user_id, "name": "John Doe"}

    # External API call with default external service strategy
    async def fetch_weather_data(city: str) -> dict[str, Any]:
        # Simulate external API call
        await asyncio.sleep(0.2)
        return {"city": city, "temperature": 22.5}

    # Database call with default database strategy
    async def get_user_orders(user_id: str) -> list[dict[str, Any]]:
        # Simulate database query
        await asyncio.sleep(0.05)
        return [{"order_id": "123", "amount": 99.99}]

    try:
        # These calls automatically get appropriate resilience patterns
        user = await resilient_internal_call(
            fetch_user_profile, "user123", name="user_service_get_profile"
        )

        weather = await resilient_external_call(
            fetch_weather_data, "London", name="weather_api_get_data"
        )

        orders = await resilient_database_call(get_user_orders, "user123", name="orders_db_query")

        logger.info("Successfully retrieved: user=%s, weather=%s, orders=%s", user, weather, orders)

    except Exception as e:
        logger.error("Service calls failed: %s", e)


# Example 2: Using the manager directly with custom configuration
async def example_custom_resilience():
    """Demonstrate using the manager directly with custom configurations."""

    # Create custom configuration
    config = ConsolidatedResilienceConfig(
        # Circuit breaker settings
        circuit_breaker_failure_threshold=3,
        circuit_breaker_recovery_timeout=30.0,
        # Retry settings
        retry_max_attempts=5,
        retry_base_delay=0.5,
        retry_exponential_base=1.5,
        # Timeout settings
        timeout_seconds=15.0,
        # Enable bulkhead for this use case
        bulkhead_enabled=True,
        bulkhead_max_concurrent=10,
        # Strategy-specific overrides
        strategy_overrides={
            ResilienceStrategy.EXTERNAL_SERVICE: {
                "timeout_seconds": 30.0,
                "retry_max_attempts": 3,
                "circuit_breaker_failure_threshold": 5,
            }
        },
    )

    # Create manager with custom config
    manager = ConsolidatedResilienceManager(config)

    # Example function that might fail
    async def unreliable_external_call(data: str) -> str:
        # Simulate potential failure
        if random.random() < 0.3:
            raise Exception("Simulated external service failure")
        await asyncio.sleep(0.1)
        return f"Processed: {data}"

    try:
        result = await manager.execute_resilient(
            unreliable_external_call,
            "test_data",
            name="external_processor",
            strategy=ResilienceStrategy.EXTERNAL_SERVICE,
        )

        logger.info("Custom resilience call succeeded: %s", result)

        # Get metrics
        metrics = manager.get_metrics()
        logger.info("Resilience metrics: %s", metrics)

    except Exception as e:
        logger.error("Custom resilience call failed: %s", e)


# Example 3: Using the decorator pattern
def example_decorator_usage():
    """Demonstrate using the resilient_call decorator."""

    # Create a manager with defaults
    manager = create_resilience_manager_with_defaults()

    # Apply resilience patterns using decorator
    @manager.resilient_call(name="payment_service", strategy=ResilienceStrategy.EXTERNAL_SERVICE)
    async def process_payment(amount: float, currency: str) -> dict[str, Any]:
        # Simulate payment processing
        await asyncio.sleep(0.2)
        if amount > 1000:
            raise Exception("Amount too large for processing")
        return {"transaction_id": "txn_123", "status": "completed"}

    @manager.resilient_call(name="user_cache", strategy=ResilienceStrategy.CACHE)
    async def get_cached_user(user_id: str) -> dict[str, Any] | None:
        # Simulate cache lookup
        await asyncio.sleep(0.01)
        return {"user_id": user_id, "cached_at": "2023-10-17T10:00:00Z"}

    return process_payment, get_cached_user


# Example 4: Migration from old resilient decorator
async def example_migration_from_old_decorator():
    """Show how to migrate from the old stubbed resilient decorator."""

    # OLD WAY (deprecated, had stubbed implementations):
    # @resilient(
    #     circuit_breaker_config=CircuitBreakerConfig(...),
    #     bulkhead_config=BulkheadConfig(...),
    #     timeout=30.0
    # )
    # async def old_service_call():
    #     pass

    # NEW WAY (consolidated manager):
    manager = get_resilience_manager()

    @manager.resilient_call(name="migrated_service", strategy=ResilienceStrategy.INTERNAL_SERVICE)
    async def new_service_call(request_id: str) -> dict[str, Any]:
        """Service call with comprehensive resilience patterns."""
        await asyncio.sleep(0.1)
        return {"request_id": request_id, "processed": True}

    try:
        result = await new_service_call("req_123")
        logger.info("Migrated service call result: %s", result)
    except Exception as e:
        logger.error("Migrated service call failed: %s", e)


# Example 5: Configuration for different environments
def get_resilience_config_for_environment(env: str) -> ConsolidatedResilienceConfig:
    """Get resilience configuration based on environment."""

    if env == "development":
        return ConsolidatedResilienceConfig(
            circuit_breaker_failure_threshold=10,  # More lenient
            retry_max_attempts=2,  # Fewer retries
            timeout_seconds=60.0,  # Longer timeouts
            bulkhead_enabled=False,  # Disable bulkhead
        )

    elif env == "staging":
        return ConsolidatedResilienceConfig(
            circuit_breaker_failure_threshold=5,
            retry_max_attempts=3,
            timeout_seconds=30.0,
            bulkhead_enabled=True,
            bulkhead_max_concurrent=50,
        )

    elif env == "production":
        return ConsolidatedResilienceConfig(
            circuit_breaker_failure_threshold=3,  # Strict
            retry_max_attempts=3,
            timeout_seconds=15.0,  # Tight timeouts
            bulkhead_enabled=True,
            bulkhead_max_concurrent=100,
            # Production-specific strategy overrides
            strategy_overrides={
                ResilienceStrategy.DATABASE: {
                    "timeout_seconds": 5.0,
                    "retry_max_attempts": 2,
                    "circuit_breaker_failure_threshold": 2,
                },
                ResilienceStrategy.CACHE: {
                    "timeout_seconds": 1.0,
                    "retry_max_attempts": 1,
                    "circuit_breaker_failure_threshold": 5,
                },
            },
        )

    else:
        # Default configuration
        return ConsolidatedResilienceConfig()


async def main():
    """Run all examples."""

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    logger.info("=== Consolidated Resilience Manager Examples ===")

    # Example 1: Strategy-specific helpers
    logger.info("\n1. Strategy-specific helper functions:")
    await example_service_calls()

    # Example 2: Custom configuration
    logger.info("\n2. Custom resilience configuration:")
    await example_custom_resilience()

    # Example 3: Decorator pattern
    logger.info("\n3. Decorator pattern usage:")
    process_payment, get_cached_user = example_decorator_usage()
    try:
        payment_result = await process_payment(500.0, "USD")
        cache_result = await get_cached_user("user456")
        logger.info("Decorator results: payment=%s, cache=%s", payment_result, cache_result)
    except Exception as e:
        logger.error("Decorator example failed: %s", e)

    # Example 4: Migration
    logger.info("\n4. Migration from old decorator:")
    await example_migration_from_old_decorator()

    # Example 5: Environment configuration
    logger.info("\n5. Environment-specific configuration:")
    prod_config = get_resilience_config_for_environment("production")
    logger.info(
        "Production config created with %d failure threshold",
        prod_config.circuit_breaker_failure_threshold,
    )

    logger.info("\n=== Examples completed ===")


if __name__ == "__main__":
    asyncio.run(main())
