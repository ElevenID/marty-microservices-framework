# Event Bus Strategy Consolidation & Architectural Decisions

## Executive Summary

This document outlines the consolidated event bus strategy for the Marty Microservices Framework, consolidating multiple competing implementations into a unified, coherent architecture that supports both domain events and transactional outbox patterns.

## Current State Analysis

### Existing Implementations

1. **Enhanced Event Bus** (`mmf/framework/events/enhanced_event_bus.py`)
   - Kafka-only event bus with transactional outbox pattern
   - Complete lifecycle management (publish, consume, retry, DLQ)
   - Plugin integration support
   - **Status**: Primary implementation, feature-complete

2. **Event Publisher** (`mmf/framework/events/publisher.py`)
   - Unified publisher for audit/notification/domain events
   - Kafka integration with outbox pattern support
   - **Status**: Overlapping functionality with Enhanced Event Bus

3. **Outbox Repository** (`mmf/framework/database/outbox.py`)
   - Database pattern implementation for transactional consistency
   - Simple outbox table management
   - **Status**: Superseded by Enhanced Event Bus outbox implementation

4. **Event Streaming Core** (`mmf/framework/event_streaming/core.py`)
   - Event sourcing abstractions and domain event patterns
   - **Status**: Keep for event sourcing use cases

5. **Domain-specific Outbox Services** (Examples)
   - Petstore domain-specific implementations
   - **Status**: Convert to use consolidated approach

## Architectural Decisions

### AD-001: Single Primary Event Bus Implementation

**Decision**: Use Enhanced Event Bus as the single primary event bus implementation.

**Rationale**:

- Most comprehensive feature set (outbox, DLQ, retries, plugins)
- Kafka-native with proper transactional guarantees
- Already implements industry-standard patterns
- Extensible architecture for future needs

**Impact**: Deprecate competing implementations, migrate existing usage

### AD-002: Unified Event Publishing Interface

**Decision**: Consolidate Event Publisher functionality into Enhanced Event Bus.

**Rationale**:

- Eliminate code duplication and maintenance overhead
- Provide single point of integration for all event publishing
- Maintain backwards compatibility through adapter pattern

**Implementation**:

```python
# New unified interface
class UnifiedEventBus(EnhancedEventBus):
    """Unified event bus combining all event publishing capabilities."""

    async def publish_audit_event(self, event_type: AuditEventType, **kwargs) -> None:
        """Publish audit events with proper categorization."""

    async def publish_domain_event(self, aggregate_id: str, event_type: str, **kwargs) -> None:
        """Publish domain events with aggregate context."""

    async def publish_notification_event(self, event_type: NotificationEventType, **kwargs) -> None:
        """Publish notification events for user/system alerts."""
```

### AD-003: Outbox Pattern as Default for Transactional Scenarios

**Decision**: Make transactional outbox pattern the default for all database-integrated scenarios.

**Rationale**:

- Ensures ACID compliance for business operations + event publishing
- Eliminates dual-write problem
- Provides reliable event delivery guarantees
- Industry best practice for microservices

**Configuration**:

```python
# Default transactional mode
event_bus = UnifiedEventBus(
    kafka_config=kafka_config,
    outbox_config=OutboxConfig(database_url=db_url),  # Enabled by default
    mode=EventBusMode.TRANSACTIONAL  # Default mode
)

# Direct mode for non-transactional scenarios
event_bus_direct = UnifiedEventBus(
    kafka_config=kafka_config,
    mode=EventBusMode.DIRECT  # Bypass outbox for high-throughput scenarios
)
```

### AD-004: Event Classification and Routing Strategy

**Decision**: Implement event classification with automatic routing.

**Event Categories**:

1. **Domain Events** - Business logic changes within bounded contexts
2. **Integration Events** - Cross-service communication
3. **System Events** - Infrastructure and operational events
4. **Audit Events** - Compliance and security tracking
5. **Notification Events** - User and system notifications

**Routing Strategy**:

```python
# Automatic topic generation based on event classification
domain_event → topic: "domain.{service}.{aggregate_type}.{event_type}"
integration_event → topic: "integration.{source_service}.{target_service}.{event_type}"
audit_event → topic: "audit.{service}.{event_category}"
system_event → topic: "system.{service}.{event_type}"
notification_event → topic: "notifications.{channel}.{type}"
```

### AD-005: Plugin Integration Architecture

**Decision**: Maintain plugin integration through Enhanced Event Bus subscription model.

**Implementation**:

- Plugins subscribe to events through EventFilter criteria
- Framework automatically routes relevant events to plugin handlers
- Plugin handlers can be sync or async
- Built-in error handling and circuit breaker patterns

### AD-006: Dead Letter Queue and Error Handling Strategy

**Decision**: Implement comprehensive error handling with DLQ support.

**Error Handling Hierarchy**:

1. **Immediate Retry** - Transient failures (network, temporary service unavailability)
2. **Exponential Backoff** - Persistent but potentially recoverable failures
3. **Dead Letter Queue** - Permanent failures requiring manual intervention
4. **Error Notifications** - Alert operations team for critical failures

**DLQ Processing**:

- Manual retry capability through management API
- Error analysis and categorization
- Automatic cleanup of old processed events

### AD-007: Monitoring and Observability Integration

**Decision**: Built-in observability with metrics, tracing, and health checks.

**Observability Features**:

- Event publishing metrics (throughput, latency, failures)
- Outbox processing metrics (queue depth, processing time)
- Distributed tracing integration
- Health check endpoints
- Dead letter queue monitoring

### AD-008: Configuration Management Strategy

