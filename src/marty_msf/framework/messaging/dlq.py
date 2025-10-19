"""
Dead Letter Queue (DLQ) Management

Provides comprehensive dead letter queue functionality including retry strategies,
failure analysis, message recovery, and DLQ monitoring.
"""

import asyncio
import builtins
import logging
import random
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .backends import MessageBackend
from .core import Message, MessageStatus

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""

    IMMEDIATE = "immediate"
    LINEAR_BACKOFF = "linear_backoff"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    CUSTOM = "custom"


class DLQPolicy(Enum):
    """Dead letter queue policies."""

    RETRY_THEN_DLQ = "retry_then_dlq"
    IMMEDIATE_DLQ = "immediate_dlq"
    DROP_MESSAGE = "drop_message"
    CUSTOM_HANDLER = "custom_handler"


@dataclass
class RetryConfig:
    """Configuration for message retry behavior."""

    # Basic retry settings
    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF

    # Timing settings
    initial_delay: float = 1.0
    max_delay: float = 300.0  # 5 minutes
    backoff_multiplier: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd

    # Custom retry function
    custom_delay_func: Callable[[int], float] | None = None

    # Retry conditions
    retry_on_exceptions: builtins.list[type] = field(default_factory=list)
    no_retry_on_exceptions: builtins.list[type] = field(default_factory=list)

    # Message inspection
    retry_filter: Callable[[Message, Exception], bool] | None = None


@dataclass
class DLQConfig:
    """Configuration for dead letter queue behavior."""

    # DLQ naming
    dlq_suffix: str = ".dlq"
    retry_suffix: str = ".retry"

    # DLQ policy
    policy: DLQPolicy = DLQPolicy.RETRY_THEN_DLQ

    # Storage settings
    dlq_ttl: float | None = None  # Messages expire after this time
    max_dlq_size: int | None = None  # Max messages in DLQ

    # Retry settings
    retry_config: RetryConfig = field(default_factory=RetryConfig)

    # Monitoring
    enable_metrics: bool = True
    alert_threshold: int = 100  # Alert when DLQ size exceeds this

    # Custom handlers
    on_dlq_message: Callable[[Message], None] | None = None
    on_retry_exhausted: Callable[[Message], None] | None = None


@dataclass
class DLQStats:
    """Dead letter queue statistics."""

    # Counts
    total_failed_messages: int = 0
    total_retried_messages: int = 0
    total_dlq_messages: int = 0
    current_dlq_size: int = 0

    # Retry statistics
    avg_retry_attempts: float = 0.0
    max_retry_attempts: int = 0
    retry_success_rate: float = 0.0

    # Timing statistics
    avg_time_to_dlq: float = 0.0
    avg_retry_delay: float = 0.0

    # Failure analysis
    failure_reasons: builtins.dict[str, int] = field(default_factory=dict)
    top_failed_queues: builtins.list[str] = field(default_factory=list)

    # Performance metrics
    dlq_throughput: float = 0.0
    retry_throughput: float = 0.0


