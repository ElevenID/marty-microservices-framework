"""
MMF Push Notification Framework.

This package provides transport-agnostic push notification delivery
with support for FCM, SSE, webhooks, and other channels.

Usage:
    from mmf.framework.push import (
        PushManager,
        PushMessage,
        PushTarget,
        PushChannel,
    )
    from mmf.framework.push.fcm import FCMAdapter, FCMConfig
    from mmf.framework.push.sse import SSEAdapter, SSEConfig
    from mmf.framework.push.webhook import WebhookAdapter, WebhookConfig
    from mmf.framework.push.mock import MockPushAdapter, MockPushConfig

    # Create adapters
    fcm = FCMAdapter(FCMConfig(project_id="my-project", ...))
    sse = SSEAdapter(SSEConfig(heartbeat_interval=15))

    # Create manager and register adapters
    manager = PushManager()
    manager.register_adapter(fcm)
    manager.register_adapter(sse)

    # Send messages
    message = PushMessage(
        target=PushTarget(device_tokens=["token123"]),
        title="Hello",
        body="World",
        data={"key": "value"},
    )
    results = await manager.send(message)
"""

from mmf.core.push import (
    IDeviceTokenStore,
    IPushAdapter,
    IPushEventHandler,
    IPushManager,
    PushChannel,
    PushManager,
    PushMessage,
    PushPriority,
    PushResult,
    PushStatus,
    PushTarget,
)

from .lifecycle import (
    ITokenLifecycleHandler,
    TokenInvalidationEvent,
    TokenInvalidationReason,
    TokenLifecycleEventHandler,
    TokenRegistrationEvent,
    reason_from_apns_error,
    reason_from_fcm_error,
)

__all__ = [
    # Core types
    "PushChannel",
    "PushPriority",
    "PushStatus",
    "PushTarget",
    "PushMessage",
    "PushResult",
    # Interfaces
    "IPushAdapter",
    "IPushManager",
    "IDeviceTokenStore",
    "IPushEventHandler",
    # Implementations
    "PushManager",
    # Lifecycle
    "ITokenLifecycleHandler",
    "TokenInvalidationEvent",
    "TokenInvalidationReason",
    "TokenRegistrationEvent",
    "TokenLifecycleEventHandler",
    "reason_from_fcm_error",
    "reason_from_apns_error",
]
