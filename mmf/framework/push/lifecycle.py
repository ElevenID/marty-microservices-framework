"""
Token Lifecycle Management.

This module provides interfaces and implementations for handling
device token lifecycle events, particularly invalidation.

The lifecycle system uses both:
1. Direct interface calls for synchronous handling
2. Event bus emission for decoupled, observable handling

This allows applications to:
- React immediately to token invalidation
- Audit token lifecycle events
- Build monitoring and analytics
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from mmf.core.push import PushChannel

logger = logging.getLogger(__name__)


# =============================================================================
# Token Invalidation Types
# =============================================================================


class TokenInvalidationReason(str, Enum):
    """Reasons why a device token may be invalidated."""

    # Provider-reported
    UNREGISTERED = "unregistered"  # Device unregistered with provider
    INVALID_FORMAT = "invalid_format"  # Token format is invalid
    EXPIRED = "expired"  # Token has expired
    SENDER_ID_MISMATCH = "sender_id_mismatch"  # FCM sender ID mismatch

    # Application-reported
    USER_LOGOUT = "user_logout"  # User logged out
    DEVICE_UNREGISTERED = "device_unregistered"  # Device explicitly unregistered
    USER_REQUEST = "user_request"  # User requested removal

    # System-detected
    REPEATED_FAILURES = "repeated_failures"  # Too many delivery failures
    STALE = "stale"  # Token hasn't been used in too long

    # Unknown
    UNKNOWN = "unknown"  # Reason not specified


@dataclass
class TokenInvalidationEvent:
    """
    Event emitted when a device token is invalidated.

    This event can be consumed by:
    - Token store (to remove the token)
    - Audit system (to log the invalidation)
    - Analytics (to track token churn)
    """

    # Token info
    token: str
    channel: PushChannel

    # Reason
    reason: TokenInvalidationReason
    reason_detail: str | None = None

    # Context
    device_id: str | None = None
    user_id: str | None = None
    organization_id: str | None = None

    # Error info (if from delivery failure)
    error_code: str | None = None
    error_message: str | None = None

    # Timing
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Correlation
    correlation_id: str | None = None

    @property
    def event_type(self) -> str:
        """Event type for event bus routing."""
        return "push.token.invalidated"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "token": self.token[:20] + "..." if len(self.token) > 20 else self.token,
            "token_hash": hash(self.token),  # For correlation without exposing token
            "channel": self.channel.value,
            "reason": self.reason.value,
            "reason_detail": self.reason_detail,
            "device_id": self.device_id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "occurred_at": self.occurred_at.isoformat(),
            "correlation_id": self.correlation_id,
        }


@dataclass
class TokenRegistrationEvent:
    """
    Event emitted when a new device token is registered.
    """

    # Token info
    token: str
    channel: PushChannel
    device_id: str

    # Context
    user_id: str | None = None
    organization_id: str | None = None

    # Metadata
    platform: str | None = None  # ios, android, web
    app_version: str | None = None
    device_model: str | None = None

    # Timing
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Correlation
    correlation_id: str | None = None

    @property
    def event_type(self) -> str:
        """Event type for event bus routing."""
        return "push.token.registered"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "token_hash": hash(self.token),  # Don't expose full token
            "channel": self.channel.value,
            "device_id": self.device_id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "platform": self.platform,
            "app_version": self.app_version,
            "device_model": self.device_model,
            "registered_at": self.registered_at.isoformat(),
            "correlation_id": self.correlation_id,
        }


# =============================================================================
# Lifecycle Handler Interface
# =============================================================================


@runtime_checkable
class ITokenLifecycleHandler(Protocol):
    """
    Interface for handling device token lifecycle events.

    Implementations react to token registration, invalidation,
    and other lifecycle events.

    This is the primary interface for token management. The event
    bus is used for secondary/observational handlers.
    """

    async def on_token_registered(
        self,
        event: TokenRegistrationEvent,
    ) -> None:
        """
        Handle a new token registration.

        Called when a device registers a new push token.

        Args:
            event: The registration event
        """
        ...

    async def on_token_invalidated(
        self,
        event: TokenInvalidationEvent,
    ) -> None:
        """
        Handle a token invalidation.

        Called when a token is found to be invalid, whether from
        provider feedback, user action, or system detection.

        Args:
            event: The invalidation event
        """
        ...

    async def on_token_refreshed(
        self,
        old_token: str,
        new_token: str,
        device_id: str,
        channel: PushChannel,
    ) -> None:
        """
        Handle a token refresh (old token replaced with new).

        Called when a device refreshes its push token.

        Args:
            old_token: The previous token
            new_token: The new token
            device_id: The device identifier
            channel: The push channel
        """
        ...


# =============================================================================
# Event Bus Integration
# =============================================================================


# Type alias for event bus publish function
EventPublisher = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


class TokenLifecycleEventHandler:
    """
    Token lifecycle handler that emits events to the event bus.

    This handler wraps an underlying ITokenLifecycleHandler and
    additionally publishes events to the event bus for:
    - Decoupled observers (audit, analytics, monitoring)
    - Cross-service event propagation

    Usage:
        # Wrap an existing handler
        handler = TokenLifecycleEventHandler(
            delegate=device_registry,
            event_publisher=event_bus.publish,
        )

        # Or use standalone (just events, no delegate)
        handler = TokenLifecycleEventHandler(
            event_publisher=event_bus.publish,
        )
    """

    def __init__(
        self,
        event_publisher: EventPublisher | None = None,
        delegate: ITokenLifecycleHandler | None = None,
    ):
        """
        Initialize the event handler.

        Args:
            event_publisher: Function to publish events (e.g., event_bus.publish)
            delegate: Optional underlying handler to delegate to
        """
        self._publisher = event_publisher
        self._delegate = delegate

    async def on_token_registered(
        self,
        event: TokenRegistrationEvent,
    ) -> None:
        """Handle token registration with event emission."""
        # Delegate first
        if self._delegate:
            await self._delegate.on_token_registered(event)

        # Emit event
        await self._publish_event(event.event_type, event.to_dict())

    async def on_token_invalidated(
        self,
        event: TokenInvalidationEvent,
    ) -> None:
        """Handle token invalidation with event emission."""
        logger.info(
            f"Token invalidated: channel={event.channel.value}, "
            f"reason={event.reason.value}, device_id={event.device_id}"
        )

        # Delegate first
        if self._delegate:
            await self._delegate.on_token_invalidated(event)

        # Emit event
        await self._publish_event(event.event_type, event.to_dict())

    async def on_token_refreshed(
        self,
        old_token: str,
        new_token: str,
        device_id: str,
        channel: PushChannel,
    ) -> None:
        """Handle token refresh with event emission."""
        # Delegate first
        if self._delegate:
            await self._delegate.on_token_refreshed(old_token, new_token, device_id, channel)

        # Emit event
        await self._publish_event(
            "push.token.refreshed",
            {
                "old_token_hash": hash(old_token),
                "new_token_hash": hash(new_token),
                "device_id": device_id,
                "channel": channel.value,
            },
        )

    async def _publish_event(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Publish an event to the event bus."""
        if self._publisher:
            try:
                await self._publisher(event_type, data)
            except Exception as e:
                logger.warning(f"Failed to publish lifecycle event: {e}")


