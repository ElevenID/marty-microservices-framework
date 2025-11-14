# Events and Messaging Frameworks - Archived 2025-11-14

## Migration Status
The events and messaging frameworks have been fully migrated from `src/marty_msf/framework/events/` and `src/marty_msf/framework/messaging/` to `mmf_new/core/` as part of the mmf_new framework migration.

## What Was Migrated

### Events Module (`mmf_new/core/events/`)
- **enhanced_event_bus.py** - Kafka-based event bus with transactional outbox pattern
- **enhanced_events.py** - DomainEvent, SystemEvent, EventRegistry for event types
- **decorators.py** - @audit_event, @domain_event, @publish_on_success, @publish_on_error
- **event_bus_service.py** - DI-integrated service wrapper for the event bus
- **config.py** - Event bus configuration
- **types.py** - AuditEventType, NotificationEventType enumerations
- **exceptions.py** - EventPublishingError and related exceptions

### Messaging Module (`mmf_new/core/messaging/`)
- **api.py** - Messaging contracts and interfaces (IMessageBackend, IMessageBus, etc.)
- **bootstrap.py** - Concrete implementations (MessageBus, MessageQueue, MessageProducer/Consumer)
- **extended/** - Multi-backend messaging support:
  - `extended_architecture.py` - Unified event bus architecture
  - `nats_backend.py` - NATS backend implementation
  - `aws_sns_backend.py` - AWS SNS backend implementation
  - `saga_integration.py` - Saga pattern integration (partially disabled)
  - `examples.py` - Usage examples

## Import Changes
All imports have been refactored:
- `from marty_msf.framework.events` → `from mmf_new.core.events`
- `from marty_msf.framework.messaging` → `from mmf_new.core.messaging`
- `from marty_msf.core` → `from mmf_new.core` (DI, base services)

## Features Now Available in mmf_new
- Event-driven architecture with Kafka
- Transactional outbox pattern for reliable event publishing
- Domain events, system events, audit events
- Multi-backend messaging (Kafka, NATS, AWS SNS, in-memory)
- Dead letter queue support
- Event decorators for automatic publishing
- Circuit breakers and retry mechanisms
- Message routing and filtering
- Plugin-based event handlers

## Dependencies
### Completed Dependencies
- ✅ Core DI system (mmf_new.core)
- ✅ Base services (mmf_new.core)
- ✅ Observability (mmf_new.core.observability) - now uses events for Kafka

### Pending Dependencies
- ⏸️ Patterns module (CQRS, Saga, Event Sourcing) - saga_integration.py awaits this
- ⏸️ gRPC framework - for streaming events

## Integration Updates
- **observability/kafka/__init__.py** - Now exposes EnhancedEventBus (no longer a placeholder)
- **messaging/extended/saga_integration.py** - Saga imports commented out until patterns migration

## Git Commit
Migration completed in commit: b03f780 (2025-11-14)

## Reason for Archival
These modules have been successfully migrated to the new mmf_new structure. The old modules are archived here for reference during the transition period and to prevent accidental use of deprecated code paths.

## Next Migration Targets
Based on dependencies and usage:
1. **Patterns Module** (patterns/) - CQRS, Saga, Event Sourcing, Outbox patterns
2. **gRPC Framework** (framework/grpc/) - Service mesh and RPC communication
3. **Authentication/Authorization** - Security modules

## Related Migrations
- Services: boneyard/services_migration_20251114/
- Config: boneyard/config_migration_20251112/
- Database Infrastructure: boneyard/database_infrastructure_migration_20241110/
- Observability: boneyard/observability_migration_20251114/
