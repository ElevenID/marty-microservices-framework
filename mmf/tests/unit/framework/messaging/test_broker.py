"""
Unit tests for MessageBroker.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mmf.framework.messaging.application.broker import MessageBroker
from mmf.framework.messaging.domain.models import Message
from mmf.framework.messaging.interfaces import (
    IMessageBackend,
    IMessageConsumer,
    IMessageProducer,
    IMessageRouter,
)


class TestMessageBroker:
    """Test suite for MessageBroker."""

    @pytest.fixture
    def mock_backend(self):
        backend = MagicMock(spec=IMessageBackend)
        backend.create_producer = AsyncMock()
        backend.create_consumer = AsyncMock()
        return backend

    @pytest.fixture
    def mock_router(self):
        router = MagicMock(spec=IMessageRouter)
        router.route = AsyncMock(return_value=("test_exchange", "test_key"))
        return router

    @pytest.fixture
    def broker(self, mock_backend, mock_router):
        return MessageBroker(mock_backend, mock_router)

    @pytest.mark.asyncio
    async def test_publish_creates_producer_and_sends(self, broker, mock_backend, mock_router):
        """Test that publish routes message, creates producer, and sends."""
        # Setup
        message = MagicMock(spec=Message)
        mock_producer = AsyncMock(spec=IMessageProducer)
        mock_producer.publish = AsyncMock(return_value=True)
        mock_backend.create_producer.return_value = mock_producer

        # Execute
        result = await broker.publish(message)

        # Verify
        assert result is True
        mock_router.route.assert_called_once_with(message)
        mock_backend.create_producer.assert_called_once()
        mock_producer.start.assert_called_once()
        mock_producer.publish.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_publish_reuses_producer(self, broker, mock_backend):
        """Test that publish reuses existing producer for same exchange."""
        # Setup
        message = MagicMock(spec=Message)
        mock_producer = AsyncMock(spec=IMessageProducer)
        mock_producer.publish = AsyncMock(return_value=True)
        mock_backend.create_producer.return_value = mock_producer

        # Execute twice
        await broker.publish(message)
        await broker.publish(message)

        # Verify producer created only once
        mock_backend.create_producer.assert_called_once()
        assert mock_producer.publish.call_count == 2

    @pytest.mark.asyncio
    async def test_subscribe(self, broker, mock_backend):
        """Test subscription creates consumer and starts it."""
        # Setup
        mock_consumer = AsyncMock(spec=IMessageConsumer)
        mock_backend.create_consumer.return_value = mock_consumer
        handler = MagicMock()

        # Execute
        await broker.subscribe("test_queue", handler)

        # Verify
        mock_backend.create_consumer.assert_called_once()
        mock_consumer.set_handler.assert_called_once_with(handler)
        mock_consumer.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsubscribe(self, broker, mock_backend):
        """Test unsubscribe stops consumer."""
        # Setup
        mock_consumer = AsyncMock(spec=IMessageConsumer)
        mock_backend.create_consumer.return_value = mock_consumer
        await broker.subscribe("test_queue", MagicMock())

        # Execute
        await broker.unsubscribe("test_queue")

        # Verify
        mock_consumer.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown(self, broker, mock_backend):
        """Test shutdown stops all components."""
        # Setup
        mock_producer = AsyncMock(spec=IMessageProducer)
        mock_consumer = AsyncMock(spec=IMessageConsumer)
        mock_backend.create_producer.return_value = mock_producer
        mock_backend.create_consumer.return_value = mock_consumer

        await broker.publish(MagicMock(spec=Message))
        await broker.subscribe("test_queue", MagicMock())

        # Execute
        await broker.shutdown()

        # Verify
        mock_producer.stop.assert_called_once()
        mock_consumer.stop.assert_called_once()
