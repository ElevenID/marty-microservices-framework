"""
Example Performance Tests for MMF Framework

This module demonstrates performance testing patterns using the MMF testing framework.
"""

import asyncio
import time
from typing import Any

import pytest

from mmf.framework.events import Event
from mmf.framework.events.enhanced_event_bus import EventBus as MessageBroker


@pytest.mark.performance
class TestMessageBrokerPerformance:
    """Performance tests for message broker components."""

    async def test_message_throughput(self, performance_metrics, message_broker):
        """Test message broker throughput under load."""
        message_count = 1000
        payload_size = 1024  # 1KB messages

        # Create test messages
        messages = []
        for i in range(message_count):
            event = Event(
                event_type="test_event", data={"payload": "x" * payload_size, "sequence": i}
            )
            messages.append(event)

        # Measure publishing performance
        start_time = time.time()

        for message in messages:
            await message_broker.publish("test.topic", message)

        publish_duration = time.time() - start_time

        # Calculate metrics
        throughput = message_count / publish_duration
        avg_latency = publish_duration / message_count * 1000  # ms

        # Record metrics
        performance_metrics.record_response_time(avg_latency)
        performance_metrics.record_throughput(throughput)

        # Assertions
        assert throughput > 100, f"Throughput too low: {throughput} msg/s"
        assert avg_latency < 10, f"Average latency too high: {avg_latency} ms"

    async def test_concurrent_consumers(self, performance_metrics, message_broker):
        """Test performance with multiple concurrent consumers."""
        consumer_count = 10
        messages_per_consumer = 100

        async def consumer_worker(consumer_id: int, results: list[dict[str, Any]]):
            """Worker function for concurrent consumers."""
            start_time = time.time()
            consumed_count = 0

            async def handler(event: Event):
                nonlocal consumed_count
                consumed_count += 1
                if consumed_count >= messages_per_consumer:
                    return False  # Stop consuming
                return True

            await message_broker.subscribe(f"perf.consumer.{consumer_id}", handler)

            duration = time.time() - start_time
            results.append(
                {
                    "consumer_id": consumer_id,
                    "messages": consumed_count,
                    "duration": duration,
                    "rate": consumed_count / duration if duration > 0 else 0,
                }
            )

        # Start producers to generate load
        async def producer_worker():
            for i in range(consumer_count * messages_per_consumer):
                consumer_id = i % consumer_count
                event = Event(event_type="perf_test", data={"message_id": i})
                await message_broker.publish(f"perf.consumer.{consumer_id}", event)

        # Run concurrent test
        results = []

        # Start consumers
        consumer_tasks = [
            asyncio.create_task(consumer_worker(i, results)) for i in range(consumer_count)
        ]

        # Start producer
        producer_task = asyncio.create_task(producer_worker())

        # Wait for completion
        await asyncio.gather(*consumer_tasks, producer_task)

        # Analyze results
        total_messages = sum(r["messages"] for r in results)
        avg_rate = sum(r["rate"] for r in results) / len(results)

        performance_metrics.record_throughput(avg_rate)

        # Assertions
        assert total_messages == consumer_count * messages_per_consumer
        assert avg_rate > 50, f"Average consumption rate too low: {avg_rate} msg/s"


@pytest.mark.performance
class TestEventProcessingPerformance:
    """Performance tests for event processing pipeline."""

    async def test_event_processing_latency(self, performance_metrics, event_processor):
        """Test event processing latency under various loads."""
        test_cases = [
            {"batch_size": 1, "expected_latency": 5},
            {"batch_size": 10, "expected_latency": 15},
            {"batch_size": 100, "expected_latency": 100},
        ]

        for test_case in test_cases:
            batch_size = test_case["batch_size"]
            expected_latency = test_case["expected_latency"]

            # Create batch of events
            events = []
            for i in range(batch_size):
                event = Event(event_type="processing_test", data={"batch": batch_size, "index": i})
                events.append(event)

            # Measure processing time
            start_time = time.time()

            for event in events:
                await event_processor.process(event)

            end_time = time.time()
            total_latency = (end_time - start_time) * 1000  # ms
            avg_latency = total_latency / batch_size

            # Record metrics
            performance_metrics.record_response_time(avg_latency)

            # Assertions
            assert avg_latency < expected_latency, (
                f"Batch size {batch_size}: latency {avg_latency:.2f}ms "
                f"exceeds expected {expected_latency}ms"
            )

    async def test_memory_usage_under_load(self, performance_metrics, resource_monitor):
        """Test memory usage during high-load event processing."""
        initial_memory = resource_monitor.get_memory_usage()

        # Process large number of events
        event_count = 10000

        for _ in range(event_count):
            Event(
                event_type="memory_test",
                data={"large_payload": "x" * 1024 * 10},  # 10KB payload
            )
            # Process event (implementation would be provided by fixture)

        peak_memory = resource_monitor.get_peak_memory_usage()
        memory_increase = peak_memory - initial_memory

        # Record metrics
        performance_metrics.record_memory_usage(peak_memory)

        # Assertions - memory increase should be reasonable
        max_allowed_increase = 500 * 1024 * 1024  # 500MB
        assert memory_increase < max_allowed_increase, (
            f"Memory increase {memory_increase / 1024 / 1024:.2f}MB "
            f"exceeds limit {max_allowed_increase / 1024 / 1024:.2f}MB"
        )


