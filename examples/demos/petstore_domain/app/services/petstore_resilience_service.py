"""
Petstore Resilience Manager

Manages resilience patterns including bulkheads, timeouts, and circuit breakers
for all external dependencies in the petstore domain.
"""

import asyncio
import logging
import random
from typing import Any

from marty_msf.framework.resilience import (
    BulkheadConfig,
    CircuitBreakerConfig,
    DependencyType,
    ExternalDependencyManager,
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

# Import the enhanced resilience framework
try:
    RESILIENCE_AVAILABLE = True
except ImportError:
    # Fallback for when resilience framework is not available
    RESILIENCE_AVAILABLE = False
    print("Resilience framework not available, using basic implementation")

logger = logging.getLogger(__name__)


class PetstoreResilienceManager:
    """Manages resilience patterns for the petstore domain."""

    def __init__(self, config: dict[str, Any]):
        """Initialize the resilience manager with configuration."""
        self.config = config
        self.resilience_config = config.get("resilience", {})
        self.external_deps_config = self.resilience_config.get("external_dependencies", {})

        if RESILIENCE_AVAILABLE:
            self._setup_external_dependencies()
            logger.info("Petstore resilience patterns initialized")
        else:
            logger.warning("Resilience framework not available, using fallback implementation")

    def _setup_external_dependencies(self) -> None:
        """Setup external dependencies with appropriate resilience patterns."""
        if not RESILIENCE_AVAILABLE:
            return

        # Register database dependency
        db_config = self.external_deps_config.get("petstore_database", {})
        register_database_dependency(
            name="petstore_database",
            max_concurrent=db_config.get("max_concurrent", 10),
            timeout_seconds=db_config.get("timeout_seconds", 10.0),
            enable_circuit_breaker=db_config.get("enable_circuit_breaker", True),
        )

        # Register payment gateway API
        payment_config = self.external_deps_config.get("payment_gateway", {})
        register_api_dependency(
            name="payment_gateway",
            max_concurrent=payment_config.get("max_concurrent", 5),
            timeout_seconds=payment_config.get("timeout_seconds", 25.0),
            enable_circuit_breaker=payment_config.get("enable_circuit_breaker", True),
        )

        # Register Redis cache
        cache_config = self.external_deps_config.get("redis_cache", {})
        register_cache_dependency(
            name="redis_cache",
            max_concurrent=cache_config.get("max_concurrent", 100),
            timeout_seconds=cache_config.get("timeout_seconds", 1.5),
            enable_circuit_breaker=cache_config.get("enable_circuit_breaker", False),
        )

        # Register Kafka message queue
        kafka_config = self.external_deps_config.get("kafka_events", {})
        register_api_dependency(  # Using API dependency for message queue
            name="kafka_events",
            max_concurrent=kafka_config.get("max_concurrent", 20),
            timeout_seconds=kafka_config.get("timeout_seconds", 8.0),
            enable_circuit_breaker=kafka_config.get("enable_circuit_breaker", True),
        )

        # Register ML Pet Advisor service
        ml_config = self.external_deps_config.get("ml_pet_advisor", {})
        register_api_dependency(
            name="ml_pet_advisor",
            max_concurrent=ml_config.get("max_concurrent", 6),
            timeout_seconds=ml_config.get("timeout_seconds", 30.0),
            enable_circuit_breaker=ml_config.get("enable_circuit_breaker", True),
        )

        logger.info("All external dependencies registered with resilience patterns")

    async def get_resilience_health(self) -> dict[str, Any]:
        """Get comprehensive resilience health status."""
        if not RESILIENCE_AVAILABLE:
            return {"status": "resilience_framework_unavailable"}

        manager = get_external_dependency_manager()
        stats = manager.get_all_dependencies_stats()

        health = {
            "service": "petstore_domain",
            "resilience_framework": "enabled",
            "timestamp": asyncio.get_event_loop().time(),
            "dependencies": {},
            "overall_status": "healthy",
        }

        degraded_count = 0

        for dep_name, dep_stats in stats.items():
            bulkhead_stats = dep_stats.get("bulkhead", {})
            cb_stats = dep_stats.get("circuit_breaker", {})

            current_load = bulkhead_stats.get("current_load", 0)
            capacity = bulkhead_stats.get("capacity", 0)
            success_rate = bulkhead_stats.get("success_rate", 1.0)
            cb_state = cb_stats.get("state", "unknown")

            # Determine dependency health
            dep_health = "healthy"
            if success_rate < 0.8 or cb_state == "open":
                dep_health = "degraded"
                degraded_count += 1
            elif current_load / max(capacity, 1) > 0.9:
                dep_health = "under_pressure"

            health["dependencies"][dep_name] = {
                "status": dep_health,
                "bulkhead_utilization": f"{current_load}/{capacity}",
                "success_rate": f"{success_rate:.2%}",
                "circuit_breaker_state": cb_state,
                "total_requests": bulkhead_stats.get("total_requests", 0),
                "rejected_requests": bulkhead_stats.get("rejected_requests", 0),
            }

        # Overall health assessment
        if degraded_count > 0:
            health["overall_status"] = "degraded"
        elif any(dep["status"] == "under_pressure" for dep in health["dependencies"].values()):
            health["overall_status"] = "under_pressure"

        return health


class PetstoreResilientOperations:
    """Resilient operations for the petstore domain using decorators."""

    def __init__(self, resilience_manager: PetstoreResilienceManager):
        self.resilience_manager = resilience_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    # Database operations with resilience
    @database_call(dependency_name="petstore_database", operation_name="get_pet")
    async def get_pet_from_database(self, pet_id: str) -> dict[str, Any] | None:
        """Get pet data from database with resilience patterns."""
        # Simulate database call
        await asyncio.sleep(0.1)
        self.logger.info(f"Retrieved pet {pet_id} from database")

        if pet_id == "error_pet":
            raise Exception("Database connection failed")

        return {
            "pet_id": pet_id,
            "name": f"Pet {pet_id}",
            "category": "dog",
            "price": 299.99,
            "availability": "available"
        }

    @database_call(dependency_name="petstore_database", operation_name="save_order")
    async def save_order_to_database(self, order_data: dict[str, Any]) -> bool:
        """Save order to database with resilience patterns."""
        await asyncio.sleep(0.2)
        self.logger.info(f"Saved order {order_data.get('order_id')} to database")
        return True

    @database_call(dependency_name="petstore_database", operation_name="update_inventory")
    async def update_inventory_in_database(self, pet_id: str, quantity_change: int) -> bool:
        """Update inventory in database with resilience patterns."""
        await asyncio.sleep(0.15)
        self.logger.info(f"Updated inventory for pet {pet_id}: {quantity_change}")
        return True

    # External API operations with resilience
    @api_call(dependency_name="payment_gateway", operation_name="process_payment")
    async def process_payment_external(self, payment_data: dict[str, Any]) -> dict[str, Any]:
        """Process payment with external gateway using resilience patterns."""
        await asyncio.sleep(0.5)  # Payment processing takes longer

        amount = payment_data.get("amount", 0)
        if amount > 10000:
            raise Exception("Payment gateway error: Amount too high")

        transaction_id = f"txn_{payment_data.get('customer_id')}_{amount}"
        self.logger.info(f"Processed payment: {transaction_id}")

        return {
            "transaction_id": transaction_id,
            "status": "completed",
            "amount": amount,
            "gateway_response": "approved"
        }

    @api_call(dependency_name="ml_pet_advisor", operation_name="get_recommendation")
    async def get_pet_recommendation_external(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        """Get pet recommendations from ML service with resilience patterns."""
        await asyncio.sleep(0.8)  # ML processing takes time

        self.logger.info(f"Generated pet recommendations for customer {customer_data.get('customer_id')}")

        # Simulate ML recommendation
        recommendations = [
            {"pet_id": "rec_001", "breed": "Golden Retriever", "confidence": 0.92},
            {"pet_id": "rec_002", "breed": "Labrador", "confidence": 0.88},
            {"pet_id": "rec_003", "breed": "Beagle", "confidence": 0.84},
        ]

        return {
            "customer_id": customer_data.get("customer_id"),
            "recommendations": recommendations,
            "algorithm_version": "v2.1",
        }

    # Cache operations with resilience
    @cache_call(dependency_name="redis_cache", operation_name="get_pet_catalog")
    async def get_pet_catalog_from_cache(self, category: str) -> dict[str, Any] | None:
        """Get pet catalog from cache with resilience patterns."""
        await asyncio.sleep(0.01)

        # Simulate cache hit/miss
        if random.random() < 0.7:  # 70% cache hit rate
            self.logger.info(f"Cache hit for pet catalog: {category}")
            return {
                "category": category,
                "pets": [f"pet_{i}" for i in range(1, 6)],
                "cached_at": asyncio.get_event_loop().time(),
            }
        else:
            self.logger.info(f"Cache miss for pet catalog: {category}")
            return None

    @cache_call(dependency_name="redis_cache", operation_name="cache_order_status")
    async def cache_order_status(self, order_id: str, status: str) -> bool:
        """Cache order status with resilience patterns."""
        await asyncio.sleep(0.01)
        self.logger.info(f"Cached order status: {order_id} -> {status}")
        return True

    # Message queue operations with resilience
    @api_call(dependency_name="kafka_events", operation_name="publish_order_event")
    async def publish_order_event(self, event_data: dict[str, Any]) -> bool:
        """Publish order event to Kafka with resilience patterns."""
        await asyncio.sleep(0.1)
        self.logger.info(f"Published order event: {event_data.get('event_type')}")
        return True

    # Complex business operation combining multiple dependencies
    @resilience_pattern(
        config=ResilienceConfig(
            timeout_seconds=45.0,
            retry_config=RetryConfig(max_attempts=3, base_delay=1.0),
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=5),
        ),
        operation_name="complete_pet_order_with_recommendations"
    )
    async def complete_pet_order_with_recommendations(
        self,
        customer_id: str,
        pet_id: str,
        payment_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Complete a pet order with ML recommendations and full resilience patterns.

        This demonstrates combining multiple resilient operations in a business transaction.
        """
        result = {
            "customer_id": customer_id,
            "pet_id": pet_id,
            "steps_completed": [],
            "timestamp": asyncio.get_event_loop().time(),
        }

        try:
            # Step 1: Get pet details
            pet_data = await self.get_pet_from_database(pet_id)
            if not pet_data:
                raise ValueError(f"Pet {pet_id} not found")
            result["pet_data"] = pet_data
            result["steps_completed"].append("pet_retrieved")

            # Step 2: Check cache for similar order patterns
            cached_info = await self.get_pet_catalog_from_cache(pet_data["category"])
            if cached_info:
                result["catalog_cache"] = "hit"
            else:
                result["catalog_cache"] = "miss"
            result["steps_completed"].append("cache_checked")

            # Step 3: Get ML recommendations (non-critical)
            try:
                recommendations = await self.get_pet_recommendation_external({
                    "customer_id": customer_id,
                    "current_pet": pet_data,
                })
                result["ml_recommendations"] = recommendations
                result["steps_completed"].append("ml_recommendations_retrieved")
            except Exception as e:
                self.logger.warning(f"ML recommendations failed: {e}")
                result["ml_recommendations_error"] = str(e)

            # Step 4: Process payment
            payment_result = await self.process_payment_external({
                **payment_data,
                "customer_id": customer_id,
                "amount": pet_data["price"],
            })
            result["payment"] = payment_result
            result["steps_completed"].append("payment_processed")

            # Step 5: Update inventory
            await self.update_inventory_in_database(pet_id, -1)
            result["steps_completed"].append("inventory_updated")

            # Step 6: Save order
            order_data = {
                "order_id": f"order_{customer_id}_{pet_id}",
                "customer_id": customer_id,
                "pet_id": pet_id,
                "amount": pet_data["price"],
                "transaction_id": payment_result["transaction_id"],
                "status": "completed",
            }
            await self.save_order_to_database(order_data)
            result["order"] = order_data
            result["steps_completed"].append("order_saved")

            # Step 7: Cache order status
            await self.cache_order_status(order_data["order_id"], "completed")
            result["steps_completed"].append("order_status_cached")

            # Step 8: Publish event (fire-and-forget)
            try:
                await self.publish_order_event({
                    "event_type": "order_completed",
                    "order_id": order_data["order_id"],
                    "customer_id": customer_id,
                    "pet_id": pet_id,
                    "amount": pet_data["price"],
                })
                result["steps_completed"].append("event_published")
            except Exception as e:
                self.logger.warning(f"Event publishing failed: {e}")
                result["event_error"] = str(e)

            result["status"] = "completed"
            result["order_id"] = order_data["order_id"]

            return result

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            self.logger.error(f"Order completion failed for customer {customer_id}: {e}")
            raise
