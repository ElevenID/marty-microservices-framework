"""
Fallback Pattern Implementation

Provides graceful degradation strategies when primary operations fail,
including static fallbacks, function-based fallbacks, and cache fallbacks.
"""

import asyncio
import builtins
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


class FallbackType(Enum):
    """Types of fallback strategies."""

    STATIC = "static"  # Return static value
    FUNCTION = "function"  # Call fallback function
    CACHE = "cache"  # Use cached value
    CHAIN = "chain"  # Chain multiple fallbacks
    CIRCUIT_BREAKER = "circuit"  # Circuit breaker fallback


class FallbackError(Exception):
    """Exception raised when all fallback strategies fail."""

    def __init__(self, message: str, original_error: Exception, fallback_attempts: int):
        super().__init__(message)
        self.original_error = original_error
        self.fallback_attempts = fallback_attempts


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior."""

    # Fallback strategy type
    fallback_type: FallbackType = FallbackType.STATIC

    # Exception types that trigger fallbacks
    trigger_exceptions: tuple = (Exception,)

    # Exception types that don't trigger fallbacks
    ignore_exceptions: tuple = ()

    # Enable fallback logging
    log_fallbacks: bool = True

    # Maximum fallback attempts in chain
    max_fallback_attempts: int = 3

    # Timeout for fallback operations
    fallback_timeout: float = 10.0

    # Enable metrics collection
    collect_metrics: bool = True


class FallbackStrategy(ABC):
    """Abstract base class for fallback strategies."""

    def __init__(self, name: str, config: FallbackConfig | None = None):
        self.name = name
        self.config = config or FallbackConfig()

        # Metrics
        self._total_attempts = 0
        self._successful_fallbacks = 0
        self._failed_fallbacks = 0
        self._total_fallback_time = 0.0

    @abstractmethod
    async def execute_fallback(self, original_error: Exception, *args, **kwargs) -> T:
        """Execute the fallback strategy."""

    def _record_attempt(self, success: bool, execution_time: float):
        """Record fallback attempt."""
        self._total_attempts += 1
        self._total_fallback_time += execution_time

        if success:
            self._successful_fallbacks += 1
        else:
            self._failed_fallbacks += 1

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get fallback strategy statistics."""
        success_rate = self._successful_fallbacks / max(1, self._total_attempts)
        avg_execution_time = self._total_fallback_time / max(1, self._total_attempts)

        return {
            "name": self.name,
            "type": self.config.fallback_type.value,
            "total_attempts": self._total_attempts,
            "successful_fallbacks": self._successful_fallbacks,
            "failed_fallbacks": self._failed_fallbacks,
            "success_rate": success_rate,
            "average_execution_time": avg_execution_time,
        }


class StaticFallback(FallbackStrategy):
    """Fallback that returns a static value."""

    def __init__(self, name: str, fallback_value: T, config: FallbackConfig | None = None):
        super().__init__(name, config)
        self.fallback_value = fallback_value

    async def execute_fallback(self, original_error: Exception, *args, **kwargs) -> T:
        """Return static fallback value."""
        start_time = time.time()

        try:
            if self.config.log_fallbacks:
                logger.info(
                    "Using static fallback '%s' due to error: %s",
                    self.name,
                    str(original_error),
                )

            self._record_attempt(True, time.time() - start_time)
            return self.fallback_value

        except Exception as e:
            self._record_attempt(False, time.time() - start_time)
            raise FallbackError(f"Static fallback '{self.name}' failed", original_error, 1) from e


