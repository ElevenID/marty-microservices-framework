# Extended Messaging System

This module provides extended messaging capabilities for the Marty Microservices Framework, including unified event bus support, multiple backend implementations, and enhanced Saga integration.

## Features

### 🔄 Unified Event Bus

- Single API for all messaging patterns
- Automatic backend selection based on message type
- Pattern-specific optimizations
- Cross-backend compatibility

### 🚀 Multiple Backend Support

- **NATS**: High-performance, low-latency messaging with JetStream
- **AWS SNS**: Cloud-native pub/sub with FIFO support
- **Kafka**: High-throughput event streaming (existing)
- **RabbitMQ**: Reliable message queuing (existing)
- **Redis**: Fast in-memory messaging (existing)

### 🎯 Messaging Patterns

- **Pub/Sub**: Event broadcasting and subscription
- **Point-to-Point**: Direct service-to-service messaging
- **Request/Response**: Query/reply patterns with timeouts
- **Streaming**: High-throughput data processing

### 🔧 Enhanced Saga Integration

- Distributed saga orchestration
- Automatic compensation handling
- Cross-service transaction coordination
- Failure recovery mechanisms

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Unified Event Bus                        │
├─────────────────────────────────────────────────────────────┤
│  Pattern Selection │ Backend Registry │ Message Routing     │
├─────────────────────────────────────────────────────────────┤
│  NATS Backend  │ AWS SNS Backend │ Kafka │ RabbitMQ │ Redis │
└─────────────────────────────────────────────────────────────┘
```

## Components

### Core Architecture (`extended_architecture.py`)

- `MessageBackendType`: Enum of supported backends
- `MessagingPattern`: Enum of messaging patterns
- `UnifiedEventBus`: Main interface for messaging
- `PatternSelector`: Smart pattern selection logic

### Backend Implementations

- `NATSBackend`: NATS with JetStream support
- `AWSSNSBackend`: AWS SNS with FIFO topics

### Unified Event Bus (`unified_event_bus.py`)

- `UnifiedEventBusImpl`: Main implementation
- `create_unified_event_bus()`: Factory function

### Saga Integration (`saga_integration.py`)

- `EnhancedSagaOrchestrator`: Enhanced saga coordination
- `DistributedSagaManager`: Cross-service saga management

## Usage Examples

### Basic Usage

```python
from marty_msf.framework.messaging.extended import (
    create_unified_event_bus,
    NATSBackend,
    NATSConfig,
    MessageBackendType
)

# Create and configure event bus
event_bus = create_unified_event_bus()

# Add NATS backend
nats_config = NATSConfig(servers=["nats://localhost:4222"])
nats_backend = NATSBackend(nats_config)
event_bus.register_backend(MessageBackendType.NATS, nats_backend)

await event_bus.start()

# Publish event
await event_bus.publish_event(
    event_type="user_registered",
    data={"user_id": "123", "email": "user@example.com"}
)

# Send command
await event_bus.send_command(
    command_type="process_payment",
    data={"order_id": "456", "amount": 99.99},
    target_service="payment_service"
)

await event_bus.stop()
```

### Enhanced Saga Example

```python
from marty_msf.framework.messaging.extended import create_distributed_saga_manager

# Create saga manager
saga_manager = create_distributed_saga_manager(event_bus)

# Start distributed saga
saga_id = await saga_manager.create_and_start_saga(
    "order_processing",
    {"order_id": "123", "customer_id": "456"}
)
```

## Configuration

### NATS Configuration

```python
nats_config = NATSConfig(
    servers=["nats://localhost:4222"],
    jetstream_enabled=True,
    stream_config={
        "max_msgs": 10000,
        "max_bytes": 1024 * 1024,
        "retention": "workqueue"
    }
)
```

### AWS SNS Configuration

```python
sns_config = AWSSNSConfig(
    region_name="us-east-1",
    fifo_topics=True,
    credentials={
        "aws_access_key_id": "your_access_key",
        "aws_secret_access_key": "your_secret_key"
    }
)
```

## Dependencies

### Required

- `asyncio`: Async/await support
- `typing`: Type annotations
- `abc`: Abstract base classes

### Optional (Backend-specific)

- `nats-py`: For NATS backend
- `boto3`: For AWS SNS backend
- `aiokafka`: For Kafka backend (existing)
- `aio-pika`: For RabbitMQ backend (existing)
- `aioredis`: For Redis backend (existing)

## Installation

Install optional dependencies based on backends you plan to use:

```bash
# For NATS support
pip install nats-py

# For AWS SNS support
pip install boto3

# For all messaging backends
pip install nats-py boto3 aiokafka aio-pika aioredis
```

## Testing

Run the examples:

```bash
python -m marty_msf.framework.messaging.extended.examples
```

## Integration with Existing Framework

The extended messaging system is designed to:

- Work alongside existing messaging infrastructure
- Provide backward compatibility
- Enable gradual migration to unified patterns
- Support mixed messaging architectures

## Backend Selection Guidelines

### NATS

- **Best for**: Low-latency, high-performance messaging
- **Use cases**: Real-time notifications, microservice coordination
- **Patterns**: All patterns with JetStream support

### AWS SNS

- **Best for**: Cloud-native, scalable pub/sub
- **Use cases**: Event broadcasting, fan-out messaging
- **Patterns**: Pub/Sub primarily, Point-to-Point with SQS

### Kafka (Existing)

- **Best for**: High-throughput event streaming
- **Use cases**: Event sourcing, log aggregation
- **Patterns**: Streaming, Pub/Sub

### RabbitMQ (Existing)

- **Best for**: Reliable message queuing
- **Use cases**: Work distribution, guaranteed delivery
- **Patterns**: Point-to-Point, Request/Response

### Redis (Existing)

- **Best for**: Fast in-memory messaging
- **Use cases**: Caching, session state, real-time features
- **Patterns**: Pub/Sub, Point-to-Point

## Future Enhancements

- [ ] Additional backends (Apache Pulsar, Azure Service Bus)
- [ ] Advanced routing and filtering
- [ ] Message transformation pipelines
- [ ] Circuit breaker patterns
- [ ] Observability and metrics
- [ ] Schema registry integration
- [ ] Dead letter queue enhancements
