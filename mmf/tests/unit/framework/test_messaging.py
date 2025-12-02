import asyncio

import pytest

from mmf.framework.messaging.bootstrap import create_messaging_manager
from mmf.framework.messaging.domain.models import (
    ConsumerConfig,
    ExchangeConfig,
    Message,
    MessageStatus,
    ProducerConfig,
    QueueConfig,
)


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessagingManager:
    async def test_manager_initialization(self):
        manager = create_messaging_manager()
        await manager.initialize()
        assert manager._initialized is True
        await manager.shutdown()
        assert manager._initialized is False

    async def test_producer_creation(self):
        manager = create_messaging_manager()
        await manager.initialize()

        config = ProducerConfig(name="test-producer", routing_key="test-key")
        producer = await manager.create_producer(config)

        assert producer is not None
        await manager.shutdown()

    async def test_consumer_creation(self):
        manager = create_messaging_manager()
        await manager.initialize()

        config = ConsumerConfig(name="test-consumer", queue="test-queue")
        consumer = await manager.create_consumer(config)

        assert consumer is not None
        await manager.shutdown()

    async def test_publish_consume_flow(self):
        manager = create_messaging_manager()
        await manager.initialize()
        backend = await manager.get_backend()

        # Setup infrastructure (Exchange & Queue)
        exchange_config = ExchangeConfig(name="test-exchange")
        await backend.create_exchange(exchange_config)

        queue_config = QueueConfig(name="test-queue")
        queue = await backend.create_queue(queue_config)
        await queue.bind("test-exchange", "test-key")

        # Setup consumer
        received_messages = []

        async def handler(msg: Message):
            received_messages.append(msg)
            return True

        consumer_config = ConsumerConfig(name="test-consumer", queue="test-queue")
        consumer = await manager.create_consumer(consumer_config)
        await consumer.set_handler(handler)
        await consumer.start()

        # Setup producer
        producer_config = ProducerConfig(
            name="test-producer", exchange="test-exchange", routing_key="test-key"
        )
        producer = await manager.create_producer(producer_config)

        # Publish message
        msg = Message(body={"test": "data"})
        await producer.publish(msg)

        # Wait for processing
        await asyncio.sleep(0.1)

        # Now that MemoryBackend implements delivery, this should pass
        assert len(received_messages) == 1
        assert received_messages[0].body == {"test": "data"}

        await manager.shutdown()
