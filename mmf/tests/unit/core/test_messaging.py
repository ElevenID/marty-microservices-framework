"""
Unit tests for core messaging module.

Tests Message class, enums, and related data structures.
"""

import time
import uuid

import pytest

from mmf.core.messaging import (
    BackendConfig,
    BackendType,
    ConsumerMode,
    DLQPolicy,
    ExchangeConfig,
    MatchType,
    Message,
    MessageHeaders,
    MessagePattern,
    MessagePriority,
    MessageStatus,
    MessagingError,
    MiddlewareStage,
    MiddlewareType,
    ProducerConfig,
    QueueConfig,
    RetryStrategy,
    RoutingType,
)


class TestMessagePriority:
    """Tests for MessagePriority enum."""

    def test_priority_values(self):
        """Test priority numeric values are ordered correctly."""
        assert MessagePriority.LOW.value < MessagePriority.NORMAL.value
        assert MessagePriority.NORMAL.value < MessagePriority.HIGH.value
        assert MessagePriority.HIGH.value < MessagePriority.CRITICAL.value

    def test_priority_comparison(self):
        """Test that priorities can be compared by value."""
        assert MessagePriority.LOW.value == 1
        assert MessagePriority.NORMAL.value == 5
        assert MessagePriority.HIGH.value == 10
        assert MessagePriority.CRITICAL.value == 15

    def test_all_priorities_exist(self):
        """Test all expected priorities are defined."""
        priorities = list(MessagePriority)
        assert len(priorities) == 4
        assert MessagePriority.LOW in priorities
        assert MessagePriority.NORMAL in priorities
        assert MessagePriority.HIGH in priorities
        assert MessagePriority.CRITICAL in priorities


class TestMessageStatus:
    """Tests for MessageStatus enum."""

    def test_status_values(self):
        """Test status string values."""
        assert MessageStatus.PENDING.value == "pending"
        assert MessageStatus.PROCESSING.value == "processing"
        assert MessageStatus.PROCESSED.value == "processed"
        assert MessageStatus.FAILED.value == "failed"
        assert MessageStatus.DEAD_LETTER.value == "dead_letter"
        assert MessageStatus.RETRY.value == "retry"

    def test_all_statuses_exist(self):
        """Test all expected statuses are defined."""
        statuses = list(MessageStatus)
        assert len(statuses) == 6


class TestBackendType:
    """Tests for BackendType enum."""

    def test_backend_values(self):
        """Test backend string values."""
        assert BackendType.RABBITMQ.value == "rabbitmq"
        assert BackendType.REDIS.value == "redis"
        assert BackendType.KAFKA.value == "kafka"
        assert BackendType.MEMORY.value == "memory"
        assert BackendType.NATS.value == "nats"

    def test_all_backends_exist(self):
        """Test all expected backends are defined."""
        backends = list(BackendType)
        assert len(backends) == 5


class TestMessagePattern:
    """Tests for MessagePattern enum."""

    def test_pattern_values(self):
        """Test pattern string values."""
        assert MessagePattern.REQUEST_REPLY.value == "request_reply"
        assert MessagePattern.PUBLISH_SUBSCRIBE.value == "publish_subscribe"
        assert MessagePattern.WORK_QUEUE.value == "work_queue"
        assert MessagePattern.ROUTING.value == "routing"
        assert MessagePattern.RPC.value == "rpc"


class TestConsumerMode:
    """Tests for ConsumerMode enum."""

    def test_mode_values(self):
        """Test consumer mode string values."""
        assert ConsumerMode.PULL.value == "pull"
        assert ConsumerMode.PUSH.value == "push"
        assert ConsumerMode.STREAMING.value == "streaming"


class TestMiddlewareType:
    """Tests for MiddlewareType enum."""

    def test_all_middleware_types_exist(self):
        """Test all expected middleware types are defined."""
        types = list(MiddlewareType)
        assert len(types) >= 10
        assert MiddlewareType.AUTHENTICATION in types
        assert MiddlewareType.AUTHORIZATION in types
        assert MiddlewareType.LOGGING in types
        assert MiddlewareType.METRICS in types
        assert MiddlewareType.TRACING in types
        assert MiddlewareType.VALIDATION in types
        assert MiddlewareType.TRANSFORMATION in types
        assert MiddlewareType.RETRY in types
        assert MiddlewareType.CIRCUIT_BREAKER in types
        assert MiddlewareType.RATE_LIMITING in types


