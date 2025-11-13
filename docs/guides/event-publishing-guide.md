# Unified Event Publishing Guide

This guide covers the unified event publishing system in the Marty Microservices Framework, which provides consistent patterns for audit events, notifications, and domain events.

## Overview

The unified event publishing system eliminates the need for each service to implement custom Kafka event publishing logic. It provides:

- **EventPublisher**: Unified interface for all event types
- **Decorators**: Automatic event publishing on method execution
- **Outbox Pattern**: Transactional consistency for event publishing
- **Standard Event Types**: Pre-defined audit and notification event types
- **Configuration Management**: Environment-based configuration

## Quick Start

### Basic Setup

```python
from framework.events import EventPublisher, EventConfig, get_event_publisher

# Option 1: Use environment-based configuration
publisher = get_event_publisher()

# Option 2: Use explicit configuration
config = EventConfig(
    kafka_brokers=["localhost:9092"],
    service_name="user-service",
    topic_prefix="marty"
)
publisher = EventPublisher(config)

# Start the publisher
await publisher.start()
```

### Publishing Audit Events

```python
from framework.events import AuditEventType

# Publish an audit event
await publisher.publish_audit_event(
    event_type=AuditEventType.DATA_CREATED,
    action="create_user",
    resource_type="user",
    resource_id="user-123",
    operation_details={
        "user_data": {"email": "user@example.com", "role": "customer"}
    }
)
```

### Publishing Notification Events

```python
from framework.events import NotificationEventType

# Publish a notification event
await publisher.publish_notification_event(
    event_type=NotificationEventType.USER_WELCOME,
    recipient_type="user",
    recipient_ids=["user-123"],
    subject="Welcome to Marty!",
    message="Your account has been created successfully."
)
```

### Publishing Domain Events

```python
# Publish a domain event
await publisher.publish_domain_event(
    aggregate_type="user",
    aggregate_id="user-123",
    event_type="user_created",
    event_data={
        "email": "user@example.com",
        "role": "customer",
        "created_at": "2024-01-01T00:00:00Z"
    }
)
```

## Using Decorators

Decorators provide automatic event publishing based on method execution:

### Audit Event Decorator

```python
from framework.events import audit_event, AuditEventType

class UserService:
    @audit_event(
        event_type=AuditEventType.DATA_CREATED,
        action="create_user",
        resource_type="user",
        resource_id_field="user_id",
        include_args=True
    )
    async def create_user(self, user_id: str, user_data: dict) -> User:
        # Method implementation
        user = User(**user_data)
        await self.repository.save(user)
        return user
```

### Domain Event Decorator

```python
from framework.events import domain_event

class UserService:
    @domain_event(
        aggregate_type="user",
        event_type="user_updated",
        aggregate_id_field="user_id"
    )
    async def update_user(self, user_id: str, updates: dict) -> User:
        # Method implementation
        user = await self.repository.get(user_id)
        user.update(updates)
        await self.repository.save(user)
        return user
```

### Success/Error Event Decorators

```python
from framework.events import publish_on_success, publish_on_error

class AuthService:
    @publish_on_success(
        topic="auth.events",
        event_type="login_successful",
        key_field="user_id"
    )
    @publish_on_error(
        topic="auth.events",
        event_type="login_failed",
        key_field="user_id"
    )
    async def authenticate(self, user_id: str, password: str) -> bool:
        # Authentication logic
        return self.verify_password(user_id, password)
```

## Configuration

### Environment Variables

The system supports configuration via environment variables:

```bash
# Kafka Configuration
KAFKA_BROKERS=localhost:9092,localhost:9093
KAFKA_SECURITY_PROTOCOL=PLAINTEXT
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=user
KAFKA_SASL_PASSWORD=pass

# Event Configuration
EVENT_TOPIC_PREFIX=marty
SERVICE_NAME=user-service
SERVICE_VERSION=1.0.0
USE_OUTBOX_PATTERN=true
ENABLE_EVENT_TRACING=true
ENABLE_EVENT_METRICS=true
```

### Configuration Classes

```python
from framework.events import EventConfig, EventPublisherConfig

# Dataclass-based configuration
config = EventConfig(
    kafka_brokers=["localhost:9092"],
    service_name="user-service",
    topic_prefix="marty",
    use_outbox_pattern=True,
    audit_topic="audit.events",
    notification_topic="notification.events"
)

# Pydantic-based configuration (with validation)
config = EventPublisherConfig(
    kafka_brokers=["localhost:9092"],
    service_name="user-service",
    topic_prefix="marty"
)
```

