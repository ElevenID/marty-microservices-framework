"""
Messaging Middleware Framework

Provides extensible middleware framework for message processing including
validation, transformation, enrichment, authentication, and custom processing.
"""

import asyncio
import builtins
import gzip
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .core import Message

logger = logging.getLogger(__name__)


class MiddlewareType(Enum):
    """Middleware execution types."""

    INBOUND = "inbound"  # Process incoming messages
    OUTBOUND = "outbound"  # Process outgoing messages
    BIDIRECTIONAL = "bidirectional"  # Process both directions


class MiddlewareStage(Enum):
    """Middleware execution stages."""

    PRE_DESERIALIZE = "pre_deserialize"
    POST_DESERIALIZE = "post_deserialize"
    PRE_ROUTE = "pre_route"
    POST_ROUTE = "post_route"
    PRE_PROCESS = "pre_process"
    POST_PROCESS = "post_process"
    PRE_SERIALIZE = "pre_serialize"
    POST_SERIALIZE = "post_serialize"
    PRE_PUBLISH = "pre_publish"
    POST_PUBLISH = "post_publish"
    ON_ERROR = "on_error"
    ON_RETRY = "on_retry"


@dataclass
class MiddlewareConfig:
    """Configuration for middleware execution."""

    # Execution settings
    enabled: bool = True
    priority: int = 0  # Higher priority executes first
    async_execution: bool = False
    timeout: float | None = None

    # Stage configuration
    stages: builtins.list[MiddlewareStage] = field(default_factory=list)
    middleware_type: MiddlewareType = MiddlewareType.BIDIRECTIONAL

    # Error handling
    continue_on_error: bool = False
    retry_on_error: bool = False
    max_retries: int = 3

    # Conditions
    apply_conditions: builtins.dict[str, Any] = field(default_factory=dict)
    skip_conditions: builtins.dict[str, Any] = field(default_factory=dict)

    # Monitoring
    enable_metrics: bool = True
    log_execution: bool = False


class MiddlewareContext:
    """Context for middleware execution."""

    def __init__(self, message: Message, stage: MiddlewareStage, direction: MiddlewareType):
        self.message = message
        self.stage = stage
        self.direction = direction
        self.metadata: builtins.dict[str, Any] = {}
        self.start_time = time.time()
        self.skip_remaining = False
        self.error: Exception | None = None

    def set_metadata(self, key: str, value: Any):
        """Set context metadata."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get context metadata."""
        return self.metadata.get(key, default)

    def skip_remaining_middleware(self):
        """Skip remaining middleware in the chain."""
        self.skip_remaining = True

    def execution_time(self) -> float:
        """Get middleware execution time."""
        return time.time() - self.start_time


class MessageMiddleware(ABC):
    """Abstract base class for message middleware."""

    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self.stats = {"executions": 0, "errors": 0, "total_time": 0.0, "avg_time": 0.0}

    @abstractmethod
    async def process(self, context: MiddlewareContext) -> bool:
        """
        Process message in middleware.

        Args:
            context: Middleware execution context

        Returns:
            True if processing should continue, False to stop chain
        """

    async def on_error(self, context: MiddlewareContext, error: Exception):
        """Handle processing error."""
        logger.error("Middleware %s error: %s", self.__class__.__name__, error)

    def should_apply(self, context: MiddlewareContext) -> bool:
        """Check if middleware should be applied to message."""
        # Check enabled
        if not self.config.enabled:
            return False

        # Check stage
        if self.config.stages and context.stage not in self.config.stages:
            return False

        # Check direction
        if (
            self.config.middleware_type != MiddlewareType.BIDIRECTIONAL
            and self.config.middleware_type != context.direction
        ):
            return False

        # Check apply conditions
        if self.config.apply_conditions:
            if not self._check_conditions(context, self.config.apply_conditions):
                return False

        # Check skip conditions
        if self.config.skip_conditions:
            if self._check_conditions(context, self.config.skip_conditions):
                return False

        return True

    def _check_conditions(
        self, context: MiddlewareContext, conditions: builtins.dict[str, Any]
    ) -> bool:
        """Check if conditions are met."""
        message = context.message

        for condition, expected_value in conditions.items():
            if condition == "routing_key":
                if message.headers.routing_key != expected_value:
                    return False

            elif condition == "exchange":
                if message.headers.exchange != expected_value:
                    return False

            elif condition == "priority":
                if message.headers.priority.value < expected_value:
                    return False

            elif condition.startswith("header."):
                header_name = condition[7:]  # Remove "header." prefix
                header_value = message.headers.custom.get(header_name)
                if header_value != expected_value:
                    return False

            elif condition == "message_type":
                message_type = type(message.body).__name__
                if message_type != expected_value:
                    return False

        return True

    def update_stats(self, execution_time: float, error: bool = False):
        """Update middleware statistics."""
        if not self.config.enable_metrics:
            return

        self.stats["executions"] += 1
        if error:
            self.stats["errors"] += 1

        self.stats["total_time"] += execution_time
        self.stats["avg_time"] = self.stats["total_time"] / self.stats["executions"]