class TestMiddlewareStage:
    """Tests for MiddlewareStage enum."""

    def test_stage_values(self):
        """Test middleware stage string values."""
        assert MiddlewareStage.PRE_PUBLISH.value == "pre_publish"
        assert MiddlewareStage.POST_PUBLISH.value == "post_publish"
        assert MiddlewareStage.PRE_CONSUME.value == "pre_consume"
        assert MiddlewareStage.POST_CONSUME.value == "post_consume"
        assert MiddlewareStage.ERROR_HANDLING.value == "error_handling"


class TestDLQPolicy:
    """Tests for DLQPolicy enum."""

    def test_policy_values(self):
        """Test DLQ policy string values."""
        assert DLQPolicy.DROP.value == "drop"
        assert DLQPolicy.RETRY.value == "retry"
        assert DLQPolicy.FORWARD.value == "forward"
        assert DLQPolicy.STORE.value == "store"


class TestRoutingType:
    """Tests for RoutingType enum."""

    def test_routing_values(self):
        """Test routing type string values."""
        assert RoutingType.DIRECT.value == "direct"
        assert RoutingType.TOPIC.value == "topic"
        assert RoutingType.FANOUT.value == "fanout"
        assert RoutingType.HEADERS.value == "headers"


class TestMatchType:
    """Tests for MatchType enum."""

    def test_match_values(self):
        """Test match type string values."""
        assert MatchType.EXACT.value == "exact"
        assert MatchType.PREFIX.value == "prefix"
        assert MatchType.SUFFIX.value == "suffix"
        assert MatchType.REGEX.value == "regex"
        assert MatchType.WILDCARD.value == "wildcard"


class TestRetryStrategy:
    """Tests for RetryStrategy enum."""

    def test_strategy_values(self):
        """Test retry strategy string values."""
        assert RetryStrategy.FIXED_DELAY.value == "fixed_delay"
        assert RetryStrategy.EXPONENTIAL_BACKOFF.value == "exponential_backoff"
        assert RetryStrategy.LINEAR_BACKOFF.value == "linear_backoff"


class TestMessageHeaders:
    """Tests for MessageHeaders class."""

    def test_default_headers(self):
        """Test default empty headers."""
        headers = MessageHeaders()
        assert headers.data == {}

    def test_get_existing_header(self):
        """Test getting an existing header."""
        headers = MessageHeaders(data={"key": "value"})
        assert headers.get("key") == "value"

    def test_get_missing_header_with_default(self):
        """Test getting a missing header with default."""
        headers = MessageHeaders()
        assert headers.get("missing", "default") == "default"

    def test_get_missing_header_without_default(self):
        """Test getting a missing header without default."""
        headers = MessageHeaders()
        assert headers.get("missing") is None

    def test_set_header(self):
        """Test setting a header."""
        headers = MessageHeaders()
        headers.set("key", "value")
        assert headers.get("key") == "value"

    def test_set_header_overwrites(self):
        """Test that setting a header overwrites existing."""
        headers = MessageHeaders(data={"key": "old"})
        headers.set("key", "new")
        assert headers.get("key") == "new"

    def test_remove_header(self):
        """Test removing a header."""
        headers = MessageHeaders(data={"key": "value"})
        headers.remove("key")
        assert headers.get("key") is None

    def test_remove_missing_header(self):
        """Test removing a header that doesn't exist doesn't raise."""
        headers = MessageHeaders()
        headers.remove("missing")  # Should not raise


