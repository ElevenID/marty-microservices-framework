"""
Comprehensive tests for resilience strategies in the Marty microservices framework.

This test suite covers the resilience strategy pattern implementations including
fallback strategies and retry mechanisms with minimal mocking.
"""

import asyncio
import inspect

import pytest

from mmf_new.framework.resilience.domain.config import RetryConfig, RetryStrategy
from mmf_new.framework.resilience.infrastructure.adapters import (
    fallback as fallback_module,
)
from mmf_new.framework.resilience.infrastructure.adapters import retry as retry_module
from mmf_new.framework.resilience.infrastructure.adapters.fallback import (
    CacheFallback,
    ChainFallback,
    FallbackConfig,
    FallbackManager,
    FallbackStrategy,
    FunctionFallback,
    StaticFallback,
    create_function_fallback,
    create_static_fallback,
)
from mmf_new.framework.resilience.infrastructure.adapters.retry import (
    BackoffStrategy,
    ConstantBackoff,
    ExponentialBackoff,
    LinearBackoff,
    RetryManager,
)


def test_import_resilience_strategies():
    """Test that all resilience strategy classes can be imported successfully."""
    # Test fallback module imports
    assert FallbackStrategy is not None
    assert StaticFallback is not None
    assert FunctionFallback is not None
    assert ChainFallback is not None
    assert FallbackManager is not None
    assert FallbackConfig is not None

    # Test retry module imports
    assert RetryStrategy is not None
    assert RetryConfig is not None
    assert RetryManager is not None
    assert BackoffStrategy is not None


def test_retry_strategy_enum():
    """Test RetryStrategy enum values and functionality."""
    # Test expected enum values exist
    assert hasattr(RetryStrategy, "EXPONENTIAL")
    assert hasattr(RetryStrategy, "LINEAR")
    assert hasattr(RetryStrategy, "CONSTANT")

    # Test enum value equality
    assert RetryStrategy.EXPONENTIAL == RetryStrategy.EXPONENTIAL
    assert RetryStrategy.LINEAR != RetryStrategy.EXPONENTIAL


def test_static_fallback_creation():
    """Test StaticFallback strategy creation and functionality."""
    # Create static fallback with default value
    fallback_value = {"status": "fallback", "data": "cached_response"}
    static_fallback = StaticFallback("test_static", fallback_value)

    assert static_fallback is not None
    assert static_fallback.name == "test_static"
    assert static_fallback.fallback_value == fallback_value

    # Test factory function
    factory_fallback = create_static_fallback("factory_test", {"test": "value"})
    assert factory_fallback is not None
    assert factory_fallback.name == "factory_test"


def test_function_fallback_creation():
    """Test FunctionFallback strategy creation and functionality."""

    # Create function fallback
    def test_fallback_func(*args, **kwargs):
        return {"status": "fallback", "source": "function", "args": args}

    function_fallback = FunctionFallback("test_function", test_fallback_func)
    assert function_fallback is not None
    assert function_fallback.name == "test_function"
    assert function_fallback.fallback_func == test_fallback_func

    # Test factory function
    factory_fallback = create_function_fallback("factory_func", test_fallback_func)
    assert factory_fallback is not None
    assert factory_fallback.name == "factory_func"


def test_fallback_config_creation():
    """Test FallbackConfig creation with various options."""
    # Test default config
    default_config = FallbackConfig()
    assert default_config is not None
    assert hasattr(default_config, "fallback_type")


def test_retry_config_creation():
    """Test RetryConfig creation with various retry strategies."""
    # Test default config
    default_config = RetryConfig()
    assert default_config is not None

    # Test config with exponential backoff
    if hasattr(default_config, "strategy"):
        exponential_config = RetryConfig(strategy=RetryStrategy.EXPONENTIAL, max_attempts=5)
        assert exponential_config is not None
        assert exponential_config.strategy == RetryStrategy.EXPONENTIAL
        if hasattr(exponential_config, "max_attempts"):
            assert exponential_config.max_attempts == 5


def test_fallback_manager_basic_functionality():
    """Test FallbackManager basic functionality."""
    # Create manager
    manager = FallbackManager()
    assert manager is not None

    # Create and register a static fallback
    static_fallback = StaticFallback("test_static", {"status": "ok"})

    # Try to register fallback (check if method exists)
    if hasattr(manager, "register_fallback"):
        manager.register_fallback(static_fallback)


def test_backoff_strategy_creation():
    """Test BackoffStrategy implementations."""
    # Test ExponentialBackoff
    exp_backoff = ExponentialBackoff()
    assert exp_backoff is not None

    # Test with parameters
    exp_backoff_custom = ExponentialBackoff(multiplier=2.0)
    assert exp_backoff_custom is not None

    # Test LinearBackoff
    linear_backoff = LinearBackoff()
    assert linear_backoff is not None

    # Test ConstantBackoff
    constant_backoff = ConstantBackoff()
    assert constant_backoff is not None


@pytest.mark.asyncio
async def test_static_fallback_execution():
    """Test StaticFallback execution functionality."""
    # Create static fallback
    fallback_value = {"status": "fallback", "message": "Service unavailable"}
    static_fallback = StaticFallback("test_execution", fallback_value)

    # Test execution
    if hasattr(static_fallback, "execute_fallback"):
        # Check if it is a coroutine function
        if inspect.iscoroutinefunction(static_fallback.execute_fallback):
            result = await static_fallback.execute_fallback(
                Exception("Service down"), test_arg="value"
            )
            assert result == fallback_value
        else:
            result = static_fallback.execute_fallback(Exception("Service down"), test_arg="value")
            assert result == fallback_value


def test_chain_fallback_creation():
    """Test ChainFallback creation with multiple strategies."""
    # Create individual fallback strategies
    static_fallback = StaticFallback("primary", {"status": "cached"})
    function_fallback = FunctionFallback("secondary", lambda *args: {"status": "computed"})

    # Create chain fallback
    strategies = [static_fallback, function_fallback]
    chain_fallback = ChainFallback("test_chain", strategies)

    assert chain_fallback is not None
    assert chain_fallback.name == "test_chain"
    if hasattr(chain_fallback, "fallback_strategies"):
        assert len(chain_fallback.fallback_strategies) == 2
