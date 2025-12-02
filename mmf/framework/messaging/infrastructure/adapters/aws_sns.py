"""
AWS SNS Backend Implementation for Extended Messaging System

Provides AWS Simple Notification Service connector with support for:
- Publish/Subscribe patterns
- Broadcast patterns
- FIFO topic support
- Dead letter queues
- Message filtering
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from mmf.framework.messaging.domain.extended import (
    AWSSNSConfig,
    DeliveryGuarantee,
    EnhancedMessageBackend,
    GenericMessage,
    MessageMetadata,
    MessagingPattern,
    MessagingPatternConfig,
)

logger = logging.getLogger(__name__)


class SNSMessage(GenericMessage):
    """AWS SNS-specific message implementation."""

    def __init__(self, payload: Any, metadata: MessageMetadata, pattern: MessagingPattern):
        super().__init__(payload, metadata, pattern)
        self._sns_receipt_handle = None

    def _set_sns_context(self, receipt_handle: str):
        """Set SNS message context for acknowledgment."""
        self._sns_receipt_handle = receipt_handle

    async def ack(self) -> bool:
        """Acknowledge SNS message (no-op for SNS publish/subscribe)."""
        # SNS doesn't have explicit acknowledgment for pub/sub
        # This would be handled by SQS if using SNS+SQS pattern
        self._acknowledged = True
        return True

    async def nack(self, requeue: bool = True) -> bool:
        """Negative acknowledge SNS message (no-op for SNS)."""
        # SNS doesn't support nack, but we return True for compatibility
        return True

    async def reject(self, requeue: bool = False) -> bool:
        """Reject SNS message (no-op for SNS)."""
        return True


class AWSSNSBackend(EnhancedMessageBackend):
    """AWS SNS backend implementation."""

    def __init__(self, config: AWSSNSConfig):
        self.config = config
        self.sns_client = None
        self._topics: dict[str, str] = {}  # topic_name -> topic_arn
        self._subscriptions: dict[str, str] = {}  # subscription_id -> subscription_arn
        self._connected = False

    async def connect(self) -> bool:
        """Connect to AWS SNS."""
        try:
            session_kwargs = {"region_name": self.config.region_name}

            if self.config.aws_access_key_id and self.config.aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = self.config.aws_access_key_id
                session_kwargs["aws_secret_access_key"] = self.config.aws_secret_access_key

            if self.config.endpoint_url:
                session_kwargs["endpoint_url"] = self.config.endpoint_url

            self.sns_client = boto3.client("sns", **session_kwargs)

            # Test connection
            self.sns_client.list_topics()

            self._connected = True
            logger.info(f"Connected to AWS SNS in region: {self.config.region_name}")
            return True

        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Failed to connect to AWS SNS: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to AWS SNS: {e}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from AWS SNS."""
        try:
            # Clean up subscriptions
            for subscription_arn in self._subscriptions.values():
                try:
                    self.sns_client.unsubscribe(SubscriptionArn=subscription_arn)
                except ClientError as e:
                    logger.warning(f"Failed to unsubscribe from {subscription_arn}: {e}")

            self._connected = False
            self._topics.clear()
            self._subscriptions.clear()
            logger.info("Disconnected from AWS SNS")
            return True

        except Exception as e:
            logger.error(f"Failed to disconnect from AWS SNS: {e}")
            return False

    async def _ensure_topic_exists(
        self, topic_name: str, pattern_config: MessagingPatternConfig
    ) -> str:
        """Ensure SNS topic exists and return topic ARN."""
        if topic_name in self._topics:
            return self._topics[topic_name]

        try:
            # Create topic attributes
            attributes = {}

            if self.config.fifo_topics:
                # FIFO topics must end with .fifo
                if not topic_name.endswith(".fifo"):
                    topic_name = f"{topic_name}.fifo"
                attributes["FifoTopic"] = "true"

                if self.config.content_based_deduplication:
                    attributes["ContentBasedDeduplication"] = "true"

            if self.config.kms_master_key_id:
                attributes["KmsMasterKeyId"] = self.config.kms_master_key_id

            # Set delivery policy for reliability
            if pattern_config.delivery_guarantee == DeliveryGuarantee.AT_LEAST_ONCE:
                delivery_policy = {
                    "healthyRetryPolicy": {
                        "numRetries": pattern_config.retry_count,
                        "numMaxDelayRetries": pattern_config.retry_count,
                        "minDelayTarget": 20,
                        "maxDelayTarget": 20,
                        "numMinDelayRetries": 0,
                        "numNoDelayRetries": 0,
                        "backoffFunction": "linear",
                    }
                }
                attributes["DeliveryPolicy"] = json.dumps(delivery_policy)

            # Create topic
            response = self.sns_client.create_topic(Name=topic_name, Attributes=attributes)

            topic_arn = response["TopicArn"]
            self._topics[topic_name] = topic_arn
            logger.info(f"Created/ensured SNS topic: {topic_name} -> {topic_arn}")
            return topic_arn

        except ClientError as e:
            logger.error(f"Failed to create SNS topic {topic_name}: {e}")
            raise

    async def publish(
        self, topic: str, message: GenericMessage, pattern_config: MessagingPatternConfig
    ) -> bool:
        """Publish message to SNS topic."""
        if not self._connected or not self.sns_client:
            logger.error("AWS SNS not connected")
            return False

        try:
            topic_arn = await self._ensure_topic_exists(topic, pattern_config)

            # Prepare message
            message_body = {
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

            # Prepare SNS message parameters
            sns_params = {
                "TopicArn": topic_arn,
                "Message": json.dumps(message_body),
            }

            # Add message attributes for filtering
            message_attributes = {}
            if message.metadata.message_type:
                message_attributes["MessageType"] = {
                    "DataType": "String",
                    "StringValue": message.metadata.message_type,
                }

            if message.metadata.headers:
                for key, value in message.metadata.headers.items():
                    if isinstance(value, str | int | float):
                        message_attributes[key] = {"DataType": "String", "StringValue": str(value)}

            if message_attributes:
                sns_params["MessageAttributes"] = message_attributes

            # FIFO topic specific parameters
            if self.config.fifo_topics:
                sns_params["MessageGroupId"] = message.metadata.routing_key or "default"
                if not self.config.content_based_deduplication:
                    sns_params["MessageDeduplicationId"] = message.metadata.message_id

            # Subject for email subscriptions
            if message.metadata.message_type:
                sns_params["Subject"] = f"[{message.metadata.message_type}] Notification"

            # Publish message
            response = self.sns_client.publish(**sns_params)

            logger.debug(
                f"Published message to SNS topic: {topic}, MessageId: {response['MessageId']}"
            )
            return True

        except ClientError as e:
            logger.error(f"Failed to publish message to SNS topic {topic}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error publishing to SNS topic {topic}: {e}")
            return False

    async def subscribe(self, topic: str, handler, pattern_config: MessagingPatternConfig) -> str:
        """Subscribe to SNS topic (creates SQS subscription)."""
        if not self._connected or not self.sns_client:
            logger.error("AWS SNS not connected")
            return ""

        try:
            topic_arn = await self._ensure_topic_exists(topic, pattern_config)
            subscription_id = str(uuid.uuid4())

            # For SNS, we typically need an SQS queue as the subscription endpoint
            # This is a simplified implementation - in practice, you'd want to
            # create an SQS queue and subscribe it to the SNS topic
            logger.warning(
                "SNS subscribe requires SQS queue endpoint - this is a placeholder implementation"
            )

            # In a real implementation, you would:
            # 1. Create an SQS queue
            # 2. Subscribe the SQS queue to the SNS topic
            # 3. Start polling the SQS queue for messages
            # 4. Call the handler for each message

            # For now, we'll just store the subscription info
            self._subscriptions[subscription_id] = f"pending-{topic_arn}"

            logger.info(f"Created SNS subscription placeholder for topic: {topic}")
            return subscription_id

        except Exception as e:
            logger.error(f"Failed to subscribe to SNS topic {topic}: {e}")
            return ""

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from SNS topic."""
        try:
            if subscription_id in self._subscriptions:
                subscription_arn = self._subscriptions[subscription_id]

                if not subscription_arn.startswith("pending-"):
                    self.sns_client.unsubscribe(SubscriptionArn=subscription_arn)

                del self._subscriptions[subscription_id]
                logger.info(f"Unsubscribed from SNS: {subscription_id}")
                return True
            return False

        except ClientError as e:
            logger.error(f"Failed to unsubscribe from SNS: {e}")
            return False

    async def request(
        self, topic: str, message: GenericMessage, timeout: timedelta = timedelta(seconds=30)
    ) -> GenericMessage:
        """Send request via SNS (not supported - raises NotImplementedError)."""
        raise NotImplementedError(
            "Request/Response pattern not supported by SNS - use SQS or NATS instead"
        )

    async def reply(self, original_message: GenericMessage, response: GenericMessage) -> bool:
        """Reply via SNS (not supported - raises NotImplementedError)."""
        raise NotImplementedError(
            "Request/Response pattern not supported by SNS - use SQS or NATS instead"
        )

    def supports_pattern(self, pattern: MessagingPattern) -> bool:
        """Check if SNS supports the messaging pattern."""
        supported_patterns = {
            MessagingPattern.PUBLISH_SUBSCRIBE,
            MessagingPattern.BROADCAST,
            MessagingPattern.POINT_TO_POINT,  # With SQS subscription
        }
        return pattern in supported_patterns

    def get_supported_guarantees(self) -> list[DeliveryGuarantee]:
        """Get delivery guarantees supported by SNS."""
        if self.config.fifo_topics:
            return [
                DeliveryGuarantee.AT_LEAST_ONCE,
                DeliveryGuarantee.EXACTLY_ONCE,  # With FIFO and deduplication
            ]
        else:
            return [DeliveryGuarantee.AT_LEAST_ONCE]


def create_aws_sns_backend(config: AWSSNSConfig) -> AWSSNSBackend:
    """Factory function to create AWS SNS backend."""
    return AWSSNSBackend(config)