class TestMessage:
    """Tests for Message class."""

    def test_message_default_values(self):
        """Test message has sensible defaults."""
        msg = Message()

        assert msg.id is not None
        assert uuid.UUID(msg.id)  # Should be valid UUID
        assert msg.body is None
        assert isinstance(msg.headers, MessageHeaders)
        assert msg.priority == MessagePriority.NORMAL
        assert msg.status == MessageStatus.PENDING
        assert msg.routing_key == ""
        assert msg.exchange == ""
        assert msg.timestamp > 0
        assert msg.expiration is None
        assert msg.retry_count == 0
        assert msg.max_retries == 3
        assert msg.correlation_id is None
        assert msg.reply_to is None
        assert msg.content_type == "application/json"
        assert msg.content_encoding == "utf-8"
        assert msg.metadata == {}

    def test_message_with_body(self):
        """Test message with body."""
        body = {"event": "test", "data": {"value": 123}}
        msg = Message(body=body)
        assert msg.body == body

    def test_message_with_priority(self):
        """Test message with priority."""
        msg = Message(priority=MessagePriority.CRITICAL)
        assert msg.priority == MessagePriority.CRITICAL

    def test_message_with_routing_key(self):
        """Test message with routing key."""
        msg = Message(routing_key="events.user.created", exchange="events")
        assert msg.routing_key == "events.user.created"
        assert msg.exchange == "events"

    def test_message_is_expired_without_expiration(self):
        """Test message without expiration is not expired."""
        msg = Message()
        assert msg.is_expired() is False

    def test_message_is_expired_future_expiration(self):
        """Test message with future expiration is not expired."""
        msg = Message(expiration=time.time() + 3600)
        assert msg.is_expired() is False

    def test_message_is_expired_past_expiration(self):
        """Test message with past expiration is expired."""
        msg = Message(expiration=time.time() - 3600)
        assert msg.is_expired() is True

    def test_message_can_retry_default(self):
        """Test message can retry by default."""
        msg = Message()
        assert msg.can_retry() is True

    def test_message_can_retry_after_some_retries(self):
        """Test message can retry after some retries."""
        msg = Message(retry_count=1, max_retries=3)
        assert msg.can_retry() is True

    def test_message_cannot_retry_at_max(self):
        """Test message cannot retry at max retries."""
        msg = Message(retry_count=3, max_retries=3)
        assert msg.can_retry() is False

    def test_message_cannot_retry_over_max(self):
        """Test message cannot retry over max retries."""
        msg = Message(retry_count=5, max_retries=3)
        assert msg.can_retry() is False

    def test_message_with_correlation_id(self):
        """Test message with correlation id for request-reply."""
        correlation_id = str(uuid.uuid4())
        msg = Message(
            correlation_id=correlation_id,
            reply_to="reply.queue",
        )
        assert msg.correlation_id == correlation_id
        assert msg.reply_to == "reply.queue"

    def test_message_unique_ids(self):
        """Test that messages get unique IDs."""
        msg1 = Message()
        msg2 = Message()
        assert msg1.id != msg2.id

    def test_message_custom_metadata(self):
        """Test message with custom metadata."""
        metadata = {"source": "test", "trace_id": "abc123"}
        msg = Message(metadata=metadata)
        assert msg.metadata == metadata


class TestQueueConfig:
    """Tests for QueueConfig class."""

    def test_queue_defaults(self):
        """Test queue config defaults."""
        config = QueueConfig(name="test-queue")

        assert config.name == "test-queue"
        assert config.durable is True
        assert config.exclusive is False
        assert config.auto_delete is False
        assert config.arguments == {}
        assert config.max_length is None
        assert config.max_length_bytes is None
        assert config.ttl is None
        assert config.dlq_enabled is True
        assert config.dlq_name is None

    def test_queue_with_limits(self):
        """Test queue config with limits."""
        config = QueueConfig(
            name="limited-queue",
            max_length=10000,
            max_length_bytes=104857600,
            ttl=3600,
        )
        assert config.max_length == 10000
        assert config.max_length_bytes == 104857600
        assert config.ttl == 3600

    def test_queue_with_dlq(self):
        """Test queue config with explicit DLQ."""
        config = QueueConfig(
            name="main-queue",
            dlq_enabled=True,
            dlq_name="main-queue.dlq",
        )
        assert config.dlq_enabled is True
        assert config.dlq_name == "main-queue.dlq"

    def test_temporary_queue(self):
        """Test temporary queue config."""
        config = QueueConfig(
            name="temp-queue",
            durable=False,
            exclusive=True,
            auto_delete=True,
        )
        assert config.durable is False
        assert config.exclusive is True
        assert config.auto_delete is True


class TestExchangeConfig:
    """Tests for ExchangeConfig class."""

    def test_exchange_defaults(self):
        """Test exchange config defaults."""
        config = ExchangeConfig(name="test-exchange")

        assert config.name == "test-exchange"
        assert config.type == "direct"
        assert config.durable is True
        assert config.auto_delete is False
        assert config.arguments == {}

    def test_topic_exchange(self):
        """Test topic exchange config."""
        config = ExchangeConfig(name="events", type="topic")
        assert config.type == "topic"

    def test_fanout_exchange(self):
        """Test fanout exchange config."""
        config = ExchangeConfig(name="broadcast", type="fanout")
        assert config.type == "fanout"


