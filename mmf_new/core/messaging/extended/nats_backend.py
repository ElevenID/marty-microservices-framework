"""
NATS Backend Implementation for Extended Messaging System

Provides NATS.io connector with support for:
- Publish/Subscribe patterns
- Request/Response patterns
- Stream processing via JetStream
- High performance, low latency messaging
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext

from .extended_architecture import (
    DeliveryGuarantee,
    EnhancedMessageBackend,
    GenericMessage,
    MessageMetadata,
    MessagingPattern,
    MessagingPatternConfig,
    NATSConfig,
)

try:
    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False


logger = logging.getLogger(__name__)


class NATSMessage(GenericMessage):
    """NATS-specific message implementation."""

    def __init__(self, payload: Any, metadata: MessageMetadata, pattern: MessagingPattern):
        super().__init__(payload, metadata, pattern)
        self._nats_msg = None
        self._nc = None

    def _set_nats_context(self, nats_msg, nc):
        """Set NATS message context for acknowledgment."""
        self._nats_msg = nats_msg
        self._nc = nc

    async def ack(self) -> bool:
        """Acknowledge NATS message."""
        try:
            if self._nats_msg and hasattr(self._nats_msg, "ack"):
                await self._nats_msg.ack()
                self._acknowledged = True
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to ack NATS message: {e}")
            return False

    async def nack(self, requeue: bool = True) -> bool:
        """Negative acknowledge NATS message."""
        try:
            if self._nats_msg and hasattr(self._nats_msg, "nak"):
                if requeue:
                    await self._nats_msg.nak()
                else:
                    await self._nats_msg.term()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to nack NATS message: {e}")
            return False

    async def reject(self, requeue: bool = False) -> bool:
        """Reject NATS message."""
        return await self.nack(requeue=requeue)


class NATSBackend(EnhancedMessageBackend):
    """NATS backend implementation."""

    def __init__(self, config: NATSConfig):
        if not NATS_AVAILABLE:
            raise ImportError("NATS is not installed. Install with: pip install nats-py")

        self.config = config
        self.nc: NATS | None = None
        self.js: JetStreamContext | None = None
        self._subscriptions: dict[str, Any] = {}
        self._connected = False

    async def connect(self) -> bool:
        """Connect to NATS server."""
        try:
            options = {
                "servers": self.config.servers,
                "max_reconnect_attempts": self.config.max_reconnect_attempts,
                "reconnect_time_wait": self.config.reconnect_time_wait,
            }

            if self.config.user and self.config.password:
                options["user"] = self.config.user
                options["password"] = self.config.password
            elif self.config.token:
                options["token"] = self.config.token

            if self.config.tls_enabled:
                options["tls"] = True

            self.nc = await nats.connect(**options)

            if self.config.jetstream_enabled:
                self.js = self.nc.jetstream()

            self._connected = True
            logger.info(f"Connected to NATS servers: {self.config.servers}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from NATS server."""
        try:
            if self.nc:
                await self.nc.close()

            self._connected = False
            self._subscriptions.clear()
            logger.info("Disconnected from NATS")
            return True

        except Exception as e:
            logger.error(f"Failed to disconnect from NATS: {e}")
            return False

    async def publish(
        self, topic: str, message: GenericMessage, pattern_config: MessagingPatternConfig
    ) -> bool:
        """Publish message to NATS."""
        if not self._connected or not self.nc:
            logger.error("NATS not connected")
            return False

        try:
            # Serialize message
            payload = {
                "data": message.payload,
                "metadata": {
                    "message_id": message.metadata.message_id,
                    "correlation_id": message.metadata.correlation_id,
                    "causation_id": message.metadata.causation_id,
                    "timestamp": message.metadata.timestamp.isoformat(),
                    "ttl": message.metadata.ttl.total_seconds() if message.metadata.ttl else None,
                    "priority": message.metadata.priority,
                    "content_type": message.metadata.content_type,
                    "headers": message.metadata.headers,
                    "routing_key": message.metadata.routing_key,
                    "reply_to": message.metadata.reply_to,
                    "message_type": message.metadata.message_type,
                },
            }

            message_bytes = json.dumps(payload).encode("utf-8")

            # Choose publishing method based on pattern
            if pattern_config.pattern == MessagingPattern.STREAM_PROCESSING:
                if not self.js:
                    logger.error("JetStream not enabled for stream processing")
                    return False

                await self.js.publish(topic, message_bytes)
            else:
                # Standard pub/sub or point-to-point
                await self.nc.publish(topic, message_bytes)

            logger.debug(f"Published message to NATS topic: {topic}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish message to NATS topic {topic}: {e}")
            return False

    async def subscribe(self, topic: str, handler, pattern_config: MessagingPatternConfig) -> str:
        """Subscribe to NATS topic."""
        if not self._connected or not self.nc:
            logger.error("NATS not connected")
            return ""

        try:
            subscription_id = str(uuid.uuid4())

            async def message_handler(msg):
                try:
                    # Deserialize message
                    payload = json.loads(msg.data.decode("utf-8"))

                    # Reconstruct metadata
                    metadata_dict = payload.get("metadata", {})
                    metadata = MessageMetadata(
                        message_id=metadata_dict.get("message_id", str(uuid.uuid4())),
                        correlation_id=metadata_dict.get("correlation_id"),
                        causation_id=metadata_dict.get("causation_id"),
                        timestamp=datetime.fromisoformat(metadata_dict["timestamp"])
                        if metadata_dict.get("timestamp")
                        else datetime.utcnow(),
                        ttl=timedelta(seconds=metadata_dict["ttl"])
                        if metadata_dict.get("ttl")
                        else None,
                        priority=metadata_dict.get("priority", 0),
                        content_type=metadata_dict.get("content_type", "application/json"),
                        headers=metadata_dict.get("headers", {}),
                        routing_key=metadata_dict.get("routing_key"),
                        reply_to=metadata_dict.get("reply_to"),
                        message_type=metadata_dict.get("message_type"),
                    )

                    # Create message object
                    nats_message = NATSMessage(
                        payload=payload.get("data"),
                        metadata=metadata,
                        pattern=pattern_config.pattern,
                    )
                    nats_message._set_nats_context(msg, self.nc)

                    # Call handler
                    await handler(nats_message)

                except Exception as e:
                    logger.error(f"Error processing NATS message: {e}")

            # Subscribe based on pattern
            if pattern_config.pattern == MessagingPattern.STREAM_PROCESSING:
                if not self.js:
                    logger.error("JetStream not enabled for stream processing")
                    return ""

                # For stream processing, create a durable consumer
                consumer_config = {
                    "durable_name": f"consumer_{subscription_id}",
                    "deliver_policy": "new",
                }

                if pattern_config.delivery_guarantee == DeliveryGuarantee.EXACTLY_ONCE:
                    consumer_config["ack_policy"] = "explicit"
                elif pattern_config.delivery_guarantee == DeliveryGuarantee.AT_LEAST_ONCE:
                    consumer_config["ack_policy"] = "explicit"
                else:
                    consumer_config["ack_policy"] = "none"

                subscription = await self.js.subscribe(topic, cb=message_handler, **consumer_config)
            else:
                # Standard subscription
                subscription = await self.nc.subscribe(topic, cb=message_handler)

            self._subscriptions[subscription_id] = subscription
            logger.info(f"Subscribed to NATS topic: {topic}")
            return subscription_id

        except Exception as e:
            logger.error(f"Failed to subscribe to NATS topic {topic}: {e}")
            return ""

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from NATS topic."""
        try:
            if subscription_id in self._subscriptions:
                subscription = self._subscriptions[subscription_id]
                await subscription.unsubscribe()
                del self._subscriptions[subscription_id]
                logger.info(f"Unsubscribed from NATS subscription: {subscription_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to unsubscribe from NATS: {e}")
            return False

    async def request(
        self, topic: str, message: GenericMessage, timeout: timedelta = timedelta(seconds=30)
    ) -> GenericMessage:
        """Send request and wait for response via NATS."""
        if not self._connected or not self.nc:
            raise RuntimeError("NATS not connected")

        try:
            # Serialize request
            payload = {
                "data": message.payload,
                "metadata": {
                    "message_id": message.metadata.message_id,
                    "correlation_id": message.metadata.correlation_id,
                    "causation_id": message.metadata.causation_id,
                    "timestamp": message.metadata.timestamp.isoformat(),
                    "ttl": message.metadata.ttl.total_seconds() if message.metadata.ttl else None,
                    "priority": message.metadata.priority,
                    "content_type": message.metadata.content_type,
                    "headers": message.metadata.headers,
                    "routing_key": message.metadata.routing_key,
                    "reply_to": message.metadata.reply_to,
                    "message_type": message.metadata.message_type,
                },
            }

            message_bytes = json.dumps(payload).encode("utf-8")

            # Send request and wait for response
            response = await self.nc.request(topic, message_bytes, timeout=timeout.total_seconds())

            # Deserialize response
            response_payload = json.loads(response.data.decode("utf-8"))

            # Reconstruct response metadata
            metadata_dict = response_payload.get("metadata", {})
            response_metadata = MessageMetadata(
                message_id=metadata_dict.get("message_id", str(uuid.uuid4())),
                correlation_id=metadata_dict.get("correlation_id"),
                causation_id=metadata_dict.get("causation_id"),
                timestamp=datetime.fromisoformat(metadata_dict["timestamp"])
                if metadata_dict.get("timestamp")
                else datetime.utcnow(),
                ttl=timedelta(seconds=metadata_dict["ttl"]) if metadata_dict.get("ttl") else None,
                priority=metadata_dict.get("priority", 0),
                content_type=metadata_dict.get("content_type", "application/json"),
                headers=metadata_dict.get("headers", {}),
                routing_key=metadata_dict.get("routing_key"),
                reply_to=metadata_dict.get("reply_to"),
                message_type=metadata_dict.get("message_type"),
            )

            # Create response message
            response_message = NATSMessage(
                payload=response_payload.get("data"),
                metadata=response_metadata,
                pattern=MessagingPattern.REQUEST_RESPONSE,
            )

            return response_message

        except Exception as e:
            logger.error(f"Failed to send NATS request to {topic}: {e}")
            raise

    async def reply(self, original_message: GenericMessage, response: GenericMessage) -> bool:
        """Reply to a request message via NATS."""
        if not self._connected or not self.nc:
            logger.error("NATS not connected")
            return False

        try:
            reply_to = original_message.metadata.reply_to
            if not reply_to:
                logger.error("No reply_to address in original message")
                return False

            # Serialize response
            payload = {
                "data": response.payload,
                "metadata": {
                    "message_id": response.metadata.message_id,
                    "correlation_id": original_message.metadata.correlation_id,  # Keep original correlation
                    "causation_id": original_message.metadata.message_id,  # Causation is original message
                    "timestamp": response.metadata.timestamp.isoformat(),
                    "ttl": response.metadata.ttl.total_seconds() if response.metadata.ttl else None,
                    "priority": response.metadata.priority,
                    "content_type": response.metadata.content_type,
                    "headers": response.metadata.headers,
                    "routing_key": response.metadata.routing_key,
                    "reply_to": response.metadata.reply_to,
                    "message_type": response.metadata.message_type,
                },
            }

            message_bytes = json.dumps(payload).encode("utf-8")

            # Send reply
            await self.nc.publish(reply_to, message_bytes)

            logger.debug(f"Sent NATS reply to: {reply_to}")
            return True

        except Exception as e:
            logger.error(f"Failed to send NATS reply: {e}")
            return False

    def supports_pattern(self, pattern: MessagingPattern) -> bool:
        """Check if NATS supports the messaging pattern."""
        # NATS supports all patterns
        return True

    def get_supported_guarantees(self) -> list[DeliveryGuarantee]:
        """Get delivery guarantees supported by NATS."""
        if self.config.jetstream_enabled:
            return [
                DeliveryGuarantee.AT_MOST_ONCE,
                DeliveryGuarantee.AT_LEAST_ONCE,
                DeliveryGuarantee.EXACTLY_ONCE,
            ]
        else:
            return [DeliveryGuarantee.AT_MOST_ONCE]


def create_nats_backend(config: NATSConfig) -> NATSBackend:
    """Factory function to create NATS backend."""
    return NATSBackend(config)
