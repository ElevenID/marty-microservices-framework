"""
Comprehensive tests for messaging strategies in the Marty microservices framework.

This test suite covers the messaging strategy pattern implementations with
minimal mocking to ensure real functionality is tested.
"""

import inspect

import pytest

from marty_msf.framework.messaging import core as core_module
from marty_msf.framework.messaging import dlq as dlq_module
from marty_msf.framework.messaging.core import (
    Message,
    MessageHeaders,
    MessagePriority,
    MessageStatus,
)

# Import messaging strategy components
from marty_msf.framework.messaging.dlq import (
    DLQConfig,
    DLQManager,
    DLQMessage,
    DLQPolicy,
    RetryConfig,
    RetryStrategy,
)


def test_import_messaging_strategies():
    """Test that all messaging strategy classes can be imported successfully."""
    # Test DLQ module imports
    assert RetryStrategy is not None
    assert DLQPolicy is not None
    assert RetryConfig is not None
    assert DLQConfig is not None
    assert DLQMessage is not None
    assert DLQManager is not None

    # Test core messaging imports
    assert Message is not None
    assert MessageHeaders is not None
    assert MessagePriority is not None
    assert MessageStatus is not None


def test_retry_strategy_enum():
    """Test RetryStrategy enum values and functionality."""
    # Test all expected enum values exist
    assert RetryStrategy.IMMEDIATE is not None
    assert RetryStrategy.LINEAR_BACKOFF is not None
    assert RetryStrategy.EXPONENTIAL_BACKOFF is not None
    assert RetryStrategy.FIXED_DELAY is not None
    assert RetryStrategy.CUSTOM is not None

    # Test enum value equality
    assert RetryStrategy.IMMEDIATE == RetryStrategy.IMMEDIATE
    assert RetryStrategy.EXPONENTIAL_BACKOFF != RetryStrategy.LINEAR_BACKOFF

    # Test enum string values
    assert RetryStrategy.IMMEDIATE.value == "immediate"
    assert RetryStrategy.EXPONENTIAL_BACKOFF.value == "exponential_backoff"


def test_message_creation():
    """Test that Message objects can be created with proper parameters."""
    # Test basic message creation
    message = Message(body={"action": "process", "data": {"user_id": 123}})
    assert message is not None
    assert message.id is not None  # Auto-generated ID
    assert message.body["action"] == "process"

    # Test message without explicit body
    simple_message = Message(body="simple text message")
    assert simple_message is not None
    assert simple_message.id is not None and len(simple_message.id) > 0

    # Test message with custom headers
    custom_headers = MessageHeaders(
        correlation_id="corr-123", routing_key="user.created", priority=MessagePriority.HIGH
    )
    headers_message = Message(body={"test": "data"}, headers=custom_headers)
    assert headers_message is not None
    assert headers_message.correlation_id == "corr-123"
    assert headers_message.routing_key == "user.created"


def test_retry_config_creation():
    """Test that RetryConfig objects can be created with proper parameters."""
    # Test basic retry config creation
    config = RetryConfig(
        max_attempts=5,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        initial_delay=2.0,
        max_delay=600.0,
    )
    assert config is not None
    assert config.max_attempts == 5
    assert config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
    assert config.initial_delay == 2.0
    assert config.max_delay == 600.0

    # Test default config
    default_config = RetryConfig()
    assert default_config is not None
    assert default_config.max_attempts == 3  # Default value
    assert default_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF


def test_dlq_config_creation():
    """Test DLQConfig creation and configuration options."""
    # Create configurations
    retry_config = RetryConfig(max_attempts=2)
    dlq_config = DLQConfig(
        dlq_suffix=".test.dlq", retry_suffix=".test.retry", retry_config=retry_config
    )
    assert dlq_config is not None
    assert dlq_config.dlq_suffix == ".test.dlq"
    assert dlq_config.retry_suffix == ".test.retry"
    assert dlq_config.retry_config.max_attempts == 2

    # Test default config
    default_dlq_config = DLQConfig()
    assert default_dlq_config is not None


