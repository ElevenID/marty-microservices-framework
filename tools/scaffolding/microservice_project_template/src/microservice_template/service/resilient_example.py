"""
Example Service with Comprehensive Resilience Patterns

This example demonstrates how to properly integrate bulkheads, timeouts,
circuit breakers, and other resilience patterns in a microservice.
"""

import asyncio
import logging
import random
from typing import Any

# Import resilience patterns for robust service design
from marty_msf.framework.resilience import (
    BulkheadConfig,
    CircuitBreakerConfig,
    ResilienceConfig,
    RetryConfig,
    TimeoutConfig,
    api_call,
    cache_call,
    database_call,
    get_external_dependency_manager,
    register_api_dependency,
    register_cache_dependency,
    register_database_dependency,
    resilience_pattern,
)

logger = logging.getLogger(__name__)


class ResilientExternalService:
    """Example service demonstrating resilience patterns for external dependencies."""

    def __init__(self):
        """Initialize the service with resilience patterns."""
        self._setup_resilience_patterns()
        logger.info("ResilientExternalService initialized with resilience patterns")

    def _setup_resilience_patterns(self) -> None:
        """Setup resilience patterns for external dependencies."""
        # Register database dependency with bulkhead and circuit breaker
        register_database_dependency(
            name="user_database",
            max_concurrent=10,
            timeout_seconds=10.0,
            enable_circuit_breaker=True,
        )

        # Register payment API with strict limits
        register_api_dependency(
            name="payment_gateway",
            max_concurrent=5,  # Limited concurrency for payment operations
            timeout_seconds=20.0,
            enable_circuit_breaker=True,
        )

        # Register notification service API
        register_api_dependency(
            name="notification_service",
            max_concurrent=15,
            timeout_seconds=10.0,
            enable_circuit_breaker=True,
        )

        # Register cache with high concurrency
        register_cache_dependency(
            name="session_cache",
            max_concurrent=100,
            timeout_seconds=1.0,
            enable_circuit_breaker=False,  # Cache failures shouldn't circuit break
        )

    # Database operations with resilience
    @database_call(dependency_name="user_database", operation_name="get_user")
    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Get user data from database with resilience patterns."""
        # Simulate database call
        await asyncio.sleep(0.1)
        if user_id == "error":
            raise Exception("Database connection failed")

        return {
            "user_id": user_id,
            "name": f"User {user_id}",
            "email": f"user{user_id}@example.com",
        }

    @database_call(dependency_name="user_database", operation_name="save_user")
    async def save_user(self, user_data: dict[str, Any]) -> bool:
        """Save user data to database with resilience patterns."""
        # Simulate database write
        await asyncio.sleep(0.2)
        logger.info("User saved: %s", user_data.get("user_id"))
        return True

    # External API calls with resilience
    @api_call(dependency_name="payment_gateway", operation_name="process_payment")
    async def process_payment(self, payment_data: dict[str, Any]) -> dict[str, Any]:
        """Process payment with external gateway using resilience patterns."""
        # Simulate external API call
        await asyncio.sleep(0.5)  # Payment processing takes longer

        if payment_data.get("amount", 0) > 10000:
            raise Exception("Payment gateway error: Amount too high")

        return {
            "transaction_id": f"txn_{payment_data.get('user_id')}_{payment_data.get('amount')}",
            "status": "completed",
            "amount": payment_data.get("amount"),
        }

    @api_call(dependency_name="notification_service", operation_name="send_notification")
    async def send_notification(self, notification_data: dict[str, Any]) -> bool:
        """Send notification using external service with resilience patterns."""
        # Simulate notification API call
        await asyncio.sleep(0.1)

        logger.info("Notification sent: %s", notification_data.get("message"))
        return True

    # Cache operations with resilience
    @cache_call(dependency_name="session_cache", operation_name="get_session")
    async def get_user_session(self, session_id: str) -> dict[str, Any] | None:
        """Get user session from cache with resilience patterns."""
        # Simulate cache lookup
        await asyncio.sleep(0.01)

        # Simulate cache miss 50% of the time
        if random.random() < 0.5:
            return None

        return {
            "session_id": session_id,
            "user_id": f"user_{session_id[-3:]}",
            "expires_at": "2024-12-31T23:59:59Z",
        }

    @cache_call(dependency_name="session_cache", operation_name="store_session")
    async def store_user_session(self, session_data: dict[str, Any]) -> bool:
        """Store user session in cache with resilience patterns."""
        # Simulate cache write
        await asyncio.sleep(0.01)
        logger.info("Session stored: %s", session_data.get("session_id"))
        return True

    # Complex business operation combining multiple dependencies
    @resilience_pattern(
        config=ResilienceConfig(
            timeout_seconds=30.0,
            retry_config=RetryConfig(max_attempts=3, base_delay=1.0),
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=5),
        ),
        operation_name="complete_user_transaction"
    )
    async def complete_user_transaction(
        self,
        user_id: str,
        payment_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Complete a user transaction involving multiple external dependencies.

        This method demonstrates how to combine multiple resilient operations
        within a single business transaction.
        """
        result = {"user_id": user_id, "steps_completed": []}

        try:
            # Step 1: Get user data
            user = await self.get_user_by_id(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            result["user"] = user
            result["steps_completed"].append("user_retrieved")

            # Step 2: Process payment
            payment_result = await self.process_payment({
                **payment_data,
                "user_id": user_id,
            })
            result["payment"] = payment_result
            result["steps_completed"].append("payment_processed")

            # Step 3: Update user data
            user["last_transaction"] = payment_result["transaction_id"]
            await self.save_user(user)
            result["steps_completed"].append("user_updated")

            # Step 4: Send notification (non-critical, fire-and-forget)
            try:
                await self.send_notification({
                    "user_id": user_id,
                    "message": f"Payment of {payment_data.get('amount')} processed successfully",
                    "type": "payment_confirmation",
                })
                result["steps_completed"].append("notification_sent")
            except Exception as e:
                # Don't fail the transaction if notification fails
                logger.warning("Failed to send notification: %s", str(e))
                result["notification_error"] = str(e)

            result["status"] = "completed"
            result["transaction_id"] = payment_result["transaction_id"]

            return result

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.error("Transaction failed for user %s: %s", user_id, str(e))
            raise

    async def get_service_health(self) -> dict[str, Any]:
        """Get health status including resilience patterns statistics."""
        manager = get_external_dependency_manager()
        stats = manager.get_all_dependencies_stats()

        health = {
            "service": "ResilientExternalService",
            "status": "healthy",
            "dependencies": {},
            "timestamp": asyncio.get_event_loop().time(),
        }

        for dep_name, dep_stats in stats.items():
            health["dependencies"][dep_name] = {
                "status": "healthy" if dep_stats.get("bulkhead", {}).get("success_rate", 0) > 0.8 else "degraded",
                "bulkhead_load": dep_stats.get("bulkhead", {}).get("current_load", 0),
                "bulkhead_capacity": dep_stats.get("bulkhead", {}).get("capacity", 0),
                "success_rate": dep_stats.get("bulkhead", {}).get("success_rate", 0),
                "circuit_breaker_state": dep_stats.get("circuit_breaker", {}).get("state", "unknown"),
            }

        return health


# Example usage and testing
async def example_usage():
    """Demonstrate the resilient service in action."""
    service = ResilientExternalService()

    print("=== Resilient Service Example ===")

    # Example 1: Successful transaction
    try:
        result = await service.complete_user_transaction(
            user_id="user123",
            payment_data={"amount": 100.0, "currency": "USD"}
        )
        print("✓ Successful transaction:", result["status"])
        print(f"  Transaction ID: {result.get('transaction_id')}")
        print(f"  Steps completed: {', '.join(result['steps_completed'])}")
    except Exception as e:
        print("✗ Transaction failed:", str(e))

    # Example 2: Failed transaction (high amount)
    try:
        result = await service.complete_user_transaction(
            user_id="user456",
            payment_data={"amount": 15000.0, "currency": "USD"}
        )
        print("✓ High amount transaction:", result["status"])
    except Exception as e:
        print("✗ High amount transaction failed:", str(e))

    # Example 3: Database error
    try:
        result = await service.complete_user_transaction(
            user_id="error",
            payment_data={"amount": 50.0, "currency": "USD"}
        )
        print("✓ Error user transaction:", result["status"])
    except Exception as e:
        print("✗ Error user transaction failed:", str(e))

    # Show service health
    health = await service.get_service_health()
    print(f"\n=== Service Health ===")
    print(f"Service status: {health['status']}")
    for dep_name, dep_health in health["dependencies"].items():
        print(f"  {dep_name}: {dep_health['status']} "
              f"({dep_health['bulkhead_load']}/{dep_health['bulkhead_capacity']} load, "
              f"{dep_health['success_rate']:.2%} success rate)")


if __name__ == "__main__":
    # Run the example
    asyncio.run(example_usage())
