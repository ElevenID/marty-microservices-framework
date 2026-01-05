"""
Core Push Notification Interfaces and Models.

This module defines the standard interfaces and models for push notification delivery.
It provides a generic abstraction layer for push transports (FCM, SSE, WebPush, etc.)
that can be used by any application built on MMF.

The interfaces are designed to be:
- Transport-agnostic: Same interface for FCM, SSE, webhooks, etc.
- Lifecycle-aware: Built-in hooks for token invalidation, connection management
- Event-bus integrated: Emits events for monitoring and extensibility
"""

from __future__ import annotations

import time
import uuid
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

# =============================================================================
# Core Enums
# =============================================================================


class PushChannel(str, Enum):
    """Push notification delivery channels."""

    FCM = "fcm"  # Firebase Cloud Messaging
    APNS = "apns"  # Apple Push Notification Service
    SSE = "sse"  # Server-Sent Events
    WEBHOOK = "webhook"  # HTTP callbacks
    WEBPUSH = "webpush"  # Web Push API
    WEBSOCKET = "websocket"  # WebSocket connections


class PushPriority(str, Enum):
    """Push notification priority levels."""

    LOW = "low"  # Background sync, non-urgent updates
    NORMAL = "normal"  # Standard notifications
    HIGH = "high"  # Important, time-sensitive notifications
    CRITICAL = "critical"  # Urgent, requires immediate attention


class PushStatus(str, Enum):
    """Push delivery status."""

    PENDING = "pending"  # Queued for delivery
    SENDING = "sending"  # Being sent
    DELIVERED = "delivered"  # Successfully delivered
    FAILED = "failed"  # Delivery failed
    EXPIRED = "expired"  # TTL exceeded before delivery
    REJECTED = "rejected"  # Rejected by provider (invalid token, etc.)


# =============================================================================
# Core Data Models
# =============================================================================


@dataclass
class PushTarget:
    """
    Target for a push notification.

    Identifies where the notification should be delivered.
    A target can specify multiple channels for fallback/redundancy.
    """

    # Device tokens for mobile push (FCM, APNS)
    device_tokens: list[str] = field(default_factory=list)

    # Connection IDs for real-time channels (SSE, WebSocket)
    connection_ids: list[str] = field(default_factory=list)

    # URLs for webhook delivery
    webhook_urls: list[str] = field(default_factory=list)

    # User/organization for lookup-based targeting
    user_id: str | None = None
    organization_id: str | None = None

    # Preferred channels in order of priority
    channels: list[PushChannel] = field(default_factory=lambda: [PushChannel.FCM])

    def has_targets(self) -> bool:
        """Check if target has at least one destination."""
        return bool(
            self.device_tokens
            or self.connection_ids
            or self.webhook_urls
            or self.user_id
            or self.organization_id
        )


@dataclass
class PushMessage:
    """
    Push notification message.

    A transport-agnostic representation of a push notification.
    Each adapter is responsible for transforming this into its specific format.
    """

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Targeting
    target: PushTarget = field(default_factory=PushTarget)

    # Content (used for display notifications)
    title: str = ""
    body: str = ""

    # Data payload (passed to the application)
    data: dict[str, Any] = field(default_factory=dict)

    # Priority and TTL
    priority: PushPriority = PushPriority.NORMAL
    ttl_seconds: int = 86400  # 24 hours default

    # Options
    collapse_key: str | None = None  # For collapsing similar notifications
    mutable_content: bool = False  # Allow client-side modification (iOS)
    content_available: bool = False  # Background processing (iOS)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Correlation
    correlation_id: str | None = None

    def is_expired(self) -> bool:
        """Check if the message has expired."""
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "data": self.data,
            "priority": self.priority.value,
            "ttl_seconds": self.ttl_seconds,
            "collapse_key": self.collapse_key,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
        }