**Decision**: Environment-based configuration with sensible defaults.

**Configuration Hierarchy**:

1. Framework defaults (development-friendly)
2. Environment variables (container/k8s deployment)
3. Configuration files (complex scenarios)
4. Runtime overrides (testing/debugging)

## Migration Strategy

### Phase 1: Consolidation (Sprint 1-2)

1. **Enhance Event Bus Integration**

   ```python
   # Add unified publishing methods to Enhanced Event Bus
   class EnhancedEventBus:
       async def publish_audit_event(self, ...): ...
       async def publish_domain_event(self, ...): ...
       async def publish_notification_event(self, ...): ...
   ```

2. **Create Compatibility Layer**

   ```python
   # Backwards compatibility for existing EventPublisher usage
   class EventPublisherAdapter:
       def __init__(self, unified_event_bus: UnifiedEventBus):
           self._bus = unified_event_bus

       async def publish_audit_event(self, ...):
           return await self._bus.publish_audit_event(...)
   ```

3. **Update Framework Exports**

   ```python
   # mmf/framework/events/__init__.py
   from .enhanced_event_bus import EnhancedEventBus as UnifiedEventBus
   from .adapters import EventPublisherAdapter as EventPublisher  # Compatibility
   ```

### Phase 2: Migration (Sprint 3-4)

1. **Update Example Applications**
   - Migrate Petstore domain to use UnifiedEventBus
   - Update all demo applications
   - Create migration examples

2. **Update Documentation**
   - Comprehensive usage guides
   - Migration instructions
   - Best practices documentation

### Phase 3: Cleanup (Sprint 5)

1. **Remove Deprecated Components**
   - Mark old implementations as deprecated
   - Remove unused outbox implementations
   - Clean up redundant code

2. **Performance Optimization**
   - Optimize outbox processing
   - Tune Kafka producer/consumer settings
   - Implement connection pooling

## Implementation Plan

### Immediate Actions (Week 1)

1. **Consolidate Enhanced Event Bus** ✅ (Already completed)
   - Transactional outbox pattern implemented
   - Kafka integration complete
   - Plugin support available

2. **Add Unified Publishing Methods**

   ```python
   # Add to Enhanced Event Bus
   async def publish_audit_event(self, event_type: AuditEventType, action: str, **kwargs)
   async def publish_domain_event(self, aggregate_id: str, event_type: str, **kwargs)
   async def publish_notification_event(self, event_type: NotificationEventType, **kwargs)
   ```

3. **Create Event Classification System**

   ```python
   class EventCategory(Enum):
       DOMAIN = "domain"
       INTEGRATION = "integration"
       AUDIT = "audit"
       SYSTEM = "system"
       NOTIFICATION = "notification"
   ```

### Short-term Actions (Week 2-3)

1. **Implement Routing Strategy**
2. **Add Observability Metrics**
3. **Create Migration Documentation**
4. **Update Framework Exports**

### Medium-term Actions (Month 1-2)

1. **Migrate Example Applications**
2. **Performance Testing and Optimization**
3. **Comprehensive Documentation**
4. **Community Feedback Integration**

## Configuration Examples

### Development Configuration

```python
# Simple development setup
event_bus = UnifiedEventBus(
    kafka_config=KafkaConfig(bootstrap_servers=["localhost:9092"]),
    # Outbox disabled for development simplicity
    mode=EventBusMode.DIRECT
)
```

### Production Configuration

```python
# Production setup with full reliability
event_bus = UnifiedEventBus(
    kafka_config=KafkaConfig(
        bootstrap_servers=["kafka1:9092", "kafka2:9092", "kafka3:9092"],
        security_protocol="SASL_SSL",
        sasl_mechanism="SCRAM-SHA-256",
        sasl_plain_username=env("KAFKA_USERNAME"),
        sasl_plain_password=env("KAFKA_PASSWORD")
    ),
    outbox_config=OutboxConfig(
        database_url=env("DATABASE_URL"),
        batch_size=100,
        poll_interval=timedelta(seconds=5),
        max_retries=3,
        enable_dead_letter_queue=True
    ),
    mode=EventBusMode.TRANSACTIONAL
)
```

### Testing Configuration

```python
# Testing with in-memory capabilities
event_bus = UnifiedEventBus(
    kafka_config=KafkaConfig(bootstrap_servers=["testcontainer:9092"]),
    mode=EventBusMode.TESTING,  # Special mode for tests
    enable_test_mode=True
)
```

## Success Metrics

1. **Code Quality**
   - Eliminate duplicate event publishing code
   - Single source of truth for event bus functionality
   - Improved test coverage (>90%)

2. **Developer Experience**
   - Simplified API surface (single event bus class)
   - Comprehensive documentation and examples
   - Clear migration path from legacy implementations

3. **Operational Excellence**
   - Built-in observability and monitoring
   - Reliable event delivery (>99.9%)
   - Efficient outbox processing (<100ms p95)

4. **Maintainability**
   - Reduced codebase complexity
   - Consolidated configuration management
   - Easier future enhancements

## Conclusion

This consolidation strategy provides a clear path forward for unifying the event bus implementations while maintaining backwards compatibility and ensuring enterprise-grade reliability. The Enhanced Event Bus serves as the foundation, with additional unified publishing methods and improved observability to create a comprehensive event-driven architecture solution.

The transactional outbox pattern becomes the default for database-integrated scenarios, ensuring data consistency while providing the flexibility to use direct publishing for high-throughput use cases. This approach aligns with industry best practices and provides a solid foundation for future microservices development within the Marty framework.
