"""
Integration test specific fixtures and utilities.

This module provides fixtures for integration tests that use real implementations
and external services in controlled environments.
"""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
import docker
import pytest
import redis.asyncio as redis
from testcontainers.kafka import KafkaContainer
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from mmf_new.framework.events.enhanced_event_bus import EnhancedEventBus as EventBus
from mmf_new.framework.messaging import MessagingManager as MessageBus


@pytest.fixture(scope="session")
async def docker_client():
    """Provide a Docker client for managing test containers."""
    client = docker.from_env()
    yield client
    client.close()


@pytest.fixture(scope="session")
async def postgres_container() -> AsyncGenerator[PostgresContainer, None]:
    """Provide a PostgreSQL container for integration tests."""
    with PostgresContainer("postgres:15-alpine") as postgres:
        postgres.start()
        yield postgres


@pytest.fixture(scope="session")
async def redis_container() -> AsyncGenerator[RedisContainer, None]:
    """Provide a Redis container for integration tests."""
    with RedisContainer("redis:7-alpine") as redis:
        redis.start()
        yield redis


@pytest.fixture(scope="session")
async def kafka_container() -> AsyncGenerator[KafkaContainer, None]:
    """Provide a Kafka container for integration tests."""
    with KafkaContainer("confluentinc/cp-kafka:latest") as kafka:
        kafka.start()
        yield kafka


@pytest.fixture
async def real_database_connection(postgres_container: PostgresContainer):
    """Provide a real database connection for integration tests."""

    connection_url = postgres_container.get_connection_url()
    # Convert psycopg2 URL to asyncpg format
    asyncpg_url = connection_url.replace("postgresql+psycopg2://", "postgresql://")

    connection = await asyncpg.connect(asyncpg_url)

    # Setup test schema
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS test_events (
            id SERIAL PRIMARY KEY,
            event_type VARCHAR(255) NOT NULL,
            event_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    yield connection

    # Cleanup
    await connection.execute("DROP TABLE IF EXISTS test_events")
    await connection.close()


@pytest.fixture
async def real_redis_client(redis_container: RedisContainer):
    """Provide a real Redis client for integration tests."""

    redis_url = f"redis://localhost:{redis_container.get_exposed_port(6379)}/0"
    client = redis.from_url(redis_url)

    yield client

    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture
async def real_event_bus(
    kafka_container: KafkaContainer, test_service_name: str
) -> AsyncGenerator[EventBus, None]:
    """Provide a real event bus with Kafka for integration tests."""
    bootstrap_servers = [f"localhost:{kafka_container.get_exposed_port(9093)}"]

    event_bus = EventBus(
        service_name=test_service_name,
        bootstrap_servers=bootstrap_servers,
        consumer_group=f"{test_service_name}-integration-test",
    )

    try:
        await event_bus.start()
        yield event_bus
    finally:
        await event_bus.stop()


@pytest.fixture
async def real_message_bus(
    kafka_container: KafkaContainer, test_service_name: str
) -> AsyncGenerator[MessageBus, None]:
    """Provide a real message bus with Kafka for integration tests."""
    bootstrap_servers = [f"localhost:{kafka_container.get_exposed_port(9093)}"]

    config = {
        "kafka_bootstrap_servers": bootstrap_servers,
        "kafka_consumer_group": f"{test_service_name}-integration-test",
    }

    message_bus = MessageBus(service_name=test_service_name, config=config)

    try:
        await message_bus.start()
        yield message_bus
    finally:
        await message_bus.stop()


@pytest.fixture
def integration_test_data_dir(temp_dir: Path) -> Path:
    """Provide a directory for integration test data files."""
    data_dir = temp_dir / "integration_data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


@pytest.fixture
async def service_mesh_environment():
    """Setup a minimal service mesh environment for testing."""
    # This would setup service discovery, load balancing, etc.
    # For now, return a mock environment
    mesh_env = {"services": [], "load_balancer": None, "service_registry": {}}
    yield mesh_env


# Integration test utilities
async def wait_for_service_ready(service, timeout: float = 30.0):
    """Wait for a service to be ready."""
    elapsed = 0.0
    while elapsed < timeout:
        try:
            health = await service.health_check()
            if health.get("status") == "healthy":
                return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
        elapsed += 0.5
    return False


async def wait_for_message_consumption(consumer, expected_count: int, timeout: float = 10.0):
    """Wait for a specific number of messages to be consumed."""
    elapsed = 0.0
    while elapsed < timeout:
        if hasattr(consumer, "message_count") and consumer.message_count >= expected_count:
            return True
        await asyncio.sleep(0.1)
        elapsed += 0.1
    return False


def create_test_database_schema(connection):
    """Create test database schema for integration tests."""
    # This would create the necessary tables and indexes
    # Implementation depends on your database layer
    pass


def cleanup_test_database(connection):
    """Cleanup test database after integration tests."""
    # This would clean up test data and reset state
    # Implementation depends on your database layer
    pass