@pytest.mark.performance
@pytest.mark.slow
class TestSystemPerformance:
    """End-to-end system performance tests."""

    async def test_full_pipeline_performance(self, performance_metrics, system_under_test):
        """Test complete system performance under realistic load."""
        # Simulate realistic workload
        test_duration = 60  # 1 minute test
        target_rps = 100  # 100 requests per second

        start_time = time.time()
        total_requests = 0
        response_times = []

        while time.time() - start_time < test_duration:
            batch_start = time.time()

            # Send batch of requests
            batch_size = min(10, target_rps)
            batch_tasks = []

            for _ in range(batch_size):
                task = asyncio.create_task(
                    system_under_test.process_request(
                        {"type": "test_request", "timestamp": time.time()}
                    )
                )
                batch_tasks.append(task)

            # Wait for batch completion
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Record response times
            batch_end = time.time()
            batch_duration = batch_end - batch_start

            for result in results:
                if not isinstance(result, Exception):
                    response_times.append(batch_duration / batch_size * 1000)
                    total_requests += 1

            # Rate limiting
            expected_batch_duration = batch_size / target_rps
            if batch_duration < expected_batch_duration:
                await asyncio.sleep(expected_batch_duration - batch_duration)

        # Calculate final metrics
        actual_duration = time.time() - start_time
        actual_rps = total_requests / actual_duration
        avg_response_time = sum(response_times) / len(response_times)
        p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]

        # Record metrics
        performance_metrics.record_throughput(actual_rps)
        performance_metrics.record_response_time(avg_response_time)

        # Performance assertions
        assert actual_rps >= target_rps * 0.9, f"RPS {actual_rps:.2f} below target {target_rps}"
        assert avg_response_time < 100, f"Avg response time {avg_response_time:.2f}ms too high"
        assert p95_response_time < 200, f"P95 response time {p95_response_time:.2f}ms too high"


@pytest.mark.performance
class TestResourceUtilization:
    """Tests for system resource utilization."""

    async def test_cpu_utilization(self, performance_metrics, resource_monitor):
        """Test CPU utilization under various loads."""
        # CPU-intensive workload
        start_time = time.time()
        iteration_count = 1000000

        # Simulate CPU-bound work
        result = 0
        for i in range(iteration_count):
            result += i * i % 1000

        duration = time.time() - start_time
        peak_cpu = resource_monitor.get_peak_cpu_usage()

        # Record metrics
        performance_metrics.record_cpu_usage(peak_cpu)

        # Assertions
        operations_per_second = iteration_count / duration
        assert operations_per_second > 100000, f"OPS {operations_per_second:.0f} too low"
        assert peak_cpu < 80, f"CPU usage {peak_cpu:.1f}% too high"

    async def test_network_io_performance(self, performance_metrics, network_client):
        """Test network I/O performance."""
        # Test parameters
        request_count = 100
        concurrent_requests = 10

        async def make_request(request_id: int):
            """Make a single network request."""
            start_time = time.time()

            response = await network_client.get(f"/api/test/{request_id}")

            end_time = time.time()
            return {
                "request_id": request_id,
                "response_time": (end_time - start_time) * 1000,
                "status": response.status_code,
                "success": response.status_code == 200,
            }

        # Execute concurrent requests
        start_time = time.time()

        tasks = []
        for i in range(request_count):
            task = asyncio.create_task(make_request(i))
            tasks.append(task)

            # Control concurrency
            if len(tasks) >= concurrent_requests:
                results = await asyncio.gather(*tasks)
                tasks = []

                # Process results
                for result in results:
                    performance_metrics.record_response_time(result["response_time"])

        # Handle remaining tasks
        if tasks:
            results = await asyncio.gather(*tasks)
            for result in results:
                performance_metrics.record_response_time(result["response_time"])

        total_duration = time.time() - start_time
        rps = request_count / total_duration

        # Record final metrics
        performance_metrics.record_throughput(rps)

        # Assertions
        assert rps > 50, f"Network RPS {rps:.2f} too low"
