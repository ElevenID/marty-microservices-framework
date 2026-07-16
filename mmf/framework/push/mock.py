"""
Mock Push Adapter.

In-memory mock adapter for testing push notification flows.
Captures sent messages for verification without external dependencies.

Features:
- Configurable success/failure behavior
- Message capture for assertions
- Simulated delays
- Token invalidation simulation
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mmf.core.push import IPushAdapter, PushChannel, PushMessage, PushResult, PushStatus

from .lifecycle import (
    ITokenLifecycleHandler,
    TokenInvalidationEvent,
    TokenInvalidationReason,
)

logger = logging.getLogger(__name__)


@dataclass
class MockPushConfig:
    """Mock adapter configuration."""

    # Channel to mock (FCM by default, but can simulate any)
    channel: PushChannel = PushChannel.FCM

    # Simulated behavior
    success_rate: float = 1.0  # 0.0 to 1.0
    delay_seconds: float = 0.0

    # Token handling
    invalid_tokens: set[str] = field(default_factory=set)

    # Error simulation
    simulate_error: str | None = None
    simulate_error_code: str | None = None


@dataclass
class CapturedMessage:
    """A captured push message for test verification."""

    message: PushMessage
    result: PushResult
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for assertions."""
        return {
            "message_id": self.message.id,
            "title": self.message.title,
            "body": self.message.body,
            "data": self.message.data,
            "target_tokens": self.message.target.device_tokens,
            "target_user_id": self.message.target.user_id,
            "result_success": self.result.success,
            "result_status": self.result.status.value,
        }