@dataclass
class PushResult:
    """
    Result of a push notification delivery attempt.

    Contains status information for each attempted delivery.
    """

    # Identity
    message_id: str
    channel: PushChannel

    # Status
    status: PushStatus
    success: bool = False

    # Timing
    attempted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_at: datetime | None = None

    # Error info (if failed)
    error_code: str | None = None
    error_message: str | None = None

    # Retry info
    attempt_number: int = 1
    should_retry: bool = False
    retry_after_seconds: int | None = None

    # Tokens that failed (for batch sends)
    failed_tokens: list[str] = field(default_factory=list)

    # Channel-specific metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "message_id": self.message_id,
            "channel": self.channel.value,
            "status": self.status.value,
            "success": self.success,
            "attempted_at": self.attempted_at.isoformat(),
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "attempt_number": self.attempt_number,
            "should_retry": self.should_retry,
            "retry_after_seconds": self.retry_after_seconds,
            "failed_tokens": self.failed_tokens,
            "metadata": self.metadata,
        }


# =============================================================================
# Core Interfaces
# =============================================================================


@runtime_checkable
class IPushAdapter(Protocol):
    """
    Interface for push notification delivery adapters.

    Each transport (FCM, SSE, webhook, etc.) implements this interface.
    Adapters handle the actual delivery to external services.
    """

    @property
    def channel(self) -> PushChannel:
        """The channel this adapter handles."""
        ...

    async def send(self, message: PushMessage) -> PushResult:
        """
        Send a push notification.

        Args:
            message: The push message to send

        Returns:
            PushResult with delivery status
        """
        ...

    async def send_batch(self, messages: list[PushMessage]) -> list[PushResult]:
        """
        Send multiple push notifications.

        Default implementation sends sequentially; adapters may override
        for more efficient batch sending.

        Args:
            messages: List of push messages to send

        Returns:
            List of PushResult for each message
        """
        ...

    async def start(self) -> None:
        """
        Start the adapter (initialize connections, start background tasks).

        Called when the push manager is started.
        """
        ...

    async def stop(self) -> None:
        """
        Stop the adapter (cleanup connections, stop background tasks).

        Called when the push manager is stopped.
        """
        ...


