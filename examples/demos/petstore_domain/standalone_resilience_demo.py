#!/usr/bin/env python3
"""
Standalone Petstore Resilience Demo

A simplified demo that works without the full MMF framework,
demonstrating the resilience patterns using mock implementations.
"""

import asyncio
import json
import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockSemaphoreBulkhead:
    """Mock semaphore bulkhead for demonstration."""

    def __init__(self, max_concurrent: int):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.current_load = 0
        self.total_requests = 0
        self.rejected_requests = 0
        self.successful_requests = 0
        self._lock = threading.Lock()

    async def __aenter__(self):
        try:
            # Check if we can acquire without blocking
            if self.semaphore.locked() and self.current_load >= self.max_concurrent:
                self.rejected_requests += 1
                raise Exception("Bulkhead capacity exceeded")

            await self.semaphore.acquire()

            with self._lock:
                self.current_load += 1
                self.total_requests += 1
            return self
        except Exception as e:
            if "capacity exceeded" not in str(e):
                self.rejected_requests += 1
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        with self._lock:
            self.current_load -= 1
            if exc_type is None:
                self.successful_requests += 1
        self.semaphore.release()

    def get_stats(self) -> dict[str, Any]:
        return {
            "type": "semaphore",
            "max_concurrent": self.max_concurrent,
            "current_load": self.current_load,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "rejected_requests": self.rejected_requests,
            "success_rate": self.successful_requests / max(self.total_requests, 1)
        }


class MockThreadPoolBulkhead:
    """Mock thread pool bulkhead for demonstration."""

    def __init__(self, max_workers: int):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.current_load = 0
        self.total_requests = 0
        self.rejected_requests = 0
        self.successful_requests = 0
        self._lock = threading.Lock()

    async def execute(self, func, *args, **kwargs):
        with self._lock:
            self.total_requests += 1
            if self.current_load >= self.max_workers:
                self.rejected_requests += 1
                raise Exception("Thread pool capacity exceeded")
            self.current_load += 1

        try:
            # Simulate async execution in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self.executor, func, *args, **kwargs)
            with self._lock:
                self.successful_requests += 1
            return result
        finally:
            with self._lock:
                self.current_load -= 1

    def get_stats(self) -> dict[str, Any]:
        return {
            "type": "thread_pool",
            "max_workers": self.max_workers,
            "current_load": self.current_load,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "rejected_requests": self.rejected_requests,
            "success_rate": self.successful_requests / max(self.total_requests, 1)
        }


class MockCircuitBreaker:
    """Mock circuit breaker for demonstration."""

    def __init__(self, failure_threshold: int = 5):
        self.failure_threshold = failure_threshold
        self.failure_count = 0
        self.state = "closed"  # closed, open, half-open
        self.last_failure_time = None
        self.recovery_timeout = 10  # seconds

    def record_success(self):
        self.failure_count = 0
        if self.state == "half-open":
            self.state = "closed"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"

    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        elif self.state == "open":
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        else:  # half-open
            return True

    def get_stats(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold
        }


