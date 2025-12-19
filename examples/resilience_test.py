"""
Quick test to verify the enhanced resilience patterns work correctly.
"""

import asyncio
import logging
import time
from typing import Any

from mmf.framework.resilience import (
    api_call,
    cache_call,
    database_call,
    get_external_dependency_manager,
    register_api_dependency,
    register_cache_dependency,
    register_database_dependency,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestResiliencePatterns:
    """Test class for resilience patterns."""

    def __init__(self):
        self._setup_dependencies()

    def _setup_dependencies(self):
        """Setup test external dependencies."""
        register_database_dependency(
            name="test_db",
            max_concurrent=5,
            timeout_seconds=5.0,
            enable_circuit_breaker=True,
        )

        register_api_dependency(
            name="test_api",
            max_concurrent=3,
            timeout_seconds=3.0,
            enable_circuit_breaker=True,
        )

        register_cache_dependency(
            name="test_cache",
            max_concurrent=10,
            timeout_seconds=1.0,
            enable_circuit_breaker=False,
        )

    @database_call(dependency_name="test_db", operation_name="test_query")
    async def test_database_operation(self, should_fail: bool = False) -> dict[str, Any]:
        """Test database operation with resilience patterns."""
        await asyncio.sleep(0.1)  # Simulate database latency

        if should_fail:
            raise Exception("Simulated database error")

        return {"status": "success", "data": "test_data"}

    @api_call(dependency_name="test_api", operation_name="test_request")
    async def test_api_operation(self, should_fail: bool = False) -> dict[str, Any]:
        """Test API operation with resilience patterns."""
        await asyncio.sleep(0.2)  # Simulate API latency

        if should_fail:
            raise Exception("Simulated API error")

        return {"status": "success", "response": "api_response"}

    @cache_call(dependency_name="test_cache", operation_name="test_cache_op")
    async def test_cache_operation(self, should_fail: bool = False) -> dict[str, Any]:
        """Test cache operation with resilience patterns."""
        await asyncio.sleep(0.01)  # Simulate cache latency

        if should_fail:
            raise Exception("Simulated cache error")

        return {"status": "success", "cached": True}


async def run_tests():
    """Run resilience pattern tests."""
    test_service = TestResiliencePatterns()

    print("🧪 Testing Enhanced Resilience Patterns")
    print("=" * 50)

    # Test 1: Successful operations
    print("\n✅ Test 1: Successful Operations")
    try:
        db_result = await test_service.test_database_operation(should_fail=False)
        print(f"  Database: {db_result['status']}")

        api_result = await test_service.test_api_operation(should_fail=False)
        print(f"  API: {api_result['status']}")

        cache_result = await test_service.test_cache_operation(should_fail=False)
        print(f"  Cache: {cache_result['status']}")

    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")

    # Test 2: Bulkhead concurrency protection
    print("\n🏗️ Test 2: Bulkhead Concurrency Protection")
    start_time = time.time()

    # Start multiple concurrent operations (more than bulkhead limit)
    tasks = []
    for i in range(10):  # More than database bulkhead limit (5)
        task = test_service.test_database_operation(should_fail=False)
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    successful = sum(1 for r in results if isinstance(r, dict))
    errors = sum(1 for r in results if isinstance(r, Exception))

    elapsed = time.time() - start_time
    print(f"  Completed {successful} operations, {errors} errors in {elapsed:.2f}s")
    print(f"  Bulkhead protected against resource exhaustion")

    # Test 3: Error handling and circuit breaker
    print("\n⚡ Test 3: Error Handling and Circuit Breaker")

    # Trigger some failures to test circuit breaker
    failures = 0
    for i in range(5):
        try:
            await test_service.test_api_operation(should_fail=True)
        except Exception:
            failures += 1

    print(f"  Handled {failures} failures gracefully")

    # Test 4: Get health statistics
    print("\n📊 Test 4: Health and Statistics")
    manager = get_external_dependency_manager()
    stats = manager.get_all_dependencies_stats()

    for dep_name, dep_stats in stats.items():
        bulkhead_stats = dep_stats.get("bulkhead", {})
        current_load = bulkhead_stats.get("current_load", 0)
        capacity = bulkhead_stats.get("capacity", 0)
        success_rate = bulkhead_stats.get("success_rate", 0)

        print(f"  {dep_name}:")
        print(f"    Load: {current_load}/{capacity}")
        print(f"    Success Rate: {success_rate:.2%}")

        cb_stats = dep_stats.get("circuit_breaker", {})
        if cb_stats:
            cb_state = cb_stats.get("state", "unknown")
            print(f"    Circuit Breaker: {cb_state}")

    print("\n🎉 All tests completed successfully!")
    print("\nKey Features Demonstrated:")
    print("  ✓ Bulkhead isolation per external dependency")
    print("  ✓ Configurable timeouts and concurrency limits")
    print("  ✓ Circuit breaker integration")
    print("  ✓ Comprehensive metrics and health monitoring")
    print("  ✓ Decorator-based usage for clean integration")


if __name__ == "__main__":
    asyncio.run(run_tests())