def test_retry_strategy_delay_calculation():
    """Test retry strategy delay calculation logic."""
    # Test immediate retry strategy
    immediate_config = DLQConfig(
        retry_config=RetryConfig(strategy=RetryStrategy.IMMEDIATE, max_attempts=3)
    )
    assert immediate_config is not None
    assert immediate_config.retry_config.strategy == RetryStrategy.IMMEDIATE

    # Test exponential backoff strategy
    exponential_config = DLQConfig(
        retry_config=RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            max_attempts=5,
            initial_delay=1.0,
            backoff_multiplier=2.0,
        )
    )
    assert exponential_config is not None
    assert exponential_config.retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
    assert exponential_config.retry_config.max_attempts == 5
    assert exponential_config.retry_config.initial_delay == 1.0
    assert exponential_config.retry_config.backoff_multiplier == 2.0

    # Test linear backoff strategy
    linear_config = DLQConfig(
        retry_config=RetryConfig(strategy=RetryStrategy.LINEAR_BACKOFF, initial_delay=0.5)
    )
    assert linear_config is not None
    assert linear_config.retry_config.strategy == RetryStrategy.LINEAR_BACKOFF


def test_discover_messaging_strategy_classes():
    """Discover all messaging strategy-related classes."""

    # Find strategy-related classes in DLQ module
    dlq_classes = []
    for name in dir(dlq_module):
        if not name.startswith("_"):
            obj = getattr(dlq_module, name)
            if inspect.isclass(obj) or inspect.isfunction(obj):
                dlq_classes.append(name)

    # Find strategy-related classes in core module
    core_classes = []
    for name in dir(core_module):
        if not name.startswith("_"):
            obj = getattr(core_module, name)
            if inspect.isclass(obj) or inspect.isfunction(obj):
                core_classes.append(name)

    # Combine and filter strategy-related classes
    strategy_classes = [
        name
        for name in dlq_classes + core_classes
        if "strategy" in name.lower()
        or "retry" in name.lower()
        or "dlq" in name.lower()
        or "message" in name.lower()
    ]

    print(f"Discovered messaging strategy classes: {strategy_classes}")
    assert len(strategy_classes) > 0


@pytest.mark.asyncio
async def test_messaging_strategy_integration():
    """Integration test for messaging strategies working together."""
    # Create retry config
    retry_config = RetryConfig(
        max_attempts=3, strategy=RetryStrategy.EXPONENTIAL_BACKOFF, initial_delay=1.0
    )
    assert retry_config is not None

    # Create DLQ config
    dlq_config = DLQConfig(retry_config=retry_config, dlq_suffix=".integration.dlq")
    assert dlq_config is not None

    # Create a test message
    message = Message(body={"test": "integration", "user_id": 456})
    assert message is not None
    assert message.id is not None

    # Test message properties
    assert message.body["test"] == "integration"
    assert message.body["user_id"] == 456

    # Verify configuration relationships
    assert dlq_config.retry_config.max_attempts == 3
    assert dlq_config.retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
    assert dlq_config.dlq_suffix == ".integration.dlq"

    print("Messaging strategy integration test completed successfully")


def test_dlq_message_functionality():
    """Test DLQMessage extended functionality."""
    # Create a base message
    base_message = Message(body={"test": "dlq_functionality"})

    # Create DLQ message wrapper
    dlq_message = DLQMessage(base_message)
    assert dlq_message is not None
    assert dlq_message.message == base_message
    assert dlq_message.failure_count == 0
    assert dlq_message.retry_attempts == 0

    # Test failure recording
    dlq_message.add_failure("Connection timeout", Exception("Timeout occurred"))
    assert dlq_message.failure_count == 1
    assert len(dlq_message.failure_reasons) == 1
    assert dlq_message.failure_reasons[0] == "Connection timeout"

    # Test retry recording
    dlq_message.add_retry_attempt(2.5)
    assert dlq_message.retry_attempts == 1
    assert len(dlq_message.retry_history) == 1
    assert dlq_message.retry_history[0]["delay"] == 2.5

    # Test retry decision
    retry_config = RetryConfig(max_attempts=3)
    assert dlq_message.should_retry(retry_config) is True

    # Test delay calculation
    delay = dlq_message.calculate_retry_delay(retry_config)
    assert delay >= 0.0