class TestBackendConfig:
    """Tests for BackendConfig class."""

    def test_backend_defaults(self):
        """Test backend config with required fields."""
        config = BackendConfig(
            type=BackendType.MEMORY,
            connection_url="memory://",
        )

        assert config.type == BackendType.MEMORY
        assert config.connection_url == "memory://"
        assert config.pool_size == 10
        assert config.max_connections == 100
        assert config.timeout == 30
        assert config.retry_attempts == 3
        assert config.retry_delay == 1.0
        assert config.health_check_interval == 30

    def test_rabbitmq_backend(self):
        """Test RabbitMQ backend config."""
        config = BackendConfig(
            type=BackendType.RABBITMQ,
            connection_url="amqp://guest:guest@localhost:5672/",  # pragma: allowlist secret
        )
        assert config.type == BackendType.RABBITMQ

    def test_kafka_backend(self):
        """Test Kafka backend config."""
        config = BackendConfig(
            type=BackendType.KAFKA,
            connection_url="kafka://localhost:9092",
            pool_size=5,
        )
        assert config.type == BackendType.KAFKA
        assert config.pool_size == 5


class TestProducerConfig:
    """Tests for ProducerConfig class."""

    def test_producer_defaults(self):
        """Test producer config defaults."""
        config = ProducerConfig(name="test-producer")

        assert config.name == "test-producer"
        assert config.exchange is None
        assert config.routing_key == ""
        assert config.default_priority == MessagePriority.NORMAL

    def test_producer_with_exchange(self):
        """Test producer config with exchange."""
        config = ProducerConfig(
            name="event-producer",
            exchange="events",
            routing_key="events.user",
            default_priority=MessagePriority.HIGH,
        )
        assert config.exchange == "events"
        assert config.routing_key == "events.user"
        assert config.default_priority == MessagePriority.HIGH


class TestMessagingExceptions:
    """Tests for messaging exception classes."""

    def test_messaging_error(self):
        """Test base messaging error."""
        with pytest.raises(MessagingError):
            raise MessagingError("Test error")

    def test_messaging_error_with_message(self):
        """Test messaging error preserves message."""
        try:
            raise MessagingError("Custom message")
        except MessagingError as e:
            assert str(e) == "Custom message"


class TestConsumerConfig:
    """Tests for ConsumerConfig class."""

    def test_consumer_defaults(self):
        """Test consumer config defaults."""
        from mmf.core.messaging import ConsumerConfig

        config = ConsumerConfig(name="test-consumer", queue="test-queue")

        assert config.name == "test-consumer"
        assert config.queue == "test-queue"
        assert config.mode == ConsumerMode.PULL
        assert config.auto_ack is False
        assert config.prefetch_count == 10
        assert config.max_workers == 5
        assert config.timeout == 30
        assert config.retry_attempts == 3
        assert config.dlq_enabled is True
        assert config.batch_processing is False

    def test_consumer_push_mode(self):
        """Test consumer config with push mode."""
        from mmf.core.messaging import ConsumerConfig

        config = ConsumerConfig(
            name="push-consumer",
            queue="events",
            mode=ConsumerMode.PUSH,
            auto_ack=True,
            prefetch_count=1,
        )

        assert config.mode == ConsumerMode.PUSH
        assert config.auto_ack is True
        assert config.prefetch_count == 1

    def test_consumer_batch_mode(self):
        """Test consumer config with batch processing."""
        from mmf.core.messaging import ConsumerConfig

        config = ConsumerConfig(
            name="batch-consumer",
            queue="batch-queue",
            batch_processing=True,
            batch_size=50,
            batch_timeout=10.0,
        )

        assert config.batch_processing is True
        assert config.batch_size == 50
        assert config.batch_timeout == 10.0


class TestRoutingRule:
    """Tests for RoutingRule class."""

    def test_routing_rule_defaults(self):
        """Test routing rule defaults."""
        from mmf.core.messaging import RoutingRule

        rule = RoutingRule(
            pattern="user.*",
            exchange="users",
            routing_key="user.events",
        )

        assert rule.pattern == "user.*"
        assert rule.exchange == "users"
        assert rule.routing_key == "user.events"
        assert rule.priority == 0
        assert rule.condition is None
        assert rule.metadata == {}

    def test_routing_rule_with_priority(self):
        """Test routing rule with priority."""
        from mmf.core.messaging import RoutingRule

        rule = RoutingRule(
            pattern="urgent.*",
            exchange="urgent",
            routing_key="urgent.all",
            priority=100,
        )

        assert rule.priority == 100

    def test_routing_rule_with_condition(self):
        """Test routing rule with condition."""
        from mmf.core.messaging import RoutingRule

        rule = RoutingRule(
            pattern="order.*",
            exchange="orders",
            routing_key="order.process",
            condition="message.body.amount > 1000",
        )

        assert rule.condition == "message.body.amount > 1000"