# =============================================================================
# Helper Functions
# =============================================================================


def reason_from_fcm_error(error_code: str) -> TokenInvalidationReason:
    """
    Map FCM error codes to invalidation reasons.

    Args:
        error_code: The FCM error code

    Returns:
        The corresponding TokenInvalidationReason
    """
    mapping = {
        "UNREGISTERED": TokenInvalidationReason.UNREGISTERED,
        "INVALID_ARGUMENT": TokenInvalidationReason.INVALID_FORMAT,
        "SENDER_ID_MISMATCH": TokenInvalidationReason.SENDER_ID_MISMATCH,
        "messaging/registration-token-not-registered": TokenInvalidationReason.UNREGISTERED,
        "messaging/invalid-registration-token": TokenInvalidationReason.INVALID_FORMAT,
        "messaging/mismatched-credential": TokenInvalidationReason.SENDER_ID_MISMATCH,
    }
    return mapping.get(error_code, TokenInvalidationReason.UNKNOWN)


def reason_from_apns_error(error_code: str) -> TokenInvalidationReason:
    """
    Map APNS error codes to invalidation reasons.

    Args:
        error_code: The APNS error code

    Returns:
        The corresponding TokenInvalidationReason
    """
    mapping = {
        "BadDeviceToken": TokenInvalidationReason.INVALID_FORMAT,
        "Unregistered": TokenInvalidationReason.UNREGISTERED,
        "ExpiredToken": TokenInvalidationReason.EXPIRED,
        "DeviceTokenNotForTopic": TokenInvalidationReason.SENDER_ID_MISMATCH,
    }
    return mapping.get(error_code, TokenInvalidationReason.UNKNOWN)