class FunctionFallback(FallbackStrategy):
    """Fallback that calls a function."""

    def __init__(
        self,
        name: str,
        fallback_func: Callable[..., T],
        config: FallbackConfig | None = None,
    ):
        super().__init__(name, config)
        self.fallback_func = fallback_func

    async def execute_fallback(self, original_error: Exception, *args, **kwargs) -> T:
        """Execute fallback function."""
        start_time = time.time()

        try:
            if self.config.log_fallbacks:
                logger.info(
                    "Using function fallback '%s' due to error: %s",
                    self.name,
                    str(original_error),
                )

            if asyncio.iscoroutinefunction(self.fallback_func):
                result = await asyncio.wait_for(
                    self.fallback_func(*args, **kwargs),
                    timeout=self.config.fallback_timeout,
                )
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, self.fallback_func, *args, **kwargs),
                    timeout=self.config.fallback_timeout,
                )

            self._record_attempt(True, time.time() - start_time)
            return result

        except Exception as e:
            self._record_attempt(False, time.time() - start_time)
            raise FallbackError(f"Function fallback '{self.name}' failed", original_error, 1) from e


class CacheFallback(FallbackStrategy):
    """Fallback that uses cached values."""

    def __init__(
        self,
        name: str,
        cache_provider: Callable[[str], T | None],
        cache_key_func: Callable[..., str],
        config: FallbackConfig | None = None,
    ):
        super().__init__(name, config)
        self.cache_provider = cache_provider
        self.cache_key_func = cache_key_func

    async def execute_fallback(self, original_error: Exception, *args, **kwargs) -> T:
        """Get value from cache."""
        start_time = time.time()

        try:
            cache_key = self.cache_key_func(*args, **kwargs)

            if asyncio.iscoroutinefunction(self.cache_provider):
                cached_value = await self.cache_provider(cache_key)
            else:
                cached_value = self.cache_provider(cache_key)

            if cached_value is not None:
                if self.config.log_fallbacks:
                    logger.info(
                        "Using cache fallback '%s' with key '%s' due to error: %s",
                        self.name,
                        cache_key,
                        str(original_error),
                    )

                self._record_attempt(True, time.time() - start_time)
                return cached_value
            self._record_attempt(False, time.time() - start_time)
            raise FallbackError(
                f"Cache fallback '{self.name}' returned None for key '{cache_key}'",
                original_error,
                1,
            )

        except Exception as e:
            self._record_attempt(False, time.time() - start_time)
            raise FallbackError(f"Cache fallback '{self.name}' failed", original_error, 1) from e


class ChainFallback(FallbackStrategy):
    """Fallback that chains multiple strategies."""

    def __init__(
        self,
        name: str,
        fallback_strategies: builtins.list[FallbackStrategy],
        config: FallbackConfig | None = None,
    ):
        super().__init__(name, config)
        self.fallback_strategies = fallback_strategies

    async def execute_fallback(self, original_error: Exception, *args, **kwargs) -> T:
        """Try fallback strategies in order."""
        start_time = time.time()
        last_error = original_error
        attempts = 0

        for strategy in self.fallback_strategies:
            if attempts >= self.config.max_fallback_attempts:
                break

            try:
                attempts += 1
                result = await strategy.execute_fallback(last_error, *args, **kwargs)

                if self.config.log_fallbacks:
                    logger.info(
                        "Chain fallback '%s' succeeded with strategy '%s' on attempt %d",
                        self.name,
                        strategy.name,
                        attempts,
                    )

                self._record_attempt(True, time.time() - start_time)
                return result

            except FallbackError as e:
                last_error = e
                if self.config.log_fallbacks:
                    logger.warning(
                        "Chain fallback '%s' strategy '%s' failed: %s",
                        self.name,
                        strategy.name,
                        str(e),
                    )
                continue

        self._record_attempt(False, time.time() - start_time)
        raise FallbackError(
            f"All fallback strategies in chain '{self.name}' failed",
            original_error,
            attempts,
        )