class TestRoutingConfig:
    """Tests for RoutingConfig class."""

    def test_routing_config_defaults(self):
        """Test routing config defaults."""
        from mmf.core.messaging import RoutingConfig

        config = RoutingConfig()

        assert config.rules == []
        assert config.default_exchange is None
        assert config.default_routing_key == ""
        assert config.enable_fallback is True
        assert config.fallback_exchange is None

    def test_routing_config_with_rules(self):
        """Test routing config with rules."""
        from mmf.core.messaging import RoutingConfig, RoutingRule

        rule1 = RoutingRule(pattern="a.*", exchange="a", routing_key="a.all")
        rule2 = RoutingRule(pattern="b.*", exchange="b", routing_key="b.all")

        config = RoutingConfig(
            rules=[rule1, rule2],
            default_exchange="default",
            default_routing_key="default.route",
        )

        assert len(config.rules) == 2
        assert config.default_exchange == "default"
        assert config.default_routing_key == "default.route"


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_retry_config_defaults(self):
        """Test retry config defaults."""
        from mmf.core.messaging import RetryConfig

        config = RetryConfig()

        assert config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 300.0
        assert config.backoff_multiplier == 2.0
        assert config.jitter is True

    def test_retry_config_fixed_delay(self):
        """Test retry config with fixed delay strategy."""
        from mmf.core.messaging import RetryConfig

        config = RetryConfig(
            strategy=RetryStrategy.FIXED_DELAY,
            max_attempts=5,
            initial_delay=5.0,
        )

        assert config.strategy == RetryStrategy.FIXED_DELAY
        assert config.max_attempts == 5
        assert config.initial_delay == 5.0

    def test_retry_config_linear_backoff(self):
        """Test retry config with linear backoff strategy."""
        from mmf.core.messaging import RetryConfig

        config = RetryConfig(
            strategy=RetryStrategy.LINEAR_BACKOFF,
            backoff_multiplier=1.5,
            jitter=False,
        )

        assert config.strategy == RetryStrategy.LINEAR_BACKOFF
        assert config.backoff_multiplier == 1.5
        assert config.jitter is False


class TestDLQMessage:
    """Tests for DLQMessage class."""

    def test_dlq_message_defaults(self):
        """Test DLQ message defaults."""
        from mmf.core.messaging import DLQMessage

        message = Message(body={"test": "data"})
        dlq_msg = DLQMessage(message=message)

        assert dlq_msg.message == message
        assert dlq_msg.failure_count == 0
        assert dlq_msg.retry_attempts == 0
        assert dlq_msg.failure_reasons == []
        assert dlq_msg.exceptions == []

    def test_dlq_message_add_failure(self):
        """Test adding failure to DLQ message."""
        from mmf.core.messaging import DLQMessage

        message = Message(body={"test": "data"})
        dlq_msg = DLQMessage(message=message)

        dlq_msg.add_failure("Connection timeout")

        assert dlq_msg.failure_count == 1
        assert "Connection timeout" in dlq_msg.failure_reasons
        assert len(dlq_msg.exceptions) == 0

    def test_dlq_message_add_failure_with_exception(self):
        """Test adding failure with exception to DLQ message."""
        from mmf.core.messaging import DLQMessage

        message = Message(body={"test": "data"})
        dlq_msg = DLQMessage(message=message)

        error = ValueError("Invalid data")
        dlq_msg.add_failure("Validation failed", error)

        assert dlq_msg.failure_count == 1
        assert "Validation failed" in dlq_msg.failure_reasons
        assert error in dlq_msg.exceptions

    def test_dlq_message_multiple_failures(self):
        """Test multiple failures on DLQ message."""
        from mmf.core.messaging import DLQMessage

        message = Message(body={"test": "data"})
        dlq_msg = DLQMessage(message=message)

        dlq_msg.add_failure("First failure")
        dlq_msg.add_failure("Second failure", RuntimeError("Error"))
        dlq_msg.add_failure("Third failure")

        assert dlq_msg.failure_count == 3
        assert len(dlq_msg.failure_reasons) == 3
        assert len(dlq_msg.exceptions) == 1