class MiddlewareChain:
    """Chain of middleware for message processing."""

    def __init__(self):
        self._middleware: builtins.list[MessageMiddleware] = []
        self._sorted = True

    def add_middleware(self, middleware: MessageMiddleware):
        """Add middleware to chain."""
        self._middleware.append(middleware)
        self._sorted = False

    def remove_middleware(self, middleware_type: builtins.type[MessageMiddleware]) -> bool:
        """Remove middleware by type."""
        for i, middleware in enumerate(self._middleware):
            if isinstance(middleware, middleware_type):
                self._middleware.pop(i)
                return True
        return False

    def clear_middleware(self):
        """Clear all middleware."""
        self._middleware.clear()

    def _sort_middleware(self):
        """Sort middleware by priority (highest first)."""
        if not self._sorted:
            self._middleware.sort(key=lambda m: -m.config.priority)
            self._sorted = True

    async def process(
        self,
        message: Message,
        stage: MiddlewareStage,
        direction: MiddlewareType = MiddlewareType.BIDIRECTIONAL,
    ) -> bool:
        """
        Process message through middleware chain.

        Args:
            message: Message to process
            stage: Processing stage
            direction: Message direction

        Returns:
            True if processing completed successfully
        """
        self._sort_middleware()

        context = MiddlewareContext(message, stage, direction)

        for middleware in self._middleware:
            if not middleware.should_apply(context):
                continue

            if context.skip_remaining:
                break

            try:
                start_time = time.time()

                # Execute middleware with optional timeout
                if middleware.config.timeout:
                    success = await asyncio.wait_for(
                        middleware.process(context), timeout=middleware.config.timeout
                    )
                else:
                    success = await middleware.process(context)

                execution_time = time.time() - start_time
                middleware.update_stats(execution_time)

                if middleware.config.log_execution:
                    logger.debug(
                        "Middleware %s executed for message %s in %.3fms",
                        middleware.__class__.__name__,
                        message.id,
                        execution_time * 1000,
                    )

                if not success:
                    logger.warning(
                        "Middleware %s stopped processing chain for message %s",
                        middleware.__class__.__name__,
                        message.id,
                    )
                    return False

            except asyncio.TimeoutError:
                logger.error(
                    "Middleware %s timeout for message %s",
                    middleware.__class__.__name__,
                    message.id,
                )
                middleware.update_stats(middleware.config.timeout or 0, error=True)

                if not middleware.config.continue_on_error:
                    return False

            except Exception as e:
                execution_time = time.time() - start_time
                middleware.update_stats(execution_time, error=True)

                context.error = e
                await middleware.on_error(context, e)

                if not middleware.config.continue_on_error:
                    logger.error(
                        "Middleware %s failed for message %s: %s",
                        middleware.__class__.__name__,
                        message.id,
                        e,
                    )
                    return False

        return True

    def get_middleware_stats(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Get statistics for all middleware."""
        return {middleware.__class__.__name__: middleware.stats for middleware in self._middleware}


# Built-in Middleware Implementations


class ValidationMiddleware(MessageMiddleware):
    """Middleware for message validation."""

    def __init__(
        self,
        validators: builtins.list[Callable[[Message], bool]],
        config: MiddlewareConfig = None,
    ):
        super().__init__(config or MiddlewareConfig())
        self.validators = validators

    async def process(self, context: MiddlewareContext) -> bool:
        """Validate message."""
        for validator in self.validators:
            try:
                if not validator(context.message):
                    logger.warning("Message %s failed validation", context.message.id)
                    return False
            except Exception as e:
                logger.error("Validation error for message %s: %s", context.message.id, e)
                return False

        return True


class TransformationMiddleware(MessageMiddleware):
    """Middleware for message transformation."""

    def __init__(self, transformer: Callable[[Message], Message], config: MiddlewareConfig = None):
        super().__init__(config or MiddlewareConfig())
        self.transformer = transformer

    async def process(self, context: MiddlewareContext) -> bool:
        """Transform message."""
        try:
            transformed_message = self.transformer(context.message)
            # Update context with transformed message
            context.message = transformed_message
            return True
        except Exception as e:
            logger.error("Transformation error for message %s: %s", context.message.id, e)
            return False


class EnrichmentMiddleware(MessageMiddleware):
    """Middleware for message enrichment."""

    def __init__(
        self,
        enricher: Callable[[Message], builtins.dict[str, Any]],
        config: MiddlewareConfig = None,
    ):
        super().__init__(config or MiddlewareConfig())
        self.enricher = enricher

    async def process(self, context: MiddlewareContext) -> bool:
        """Enrich message with additional data."""
        try:
            enrichment_data = self.enricher(context.message)

            # Add enrichment data to message headers
            context.message.headers.custom.update(enrichment_data)

            return True
        except Exception as e:
            logger.error("Enrichment error for message %s: %s", context.message.id, e)
            return False


class AuthenticationMiddleware(MessageMiddleware):
    """Middleware for message authentication."""

    def __init__(self, authenticator: Callable[[Message], bool], config: MiddlewareConfig = None):
        super().__init__(config or MiddlewareConfig())
        self.authenticator = authenticator

    async def process(self, context: MiddlewareContext) -> bool:
        """Authenticate message."""
        try:
            is_authenticated = self.authenticator(context.message)

            if not is_authenticated:
                logger.warning("Message %s failed authentication", context.message.id)
                return False

            return True
        except Exception as e:
            logger.error("Authentication error for message %s: %s", context.message.id, e)
            return False


class RateLimitMiddleware(MessageMiddleware):
    """Middleware for rate limiting."""

    def __init__(
        self,
        max_messages_per_second: float,
        window_size: float = 60.0,
        config: MiddlewareConfig = None,
    ):
        super().__init__(config or MiddlewareConfig())
        self.max_messages_per_second = max_messages_per_second
        self.window_size = window_size
        self._message_times: builtins.list[float] = []

    async def process(self, context: MiddlewareContext) -> bool:
        """Apply rate limiting."""
        current_time = time.time()

        # Remove old messages outside window
        window_start = current_time - self.window_size
        self._message_times = [t for t in self._message_times if t >= window_start]

        # Check rate limit
        if len(self._message_times) >= self.max_messages_per_second * self.window_size:
            logger.warning("Rate limit exceeded for message %s", context.message.id)
            return False

        # Record message time
        self._message_times.append(current_time)
        return True


class CompressionMiddleware(MessageMiddleware):
    """Middleware for message compression."""

    def __init__(self, compression_type: str = "gzip", config: MiddlewareConfig = None):
        super().__init__(config or MiddlewareConfig())
        self.compression_type = compression_type

    async def process(self, context: MiddlewareContext) -> bool:
        """Compress/decompress message body."""
        try:
            if context.stage in [
                MiddlewareStage.PRE_SERIALIZE,
                MiddlewareStage.PRE_PUBLISH,
            ]:
                # Compress outgoing message
                if isinstance(context.message.body, str | bytes):
                    compressed_body = self._compress(context.message.body)
                    context.message.body = compressed_body
                    context.message.headers.custom["compression"] = self.compression_type

            elif context.stage in [
                MiddlewareStage.POST_DESERIALIZE,
                MiddlewareStage.PRE_PROCESS,
            ]:
                # Decompress incoming message
                if context.message.headers.custom.get("compression") == self.compression_type:
                    decompressed_body = self._decompress(context.message.body)
                    context.message.body = decompressed_body
                    # Remove compression header
                    context.message.headers.custom.pop("compression", None)

            return True

        except Exception as e:
            logger.error("Compression error for message %s: %s", context.message.id, e)
            return False

    def _compress(self, data: str | bytes) -> bytes:
        """Compress data."""

        if isinstance(data, str):
            data = data.encode("utf-8")

        return gzip.compress(data)

    def _decompress(self, data: bytes) -> bytes:
        """Decompress data."""

        return gzip.decompress(data)


class LoggingMiddleware(MessageMiddleware):
    """Middleware for message logging."""

    def __init__(self, log_level: str = "INFO", config: MiddlewareConfig = None):
        super().__init__(config or MiddlewareConfig())
        self.log_level = getattr(logging, log_level.upper())

    async def process(self, context: MiddlewareContext) -> bool:
        """Log message details."""
        message = context.message

        log_data = {
            "message_id": message.id,
            "stage": context.stage.value,
            "direction": context.direction.value,
            "routing_key": message.headers.routing_key,
            "exchange": message.headers.exchange,
            "priority": message.headers.priority.value,
            "timestamp": message.timestamp,
            "status": message.status.value,
        }

        logger.log(self.log_level, "Message processing: %s", log_data)
        return True


class MetricsMiddleware(MessageMiddleware):
    """Middleware for collecting message metrics."""

    def __init__(
        self,
        metrics_collector: Callable | None = None,
        config: MiddlewareConfig = None,
    ):
        super().__init__(config or MiddlewareConfig())
        self.metrics_collector = metrics_collector
        self.metrics = {
            "messages_processed": 0,
            "processing_times": [],
            "error_count": 0,
            "stage_counts": {},
        }

    async def process(self, context: MiddlewareContext) -> bool:
        """Collect message metrics."""
        self.metrics["messages_processed"] += 1

        # Track stage counts
        stage = context.stage.value
        if stage not in self.metrics["stage_counts"]:
            self.metrics["stage_counts"][stage] = 0
        self.metrics["stage_counts"][stage] += 1

        # Track processing time
        processing_time = context.execution_time()
        self.metrics["processing_times"].append(processing_time)

        # Keep only last 1000 processing times
        if len(self.metrics["processing_times"]) > 1000:
            self.metrics["processing_times"] = self.metrics["processing_times"][-1000:]

        # Send to external metrics collector if configured
        if self.metrics_collector:
            try:
                self.metrics_collector(
                    {
                        "message_id": context.message.id,
                        "stage": context.stage.value,
                        "processing_time": processing_time,
                        "direction": context.direction.value,
                    }
                )
            except Exception as e:
                logger.error("Error sending metrics: %s", e)

        return True

    def get_metrics_summary(self) -> builtins.dict[str, Any]:
        """Get metrics summary."""
        processing_times = self.metrics["processing_times"]

        summary = {
            "messages_processed": self.metrics["messages_processed"],
            "error_count": self.metrics["error_count"],
            "stage_counts": self.metrics["stage_counts"].copy(),
        }

        if processing_times:
            summary.update(
                {
                    "avg_processing_time": sum(processing_times) / len(processing_times),
                    "min_processing_time": min(processing_times),
                    "max_processing_time": max(processing_times),
                }
            )

        return summary


# Middleware Factory
class MiddlewareFactory:
    """Factory for creating common middleware instances."""

    @staticmethod
    def create_validation_middleware(
        validators: builtins.list[Callable[[Message], bool]],
        priority: int = 100,
        stages: builtins.list[MiddlewareStage] = None,
    ) -> ValidationMiddleware:
        """Create validation middleware."""
        config = MiddlewareConfig(priority=priority, stages=stages or [MiddlewareStage.PRE_PROCESS])
        return ValidationMiddleware(validators, config)

    @staticmethod
    def create_transformation_middleware(
        transformer: Callable[[Message], Message],
        priority: int = 50,
        stages: builtins.list[MiddlewareStage] = None,
    ) -> TransformationMiddleware:
        """Create transformation middleware."""
        config = MiddlewareConfig(
            priority=priority, stages=stages or [MiddlewareStage.POST_DESERIALIZE]
        )
        return TransformationMiddleware(transformer, config)

    @staticmethod
    def create_enrichment_middleware(
        enricher: Callable[[Message], builtins.dict[str, Any]],
        priority: int = 30,
        stages: builtins.list[MiddlewareStage] = None,
    ) -> EnrichmentMiddleware:
        """Create enrichment middleware."""
        config = MiddlewareConfig(priority=priority, stages=stages or [MiddlewareStage.PRE_PROCESS])
        return EnrichmentMiddleware(enricher, config)

    @staticmethod
    def create_authentication_middleware(
        authenticator: Callable[[Message], bool],
        priority: int = 200,
        stages: builtins.list[MiddlewareStage] = None,
    ) -> AuthenticationMiddleware:
        """Create authentication middleware."""
        config = MiddlewareConfig(
            priority=priority, stages=stages or [MiddlewareStage.POST_DESERIALIZE]
        )
        return AuthenticationMiddleware(authenticator, config)

    @staticmethod
    def create_rate_limit_middleware(
        max_messages_per_second: float,
        priority: int = 150,
        stages: builtins.list[MiddlewareStage] = None,
    ) -> RateLimitMiddleware:
        """Create rate limiting middleware."""
        config = MiddlewareConfig(priority=priority, stages=stages or [MiddlewareStage.PRE_PROCESS])
        return RateLimitMiddleware(max_messages_per_second, config=config)

    @staticmethod
    def create_compression_middleware(
        compression_type: str = "gzip",
        priority: int = 10,
        stages: builtins.list[MiddlewareStage] = None,
    ) -> CompressionMiddleware:
        """Create compression middleware."""
        config = MiddlewareConfig(
            priority=priority,
            stages=stages or [MiddlewareStage.PRE_SERIALIZE, MiddlewareStage.POST_DESERIALIZE],
        )
        return CompressionMiddleware(compression_type, config)

    @staticmethod
    def create_logging_middleware(
        log_level: str = "INFO",
        priority: int = 0,
        stages: builtins.list[MiddlewareStage] = None,
    ) -> LoggingMiddleware:
        """Create logging middleware."""
        config = MiddlewareConfig(
            priority=priority,
            stages=stages or [MiddlewareStage.PRE_PROCESS, MiddlewareStage.POST_PROCESS],
        )
        return LoggingMiddleware(log_level, config)

    @staticmethod
    def create_metrics_middleware(
        metrics_collector: Callable | None = None,
        priority: int = 5,
        stages: builtins.list[MiddlewareStage] = None,
    ) -> MetricsMiddleware:
        """Create metrics middleware."""
        config = MiddlewareConfig(
            priority=priority, stages=stages or [MiddlewareStage.POST_PROCESS]
        )
        return MetricsMiddleware(metrics_collector, config)