## Outbox Pattern

The outbox pattern ensures transactional consistency between database operations and event publishing:

### Setup Database Table

```sql
CREATE TABLE event_outbox (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL UNIQUE,
    topic VARCHAR(255) NOT NULL,
    payload BYTEA NOT NULL,
    key BYTEA,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3
);
```

### Using with Database Session

```python
from framework.events import get_event_publisher
from framework.database import execute_in_transaction

async def create_user_with_events(user_data: dict):
    async def transaction_handler(session):
        # Create user in database
        user = User(**user_data)
        session.add(user)

        # Get publisher with database session for outbox pattern
        publisher = get_event_publisher(database_session=session)

        # Publish events - will be stored in outbox table
        await publisher.publish_audit_event(
            event_type=AuditEventType.DATA_CREATED,
            action="create_user",
            resource_type="user",
            resource_id=user.id
        )

        await publisher.publish_domain_event(
            aggregate_type="user",
            aggregate_id=user.id,
            event_type="user_created",
            event_data=user_data
        )

    await execute_in_transaction(transaction_handler)
```

### Background Event Processor

Implement a background process to publish events from the outbox:

```python
import asyncio
from framework.events import get_event_publisher
from framework.database import OutboxRepository

async def process_outbox_events():
    """Background task to process outbox events."""
    publisher = get_event_publisher()
    await publisher.start()

    while True:
        try:
            # Get pending events from outbox
            async with get_database_session() as session:
                outbox_repo = OutboxRepository(session)
                pending_events = outbox_repo.get_pending_events(limit=100)

                for event in pending_events:
                    try:
                        # Publish event directly to Kafka
                        await publisher._publish_direct(
                            topic=event.topic,
                            event_envelope=json.loads(event.payload),
                            key=event.key.decode('utf-8') if event.key else None,
                            event_id=event.event_id
                        )

                        # Mark as processed
                        outbox_repo.mark_processed(event.event_id)

                    except Exception as e:
                        # Mark as failed
                        outbox_repo.mark_failed(event.event_id, str(e))

        except Exception as e:
            logger.error(f"Error processing outbox events: {e}")

        # Wait before next batch
        await asyncio.sleep(30)

# Start background task
asyncio.create_task(process_outbox_events())
```

## Event Types Reference

### Audit Event Types

```python
from framework.events import AuditEventType

# Authentication & Authorization
AuditEventType.USER_LOGIN
AuditEventType.USER_LOGOUT
AuditEventType.PERMISSION_DENIED

# Data Operations
AuditEventType.DATA_CREATED
AuditEventType.DATA_UPDATED
AuditEventType.DATA_DELETED
AuditEventType.DATA_ACCESSED

# Security Events
AuditEventType.CERTIFICATE_ISSUED
AuditEventType.CERTIFICATE_REVOKED
AuditEventType.SECURITY_VIOLATION

# System Events
AuditEventType.SERVICE_STARTED
AuditEventType.SERVICE_ERROR
AuditEventType.CONFIGURATION_CHANGED
```

### Notification Event Types

```python
from framework.events import NotificationEventType

# User Notifications
NotificationEventType.USER_WELCOME
NotificationEventType.USER_PASSWORD_RESET
NotificationEventType.USER_ACCOUNT_LOCKED

# Certificate Notifications
NotificationEventType.CERTIFICATE_EXPIRING
NotificationEventType.CERTIFICATE_EXPIRED

# System Notifications
NotificationEventType.SYSTEM_MAINTENANCE
NotificationEventType.SYSTEM_ALERT
```

## Topic Naming Conventions

The system follows consistent topic naming patterns:

### Audit Events

- Topic: `{prefix}.audit.events`
- Example: `marty.audit.events`

### Notification Events

- Topic: `{prefix}.notification.events`
- Example: `marty.notification.events`

### Domain Events

- Pattern: `{prefix}.{service}.{aggregate}.{event_type}`
- Example: `marty.user-service.user.user_created`

### Custom Events

- Pattern: `{prefix}.{topic}`
- Example: `marty.integration.events`

## Best Practices

### 1. Use Appropriate Event Types

- **Audit Events**: For compliance, security monitoring, and debugging
- **Notification Events**: For user communications and alerts
- **Domain Events**: For business logic and inter-service communication

### 2. Include Correlation IDs

