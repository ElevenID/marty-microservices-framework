#!/usr/bin/env python3
"""
Petstore Resilience Demo Runner

Demonstrates the enhanced resilience framework with bulkheads, timeouts,
circuit breakers, and external dependency management in the petstore domain.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from app.services.enhanced_petstore_service import EnhancedPetstoreDomainService
from app.services.petstore_resilience_service import (
    PetstoreResilienceManager,
    PetstoreResilientOperations,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import petstore services
try:
    SERVICES_AVAILABLE = True
except ImportError as e:
    SERVICES_AVAILABLE = False
    logger.error(f"Could not import petstore services: {e}")


class PetstoreResilienceDemo:
    """Demonstrates resilience patterns in the petstore domain."""

    def __init__(self, config_path: str = "config/enhanced_config.yaml"):
        """Initialize the demo with configuration."""
        self.config_path = config_path
        self.config = self._load_config()
        self.service = None
        self.start_time = datetime.utcnow()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                logger.warning(f"Config file {self.config_path} not found, using default config")
                return self._get_default_config()

            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {self.config_path}")
                return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration for the demo."""
        return {
            "resilience": {
                "bulkheads": {
                    "database": {"type": "semaphore", "max_concurrent": 10},
                    "external_api": {"type": "thread_pool", "max_workers": 5},
                    "cache": {"type": "semaphore", "max_concurrent": 100},
                    "message_queue": {"type": "semaphore", "max_concurrent": 20},
                    "file_system": {"type": "semaphore", "max_concurrent": 8}
                },
                "timeouts": {
                    "database_seconds": 10.0,
                    "api_seconds": 15.0,
                    "cache_seconds": 2.0,
                    "message_queue_seconds": 5.0,
                    "file_system_seconds": 30.0
                },
                "external_dependencies": {
                    "petstore_database": {
                        "max_concurrent": 10,
                        "timeout_seconds": 10.0,
                        "enable_circuit_breaker": True
                    },
                    "payment_gateway": {
                        "max_concurrent": 5,
                        "timeout_seconds": 25.0,
                        "enable_circuit_breaker": True
                    },
                    "redis_cache": {
                        "max_concurrent": 100,
                        "timeout_seconds": 1.5,
                        "enable_circuit_breaker": False
                    },
                    "kafka_events": {
                        "max_concurrent": 20,
                        "timeout_seconds": 8.0,
                        "enable_circuit_breaker": True
                    },
                    "ml_pet_advisor": {
                        "max_concurrent": 6,
                        "timeout_seconds": 30.0,
                        "enable_circuit_breaker": True
                    }
                }
            }
        }

    async def initialize_service(self) -> bool:
        """Initialize the petstore service with resilience."""
        if not SERVICES_AVAILABLE:
            logger.error("Petstore services not available")
            return False

        try:
            self.service = EnhancedPetstoreDomainService(config=self.config)
            logger.info("Enhanced Petstore service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize service: {e}")
            return False

    async def demo_basic_resilience_health(self):
        """Demonstrate basic resilience health check."""
        print("\n" + "="*60)
        print("RESILIENCE HEALTH CHECK")
        print("="*60)

        if not self.service:
            print("❌ Service not initialized")
            return

        try:
            health = await self.service.get_resilience_health()
            print(json.dumps(health, indent=2))
        except Exception as e:
            print(f"❌ Health check failed: {e}")

    async def demo_resilient_pet_operations(self):
        """Demonstrate resilient pet operations."""
        print("\n" + "="*60)
        print("RESILIENT PET OPERATIONS")
        print("="*60)

        if not self.service:
            print("❌ Service not initialized")
            return

        try:
            # Test getting pet with cache and recommendations
            print("\n🔍 Getting pet with cache and ML recommendations...")
            pet_result = await self.service.get_pet_with_cache_and_recommendations(
                pet_id="demo_pet_123",
                customer_id="customer_456"
            )
            print("✅ Pet retrieval successful:")
            print(json.dumps(pet_result, indent=2))

        except Exception as e:
            print(f"❌ Pet operations failed: {e}")

    async def demo_resilient_order_creation(self):
        """Demonstrate resilient order creation."""
        print("\n" + "="*60)
        print("RESILIENT ORDER CREATION")
        print("="*60)

        if not self.service:
            print("❌ Service not initialized")
            return

        try:
            print("\n📦 Creating order with full resilience patterns...")
            order_result = await self.service.create_order_with_resilience(
                customer_id="demo_customer_789",
                pet_id="premium_pet_001",
                payment_data={
                    "payment_method": "credit_card",
                    "amount": 499.99,
                    "currency": "USD"
                }
            )
            print("✅ Order creation successful:")
            print(json.dumps(order_result, indent=2))

        except Exception as e:
            print(f"❌ Order creation failed: {e}")

    async def demo_resilience_scenarios(self):
        """Demonstrate various resilience scenarios."""
        print("\n" + "="*60)
        print("RESILIENCE SCENARIO SIMULATION")
        print("="*60)

        if not self.service:
            print("❌ Service not initialized")
            return

        try:
            print("\n🧪 Running resilience scenario tests...")
            scenarios_result = await self.service.simulate_resilience_scenarios()
            print("✅ Scenario simulation completed:")
            print(json.dumps(scenarios_result, indent=2))

        except Exception as e:
            print(f"❌ Scenario simulation failed: {e}")

    async def demo_bulkhead_isolation(self):
        """Demonstrate bulkhead isolation under load."""
        print("\n" + "="*60)
        print("BULKHEAD ISOLATION DEMO")
        print("="*60)

        if not self.service or not self.service.resilient_operations:
            print("❌ Resilient operations not available")
            return

        try:
            print("\n🚧 Testing bulkhead isolation with concurrent requests...")

            # Create multiple concurrent tasks for different dependency types
            database_tasks = [
                self.service.resilient_operations.get_pet_from_database(f"bulkhead_test_{i}")
                for i in range(15)  # More than the bulkhead limit
            ]

            api_tasks = [
                self.service.resilient_operations.process_payment_external({
                    "customer_id": f"load_test_customer_{i}",
                    "amount": 99.99
                })
                for i in range(8)  # More than the bulkhead limit
            ]

            cache_tasks = [
                self.service.resilient_operations.get_pet_catalog_from_cache(f"category_{i}")
                for i in range(50)  # Within the bulkhead limit
            ]

            print(f"📊 Executing {len(database_tasks)} database, {len(api_tasks)} API, and {len(cache_tasks)} cache operations...")

            # Execute all tasks concurrently and measure timing
            start_time = asyncio.get_event_loop().time()

            # Gather results with exceptions
            db_results = await asyncio.gather(*database_tasks, return_exceptions=True)
            api_results = await asyncio.gather(*api_tasks, return_exceptions=True)
            cache_results = await asyncio.gather(*cache_tasks, return_exceptions=True)

            end_time = asyncio.get_event_loop().time()

            # Analyze results
            db_successes = sum(1 for r in db_results if not isinstance(r, Exception))
            api_successes = sum(1 for r in api_results if not isinstance(r, Exception))
            cache_successes = sum(1 for r in cache_results if not isinstance(r, Exception))

            print(f"\n📈 Bulkhead Isolation Results:")
            print(f"   Database: {db_successes}/{len(database_tasks)} successful")
            print(f"   API: {api_successes}/{len(api_tasks)} successful")
            print(f"   Cache: {cache_successes}/{len(cache_tasks)} successful")
            print(f"   Total execution time: {end_time - start_time:.2f} seconds")

            # Get updated health status
            health = await self.service.get_resilience_health()
            print(f"\n🏥 Post-load Health Status:")
            for dep_name, dep_health in health.get("dependencies", {}).items():
                print(f"   {dep_name}: {dep_health.get('status')} "
                     f"({dep_health.get('bulkhead_utilization')}, "
                     f"success_rate: {dep_health.get('success_rate')})")

        except Exception as e:
            print(f"❌ Bulkhead isolation demo failed: {e}")

    async def run_full_demo(self):
        """Run the complete resilience demonstration."""
        print("🚀 PETSTORE RESILIENCE FRAMEWORK DEMO")
        print("="*60)
        print(f"Demo started at: {self.start_time}")
        print("="*60)

        # Initialize service
        if not await self.initialize_service():
            print("❌ Failed to initialize service, aborting demo")
            return

        # Run demo sections
        await self.demo_basic_resilience_health()
        await asyncio.sleep(1)  # Brief pause between demos

        await self.demo_resilient_pet_operations()
        await asyncio.sleep(1)

        await self.demo_resilient_order_creation()
        await asyncio.sleep(1)

        await self.demo_bulkhead_isolation()
        await asyncio.sleep(1)

        await self.demo_resilience_scenarios()

        # Final status
        print("\n" + "="*60)
        print("DEMO SUMMARY")
        print("="*60)

        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()

        print(f"✅ Demo completed successfully!")
        print(f"📊 Total duration: {duration:.2f} seconds")
        print(f"🔧 Resilience features demonstrated:")
        print("   • Bulkhead isolation (semaphore & thread-pool)")
        print("   • Timeout management per dependency type")
        print("   • Circuit breaker integration")
        print("   • External dependency management")
        print("   • Comprehensive health monitoring")
        print("   • Load testing and concurrent operations")

        # Final health check
        try:
            final_health = await self.service.get_resilience_health()
            overall_status = final_health.get("overall_status", "unknown")
            print(f"🏥 Final system health: {overall_status}")
        except Exception as e:
            print(f"⚠️  Could not get final health status: {e}")


async def main():
    """Main demo execution."""
    # Change to the plugin directory
    plugin_dir = Path(__file__).parent
    os.chdir(plugin_dir)

    demo = PetstoreResilienceDemo()
    await demo.run_full_demo()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\n❌ Demo failed with error: {e}")
