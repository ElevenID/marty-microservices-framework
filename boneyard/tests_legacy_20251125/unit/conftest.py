"""
Unit test specific fixtures and utilities.

This module provides fixtures and utilities specifically for unit tests,
focusing on isolated testing with minimal external dependencies.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marty_msf.framework.config import BaseServiceConfig as FrameworkConfig
from marty_msf.framework.logging import UnifiedServiceLogger as StructuredLogger


@pytest.fixture
def mock_logger():
    """Provide a mock logger for unit tests."""
    logger = MagicMock(spec=StructuredLogger)
    logger.info = MagicMock()
    logger.debug = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.critical = MagicMock()
    return logger


@pytest.fixture
def mock_metrics():
    """Provide a mock metrics collector for unit tests."""
    metrics = MagicMock()
    metrics.increment_counter = MagicMock()
    metrics.record_histogram = MagicMock()
    metrics.set_gauge = MagicMock()
    metrics.start_timer = MagicMock()
    return metrics


@pytest.fixture
def mock_config():
    """Provide a mock configuration for unit tests."""
    config = MagicMock(spec=FrameworkConfig)
    config.service_name = "test-service"
    config.environment = "test"
    config.debug = True
    config.log_level = "DEBUG"
    return config


@pytest.fixture
def mock_event_bus():
    """Provide a mock event bus for unit tests."""
    event_bus = MagicMock()
    event_bus.publish = AsyncMock()
    event_bus.subscribe = AsyncMock()
    event_bus.start = AsyncMock()
    event_bus.stop = AsyncMock()
    return event_bus


@pytest.fixture
def mock_database():
    """Provide a mock database connection for unit tests."""
    db = MagicMock()
    db.execute = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    db.fetchone = AsyncMock(return_value=None)
    db.transaction = AsyncMock()
    return db


@pytest.fixture
def mock_cache():
    """Provide a mock cache client for unit tests."""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.exists = AsyncMock(return_value=False)
    return cache


@pytest.fixture
def patch_external_dependencies():
    """Patch common external dependencies for unit tests."""
    with (
        patch("redis.asyncio.from_url") as mock_redis,
        patch("asyncpg.connect") as mock_pg,
        patch("aiokafka.AIOKafkaProducer") as mock_kafka_producer,
        patch("aiokafka.AIOKafkaConsumer") as mock_kafka_consumer,
    ):
        # Configure mocks
        mock_redis.return_value = MagicMock()
        mock_pg.return_value = MagicMock()
        mock_kafka_producer.return_value = MagicMock()
        mock_kafka_consumer.return_value = MagicMock()

        yield {
            "redis": mock_redis,
            "postgres": mock_pg,
            "kafka_producer": mock_kafka_producer,
            "kafka_consumer": mock_kafka_consumer,
        }


# Unit test specific utilities
def create_mock_service(name: str = "test-service", version: str = "1.0.0"):
    """Create a mock service instance."""
    service = MagicMock()
    service.name = name
    service.version = version
    service.start = AsyncMock()
    service.stop = AsyncMock()
    service.health_check = AsyncMock(return_value={"status": "healthy"})
    return service


def create_mock_request(
    method: str = "GET", path: str = "/", headers: dict = None, body: Any = None
):
    """Create a mock HTTP request."""
    request = MagicMock()
    request.method = method
    request.path = path
    request.headers = headers or {}
    request.body = body
    request.json = AsyncMock(return_value=body if isinstance(body, dict) else {})
    return request


def create_mock_response(status: int = 200, body: Any = None, headers: dict = None):
    """Create a mock HTTP response."""
    response = MagicMock()
    response.status = status
    response.status_code = status
    response.body = body
    response.headers = headers or {}
    response.json = AsyncMock(return_value=body if isinstance(body, dict) else {})
    return response