class StandaloneResilienceDemo:
    """Standalone resilience demo with mock implementations."""

    def __init__(self):
        self.bulkheads = {
            "database": MockSemaphoreBulkhead(10),
            "payment_api": MockThreadPoolBulkhead(5),
            "cache": MockSemaphoreBulkhead(100),
            "message_queue": MockSemaphoreBulkhead(20),
            "ml_service": MockThreadPoolBulkhead(6)
        }

        self.circuit_breakers = {
            "database": MockCircuitBreaker(5),
            "payment_api": MockCircuitBreaker(3),
            "ml_service": MockCircuitBreaker(4)
        }

        self.timeouts = {
            "database": 2.0,
            "payment_api": 5.0,
            "cache": 0.5,
            "message_queue": 3.0,
            "ml_service": 8.0
        }

        logger.info("Standalone resilience demo initialized")

    async def simulate_database_call(self, operation: str) -> dict[str, Any]:
        """Simulate a database call with resilience patterns."""
        circuit_breaker = self.circuit_breakers["database"]

        if not circuit_breaker.can_execute():
            raise Exception("Circuit breaker is open for database")

        try:
            async with self.bulkheads["database"]:
                # Simulate database operation with timeout
                await asyncio.wait_for(
                    self._mock_database_operation(operation),
                    timeout=self.timeouts["database"]
                )
                circuit_breaker.record_success()
                return {
                    "operation": operation,
                    "status": "success",
                    "timestamp": datetime.utcnow().isoformat(),
                    "dependency": "database"
                }
        except Exception as e:
            circuit_breaker.record_failure()
            logger.error(f"Database operation failed: {e}")
            raise

    async def simulate_payment_api_call(self, amount: float) -> dict[str, Any]:
        """Simulate a payment API call with resilience patterns."""
        circuit_breaker = self.circuit_breakers["payment_api"]

        if not circuit_breaker.can_execute():
            raise Exception("Circuit breaker is open for payment API")

        try:
            # Use thread pool bulkhead for payment processing
            result = await self.bulkheads["payment_api"].execute(
                self._mock_payment_operation, amount
            )
            circuit_breaker.record_success()
            return result
        except Exception as e:
            circuit_breaker.record_failure()
            logger.error(f"Payment operation failed: {e}")
            raise

    async def simulate_cache_call(self, key: str) -> dict[str, Any]:
        """Simulate a cache call with resilience patterns."""
        try:
            async with self.bulkheads["cache"]:
                await asyncio.wait_for(
                    self._mock_cache_operation(key),
                    timeout=self.timeouts["cache"]
                )
                return {
                    "key": key,
                    "status": "hit" if random.random() > 0.3 else "miss",
                    "timestamp": datetime.utcnow().isoformat(),
                    "dependency": "cache"
                }
        except Exception as e:
            logger.warning(f"Cache operation failed: {e}")
            return {"key": key, "status": "error", "error": str(e)}

    async def simulate_ml_service_call(self, customer_id: str) -> dict[str, Any]:
        """Simulate an ML service call with resilience patterns."""
        circuit_breaker = self.circuit_breakers["ml_service"]

        if not circuit_breaker.can_execute():
            raise Exception("Circuit breaker is open for ML service")

        try:
            result = await self.bulkheads["ml_service"].execute(
                self._mock_ml_operation, customer_id
            )
            circuit_breaker.record_success()
            return result
        except Exception as e:
            circuit_breaker.record_failure()
            logger.warning(f"ML service operation failed: {e}")
            raise

    async def _mock_database_operation(self, operation: str):
        """Mock database operation with variable timing."""
        delay = random.uniform(0.1, 1.5)
        await asyncio.sleep(delay)

        # Simulate occasional failures
        if random.random() < 0.1:  # 10% failure rate
            raise Exception("Database connection timeout")

    def _mock_payment_operation(self, amount: float) -> dict[str, Any]:
        """Mock payment operation (synchronous for thread pool)."""

        # Simulate processing time
        time.sleep(random.uniform(0.5, 3.0))

        # Simulate failures for high amounts
        if amount > 10000:
            raise Exception("Payment amount exceeds limit")

        if random.random() < 0.05:  # 5% failure rate
            raise Exception("Payment gateway error")

        return {
            "transaction_id": f"txn_{int(time.time())}_{amount}",
            "amount": amount,
            "status": "approved",
            "timestamp": datetime.utcnow().isoformat(),
            "dependency": "payment_api"
        }

    async def _mock_cache_operation(self, key: str):
        """Mock cache operation with fast response."""
        await asyncio.sleep(random.uniform(0.01, 0.1))

        # Simulate occasional cache errors
        if random.random() < 0.02:  # 2% failure rate
            raise Exception("Cache connection error")

    def _mock_ml_operation(self, customer_id: str) -> dict[str, Any]:
        """Mock ML operation (synchronous for thread pool)."""

        # Simulate ML processing time
        time.sleep(random.uniform(1.0, 6.0))

        # Simulate occasional ML service failures
        if random.random() < 0.15:  # 15% failure rate
            raise Exception("ML model prediction failed")

        return {
            "customer_id": customer_id,
            "recommendations": [
                {"pet_id": f"pet_{i}", "score": random.uniform(0.7, 0.95)}
                for i in range(3)
            ],
            "model_version": "v2.1",
            "timestamp": datetime.utcnow().isoformat(),
            "dependency": "ml_service"
        }

    async def demo_basic_operations(self):
        """Demonstrate basic resilient operations."""
        print("\n" + "="*60)
        print("BASIC RESILIENT OPERATIONS")
        print("="*60)

        # Database operations
        print("\n📊 Testing database operations...")
        try:
            result = await self.simulate_database_call("get_pet")
            print(f"✅ Database operation successful: {result['operation']}")
        except Exception as e:
            print(f"❌ Database operation failed: {e}")

        # Cache operations
        print("\n💾 Testing cache operations...")
        try:
            result = await self.simulate_cache_call("pet_catalog")
            print(f"✅ Cache operation: {result['status']}")
        except Exception as e:
            print(f"❌ Cache operation failed: {e}")

        # Payment API
        print("\n💳 Testing payment API...")
        try:
            result = await self.simulate_payment_api_call(299.99)
            print(f"✅ Payment successful: {result['transaction_id']}")
        except Exception as e:
            print(f"❌ Payment failed: {e}")

        # ML Service
        print("\n🤖 Testing ML service...")
        try:
            result = await self.simulate_ml_service_call("customer_123")
            print(f"✅ ML recommendations: {len(result['recommendations'])} items")
        except Exception as e:
            print(f"❌ ML service failed: {e}")

    async def demo_bulkhead_isolation(self):
        """Demonstrate bulkhead isolation under load."""
        print("\n" + "="*60)
        print("BULKHEAD ISOLATION UNDER LOAD")
        print("="*60)

        print("\n🚧 Creating high load on database bulkhead...")

        # Create more requests than the bulkhead capacity
        database_tasks = [
            self.simulate_database_call(f"operation_{i}")
            for i in range(15)  # More than the 10-request capacity
        ]

        print(f"📊 Executing {len(database_tasks)} concurrent database operations...")
        results = await asyncio.gather(*database_tasks, return_exceptions=True)

        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful

        print(f"✅ Successful operations: {successful}")
        print(f"❌ Failed/rejected operations: {failed}")

        # Show bulkhead stats
        db_stats = self.bulkheads["database"].get_stats()
        print(f"📈 Database bulkhead stats:")
        print(f"   Total requests: {db_stats['total_requests']}")
        print(f"   Successful: {db_stats['successful_requests']}")
        print(f"   Rejected: {db_stats['rejected_requests']}")
        print(f"   Success rate: {db_stats['success_rate']:.2%}")

    async def demo_circuit_breaker(self):
        """Demonstrate circuit breaker behavior."""
        print("\n" + "="*60)
        print("CIRCUIT BREAKER DEMONSTRATION")
        print("="*60)

        print("\n⚡ Testing circuit breaker with forced failures...")

        # Trigger circuit breaker by causing failures
        for i in range(8):
            try:
                # Force high payment amount to trigger failures
                await self.simulate_payment_api_call(15000)
                print(f"✅ Payment {i+1} succeeded (unexpected)")
            except Exception as e:
                print(f"❌ Payment {i+1} failed: {str(e)[:50]}...")

                # Check circuit breaker state
                cb_stats = self.circuit_breakers["payment_api"].get_stats()
                print(f"   Circuit breaker state: {cb_stats['state']} "
                     f"(failures: {cb_stats['failure_count']}/{cb_stats['failure_threshold']})")

                if cb_stats['state'] == 'open':
                    print("🔴 Circuit breaker is now OPEN - blocking further requests")
                    break

        # Try one more request while circuit breaker is open
        print("\n🚫 Testing request while circuit breaker is open...")
        try:
            await self.simulate_payment_api_call(100.00)
            print("✅ Request succeeded (unexpected)")
        except Exception as e:
            print(f"❌ Request blocked by circuit breaker: {e}")

    async def demo_timeout_handling(self):
        """Demonstrate timeout handling."""
        print("\n" + "="*60)
        print("TIMEOUT HANDLING")
        print("="*60)

        print("\n⏱️  Testing timeout scenarios...")

        # Temporarily reduce timeout for demonstration
        original_timeout = self.timeouts["database"]
        self.timeouts["database"] = 0.5  # Very short timeout

        try:
            await self.simulate_database_call("slow_operation")
            print("✅ Operation completed within timeout")
        except asyncio.TimeoutError:
            print("❌ Operation timed out (as expected)")
        except Exception as e:
            print(f"❌ Operation failed: {e}")
        finally:
            # Restore original timeout
            self.timeouts["database"] = original_timeout

    def get_comprehensive_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics for all components."""
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "bulkheads": {},
            "circuit_breakers": {},
            "timeouts": self.timeouts
        }

        for name, bulkhead in self.bulkheads.items():
            stats["bulkheads"][name] = bulkhead.get_stats()

        for name, cb in self.circuit_breakers.items():
            stats["circuit_breakers"][name] = cb.get_stats()

        return stats

    async def run_full_demo(self):
        """Run the complete resilience demonstration."""
        print("🚀 STANDALONE PETSTORE RESILIENCE DEMO")
        print("="*60)
        print("This demo shows resilience patterns using mock implementations")
        print("that work without the full MMF framework.")
        print("="*60)

        start_time = datetime.utcnow()

        # Run all demo sections
        await self.demo_basic_operations()
        await asyncio.sleep(1)

        await self.demo_bulkhead_isolation()
        await asyncio.sleep(1)

        await self.demo_circuit_breaker()
        await asyncio.sleep(1)

        await self.demo_timeout_handling()

        # Show final statistics
        print("\n" + "="*60)
        print("FINAL RESILIENCE STATISTICS")
        print("="*60)

        stats = self.get_comprehensive_stats()
        print(json.dumps(stats, indent=2))

        # Demo summary
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        print("\n" + "="*60)
        print("DEMO SUMMARY")
        print("="*60)
        print("✅ Standalone resilience demo completed!")
        print(f"📊 Duration: {duration:.2f} seconds")
        print("🔧 Patterns demonstrated:")
        print("   • Bulkhead isolation (semaphore & thread-pool)")
        print("   • Circuit breaker protection")
        print("   • Timeout handling")
        print("   • Load testing and resource isolation")
        print("   • Comprehensive monitoring and statistics")


async def main():
    """Run the standalone demo."""
    demo = StandaloneResilienceDemo()
    await demo.run_full_demo()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\n❌ Demo failed with error: {e}")
