"""
Messaging Factories

Provides factory_boy factories for messaging domain models.
"""

import time
import uuid

import factory

from mmf.core.messaging import (
    BackendConfig,
    BackendType,
    ExchangeConfig,
    Message,
    MessageHeaders,
    MessagePriority,
    MessageStatus,
    ProducerConfig,
    QueueConfig,
)


class MessageHeadersFactory(factory.Factory):
    """Factory for MessageHeaders objects."""

    class Meta:
        model = MessageHeaders

    data = factory.LazyAttribute(lambda _: {})

    class Params:
        """Traits for common header configurations."""

        # Headers with tracing info
        with_tracing = factory.Trait(
            data=factory.LazyAttribute(
                lambda _: {
                    "trace_id": str(uuid.uuid4()),
                    "span_id": str(uuid.uuid4().hex[:16]),
                    "parent_span_id": None,
                }
            )
        )

        # Headers with content info
        with_content_info = factory.Trait(
            data=factory.LazyAttribute(
                lambda _: {
                    "content_type": "application/json",
                    "content_encoding": "utf-8",
                }
            )
        )


class MessageFactory(factory.Factory):
    """Factory for Message objects."""

    class Meta:
        model = Message

    id = factory.LazyAttribute(lambda _: str(uuid.uuid4()))
    body = factory.LazyAttribute(lambda _: {"event": "test", "data": {}})
    headers = factory.SubFactory(MessageHeadersFactory)
    priority = MessagePriority.NORMAL
    status = MessageStatus.PENDING
    routing_key = factory.Sequence(lambda n: f"test.event.{n}")
    exchange = "default"
    timestamp = factory.LazyAttribute(lambda _: time.time())
    expiration = None
    retry_count = 0
    max_retries = 3
    correlation_id = None
    reply_to = None
    content_type = "application/json"
    content_encoding = "utf-8"
    metadata = factory.LazyAttribute(lambda _: {})

    class Params:
        """Traits for common message types."""

        # High priority message
        high_priority = factory.Trait(
            priority=MessagePriority.HIGH,
        )

        # Critical message
        critical = factory.Trait(
            priority=MessagePriority.CRITICAL,
            max_retries=5,
        )

        # Request-reply message
        request_reply = factory.Trait(
            correlation_id=factory.LazyAttribute(lambda _: str(uuid.uuid4())),
            reply_to=factory.Sequence(lambda n: f"reply.queue.{n}"),
        )

        # Expired message
        expired = factory.Trait(
            expiration=factory.LazyAttribute(lambda _: time.time() - 3600),
        )

        # Failed message
        failed = factory.Trait(
            status=MessageStatus.FAILED,
            retry_count=3,
        )

        # Dead letter message
        dead_letter = factory.Trait(
            status=MessageStatus.DEAD_LETTER,
            retry_count=3,
            metadata=factory.LazyAttribute(
                lambda _: {
                    "original_routing_key": "original.key",
                    "failure_reason": "Max retries exceeded",
                }
            ),
        )

        # Processing message
        processing = factory.Trait(
            status=MessageStatus.PROCESSING,
        )


class QueueConfigFactory(factory.Factory):
    """Factory for QueueConfig objects."""

    class Meta:
        model = QueueConfig

    name = factory.Sequence(lambda n: f"queue-{n}")
    durable = True
    exclusive = False
    auto_delete = False
    arguments = factory.LazyAttribute(lambda _: {})
    max_length = None
    max_length_bytes = None
    ttl = None
    dlq_enabled = True
    dlq_name = None

    class Params:
        """Traits for queue configurations."""

        # Temporary queue
        temporary = factory.Trait(
            durable=False,
            exclusive=True,
            auto_delete=True,
            dlq_enabled=False,
        )

        # Queue with limits
        limited = factory.Trait(
            max_length=10000,
            max_length_bytes=104857600,  # 100MB
            ttl=3600,  # 1 hour
        )

        # Queue with explicit DLQ
        with_dlq = factory.Trait(
            dlq_enabled=True,
            dlq_name=factory.LazyAttribute(lambda o: f"{o.name}.dlq"),
        )


class ExchangeConfigFactory(factory.Factory):
    """Factory for ExchangeConfig objects."""

    class Meta:
        model = ExchangeConfig

    name = factory.Sequence(lambda n: f"exchange-{n}")
    type = "direct"
    durable = True
    auto_delete = False
    arguments = factory.LazyAttribute(lambda _: {})

    class Params:
        """Traits for exchange types."""

        # Topic exchange
        topic = factory.Trait(
            type="topic",
        )

        # Fanout exchange
        fanout = factory.Trait(
            type="fanout",
        )

        # Headers exchange
        headers = factory.Trait(
            type="headers",
        )


class BackendConfigFactory(factory.Factory):
    """Factory for BackendConfig objects."""

    class Meta:
        model = BackendConfig

    type = BackendType.MEMORY
    connection_url = "memory://"
    connection_params = factory.LazyAttribute(lambda _: {})
    pool_size = 10
    max_connections = 100
    timeout = 30
    retry_attempts = 3
    retry_delay = 1.0
    health_check_interval = 30

    class Params:
        """Traits for backend types."""

        # RabbitMQ backend
        rabbitmq = factory.Trait(
            type=BackendType.RABBITMQ,
            connection_url="amqp://guest:guest@localhost:5672/",  # pragma: allowlist secret
        )

        # Redis backend
        redis = factory.Trait(
            type=BackendType.REDIS,
            connection_url="redis://localhost:6379/0",
        )

        # Kafka backend
        kafka = factory.Trait(
            type=BackendType.KAFKA,
            connection_url="kafka://localhost:9092",
        )

        # NATS backend
        nats = factory.Trait(
            type=BackendType.NATS,
            connection_url="nats://localhost:4222",
        )


class ProducerConfigFactory(factory.Factory):
    """Factory for ProducerConfig objects."""

    class Meta:
        model = ProducerConfig

    name = factory.Sequence(lambda n: f"producer-{n}")
    exchange = "default"
    routing_key = ""
    default_priority = MessagePriority.NORMAL

    class Params:
        """Traits for producer configurations."""

        # High priority producer
        high_priority = factory.Trait(
            default_priority=MessagePriority.HIGH,
        )

        # Topic producer
        topic = factory.Trait(
            exchange="topic.exchange",
            routing_key="events.#",
        )