class DLQMessage:
    """Extended message with DLQ metadata."""

    def __init__(self, message: Message):
        self.message = message
        self.original_queue = message.headers.routing_key
        self.failure_count = 0
        self.retry_attempts = 0
        self.first_failure_time = time.time()
        self.last_failure_time = time.time()
        self.failure_reasons: builtins.list[str] = []
        self.retry_history: builtins.list[builtins.dict[str, Any]] = []

    def add_failure(self, reason: str, exception: Exception | None = None):
        """Record a failure."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.failure_reasons.append(reason)

        if exception:
            self.message.headers.custom["last_exception"] = str(exception)
            self.message.headers.custom["exception_type"] = exception.__class__.__name__

    def add_retry_attempt(self, delay: float):
        """Record a retry attempt."""
        self.retry_attempts += 1
        self.retry_history.append(
            {"attempt": self.retry_attempts, "timestamp": time.time(), "delay": delay}
        )

    def should_retry(self, retry_config: RetryConfig) -> bool:
        """Check if message should be retried."""
        if self.retry_attempts >= retry_config.max_attempts:
            return False

        return True

    def calculate_retry_delay(self, retry_config: RetryConfig) -> float:
        """Calculate delay for next retry attempt."""
        if retry_config.custom_delay_func:
            return retry_config.custom_delay_func(self.retry_attempts)

        if retry_config.strategy == RetryStrategy.IMMEDIATE:
            return 0.0

        if retry_config.strategy == RetryStrategy.FIXED_DELAY:
            delay = retry_config.initial_delay

        elif retry_config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = retry_config.initial_delay * (self.retry_attempts + 1)

        elif retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = retry_config.initial_delay * (
                retry_config.backoff_multiplier**self.retry_attempts
            )

        else:
            delay = retry_config.initial_delay

        # Apply max delay limit
        delay = min(delay, retry_config.max_delay)

        # Add jitter if enabled
        if retry_config.jitter:

            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)

        return max(0.0, delay)

    def time_in_dlq(self) -> float:
        """Get time spent in DLQ."""
        return time.time() - self.first_failure_time


class DLQManager:
    """Dead letter queue manager."""

    def __init__(self, config: DLQConfig, backend: MessageBackend):
        self.config = config
        self.backend = backend

        # State
        self._dlq_messages: builtins.dict[str, DLQMessage] = {}  # Message ID -> DLQMessage
        self._retry_tasks: builtins.dict[str, asyncio.Task] = {}  # Message ID -> Retry task
        self._stats = DLQStats()

        # Monitoring
        self._last_stats_update = time.time()
        self._stats_window_messages: builtins.list[float] = []  # Timestamps for throughput calc

    async def handle_failed_message(
        self, message: Message, exception: Exception, original_queue: str
    ) -> bool:
        """
        Handle a failed message according to DLQ policy.

        Args:
            message: Failed message
            exception: Exception that caused failure
            original_queue: Original queue name

        Returns:
            True if message was handled, False otherwise
        """
        try:
            # Create or get DLQ message
            dlq_message = self._get_or_create_dlq_message(message, original_queue)
            dlq_message.add_failure(str(exception), exception)

            # Update statistics
            self._stats.total_failed_messages += 1
            self._update_failure_reasons(str(exception))

            # Apply DLQ policy
            if self.config.policy == DLQPolicy.IMMEDIATE_DLQ:
                return await self._send_to_dlq(dlq_message)

            if self.config.policy == DLQPolicy.DROP_MESSAGE:
                logger.warning(f"Dropping failed message {message.id}")
                return True

            if self.config.policy == DLQPolicy.RETRY_THEN_DLQ:
                return await self._handle_retry_then_dlq(dlq_message, exception)

            if self.config.policy == DLQPolicy.CUSTOM_HANDLER:
                if self.config.on_dlq_message:
                    self.config.on_dlq_message(message)
                return True

            return False

        except Exception as e:
            logger.error(f"Error handling failed message {message.id}: {e}")
            return False

    def _get_or_create_dlq_message(self, message: Message, original_queue: str) -> DLQMessage:
        """Get or create DLQ message wrapper."""
        if message.id not in self._dlq_messages:
            dlq_message = DLQMessage(message)
            dlq_message.original_queue = original_queue
            self._dlq_messages[message.id] = dlq_message

        return self._dlq_messages[message.id]

    async def _handle_retry_then_dlq(self, dlq_message: DLQMessage, exception: Exception) -> bool:
        """Handle retry then DLQ policy."""
        retry_config = self.config.retry_config

        # Check if should retry
        if not self._should_retry_message(dlq_message, exception, retry_config):
            return await self._send_to_dlq(dlq_message)

        # Calculate retry delay
        delay = dlq_message.calculate_retry_delay(retry_config)
        dlq_message.add_retry_attempt(delay)

        # Schedule retry
        retry_task = asyncio.create_task(self._schedule_retry(dlq_message, delay))
        self._retry_tasks[dlq_message.message.id] = retry_task

        # Update statistics
        self._stats.total_retried_messages += 1

        logger.info(
            f"Scheduling retry for message {dlq_message.message.id} "
            f"(attempt {dlq_message.retry_attempts}/{retry_config.max_attempts}) "
            f"after {delay:.2f}s"
        )

        return True

    def _should_retry_message(
        self, dlq_message: DLQMessage, exception: Exception, retry_config: RetryConfig
    ) -> bool:
        """Check if message should be retried."""
        # Check retry attempts
        if not dlq_message.should_retry(retry_config):
            return False

        # Check exception type restrictions
        if retry_config.no_retry_on_exceptions:
            for exc_type in retry_config.no_retry_on_exceptions:
                if isinstance(exception, exc_type):
                    return False

        if retry_config.retry_on_exceptions:
            should_retry = False
            for exc_type in retry_config.retry_on_exceptions:
                if isinstance(exception, exc_type):
                    should_retry = True
                    break
            if not should_retry:
                return False

        # Apply custom retry filter
        if retry_config.retry_filter:
            return retry_config.retry_filter(dlq_message.message, exception)

        return True

    async def _schedule_retry(self, dlq_message: DLQMessage, delay: float):
        """Schedule message retry after delay."""
        try:
            if delay > 0:
                await asyncio.sleep(delay)

            # Retry message by republishing to original queue
            message = dlq_message.message
            message.headers.routing_key = dlq_message.original_queue
            message.status = MessageStatus.RETRYING

            # Add retry metadata
            message.headers.custom["retry_attempt"] = dlq_message.retry_attempts
            message.headers.custom["retry_timestamp"] = time.time()

            success = await self.backend.publish(message)

            if success:
                logger.info(f"Successfully retried message {message.id}")
                # Remove from retry tracking
                self._retry_tasks.pop(message.id, None)
            else:
                logger.error(f"Failed to retry message {message.id}")
                # Send to DLQ if retry publishing failed
                await self._send_to_dlq(dlq_message)

        except asyncio.CancelledError:
            logger.info(f"Retry cancelled for message {dlq_message.message.id}")
        except Exception as e:
            logger.error(f"Error during retry for message {dlq_message.message.id}: {e}")
            await self._send_to_dlq(dlq_message)

    async def _send_to_dlq(self, dlq_message: DLQMessage) -> bool:
        """Send message to dead letter queue."""
        try:
            message = dlq_message.message

            # Prepare DLQ message
            dlq_queue_name = f"{dlq_message.original_queue}{self.config.dlq_suffix}"
            message.headers.routing_key = dlq_queue_name
            message.status = MessageStatus.FAILED

            # Add DLQ metadata
            message.headers.custom.update(
                {
                    "dlq_timestamp": time.time(),
                    "original_queue": dlq_message.original_queue,
                    "failure_count": dlq_message.failure_count,
                    "retry_attempts": dlq_message.retry_attempts,
                    "first_failure_time": dlq_message.first_failure_time,
                    "last_failure_time": dlq_message.last_failure_time,
                    "failure_reasons": dlq_message.failure_reasons,
                    "time_in_dlq": dlq_message.time_in_dlq(),
                }
            )

            # Set TTL if configured
            if self.config.dlq_ttl:
                message.headers.expiration = self.config.dlq_ttl

            # Publish to DLQ
            success = await self.backend.publish(message)

            if success:
                # Update statistics
                self._stats.total_dlq_messages += 1
                self._stats.current_dlq_size += 1
                self._update_dlq_stats(dlq_message)

                # Clean up
                self._dlq_messages.pop(message.id, None)
                self._retry_tasks.pop(message.id, None)

                # Trigger callbacks
                if self.config.on_retry_exhausted:
                    self.config.on_retry_exhausted(message)

                logger.info(f"Message {message.id} sent to DLQ: {dlq_queue_name}")

                # Check alert threshold
                if (
                    self.config.alert_threshold
                    and self._stats.current_dlq_size > self.config.alert_threshold
                ):
                    await self._trigger_dlq_alert()

                return True

            return False

        except Exception as e:
            logger.error(f"Failed to send message {dlq_message.message.id} to DLQ: {e}")
            return False

    async def _trigger_dlq_alert(self):
        """Trigger DLQ size alert."""
        logger.warning(
            f"DLQ size ({self._stats.current_dlq_size}) exceeds alert threshold "
            f"({self.config.alert_threshold})"
        )
        # Here you could integrate with alerting systems

    def _update_failure_reasons(self, reason: str):
        """Update failure reason statistics."""
        if reason not in self._stats.failure_reasons:
            self._stats.failure_reasons[reason] = 0
        self._stats.failure_reasons[reason] += 1

    def _update_dlq_stats(self, dlq_message: DLQMessage):
        """Update DLQ statistics."""
        # Update retry statistics
        if dlq_message.retry_attempts > 0:
            all_retry_attempts = [
                msg.retry_attempts for msg in self._dlq_messages.values() if msg.retry_attempts > 0
            ]
            all_retry_attempts.append(dlq_message.retry_attempts)

            self._stats.avg_retry_attempts = statistics.mean(all_retry_attempts)
            self._stats.max_retry_attempts = max(all_retry_attempts)

        # Update timing statistics
        all_dlq_times = [msg.time_in_dlq() for msg in self._dlq_messages.values()]
        all_dlq_times.append(dlq_message.time_in_dlq())

        self._stats.avg_time_to_dlq = statistics.mean(all_dlq_times)

        # Update throughput
        current_time = time.time()
        self._stats_window_messages.append(current_time)

        # Keep only last 60 seconds for throughput calculation
        window_start = current_time - 60
        self._stats_window_messages = [t for t in self._stats_window_messages if t >= window_start]

        self._stats.dlq_throughput = len(self._stats_window_messages) / 60.0

    async def recover_dlq_messages(
        self,
        dlq_queue: str,
        target_queue: str | None = None,
        filter_func: Callable[[Message], bool] | None = None,
        max_messages: int | None = None,
    ) -> int:
        """
        Recover messages from DLQ back to original or target queue.

        Args:
            dlq_queue: DLQ queue name
            target_queue: Target queue (if None, use original queue)
            filter_func: Optional filter function for messages
            max_messages: Maximum number of messages to recover

        Returns:
            Number of messages recovered
        """
        recovered_count = 0

        try:
            # Consume messages from DLQ
            while True:
                if max_messages and recovered_count >= max_messages:
                    break

                message = await self.backend.consume(dlq_queue, timeout=1.0)
                if not message:
                    break

                # Apply filter if provided
                if filter_func and not filter_func(message):
                    continue

                # Determine target queue
                recovery_queue = target_queue
                if not recovery_queue:
                    recovery_queue = message.headers.custom.get("original_queue")

                if not recovery_queue:
                    logger.warning(f"No target queue for message {message.id}")
                    continue

                # Clean up DLQ metadata
                dlq_metadata_keys = [
                    "dlq_timestamp",
                    "failure_count",
                    "retry_attempts",
                    "first_failure_time",
                    "last_failure_time",
                    "failure_reasons",
                ]
                for key in dlq_metadata_keys:
                    message.headers.custom.pop(key, None)

                # Reset message state
                message.headers.routing_key = recovery_queue
                message.status = MessageStatus.PENDING
                message.headers.custom["recovered_from_dlq"] = time.time()

                # Republish message
                success = await self.backend.publish(message)

                if success:
                    recovered_count += 1
                    logger.info(f"Recovered message {message.id} to {recovery_queue}")
                else:
                    logger.error(f"Failed to recover message {message.id}")

            return recovered_count

        except Exception as e:
            logger.error(f"Error recovering DLQ messages: {e}")
            return recovered_count

    async def purge_dlq(self, dlq_queue: str) -> int:
        """
        Purge all messages from DLQ.

        Args:
            dlq_queue: DLQ queue name

        Returns:
            Number of messages purged
        """
        try:
            # This would depend on the backend implementation
            # For now, we'll consume and discard all messages
            purged_count = 0

            while True:
                message = await self.backend.consume(dlq_queue, timeout=1.0)
                if not message:
                    break

                purged_count += 1
                # Acknowledge to remove from queue
                await self.backend.ack(message)

            self._stats.current_dlq_size = max(0, self._stats.current_dlq_size - purged_count)

            logger.info(f"Purged {purged_count} messages from DLQ {dlq_queue}")
            return purged_count

        except Exception as e:
            logger.error(f"Error purging DLQ {dlq_queue}: {e}")
            return 0

    def get_stats(self) -> DLQStats:
        """Get current DLQ statistics."""
        # Update calculated stats
        if self._dlq_messages:
            retry_attempts = [msg.retry_attempts for msg in self._dlq_messages.values()]
            if retry_attempts:
                self._stats.avg_retry_attempts = statistics.mean(retry_attempts)
                self._stats.max_retry_attempts = max(retry_attempts)

        # Calculate success rate
        total_processed = self._stats.total_retried_messages + self._stats.total_dlq_messages
        if total_processed > 0:
            self._stats.retry_success_rate = self._stats.total_retried_messages / total_processed

        return self._stats

    async def cancel_all_retries(self):
        """Cancel all pending retry tasks."""
        for task in self._retry_tasks.values():
            task.cancel()

        if self._retry_tasks:
            await asyncio.gather(*self._retry_tasks.values(), return_exceptions=True)

        self._retry_tasks.clear()
        logger.info("Cancelled all pending retry tasks")

    async def shutdown(self):
        """Shutdown DLQ manager."""
        await self.cancel_all_retries()
        logger.info("DLQ manager shutdown complete")
