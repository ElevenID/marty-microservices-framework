"""
Event Publishing Exceptions

Custom exceptions for event publishing operations.
"""


class EventPublishingError(Exception):
    """Base exception for event publishing errors."""

    def __init__(self, message: str, event_id: str | None = None, cause: Exception | None = None):
        super().__init__(message)
        self.event_id = event_id
        self.cause = cause


class KafkaConnectionError(EventPublishingError):
    """Raised when unable to connect to Kafka."""


class EventSerializationError(EventPublishingError):
    """Raised when event serialization fails."""


class OutboxError(EventPublishingError):
    """Raised when outbox pattern operations fail."""


class EventValidationError(EventPublishingError):
    """Raised when event validation fails."""


class TopicNotFoundError(EventPublishingError):
    """Raised when specified topic doesn't exist."""


class EventTimeoutError(EventPublishingError):
    """Raised when event publishing times out."""