class MockPushAdapter:
    """
    Mock push adapter for testing.

    Implements IPushAdapter without any external dependencies.
    Captures all sent messages for test verification.

    Usage:
        # Basic usage
        adapter = MockPushAdapter()
        await adapter.start()

        result = await adapter.send(message)

        # Verify sent messages
        assert adapter.sent_count == 1
        assert adapter.last_message.data["key"] == "value"

        # Simulate failures
        adapter.config.success_rate = 0.0
        result = await adapter.send(message)
        assert not result.success

        # Simulate invalid tokens
        adapter.config.invalid_tokens.add("bad-token")
        message.target.device_tokens = ["bad-token"]
        result = await adapter.send(message)
        assert result.error_code == "INVALID_TOKEN"
    """

    def __init__(
        self,
        config: MockPushConfig | None = None,
        lifecycle_handler: ITokenLifecycleHandler | None = None,
    ):
        """
        Initialize the mock adapter.

        Args:
            config: Mock configuration
            lifecycle_handler: Optional handler for token lifecycle events
        """
        self.config = config or MockPushConfig()
        self._lifecycle_handler = lifecycle_handler
        self._messages: list[CapturedMessage] = []
        self._running = False

        # Custom send handler for advanced scenarios
        self._custom_handler: Callable[[PushMessage], Awaitable[PushResult]] | None = None

    @property
    def channel(self) -> PushChannel:
        """The channel this adapter handles."""
        return self.config.channel

    async def start(self) -> None:
        """Start the mock adapter."""
        self._running = True
        logger.info(f"Mock push adapter started (channel={self.config.channel.value})")

    async def stop(self) -> None:
        """Stop the mock adapter."""
        self._running = False
        logger.info("Mock push adapter stopped")

    async def send(self, message: PushMessage) -> PushResult:
        """
        Send a push message (captured for testing).

        Args:
            message: The push message

        Returns:
            PushResult based on configuration
        """
        # Apply simulated delay
        if self.config.delay_seconds > 0:
            await asyncio.sleep(self.config.delay_seconds)

        # Use custom handler if provided
        if self._custom_handler:
            result = await self._custom_handler(message)
            self._messages.append(CapturedMessage(message=message, result=result))
            return result

        # Check for simulated error
        if self.config.simulate_error:
            result = PushResult(
                message_id=message.id,
                channel=self.config.channel,
                status=PushStatus.FAILED,
                success=False,
                error_code=self.config.simulate_error_code or "SIMULATED_ERROR",
                error_message=self.config.simulate_error,
            )
            self._messages.append(CapturedMessage(message=message, result=result))
            return result

        # Check for invalid tokens
        invalid_found = []
        for token in message.target.device_tokens:
            if token in self.config.invalid_tokens:
                invalid_found.append(token)

        if invalid_found:
            # Trigger lifecycle handler
            if self._lifecycle_handler:
                for token in invalid_found:
                    event = TokenInvalidationEvent(
                        token=token,
                        channel=self.config.channel,
                        reason=TokenInvalidationReason.UNREGISTERED,
                        reason_detail="Mock: Token marked as invalid",
                    )
                    await self._lifecycle_handler.on_token_invalidated(event)

            result = PushResult(
                message_id=message.id,
                channel=self.config.channel,
                status=PushStatus.REJECTED,
                success=False,
                error_code="INVALID_TOKEN",
                error_message="One or more tokens are invalid",
                failed_tokens=invalid_found,
            )
            self._messages.append(CapturedMessage(message=message, result=result))
            return result

        # Simulate success rate
        import random

        if random.random() > self.config.success_rate:
            result = PushResult(
                message_id=message.id,
                channel=self.config.channel,
                status=PushStatus.FAILED,
                success=False,
                error_code="RANDOM_FAILURE",
                error_message="Simulated random failure based on success_rate",
                should_retry=True,
            )
            self._messages.append(CapturedMessage(message=message, result=result))
            return result

        # Success
        result = PushResult(
            message_id=message.id,
            channel=self.config.channel,
            status=PushStatus.DELIVERED,
            success=True,
            delivered_at=datetime.now(timezone.utc),
            metadata={
                "mock": True,
                "tokens_count": len(message.target.device_tokens),
            },
        )
        self._messages.append(CapturedMessage(message=message, result=result))
        return result

    async def send_batch(self, messages: list[PushMessage]) -> list[PushResult]:
        """Send multiple messages."""
        results = []
        for message in messages:
            result = await self.send(message)
            results.append(result)
        return results

    # =========================================================================
    # Test Utilities
    # =========================================================================

    @property
    def sent_count(self) -> int:
        """Number of messages sent."""
        return len(self._messages)

    @property
    def messages(self) -> list[CapturedMessage]:
        """All captured messages."""
        return self._messages

    @property
    def last_message(self) -> CapturedMessage | None:
        """The most recently sent message."""
        return self._messages[-1] if self._messages else None

    @property
    def successful_messages(self) -> list[CapturedMessage]:
        """Messages that were delivered successfully."""
        return [m for m in self._messages if m.result.success]

    @property
    def failed_messages(self) -> list[CapturedMessage]:
        """Messages that failed delivery."""
        return [m for m in self._messages if not m.result.success]

    def clear(self) -> None:
        """Clear all captured messages."""
        self._messages.clear()

    def reset(self) -> None:
        """Reset adapter to default state."""
        self._messages.clear()
        self.config = MockPushConfig(channel=self.config.channel)
        self._custom_handler = None

    def set_custom_handler(
        self,
        handler: Callable[[PushMessage], Awaitable[PushResult]],
    ) -> None:
        """
        Set a custom send handler for advanced testing scenarios.

        Args:
            handler: Async function that takes a PushMessage and returns PushResult
        """
        self._custom_handler = handler

    def find_messages(
        self,
        *,
        user_id: str | None = None,
        device_token: str | None = None,
        data_contains: dict[str, Any] | None = None,
    ) -> list[CapturedMessage]:
        """
        Find messages matching criteria.

        Args:
            user_id: Filter by target user ID
            device_token: Filter by target device token
            data_contains: Filter by data payload contents

        Returns:
            List of matching captured messages
        """
        results = []

        for captured in self._messages:
            msg = captured.message

            if user_id and msg.target.user_id != user_id:
                continue

            if device_token and device_token not in msg.target.device_tokens:
                continue

            if data_contains:
                match = all(msg.data.get(k) == v for k, v in data_contains.items())
                if not match:
                    continue

            results.append(captured)

        return results

    def assert_sent(
        self,
        *,
        count: int | None = None,
        min_count: int | None = None,
        max_count: int | None = None,
    ) -> None:
        """
        Assert on number of sent messages.

        Args:
            count: Exact count expected
            min_count: Minimum count expected
            max_count: Maximum count expected

        Raises:
            AssertionError: If assertion fails
        """
        if count is not None:
            assert self.sent_count == count, f"Expected {count} messages, got {self.sent_count}"

        if min_count is not None:
            assert (
                self.sent_count >= min_count
            ), f"Expected at least {min_count} messages, got {self.sent_count}"

        if max_count is not None:
            assert (
                self.sent_count <= max_count
            ), f"Expected at most {max_count} messages, got {self.sent_count}"

    def assert_message_sent_to(
        self,
        *,
        user_id: str | None = None,
        device_token: str | None = None,
    ) -> CapturedMessage:
        """
        Assert that a message was sent to the specified target.

        Args:
            user_id: Expected target user ID
            device_token: Expected target device token

        Returns:
            The matching message

        Raises:
            AssertionError: If no matching message found
        """
        matches = self.find_messages(user_id=user_id, device_token=device_token)

        assert matches, f"No message found for user_id={user_id}, device_token={device_token}"

        return matches[0]