class TestDLQConfig:
    """Tests for DLQConfig class."""

    def test_dlq_config_defaults(self):
        """Test DLQ config defaults."""
        from mmf.core.messaging import DLQConfig

        config = DLQConfig()

        assert config.enabled is True
        assert config.queue_name is None
        assert config.exchange_name is None
        assert config.routing_key == "dlq"
        assert config.max_retries == 3
        assert config.retry_delay == 60.0
        assert config.ttl is None
        assert config.max_length is None
        assert config.retry_config is None

    def test_dlq_config_custom(self):
        """Test DLQ config with custom values."""
        from mmf.core.messaging import DLQConfig, RetryConfig

        retry = RetryConfig(max_attempts=5)
        config = DLQConfig(
            enabled=True,
            queue_name="my-dlq",
            exchange_name="dlq-exchange",
            routing_key="dead.letters",
            max_retries=5,
            retry_delay=120.0,
            ttl=86400,
            max_length=10000,
            retry_config=retry,
        )

        assert config.queue_name == "my-dlq"
        assert config.exchange_name == "dlq-exchange"
        assert config.routing_key == "dead.letters"
        assert config.ttl == 86400
        assert config.retry_config == retry

    def test_dlq_config_disabled(self):
        """Test DLQ config when disabled."""
        from mmf.core.messaging import DLQConfig

        config = DLQConfig(enabled=False)

        assert config.enabled is False


class TestMessagingConfig:
    """Tests for MessagingConfig class."""

    def test_messaging_config_minimal(self):
        """Test messaging config with minimal required fields."""
        from mmf.core.messaging import DLQConfig, MessagingConfig, RoutingConfig

        backend = BackendConfig(
            type=BackendType.MEMORY,
            connection_url="memory://localhost",
        )
        config = MessagingConfig(backend=backend)

        assert config.backend == backend
        assert config.default_exchange is None
        assert config.default_queue is None
        assert isinstance(config.dlq, DLQConfig)
        assert isinstance(config.routing, RoutingConfig)
        assert config.enable_monitoring is True
        assert config.enable_tracing is True
        assert config.enable_metrics is True

    def test_messaging_config_full(self):
        """Test messaging config with all fields."""
        from mmf.core.messaging import DLQConfig, MessagingConfig, RoutingConfig

        backend = BackendConfig(
            type=BackendType.RABBITMQ,
            connection_url="amqp://localhost:5672",
        )
        exchange = ExchangeConfig(name="main", type="topic")
        queue = QueueConfig(name="default-queue")
        dlq = DLQConfig(queue_name="dead-letters")
        routing = RoutingConfig(default_exchange="main")

        config = MessagingConfig(
            backend=backend,
            default_exchange=exchange,
            default_queue=queue,
            dlq=dlq,
            routing=routing,
            enable_monitoring=False,
            enable_tracing=False,
            enable_metrics=True,
            metadata={"env": "production"},
        )

        assert config.default_exchange == exchange
        assert config.default_queue == queue
        assert config.dlq == dlq
        assert config.routing == routing
        assert config.enable_monitoring is False
        assert config.enable_tracing is False
        assert config.metadata["env"] == "production"


class TestMessagingExceptionHierarchy:
    """Tests for messaging exception inheritance."""

    def test_all_exceptions_inherit_from_messaging_error(self):
        """Test all messaging exceptions inherit from MessagingError."""
        from mmf.core.messaging import (
            ConsumerError,
            DLQError,
            MessagingConnectionError,
            MiddlewareError,
            ProducerError,
            RoutingError,
            SerializationError,
        )

        assert issubclass(MessagingConnectionError, MessagingError)
        assert issubclass(SerializationError, MessagingError)
        assert issubclass(RoutingError, MessagingError)
        assert issubclass(ConsumerError, MessagingError)
        assert issubclass(ProducerError, MessagingError)
        assert issubclass(DLQError, MessagingError)
        assert issubclass(MiddlewareError, MessagingError)

    def test_catch_all_with_base_exception(self):
        """Test that base exception catches all derived exceptions."""
        from mmf.core.messaging import ConsumerError

        try:
            raise ConsumerError("Consumer failed")
        except MessagingError as e:
            assert "Consumer failed" in str(e)
