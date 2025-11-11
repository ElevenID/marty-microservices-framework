# Kafka Infrastructure

This directory contains Kafka event streaming infrastructure for microservices communication.

## Components

### Event Bus (`event_bus.py`)

- **EventBus**: Main class for Kafka interaction
- **EventMessage**: Standard event format with correlation IDs
- **KafkaConfig**: Configuration settings for Kafka connections

### Key Features

- Async event publishing and consumption
- Automatic retries and error handling
- Dead letter queue support
- Correlation ID tracking for distributed tracing
- Service and domain event patterns

## Usage

### Basic Setup

```python
from marty_msf.observability.kafka import EventBus, KafkaConfig, event_bus_context

config = KafkaConfig(
    bootstrap_servers=["localhost:9092"],
    consumer_group_id="my-service"
)

async with event_bus_context(config, "my-service") as event_bus:
    # Publish events
    await event_bus.publish_event(
        topic="user.events",
        event_type="user.created",
        payload={"user_id": "123", "email": "user@example.com"}
    )

    # Register handlers
    async def handle_user_event(event):
        print(f"Received: {event.event_type}")

    event_bus.register_handler("user.events", handle_user_event)
    await event_bus.start_consumer(["user.events"])
```

### Service Events

```python
from marty_msf.observability.kafka import publish_service_event

await publish_service_event(
    event_bus,
    event_type="service.started",
    data={"version": "1.0.0", "port": 8080}
)
```

### Domain Events

```python
from marty_msf.observability.kafka import publish_domain_event

await publish_domain_event(
    event_bus,
    domain="user",
    event_type="user.profile.updated",
    data={"user_id": "123", "fields": ["email", "name"]}
)
```

## Event Patterns

### Topic Naming Convention

- Service events: `service.{service_name}.events`
- Domain events: `domain.{domain}.events`
- Integration events: `integration.{external_system}.events`

### Event Types

- Use dot notation: `entity.action` (e.g., `user.created`, `order.cancelled`)
- Include service context: `service.action` (e.g., `service.started`, `service.healthcheck`)

### Correlation IDs

- Include correlation IDs for request tracing
- Pass through correlation IDs in downstream events
- Use for distributed transaction tracking

## Monitoring

The event bus includes structured logging for:

- Event publishing metrics
- Consumer lag monitoring
- Error tracking and dead letter queue metrics
- Performance metrics (throughput, latency)