class FallbackManager:
    """Manages fallback operations."""

    def __init__(self, config: FallbackConfig | None = None):
        self.config = config or FallbackConfig()
        self._fallback_strategies: builtins.dict[str, FallbackStrategy] = {}

        # Metrics
        self._total_operations = 0
        self._fallback_triggered = 0
        self._fallback_successful = 0

    def register_fallback(self, strategy: FallbackStrategy):
        """Register a fallback strategy."""
        self._fallback_strategies[strategy.name] = strategy
        logger.info("Registered fallback strategy '%s'", strategy.name)

    def _should_trigger_fallback(self, exception: Exception) -> bool:
        """Check if exception should trigger fallback."""
        # Check if exception should be ignored
        if isinstance(exception, self.config.ignore_exceptions):
            return False

        # Check if exception triggers fallback
        return isinstance(exception, self.config.trigger_exceptions)

    async def execute_with_fallback(
        self,
        func: Callable[..., T],
        fallback_strategy: str | FallbackStrategy,
        *args,
        **kwargs,
    ) -> T:
        """Execute function with fallback protection."""
        self._total_operations += 1

        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, *args, **kwargs)

        except Exception as e:
            if not self._should_trigger_fallback(e):
                raise

            self._fallback_triggered += 1

            # Get fallback strategy
            if isinstance(fallback_strategy, str):
                if fallback_strategy not in self._fallback_strategies:
                    raise FallbackError(f"Unknown fallback strategy '{fallback_strategy}'", e, 0)
                strategy = self._fallback_strategies[fallback_strategy]
            else:
                strategy = fallback_strategy

            try:
                result = await strategy.execute_fallback(e, *args, **kwargs)
                self._fallback_successful += 1
                return result

            except FallbackError:
                raise
            except Exception as fallback_error:
                raise FallbackError(
                    f"Fallback strategy '{strategy.name}' failed with unexpected error",
                    e,
                    1,
                ) from fallback_error

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get fallback manager statistics."""
        fallback_rate = self._fallback_triggered / max(1, self._total_operations)
        fallback_success_rate = self._fallback_successful / max(1, self._fallback_triggered)

        strategy_stats = {
            name: strategy.get_stats() for name, strategy in self._fallback_strategies.items()
        }

        return {
            "total_operations": self._total_operations,
            "fallback_triggered": self._fallback_triggered,
            "fallback_successful": self._fallback_successful,
            "fallback_rate": fallback_rate,
            "fallback_success_rate": fallback_success_rate,
            "strategies": strategy_stats,
        }


# Global fallback manager
_fallback_manager = FallbackManager()


def get_fallback_manager() -> FallbackManager:
    """Get the global fallback manager."""
    return _fallback_manager


def with_fallback(
    fallback_strategy: str | FallbackStrategy,
    config: FallbackConfig | None = None,
):
    """
    Decorator to add fallback protection to functions.

    Args:
        fallback_strategy: Fallback strategy name or instance
        config: Fallback configuration

    Returns:
        Decorated function
    """
    manager = FallbackManager(config) if config else get_fallback_manager()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                return await manager.execute_with_fallback(func, fallback_strategy, *args, **kwargs)

            return async_wrapper

        @wraps(func)
        async def sync_wrapper(*args, **kwargs) -> T:
            return await manager.execute_with_fallback(func, fallback_strategy, *args, **kwargs)

        return sync_wrapper

    return decorator


# Common fallback strategies
def create_static_fallback(name: str, value: T) -> StaticFallback:
    """Create a static fallback strategy."""
    return StaticFallback(name, value)


def create_function_fallback(name: str, func: Callable[..., T]) -> FunctionFallback:
    """Create a function fallback strategy."""
    return FunctionFallback(name, func)


def create_cache_fallback(
    name: str,
    cache_provider: Callable[[str], T | None],
    cache_key_func: Callable[..., str],
) -> CacheFallback:
    """Create a cache fallback strategy."""
    return CacheFallback(name, cache_provider, cache_key_func)


def create_chain_fallback(name: str, strategies: builtins.list[FallbackStrategy]) -> ChainFallback:
    """Create a chain fallback strategy."""
    return ChainFallback(name, strategies)
