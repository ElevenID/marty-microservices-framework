# Extended Messaging System Examples

This directory contains comprehensive examples showing how to use the extended messaging system with different backends and patterns.

## Examples Overview

### 1. Backend Comparison Examples

- **NATS Example**: High-performance, low-latency messaging
- **AWS SNS Example**: Cloud-native pub/sub and broadcast messaging
- **RabbitMQ Example**: Traditional message queuing with complex routing
- **Kafka Example**: High-throughput stream processing

### 2. Pattern Examples

- **Pub/Sub Pattern**: Event notifications and reactive architectures
- **Request/Response Pattern**: Synchronous communication patterns
- **Stream Processing**: Real-time data processing pipelines
- **Point-to-Point**: Task queues and command processing

### 3. Integration Examples

- **Saga Pattern Integration**: Distributed transaction coordination
- **Multi-Backend Setup**: Using multiple backends simultaneously
- **Pattern Selection**: Choosing the right pattern for your use case

### 4. Real-World Use Cases

- **E-commerce Order Processing**: Complete order workflow with Saga
- **User Registration**: Multi-service user onboarding
- **Payment Processing**: Secure payment workflows
- **Data Analytics Pipeline**: Real-time analytics processing

## Quick Start

### Basic Setup

```python
from marty_msf.framework.messaging import (
    create_unified_event_bus,
    NATSBackend,
    NATSConfig,
    MessageBackendType
)

# Create unified event bus
event_bus = create_unified_event_bus()

# Configure NATS backend
nats_config = NATSConfig(
    servers=["nats://localhost:4222"],
    jetstream_enabled=True
)
nats_backend = NATSBackend(nats_config)

# Register backend
event_bus.register_backend(MessageBackendType.NATS, nats_backend)
event_bus.set_default_backend(MessageBackendType.NATS)

# Start event bus
await event_bus.start()
```

### Publishing Events

```python
# Publish domain event
await event_bus.publish_event(
    event_type="user_registered",
    data={
        "user_id": "123",
        "email": "user@example.com",
        "timestamp": "2024-01-15T10:30:00Z"
    }
)
```

### Subscribing to Events

```python
async def handle_user_events(event_type, data, metadata):
    print(f"Received event: {event_type}")
    print(f"Data: {data}")
    return True

# Subscribe to events
subscription_id = await event_bus.subscribe_to_events(
    event_types=["user_registered", "user_updated"],
    handler=handle_user_events
)
```

### Request/Response

```python
# Send query and get response
response = await event_bus.query(
    query_type="get_user_profile",
    data={"user_id": "123"},
    target_service="user_service",
    timeout=timedelta(seconds=10)
)
```

### Stream Processing

```python
async def process_analytics_batch(events):
    # Process batch of events
    for event in events:
        # Perform analytics processing
        pass
    return True

# Process event stream
subscription_id = await event_bus.process_stream(
    stream_name="analytics_events",
    processor=process_analytics_batch,
    consumer_group="analytics_processor",
    batch_size=100
)
```

## Pattern Selection Guide

### When to Use Each Pattern

#### Publish/Subscribe

- **Use when**: Multiple services need to react to the same event
- **Examples**: User registration, order status changes, system notifications
- **Backends**: NATS, AWS SNS, RabbitMQ

#### Request/Response

- **Use when**: You need immediate response from another service
- **Examples**: User authentication, payment authorization, data validation
- **Backends**: NATS, RabbitMQ

#### Stream Processing

- **Use when**: Processing continuous data flows with ordering requirements
- **Examples**: Real-time analytics, log processing, financial transactions
- **Backends**: Kafka, NATS JetStream

#### Point-to-Point

- **Use when**: Task processing with guaranteed delivery to single consumer
- **Examples**: Background jobs, email sending, report generation
- **Backends**: AWS SQS, RabbitMQ

### Backend Selection Matrix

| Use Case | Scale | Recommended Backend | Pattern |
|----------|-------|-------------------|---------|
| Real-time notifications | High | NATS | Pub/Sub |
| Task queues | Medium | RabbitMQ | Point-to-Point |
| Analytics processing | High | Kafka | Stream Processing |
| Microservice communication | Medium | NATS | Request/Response |
| Cloud-native pub/sub | Any | AWS SNS | Pub/Sub |
| Financial transactions | High | Kafka + NATS | Stream + Request/Response |

## Complete Examples

See the individual example files for complete implementations:

- [`nats_example.py`](./nats_example.py) - Complete NATS implementation
- [`aws_sns_example.py`](./aws_sns_example.py) - AWS SNS setup and usage
- [`saga_example.py`](./saga_example.py) - Distributed saga implementation
- [`ecommerce_example.py`](./ecommerce_example.py) - Real-world e-commerce workflow
- [`pattern_comparison.py`](./pattern_comparison.py) - Side-by-side pattern comparison

## Best Practices

1. **Choose the Right Pattern**: Match messaging patterns to your use case
2. **Handle Failures Gracefully**: Implement proper error handling and retries
3. **Monitor Your Messages**: Use correlation IDs and structured logging
4. **Test with Different Backends**: Validate your code works with multiple backends
5. **Use Saga for Complex Workflows**: Coordinate distributed transactions properly
6. **Consider Message Ordering**: Use appropriate backends when ordering matters
7. **Plan for Scale**: Choose backends that can handle your expected load
