"""
Event Publisher Configuration

Configuration classes for the unified event publishing system.
"""

import os
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


@dataclass
class EventConfig:
    """Configuration for event publishing."""

    # Kafka configuration
    kafka_brokers: list[str] = field(default_factory=lambda: ["localhost:9092"])
    kafka_security_protocol: str = "PLAINTEXT"
    kafka_sasl_mechanism: str | None = None
    kafka_sasl_username: str | None = None
    kafka_sasl_password: str | None = None

    # Topic configuration
    topic_prefix: str = "mmf"
    audit_topic: str = "audit.events"
    notification_topic: str = "notification.events"
    domain_topic_pattern: str = "{service}.{aggregate}.{event_type}"

    # Producer configuration
    producer_acks: str = "all"
    producer_retries: int = 3
    producer_timeout_ms: int = 30000
    producer_batch_size: int = 16384
    producer_linger_ms: int = 10
    producer_compression_type: str = "snappy"

    # Outbox configuration
    use_outbox_pattern: bool = True
    outbox_table_name: str = "event_outbox"
    outbox_poll_interval_seconds: int = 30
    outbox_batch_size: int = 100

    # Service configuration
    service_name: str = "unknown"
    service_version: str = "1.0.0"

    # Monitoring and observability
    enable_tracing: bool = True
    enable_metrics: bool = True
    dead_letter_topic: str = "dead.letter.queue"

    @classmethod
    def from_env(cls) -> "EventConfig":
        """Create configuration from environment variables."""
        kafka_brokers_str = os.getenv("KAFKA_BROKERS", "localhost:9092")
        kafka_brokers = [broker.strip() for broker in kafka_brokers_str.split(",")]

        return cls(
            kafka_brokers=kafka_brokers,
            kafka_security_protocol=os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
            kafka_sasl_mechanism=os.getenv("KAFKA_SASL_MECHANISM"),
            kafka_sasl_username=os.getenv("KAFKA_SASL_USERNAME"),
            kafka_sasl_password=os.getenv("KAFKA_SASL_PASSWORD"),
            topic_prefix=os.getenv("EVENT_TOPIC_PREFIX", "mmf"),
            service_name=os.getenv("SERVICE_NAME", "unknown"),
            service_version=os.getenv("SERVICE_VERSION", "1.0.0"),
            use_outbox_pattern=os.getenv("USE_OUTBOX_PATTERN", "true").lower() == "true",
            enable_tracing=os.getenv("ENABLE_EVENT_TRACING", "true").lower() == "true",
            enable_metrics=os.getenv("ENABLE_EVENT_METRICS", "true").lower() == "true",
        )


class EventPublisherConfig(BaseModel):
    """Pydantic model for event publisher configuration."""

    kafka_brokers: list[str] = Field(default_factory=lambda: ["localhost:9092"])
    kafka_security_protocol: str = "PLAINTEXT"
    kafka_sasl_mechanism: str | None = None
    kafka_sasl_username: str | None = None
    kafka_sasl_password: str | None = None

    topic_prefix: str = "mmf"
    service_name: str = "unknown"
    service_version: str = "1.0.0"

    use_outbox_pattern: bool = True
    enable_tracing: bool = True
    enable_metrics: bool = True

    producer_config: dict[str, Any] = Field(default_factory=dict)

    class Config:
        env_prefix = "EVENT_"
        env_file = ".env"

    def get_kafka_config(self) -> dict[str, Any]:
        """Get Kafka configuration for aiokafka."""
        config = {
            "bootstrap_servers": self.kafka_brokers,
            "security_protocol": self.kafka_security_protocol,
            "acks": "all",
            "retries": 3,
            "request_timeout_ms": 30000,
            "compression_type": "snappy",
        }

        if self.kafka_sasl_mechanism:
            config.update(
                {
                    "sasl_mechanism": self.kafka_sasl_mechanism,
                    "sasl_plain_username": self.kafka_sasl_username,
                    "sasl_plain_password": self.kafka_sasl_password,
                }
            )

        # Override with custom producer config
        config.update(self.producer_config)

        return config