```python
from framework.events import EventMetadata

metadata = EventMetadata(
    service_name="user-service",
    correlation_id=request.headers.get("X-Correlation-ID"),
    user_id=current_user.id,
    trace_id=trace.get_current_span().get_span_context().trace_id
)

await publisher.publish_audit_event(
    event_type=AuditEventType.DATA_CREATED,
    action="create_user",
    resource_type="user",
    metadata=metadata
)
```

### 3. Handle Sensitive Data

```python
# Don't include passwords or sensitive data in events
await publisher.publish_audit_event(
    event_type=AuditEventType.DATA_CREATED,
    action="create_user",
    resource_type="user",
    resource_id=user.id,
    operation_details={
        "email": user.email,
        "role": user.role,
        # Don't include: password, ssn, credit_card, etc.
    }
)
```

### 4. Use Outbox Pattern for Critical Events

For events that must be published reliably (audit events, critical notifications):

```python
# Configure publisher with outbox pattern
config = EventConfig(use_outbox_pattern=True)
publisher = EventPublisher(config, database_session=session)
```

### 5. Monitor Event Publishing

```python
import logging

# Enable detailed logging
logging.getLogger("framework.events").setLevel(logging.DEBUG)

# Use metrics collection
config = EventConfig(enable_metrics=True, enable_tracing=True)
```

## Migration from Existing Event Code

### Replace Custom Outbox Logic

**Before:**

```python
async def _publish_event(self, topic: str, payload: dict, session=None):
    serialized = json.dumps(payload).encode("utf-8")

    async def handler(db_session):
        outbox = OutboxRepository(db_session)
        await outbox.enqueue(topic=topic, payload=serialized)

    if session is None:
        await self._database.run_within_transaction(handler)
    else:
        await handler(session)
```

**After:**

```python
from framework.events import get_event_publisher

async def publish_event(self, event_type: str, data: dict, session=None):
    publisher = get_event_publisher(database_session=session)
    await publisher.publish_domain_event(
        aggregate_type="my_aggregate",
        aggregate_id=data.get("id"),
        event_type=event_type,
        event_data=data
    )
```

### Replace Direct Kafka Publishing

**Before:**

```python
await self.event_bus.publish("cmc.created", {
    "cmc_id": cmc_id,
    "document_number": request.document_number,
    "created_at": cmc_certificate.created_at.isoformat(),
})
```

**After:**

```python
from framework.events import get_event_publisher

publisher = get_event_publisher()
await publisher.publish_domain_event(
    aggregate_type="cmc",
    aggregate_id=cmc_id,
    event_type="cmc_created",
    event_data={
        "document_number": request.document_number,
        "created_at": cmc_certificate.created_at.isoformat(),
    }
)
```

### Replace Base Service Event Publishing

**Before:**

```python
await self.publish_event(
    topic="user.events",
    payload={"user_id": user_id, "action": "created"},
    key=user_id
)
```

**After:**

```python
from framework.events import get_event_publisher

publisher = get_event_publisher()
await publisher.publish_domain_event(
    aggregate_type="user",
    aggregate_id=user_id,
    event_type="user_created",
    event_data={"action": "created"}
)
```

## Testing

### Mock Event Publisher

```python
import pytest
from unittest.mock import AsyncMock
from framework.events import EventPublisher

@pytest.fixture
def mock_event_publisher():
    publisher = AsyncMock(spec=EventPublisher)
    return publisher

async def test_user_creation_publishes_event(mock_event_publisher):
    # Test that user creation publishes the correct event
    service = UserService(event_publisher=mock_event_publisher)

    await service.create_user("user-123", {"email": "test@example.com"})

    mock_event_publisher.publish_domain_event.assert_called_once_with(
        aggregate_type="user",
        aggregate_id="user-123",
        event_type="user_created",
        event_data={"email": "test@example.com"}
    )
```

### Integration Testing

```python
import pytest
from framework.events import EventConfig, EventPublisher

@pytest.fixture
async def test_event_publisher():
    config = EventConfig(
        kafka_brokers=["localhost:9092"],
        service_name="test-service",
        use_outbox_pattern=False  # Direct publishing for tests
    )
    publisher = EventPublisher(config)
    await publisher.start()
    yield publisher
    await publisher.stop()

async def test_event_publishing_integration(test_event_publisher):
    # Test actual event publishing to Kafka
    event_id = await test_event_publisher.publish_domain_event(
        aggregate_type="test",
        aggregate_id="test-123",
        event_type="test_event",
        event_data={"test": True}
    )

    assert event_id is not None
```

This unified event publishing system provides a consistent, reliable way to publish events across all Marty microservices while eliminating code duplication and ensuring best practices.
