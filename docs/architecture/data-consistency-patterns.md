# Data Consistency Patterns Documentation

This document provides comprehensive guidance on implementing data consistency patterns in the Marty Microservices Framework (MMF). These patterns ensure reliable, consistent, and scalable distributed systems.

## Table of Contents

1. [Overview](#overview)
2. [Saga Orchestration Pattern](#saga-orchestration-pattern)
3. [Transactional Outbox Pattern](#transactional-outbox-pattern)
4. [CQRS (Command Query Responsibility Segregation)](#cqrs-command-query-responsibility-segregation)
5. [Event Sourcing Integration](#event-sourcing-integration)
6. [Configuration Management](#configuration-management)
7. [Best Practices](#best-practices)
8. [Common Patterns and Anti-Patterns](#common-patterns-and-anti-patterns)
9. [Performance Considerations](#performance-considerations)
10. [Troubleshooting](#troubleshooting)

## Overview

The MMF data consistency patterns provide a comprehensive solution for managing distributed transactions, event-driven architectures, and read/write model separation. These patterns work together to ensure:

- **Data Consistency**: Maintain data integrity across distributed services
- **Reliability**: Handle failures gracefully with compensation mechanisms
- **Scalability**: Support high-throughput event processing
- **Observability**: Comprehensive monitoring and debugging capabilities

### Key Patterns Included

1. **Saga Orchestration**: Coordinates long-running transactions across services
2. **Transactional Outbox**: Ensures reliable event publishing with ACID guarantees
3. **CQRS**: Separates read and write operations for optimal performance
4. **Event Sourcing**: Stores state changes as a sequence of events

## Saga Orchestration Pattern

The Saga pattern manages distributed transactions by breaking them into a series of local transactions, each with a corresponding compensation action.

### Core Components

#### SagaOrchestrator

```python
from marty_msf.patterns.saga import SagaOrchestrator

# Initialize the orchestrator
orchestrator = SagaOrchestrator("order-processing")
await orchestrator.start(worker_count=3)

# Define saga steps
steps = [
    {
        "step_name": "reserve_inventory",
        "service_name": "inventory_service",
        "action": "reserve",
        "compensation_action": "release_reservation",
        "data": {"product_id": "123", "quantity": 2}
    },
    {
        "step_name": "process_payment",
        "service_name": "payment_service",
        "action": "charge",
        "compensation_action": "refund",
        "data": {"amount": 5000, "payment_method": "credit_card"}
    }
]

# Start saga execution
saga_id = await orchestrator.start_saga(
    saga_type="order_processing",
    steps=steps,
    context={"order_id": "order_123"}
)
```

#### Compensation Handlers

```python
# Register step handlers
async def reserve_inventory_handler(context):
    # Implement inventory reservation logic
    return {"reserved": True, "reservation_id": "res_456"}

async def compensate_inventory_handler(context):
    # Implement inventory release logic
    reservation_id = context.get("reservation_id")
    await inventory_service.release_reservation(reservation_id)
    return {"released": True}

orchestrator.register_step_handler("reserve_inventory", reserve_inventory_handler)
orchestrator.register_compensation_handler("reserve_inventory", compensate_inventory_handler)
```

### Advanced Features

#### Parallel Execution

```python
# Execute steps in parallel where possible
parallel_steps = [
    {
        "step_name": "validate_customer",
        "parallel_group": "validation",
        "service_name": "customer_service",
        # ... other properties
    },
    {
        "step_name": "validate_inventory",
        "parallel_group": "validation",
        "service_name": "inventory_service",
        # ... other properties
    }
]
```

#### Conditional Steps

```python
# Steps with conditions
conditional_step = {
    "step_name": "apply_discount",
    "condition": "customer.is_premium",
    "service_name": "discount_service",
    # ... other properties
}
```

## Transactional Outbox Pattern

The Outbox pattern ensures reliable event publishing by storing events in the same database transaction as the business data.

### Core Components

#### Enhanced Outbox Repository

```python
from marty_msf.patterns.outbox import EnhancedOutboxRepository, OutboxConfig

# Configure outbox
config = OutboxConfig(
    batch_size=100,
    polling_interval_ms=1000,
    max_retry_attempts=5,
    dead_letter_threshold=10
)

# Initialize repository
outbox_repo = EnhancedOutboxRepository(db_session, config)

# Enqueue events within a transaction
async with db_session.begin():
    # Save business data
    await save_order(order)

    # Enqueue domain event
    await outbox_repo.enqueue_event(
        topic="order.events",
        event_type="order_created",
        payload={
            "order_id": order.id,
            "customer_id": order.customer_id,
            "total_amount": order.total_amount
        },
        aggregate_id=order.id,
        aggregate_type="order"
    )
```

#### Message Broker Integration

```python
from marty_msf.patterns.outbox import EnhancedOutboxProcessor, create_kafka_message_broker

# Create message broker
broker = create_kafka_message_broker({
    "bootstrap_servers": "localhost:9092",
    "client_id": "order-service",
    "enable_idempotence": True
})

# Initialize processor
processor = EnhancedOutboxProcessor(
    repository=outbox_repo,
    message_broker=broker,
    config=config
)

# Start processing
await processor.start()
```

### Advanced Features

#### Batch Processing

```python
# Process events in batches for better performance
config = OutboxConfig(
    batch_size=500,
    batch_timeout_ms=5000,
    enable_batch_optimization=True
)
```

#### Dead Letter Queue

```python
# Configure dead letter handling
config = OutboxConfig(
    dead_letter_threshold=5,
    dead_letter_topic="order.events.dlq",
    enable_dead_letter_analysis=True
)
```

#### Event Prioritization

```python
# Enqueue high-priority events
await outbox_repo.enqueue_event(
    topic="order.events",
    event_type="payment_failed",
    payload=payment_data,
    priority=EventPriority.HIGH,
    max_delivery_attempts=10
)
```

## CQRS (Command Query Responsibility Segregation)

CQRS separates read and write operations, allowing for optimized data models and improved performance.

### Core Components

#### Commands and Queries

```python
from marty_msf.patterns.cqrs import BaseCommand, BaseQuery, CommandHandler, QueryHandler

@dataclass
class CreateOrderCommand(BaseCommand):
    customer_id: str
    items: list[dict]

    def validate(self):
        errors = []
        if not self.customer_id:
            errors.append("Customer ID is required")
        if not self.items:
            errors.append("Order must have items")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

@dataclass
class GetOrderQuery(BaseQuery):
    order_id: str

    def validate(self):
        errors = []
        if not self.order_id:
            errors.append("Order ID is required")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
```

#### Command Handlers

```python
class CreateOrderCommandHandler(CommandHandler[CreateOrderCommand]):
    def __init__(self, order_repository, event_bus=None):
        super().__init__(event_bus=event_bus)
        self.order_repository = order_repository

    async def _execute(self, command: CreateOrderCommand):
        # Validate business rules
        validation_result = await self._validate_business_rules(command)
        if not validation_result.is_valid:
            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.FAILED,
                errors=validation_result.errors
            )

        # Create and save order
        order = Order(
            id=str(uuid.uuid4()),
            customer_id=command.customer_id,
            items=command.items
        )
        await self.order_repository.save(order)

        # Generate events
        events = [f"order_created_{order.id}"]

        return CommandResult(
            command_id=command.command_id,
            status=CommandStatus.COMPLETED,
            result_data={"order_id": order.id},
            events_generated=events
        )
```

#### Query Handlers with Caching

```python
class GetOrderQueryHandler(QueryHandler[GetOrderQuery, dict]):
    def __init__(self, read_store, cache=None):
        super().__init__(read_store=read_store, cache=cache)

    async def _execute(self, query: GetOrderQuery) -> dict:
        # Try cache first
        cache_key = f"order:{query.order_id}"
        cached_result = await self.cache.get(cache_key) if self.cache else None

        if cached_result:
            return cached_result

        # Query read model
        order_data = await self.read_store.get_order(query.order_id)

        # Cache result
        if self.cache and order_data:
            await self.cache.set(cache_key, order_data, ttl=300)

        return order_data
```

### Read Model Management

#### Projections

```python
from marty_msf.patterns.cqrs import EventProjection, ProjectionBuilder

class OrderProjection(EventProjection):
    def __init__(self, read_store):
        self.read_store = read_store

    async def handle_order_created(self, event_data: dict):
        order_view = {
            "order_id": event_data["order_id"],
            "customer_id": event_data["customer_id"],
            "total_amount": event_data["total_amount"],
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await self.read_store.save_order_view(order_view)

    async def handle_payment_processed(self, event_data: dict):
        await self.read_store.update_order_status(
            event_data["order_id"],
            "paid"
        )
```

#### Projection Builder

```python
# Build projections from event stream
builder = ProjectionBuilder(event_store, [OrderProjection(read_store)])

# Rebuild from specific point
await builder.rebuild_from_sequence(1000)

# Real-time projection updates
await builder.start_real_time_processing()
```

## Event Sourcing Integration

Event sourcing stores all changes as a sequence of events, enabling temporal queries and audit trails.

### Event Store Integration

```python
from marty_msf.patterns.event_sourcing import EventStore, AggregateRoot

class Order(AggregateRoot):
    def __init__(self, order_id: str):
        super().__init__(order_id)
        self.customer_id = None
        self.items = []
        self.status = "pending"

    def create_order(self, customer_id: str, items: list):
        if self.status != "pending":
            raise BusinessRuleViolation("Order already created")

        event = OrderCreatedEvent(
            aggregate_id=self.id,
            customer_id=customer_id,
            items=items
        )
        self.apply_event(event)

    def _apply_order_created(self, event: OrderCreatedEvent):
        self.customer_id = event.customer_id
        self.items = event.items
        self.status = "created"

# Save aggregate
event_store = EventStore(db_session)
order = Order("order_123")
order.create_order("customer_456", items)
await event_store.save_aggregate(order)

# Load aggregate
loaded_order = await event_store.load_aggregate(Order, "order_123")
```

### Snapshots

```python
# Configure snapshots for large aggregates
class OrderSnapshot:
    def __init__(self, order: Order, sequence_number: int):
        self.order_id = order.id
        self.customer_id = order.customer_id
        self.items = order.items
        self.status = order.status
        self.sequence_number = sequence_number

# Save snapshot every 100 events
if order.version % 100 == 0:
    snapshot = OrderSnapshot(order, order.version)
    await event_store.save_snapshot(snapshot)
```

## Configuration Management

### Environment-Specific Configuration

```python
from marty_msf.patterns.config import DataConsistencyConfig, create_production_config

# Production configuration
config = create_production_config()

# Custom configuration
config = DataConsistencyConfig(
    environment="production",
    database=DatabaseConfig(
        connection_string="postgresql://prod-db:5432/orders",
        pool_size=20,
        max_overflow=50
    ),
    saga=SagaConfig(
        orchestrator_name="prod-orchestrator",
        worker_count=10,
        retry_attempts=5,
        timeout_seconds=300
    ),
    outbox=OutboxConfig(
        batch_size=500,
        polling_interval_ms=500,
        max_retry_attempts=10,
        dead_letter_threshold=5
    ),
    cqrs=CQRSConfig(
        enable_caching=True,
        cache_ttl_seconds=600,
        enable_read_model_validation=True,
        read_model_consistency_check_interval=3600
    )
)
```

### Dynamic Configuration

```python
# Runtime configuration updates
await config.update_saga_config(worker_count=15)
await config.update_outbox_config(batch_size=1000)
```

## Best Practices

### 1. Saga Design Principles

- **Keep sagas short**: Minimize the number of steps and duration
- **Design for idempotency**: Ensure steps can be safely retried
- **Use semantic locks**: Prevent concurrent modifications to the same resource
- **Monitor saga progress**: Implement comprehensive logging and metrics

```python
# Good: Short saga with clear compensation
saga_steps = [
    {"step": "reserve_inventory", "compensation": "release_inventory"},
    {"step": "charge_payment", "compensation": "refund_payment"}
]

# Avoid: Long-running sagas with many dependencies
```

### 2. Outbox Pattern Guidelines

- **Use transactions**: Always enqueue events within the same transaction as business data
- **Handle duplicates**: Design consumers to be idempotent
- **Monitor processing lag**: Track the difference between event creation and processing
- **Clean up processed events**: Implement archival or deletion strategies

```python
# Good: Transactional event enqueueing
async with db_session.begin():
    await save_business_data(data)
    await outbox_repo.enqueue_event(event_data)

# Avoid: Enqueueing events outside transactions
```

### 3. CQRS Implementation

- **Separate models**: Use different models for reads and writes
- **Eventual consistency**: Accept that read models may be slightly behind
- **Optimize read models**: Design read models for specific query patterns
- **Version read models**: Support schema evolution

```python
# Good: Specialized read model
class CustomerOrderSummary:
    customer_id: str
    total_orders: int
    total_spent: int
    favorite_category: str

# Avoid: Reusing write models for reads
```

### 4. Event Sourcing Best Practices

- **Design immutable events**: Never change event structure after deployment
- **Use event versioning**: Support schema evolution with versioned events
- **Implement snapshots**: Optimize aggregate loading for large event streams
- **Handle event ordering**: Ensure events are processed in the correct order

```python
# Good: Versioned event
@dataclass
class OrderCreatedEventV2:
    version: int = 2
    aggregate_id: str
    customer_id: str
    items: list[dict]
    created_at: datetime
    # New field with default
    currency: str = "USD"

# Good: Event upcasting
def upcast_order_created_v1_to_v2(event_v1):
    return OrderCreatedEventV2(**event_v1.__dict__, currency="USD")
```

## Common Patterns and Anti-Patterns

### Patterns ✅

#### 1. Saga Choreography for Simple Flows

```python
# Use event-driven choreography for simple, linear flows
class OrderService:
    async def handle_order_created(self, event):
        # Publish event for next service
        await self.event_bus.publish("order.inventory.check", event.data)

class InventoryService:
    async def handle_inventory_check(self, event):
        # Process and publish next event
        await self.event_bus.publish("order.payment.process", event.data)
```

#### 2. Outbox with Event Sourcing

```python
# Combine outbox pattern with event sourcing
async def save_aggregate_with_outbox(aggregate, outbox_events):
    async with db_session.begin():
        # Save aggregate events
        await event_store.save_aggregate(aggregate)

        # Enqueue outbox events
        for event in outbox_events:
            await outbox_repo.enqueue_event(**event)
```

#### 3. CQRS with Event Projections

```python
# Build read models from domain events
class OrderProjectionHandler:
    async def handle_domain_event(self, event):
        if event.type == "OrderCreated":
            await self.create_order_view(event)
        elif event.type == "PaymentProcessed":
            await self.update_order_payment_status(event)
```

### Anti-Patterns ❌

#### 1. Distributed Transactions (2PC)

```python
# Avoid: Two-Phase Commit across services
# async def transfer_money_2pc(from_account, to_account, amount):
#     transaction = DistributedTransaction()
#     try:
#         transaction.begin()
#         await account_service_1.prepare_debit(from_account, amount)
#         await account_service_2.prepare_credit(to_account, amount)
#         transaction.commit()
#     except:
#         transaction.rollback()

# Better: Use saga pattern
async def transfer_money_saga(from_account, to_account, amount):
    steps = [
        {"step": "debit_account", "account": from_account, "amount": amount},
        {"step": "credit_account", "account": to_account, "amount": amount}
    ]
    await saga_orchestrator.start_saga("money_transfer", steps)
```

#### 2. Synchronous Read-after-Write

```python
# Avoid: Immediately reading from read model after write
# async def create_order_and_return(command):
#     result = await command_handler.handle(command)
#     return await query_handler.handle(GetOrderQuery(result.order_id))

# Better: Return command result directly
async def create_order_and_return(command):
    result = await command_handler.handle(command)
    return result.result_data
```

#### 3. Large Event Payloads

```python
# Avoid: Including large data in events
# class OrderCreatedEvent:
#     order_id: str
#     customer_full_data: dict  # Large customer object
#     inventory_full_data: dict  # Large inventory data

# Better: Include only necessary identifiers
class OrderCreatedEvent:
    order_id: str
    customer_id: str
    product_ids: list[str]
```

## Performance Considerations

### 1. Saga Performance

#### Optimize Step Execution

```python
# Use parallel execution where possible
parallel_config = {
    "max_parallel_steps": 5,
    "timeout_per_step": 30,
    "enable_step_caching": True
}

# Implement step result caching
@cached_saga_step(ttl=300)
async def validate_customer_step(context):
    return await customer_service.validate(context["customer_id"])
```

#### Monitor Saga Metrics

```python
# Track saga performance
saga_metrics = {
    "total_sagas": 1000,
    "completed_sagas": 950,
    "failed_sagas": 30,
    "compensated_sagas": 20,
    "average_duration_ms": 1500,
    "p95_duration_ms": 3000
}
```

### 2. Outbox Performance

#### Batch Processing Optimization

```python
# Configure optimal batch sizes
config = OutboxConfig(
    batch_size=1000,          # Process 1000 events at once
    batch_timeout_ms=5000,    # Max wait time for batch
    prefetch_count=5000,      # Prefetch events for processing
    parallel_processors=4     # Run 4 processors in parallel
)
```

#### Connection Pooling

```python
# Use connection pooling for message brokers
kafka_config = {
    "bootstrap_servers": "kafka:9092",
    "connections_max_idle_ms": 540000,
    "max_in_flight_requests_per_connection": 5,
    "batch_size": 16384,
    "linger_ms": 100
}
```

### 3. CQRS Performance

#### Read Model Optimization

```python
# Use appropriate indexes for read models
class OrderReadModel:
    # Index on frequently queried fields
    customer_id: str  # Index: customer_orders_idx
    status: str       # Index: status_orders_idx
    created_at: datetime  # Index: created_date_idx

    # Composite index for complex queries
    # Index: customer_status_date_idx (customer_id, status, created_at)
```

#### Caching Strategy

```python
# Multi-level caching
cache_config = {
    "l1_cache": {  # In-memory cache
        "type": "redis",
        "ttl": 300,
        "max_entries": 10000
    },
    "l2_cache": {  # Distributed cache
        "type": "redis_cluster",
        "ttl": 3600,
        "max_memory": "2gb"
    }
}
```

### 4. Event Sourcing Performance

#### Snapshot Strategy

```python
# Configure snapshot frequency based on aggregate activity
class SnapshotConfig:
    def __init__(self, aggregate_type: str):
        if aggregate_type == "high_activity":
            self.snapshot_frequency = 50  # Snapshot every 50 events
        else:
            self.snapshot_frequency = 100  # Snapshot every 100 events
```

#### Event Store Partitioning

```python
# Partition events by aggregate ID for better performance
class EventStoreConfig:
    partition_strategy: str = "hash"  # hash, range, or time
    partition_count: int = 64
    partition_key: str = "aggregate_id"
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Saga Stuck in Running State

**Symptoms:**

- Saga remains in "running" status for extended periods
- No progress on saga steps
- Memory usage increasing

**Diagnosis:**

```python
# Check saga status
saga_status = await orchestrator.get_saga_status(saga_id)
print(f"Status: {saga_status.status}")
print(f"Current step: {saga_status.current_step}")
print(f"Failed attempts: {saga_status.failed_attempts}")
print(f"Last error: {saga_status.last_error}")
```

**Solutions:**

```python
# 1. Increase timeout values
config.saga.timeout_seconds = 600

# 2. Add step-level timeouts
step_config = {
    "step_name": "process_payment",
    "timeout_ms": 30000,  # 30 seconds
    "retry_attempts": 3
}

# 3. Implement circuit breaker
@circuit_breaker(failure_threshold=5, timeout=60)
async def payment_step_handler(context):
    return await payment_service.process(context)
```

#### 2. Outbox Events Not Being Processed

**Symptoms:**

- Events accumulating in outbox table
- No events being published to message broker
- Application logs showing connection errors

**Diagnosis:**

```python
# Check outbox metrics
metrics = outbox_processor.get_metrics()
print(f"Pending events: {metrics.pending_events}")
print(f"Failed events: {metrics.failed_events}")
print(f"Processing rate: {metrics.events_per_second}")

# Check broker connectivity
broker_health = await message_broker.health_check()
print(f"Broker status: {broker_health.status}")
```

**Solutions:**

```python
# 1. Verify broker configuration
broker_config = {
    "bootstrap_servers": "localhost:9092",
    "security_protocol": "PLAINTEXT",
    "acks": "all",
    "retries": 3
}

# 2. Implement retry with exponential backoff
config.outbox.retry_backoff_ms = 1000
config.outbox.max_retry_attempts = 5

# 3. Enable dead letter queue
config.outbox.dead_letter_threshold = 3
config.outbox.dead_letter_topic = "failed.events"
```

#### 3. Read Model Inconsistency

**Symptoms:**

- Read queries returning stale data
- Data inconsistency between write and read models
- Missing or duplicate records in read models

**Diagnosis:**

```python
# Check projection lag
projection_status = await projection_manager.get_status()
print(f"Last processed event: {projection_status.last_sequence}")
print(f"Current event sequence: {projection_status.current_sequence}")
print(f"Lag: {projection_status.lag}")

# Validate read model consistency
validation_result = await read_model_validator.validate("orders")
print(f"Consistency check: {validation_result.is_consistent}")
print(f"Inconsistencies: {validation_result.issues}")
```

**Solutions:**

```python
# 1. Rebuild read models
await projection_builder.rebuild_projection("order_summary")

# 2. Implement eventual consistency monitoring
consistency_monitor = ConsistencyMonitor(
    max_lag_seconds=300,
    alert_threshold=600
)

# 3. Add read model versioning
class OrderSummaryV2(ReadModel):
    version: int = 2
    # ... fields
```

#### 4. Event Store Performance Issues

**Symptoms:**

- Slow aggregate loading
- High memory usage during event replay
- Database connection timeouts

**Diagnosis:**

```python
# Profile event store performance
profiler = EventStoreProfiler()
start_time = time.time()
aggregate = await event_store.load_aggregate(Order, "order_123")
load_time = time.time() - start_time

print(f"Load time: {load_time}s")
print(f"Event count: {aggregate.version}")
print(f"Events per second: {aggregate.version / load_time}")
```

**Solutions:**

```python
# 1. Implement snapshotting
snapshot_config = SnapshotConfig(
    frequency=100,
    compression=True,
    async_snapshots=True
)

# 2. Use event streaming for large aggregates
async def load_aggregate_streaming(aggregate_id):
    aggregate = Order(aggregate_id)
    async for event in event_store.stream_events(aggregate_id):
        aggregate.apply_event(event)
    return aggregate

# 3. Implement event caching
cache_config = EventCacheConfig(
    cache_type="redis",
    ttl_seconds=3600,
    max_events_per_aggregate=1000
)
```

### Monitoring and Observability

#### Key Metrics to Track

```python
# Saga metrics
saga_metrics = {
    "saga_duration_histogram": "Histogram of saga execution times",
    "saga_failure_rate": "Rate of saga failures",
    "saga_compensation_rate": "Rate of saga compensations",
    "active_sagas_gauge": "Number of currently active sagas"
}

# Outbox metrics
outbox_metrics = {
    "outbox_processing_lag": "Time between event creation and processing",
    "outbox_throughput": "Events processed per second",
    "outbox_error_rate": "Rate of event processing failures",
    "outbox_queue_depth": "Number of pending events"
}

# CQRS metrics
cqrs_metrics = {
    "command_processing_time": "Time to process commands",
    "query_processing_time": "Time to process queries",
    "read_model_lag": "Lag between write and read model updates",
    "cache_hit_rate": "Read model cache hit rate"
}
```

#### Health Checks

```python
# Implement comprehensive health checks
class DataConsistencyHealthCheck:
    async def check_saga_health(self):
        # Check if saga orchestrator is responsive
        return await self.saga_orchestrator.health_check()

    async def check_outbox_health(self):
        # Check outbox processing lag
        lag = await self.outbox_processor.get_processing_lag()
        return {"status": "healthy" if lag < 60 else "unhealthy", "lag": lag}

    async def check_read_model_health(self):
        # Check read model consistency
        consistency = await self.read_model_validator.check_consistency()
        return {"status": "healthy" if consistency.is_consistent else "degraded"}
```

This comprehensive documentation provides the foundation for implementing robust data consistency patterns in your microservices architecture. Each pattern can be used independently or combined for maximum effectiveness.