@runtime_checkable
class IDeviceTokenStore(Protocol):
    """
    Interface for device token storage.

    Implementations manage the persistence of device tokens
    and their association with users/devices.
    """

    async def get_tokens_for_user(self, user_id: str) -> list[str]:
        """Get all device tokens for a user."""
        ...

    async def get_tokens_for_device(self, device_id: str) -> list[str]:
        """Get tokens for a specific device."""
        ...

    async def store_token(
        self,
        token: str,
        device_id: str,
        user_id: str | None = None,
        channel: PushChannel = PushChannel.FCM,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store a device token."""
        ...

    async def remove_token(self, token: str) -> None:
        """Remove a device token."""
        ...

    async def mark_token_invalid(
        self,
        token: str,
        reason: str | None = None,
    ) -> None:
        """Mark a token as invalid (will be cleaned up)."""
        ...


@runtime_checkable
class IPushManager(Protocol):
    """
    Interface for managing push notification delivery.

    The push manager coordinates between adapters, handles
    routing, and provides a unified API for sending notifications.
    """

    def register_adapter(self, adapter: IPushAdapter) -> None:
        """Register a push adapter for a channel."""
        ...

    def get_adapter(self, channel: PushChannel) -> IPushAdapter | None:
        """Get the adapter for a specific channel."""
        ...

    async def send(
        self,
        message: PushMessage,
        channels: list[PushChannel] | None = None,
    ) -> list[PushResult]:
        """
        Send a push notification through specified channels.

        Args:
            message: The push message to send
            channels: Channels to use (defaults to message.target.channels)

        Returns:
            List of PushResult for each channel attempted
        """
        ...

    async def start(self) -> None:
        """Start the push manager and all registered adapters."""
        ...

    async def stop(self) -> None:
        """Stop the push manager and all registered adapters."""
        ...


@runtime_checkable
class IPushEventHandler(Protocol):
    """
    Interface for handling push notification lifecycle events.

    Implementations can react to events like delivery success,
    failure, token invalidation, etc.
    """

    async def on_delivery_success(
        self,
        message: PushMessage,
        result: PushResult,
    ) -> None:
        """Called when a message is successfully delivered."""
        ...

    async def on_delivery_failure(
        self,
        message: PushMessage,
        result: PushResult,
    ) -> None:
        """Called when a message delivery fails."""
        ...

    async def on_token_invalid(
        self,
        token: str,
        channel: PushChannel,
        reason: str | None = None,
    ) -> None:
        """Called when a device token is found to be invalid."""
        ...


# =============================================================================
# Push Manager Implementation
# =============================================================================


class PushManager:
    """
    Default implementation of IPushManager.

    Coordinates push notification delivery across multiple channels.
    """

    def __init__(
        self,
        token_store: IDeviceTokenStore | None = None,
        event_handler: IPushEventHandler | None = None,
    ):
        """
        Initialize the push manager.

        Args:
            token_store: Optional device token store for user/device lookup
            event_handler: Optional event handler for lifecycle events
        """
        self._adapters: dict[PushChannel, IPushAdapter] = {}
        self._token_store = token_store
        self._event_handler = event_handler
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if the manager is running."""
        return self._running

    def register_adapter(self, adapter: IPushAdapter) -> None:
        """Register a push adapter for a channel."""
        self._adapters[adapter.channel] = adapter

    def get_adapter(self, channel: PushChannel) -> IPushAdapter | None:
        """Get the adapter for a specific channel."""
        return self._adapters.get(channel)

    async def send(
        self,
        message: PushMessage,
        channels: list[PushChannel] | None = None,
    ) -> list[PushResult]:
        """
        Send a push notification through specified channels.

        Args:
            message: The push message to send
            channels: Channels to use (defaults to message.target.channels)

        Returns:
            List of PushResult for each channel attempted
        """
        if message.is_expired():
            return [
                PushResult(
                    message_id=message.id,
                    channel=PushChannel.FCM,
                    status=PushStatus.EXPIRED,
                    success=False,
                    error_code="MESSAGE_EXPIRED",
                    error_message="Message TTL exceeded",
                )
            ]

        channels_to_use = channels or message.target.channels
        results: list[PushResult] = []

        # Resolve user/organization to tokens if needed
        if self._token_store and message.target.user_id:
            tokens = await self._token_store.get_tokens_for_user(message.target.user_id)
            message.target.device_tokens.extend(tokens)

        for channel in channels_to_use:
            adapter = self._adapters.get(channel)
            if not adapter:
                results.append(
                    PushResult(
                        message_id=message.id,
                        channel=channel,
                        status=PushStatus.FAILED,
                        success=False,
                        error_code="NO_ADAPTER",
                        error_message=f"No adapter registered for {channel.value}",
                    )
                )
                continue

            try:
                result = await adapter.send(message)
                results.append(result)

                # Handle events
                if self._event_handler:
                    if result.success:
                        await self._event_handler.on_delivery_success(message, result)
                    else:
                        await self._event_handler.on_delivery_failure(message, result)

                        # Handle invalid tokens
                        if result.error_code in ("INVALID_TOKEN", "UNREGISTERED"):
                            for token in result.failed_tokens:
                                await self._event_handler.on_token_invalid(
                                    token, channel, result.error_message
                                )

            except Exception as e:
                results.append(
                    PushResult(
                        message_id=message.id,
                        channel=channel,
                        status=PushStatus.FAILED,
                        success=False,
                        error_code="EXCEPTION",
                        error_message=str(e),
                        should_retry=True,
                    )
                )

        return results

    async def start(self) -> None:
        """Start the push manager and all registered adapters."""
        if self._running:
            return

        for adapter in self._adapters.values():
            await adapter.start()

        self._running = True

    async def stop(self) -> None:
        """Stop the push manager and all registered adapters."""
        if not self._running:
            return

        for adapter in self._adapters.values():
            await adapter.stop()

        self._running = False
