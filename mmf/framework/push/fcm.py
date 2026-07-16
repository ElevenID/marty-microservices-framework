"""
FCM Push Adapter.

Firebase Cloud Messaging adapter for mobile push notifications.
This is a transport-only adapter - it handles delivery to FCM
without any application-specific payload formatting.

Features:
- OAuth2 authentication with Google APIs
- Batch sending (up to 500 messages)
- Exponential backoff retry
- Token lifecycle integration
- Priority mapping
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from mmf.core.push import (
    IPushAdapter,
    PushChannel,
    PushMessage,
    PushPriority,
    PushResult,
    PushStatus,
)

from .lifecycle import (
    ITokenLifecycleHandler,
    TokenInvalidationEvent,
    TokenInvalidationReason,
    reason_from_fcm_error,
)

logger = logging.getLogger(__name__)


@dataclass
class FCMConfig:
    """
    FCM adapter configuration.

    Credentials can be provided as either a file path or a dictionary.
    """

    # Google Cloud project ID
    project_id: str

    # Service account credentials (one required)
    service_account_path: str | None = None
    service_account_json: dict[str, Any] | None = None

    # Batching
    max_batch_size: int = 500

    # Retry settings
    max_retries: int = 3
    initial_backoff: float = 1.0
    max_backoff: float = 30.0

    # HTTP settings
    timeout_seconds: float = 30.0


class FCMAdapter:
    """
    Firebase Cloud Messaging push adapter.

    Implements IPushAdapter for FCM delivery. This adapter is transport-only;
    it sends whatever payload is provided without modification (beyond
    FCM formatting requirements).

    Usage:
        config = FCMConfig(
            project_id="my-project",
            service_account_path="/path/to/service-account.json",
        )
        adapter = FCMAdapter(config)

        # With lifecycle handler for token management
        adapter = FCMAdapter(config, lifecycle_handler=my_handler)
    """

    FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

    def __init__(
        self,
        config: FCMConfig,
        lifecycle_handler: ITokenLifecycleHandler | None = None,
    ):
        """
        Initialize the FCM adapter.

        Args:
            config: FCM configuration
            lifecycle_handler: Optional handler for token lifecycle events
        """
        self.config = config
        self._lifecycle_handler = lifecycle_handler
        self._client: Any = None  # httpx.AsyncClient
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def channel(self) -> PushChannel:
        """The channel this adapter handles."""
        return PushChannel.FCM

    async def start(self) -> None:
        """Start the adapter."""
        # Import here to avoid hard dependency
        try:
            import httpx

            self._client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
            logger.info("FCM adapter started")
        except ImportError:
            raise RuntimeError("httpx is required for FCM adapter: pip install httpx")

    async def stop(self) -> None:
        """Stop the adapter and cleanup resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.info("FCM adapter stopped")

    async def send(self, message: PushMessage) -> PushResult:
        """
        Send a push notification via FCM.

        Args:
            message: The push message to send

        Returns:
            PushResult with delivery status
        """
        if not message.target.device_tokens:
            return PushResult(
                message_id=message.id,
                channel=PushChannel.FCM,
                status=PushStatus.FAILED,
                success=False,
                error_code="NO_TOKENS",
                error_message="No device tokens provided",
            )

        tokens = message.target.device_tokens

        # Use batch sending for multiple tokens
        if len(tokens) > 1:
            return await self._send_batch(message, tokens)

        return await self._send_single(message, tokens[0])

    async def send_batch(self, messages: list[PushMessage]) -> list[PushResult]:
        """Send multiple messages."""
        results = []
        for message in messages:
            result = await self.send(message)
            results.append(result)
        return results

    async def _send_single(
        self,
        message: PushMessage,
        token: str,
    ) -> PushResult:
        """Send to a single device with retry."""
        fcm_message = self._build_fcm_message(message, token)

        for attempt in range(self.config.max_retries):
            try:
                if self._client is None:
                    await self.start()

                access_token = await self._get_access_token()
                url = self.FCM_ENDPOINT.format(project_id=self.config.project_id)

                response = await self._client.post(
                    url,
                    json={"message": fcm_message},
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 200:
                    return PushResult(
                        message_id=message.id,
                        channel=PushChannel.FCM,
                        status=PushStatus.DELIVERED,
                        success=True,
                        delivered_at=datetime.now(timezone.utc),
                        metadata={"fcm_message_id": response.json().get("name")},
                    )

                # Handle errors
                error_data = response.json().get("error", {})
                error_code = error_data.get("code", str(response.status_code))
                error_message = error_data.get("message", response.text)

                # Check for invalid token
                if response.status_code == 404 or "UNREGISTERED" in str(error_data):
                    await self._handle_invalid_token(token, error_code, error_message)
                    return PushResult(
                        message_id=message.id,
                        channel=PushChannel.FCM,
                        status=PushStatus.REJECTED,
                        success=False,
                        error_code="INVALID_TOKEN",
                        error_message="Token is no longer valid",
                        failed_tokens=[token],
                    )

                # Retry on transient errors
                if response.status_code in (429, 500, 503):
                    backoff = min(
                        self.config.initial_backoff * (2**attempt),
                        self.config.max_backoff,
                    )
                    logger.warning(f"FCM retry {attempt + 1}, backing off {backoff}s")
                    await asyncio.sleep(backoff)
                    continue

                return PushResult(
                    message_id=message.id,
                    channel=PushChannel.FCM,
                    status=PushStatus.FAILED,
                    success=False,
                    error_code=error_code,
                    error_message=error_message,
                    attempt_number=attempt + 1,
                )

            except Exception as e:
                logger.error(f"FCM send error: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.initial_backoff * (2**attempt))
                    continue

                return PushResult(
                    message_id=message.id,
                    channel=PushChannel.FCM,
                    status=PushStatus.FAILED,
                    success=False,
                    error_code="EXCEPTION",
                    error_message=str(e),
                    attempt_number=attempt + 1,
                    should_retry=True,
                )

        return PushResult(
            message_id=message.id,
            channel=PushChannel.FCM,
            status=PushStatus.FAILED,
            success=False,
            error_code="MAX_RETRIES",
            error_message="Max retries exceeded",
        )

    async def _send_batch(
        self,
        message: PushMessage,
        tokens: list[str],
    ) -> PushResult:
        """Send to multiple devices in batches."""
        total_success = 0
        total_failure = 0
        failed_tokens: list[str] = []

        # Process in batches
        for i in range(0, len(tokens), self.config.max_batch_size):
            batch = tokens[i : i + self.config.max_batch_size]

            # Send each message in the batch
            tasks = [self._send_single(message, token) for token in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, result in enumerate(results):
                if isinstance(result, PushResult) and result.success:
                    total_success += 1
                else:
                    total_failure += 1
                    failed_tokens.append(batch[idx])

        success = total_failure == 0

        return PushResult(
            message_id=message.id,
            channel=PushChannel.FCM,
            status=PushStatus.DELIVERED if success else PushStatus.FAILED,
            success=success,
            delivered_at=datetime.now(timezone.utc) if success else None,
            failed_tokens=failed_tokens,
            metadata={
                "total_tokens": len(tokens),
                "success_count": total_success,
                "failure_count": total_failure,
            },
        )

    def _build_fcm_message(self, message: PushMessage, token: str) -> dict[str, Any]:
        """Build the FCM message payload."""
        # Map priority
        android_priority = "normal"
        apns_priority = "5"
        if message.priority in (PushPriority.HIGH, PushPriority.CRITICAL):
            android_priority = "high"
            apns_priority = "10"

        # Build data payload - all values must be strings
        data = {
            "message_id": message.id,
            **{k: self._serialize_value(v) for k, v in message.data.items()},
        }

        fcm_message: dict[str, Any] = {
            "token": token,
            "data": data,
            "android": {
                "priority": android_priority,
                "ttl": f"{message.ttl_seconds}s",
            },
            "apns": {
                "headers": {
                    "apns-priority": apns_priority,
                    "apns-expiration": str(int(message.ttl_seconds)),
                },
                "payload": {
                    "aps": {},
                },
            },
        }

        # Add notification block if title/body provided
        if message.title or message.body:
            fcm_message["notification"] = {
                "title": message.title,
                "body": message.body,
            }
            fcm_message["apns"]["payload"]["aps"]["alert"] = {
                "title": message.title,
                "body": message.body,
            }
            if message.priority in (PushPriority.HIGH, PushPriority.CRITICAL):
                fcm_message["apns"]["payload"]["aps"]["sound"] = "default"

        # Add collapse key if provided
        if message.collapse_key:
            fcm_message["android"]["collapse_key"] = message.collapse_key
            fcm_message["apns"]["headers"]["apns-collapse-id"] = message.collapse_key

        # Add content-available for background processing
        if message.content_available:
            fcm_message["apns"]["payload"]["aps"]["content-available"] = 1

        # Add mutable-content for iOS notification service extension
        if message.mutable_content:
            fcm_message["apns"]["payload"]["aps"]["mutable-content"] = 1

        return fcm_message

    def _serialize_value(self, value: Any) -> str:
        """Serialize a value for FCM data payload. All values must be strings."""
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int | float):
            return str(value)
        # For complex types (list, dict), use JSON serialization
        return json.dumps(value)

    async def _get_access_token(self) -> str:
        """Get OAuth2 access token for FCM API."""
        # Check if current token is still valid
        if (
            self._access_token
            and self._token_expires_at
            and datetime.now(timezone.utc) < self._token_expires_at
        ):
            return self._access_token

        # Get new token using google-auth
        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account

            scopes = ["https://www.googleapis.com/auth/firebase.messaging"]

            if self.config.service_account_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self.config.service_account_path,
                    scopes=scopes,
                )
            elif self.config.service_account_json:
                credentials = service_account.Credentials.from_service_account_info(
                    self.config.service_account_json,
                    scopes=scopes,
                )
            else:
                raise ValueError("No service account credentials provided")

            credentials.refresh(Request())
            self._access_token = credentials.token
            self._token_expires_at = credentials.expiry

            return self._access_token

        except ImportError:
            logger.error("google-auth not installed. Install with: pip install google-auth")
            raise

    async def _handle_invalid_token(
        self,
        token: str,
        error_code: str,
        error_message: str | None,
    ) -> None:
        """Handle an invalid FCM token."""
        logger.info(f"Marking token as invalid: {token[:20]}...")

        if self._lifecycle_handler:
            event = TokenInvalidationEvent(
                token=token,
                channel=PushChannel.FCM,
                reason=reason_from_fcm_error(error_code),
                reason_detail=error_message,
                error_code=error_code,
                error_message=error_message,
            )
            try:
                await self._lifecycle_handler.on_token_invalidated(event)
            except Exception as e:
                logger.error(f"Error in lifecycle handler: {e}")
