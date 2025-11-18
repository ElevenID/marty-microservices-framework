# Audit Service Migration to Hexagonal Architecture

## Overview

The audit service has been successfully migrated from
`src/marty_msf/framework/audit/` to `mmf_new/services/audit/` using hexagonal
architecture (ports and adapters pattern). This migration reuses ~85% of
existing audit functionality while adopting a clean, testable architecture
that separates business logic from infrastructure concerns.

## Architecture

### Hexagonal Architecture Layers

```text
mmf_new/services/audit/
├── domain/                    # Core business logic (no dependencies)
│   ├── entities.py           # RequestAuditEvent, ApiCallEvent, MiddlewareAuditEvent
│   ├── value_objects.py      # RequestContext, ResponseMetadata, PerformanceMetrics
│   └── contracts.py          # Port interfaces (IAuditDestination, IAuditRepository, etc.)
├── application/              # Use cases and commands
│   ├── commands.py           # Command/Response DTOs
│   └── use_cases.py          # LogRequestUseCase, QueryAuditEventsUseCase, etc.
├── infrastructure/           # External adapters
│   ├── adapters/            # Destination adapters
│   │   ├── console_destination.py
│   │   ├── file_destination.py
│   │   ├── database_destination.py
│   │   ├── siem_destination.py
│   │   └── encryption_adapter.py
│   ├── repositories/
│   │   └── audit_repository.py
│   └── models.py            # SQLAlchemy models
├── di_config.py             # Dependency injection container
├── service_factory.py       # High-level service API
└── __init__.py              # Public exports
```text

## Key Features

### 1. Auto-Forwarding to Audit Compliance

Events with severity >= HIGH are automatically forwarded to the
`audit_compliance` service with correlation tracking:

```python
if event.severity >= AuditSeverity.HIGH:
    security_event_id = await forward_to_compliance(event)
    event.security_event_id = security_event_id  # Correlation tracking
```text

### 2. Independent Destination Failure Handling

Each destination operates independently - failures in one don't block others:

```python
for destination in destinations:
    try:
        await destination.write_event(event)
    except Exception as e:
        logger.error(f"Destination {destination} failed: {e}")
        # Continue with other destinations
```text

### 3. Configurable Batching

- **Development**: Immediate mode (`immediate_mode=True`) - events written immediately
- **Production**: Batched mode (`immediate_mode=False`) - events batched for performance

```python
AuditConfig(
    batch_size=100,
    flush_interval_seconds=30,
    immediate_mode=False,  # False for production
)
```text

### 4. Encryption Adapter

Scrypt KDF + AES-256-CBC encryption for sensitive fields:

```python
encryption_adapter = AuditEncryptionAdapter()
encrypted_event = encryption_adapter.encrypt_event(event)
# Automatically detects and encrypts: password, token, secret, api_key, etc.
```text

### 5. Multiple Destinations

- **Console**: Colorized development output
- **File**: Rotation, compression, async I/O
- **Database**: Async SQLAlchemy with batching
- **SIEM**: Elasticsearch integration via audit_compliance

## Usage

### Basic Usage

```python
from mmf_new.services.audit import (
    AuditService,
    create_audit_service,
    create_default_audit_config,
    LogRequestCommand,
)
from mmf_new.core.domain.audit_types import AuditEventType, AuditSeverity, AuditOutcome

# Create configuration
config = create_default_audit_config(
    database_url="postgresql+asyncpg://user:pass@localhost/db",  # pragma: allowlist secret
    environment="development"
)

# Create and initialize service
service = create_audit_service(config)
await service.initialize(session_factory)

# Log an audit event
command = LogRequestCommand(
    event_type=AuditEventType.API_REQUEST,
    severity=AuditSeverity.INFO,
    outcome=AuditOutcome.SUCCESS,
    message="User login successful",
    method="POST",
    endpoint="/api/v1/auth/login",
    source_ip="192.168.1.100",
    user_id="user-123",
    username="john.doe",
    status_code=200,
    duration_ms=45.2,
)

response = await service.log_request(command)
print(f"Logged event: {response.event_id}")

# Shutdown service
await service.shutdown()
```text

### Context Manager Usage

```python
from mmf_new.services.audit import audit_context

async with audit_context(config, session_factory) as audit_service:
    # Service is automatically initialized
    await audit_service.log_request(command)
    # Service is automatically shutdown on exit
```text

### Query Events

```python
from mmf_new.services.audit import QueryAuditEventsCommand
from datetime import datetime, timedelta

query = QueryAuditEventsCommand(
    severity=AuditSeverity.HIGH,
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now(),
    user_id="user-123",
    limit=100,
)

response = await service.query_events(query)
for event in response.events:
    print(f"Event: {event['event_type']} at {event['timestamp']}")
```text

### Generate Reports

```python
from mmf_new.services.audit import GenerateAuditReportCommand

report_command = GenerateAuditReportCommand(
    start_time=datetime(2024, 1, 1),
    end_time=datetime(2024, 12, 31),
    severity_threshold=AuditSeverity.MEDIUM,
    format="json",
)

report = await service.generate_report(report_command)
print(f"Report ID: {report.report_id}")
print(f"Total events: {report.report_data['summary']['total_events']}")
```text

## Configuration

### AuditConfig Options

```python
@dataclass
class AuditConfig:
    # Database
    database_url: str
    database_pool_size: int = 20

    # Batching
    batch_size: int = 100
    flush_interval_seconds: int = 30
    immediate_mode: bool = False  # True for dev, False for prod

    # Destinations
    enabled_destinations: list[str] = ["database", "console"]
    # Options: "database", "file", "console", "siem"

    # File destination
    file_log_directory: str = "./logs/audit"
    file_max_size_mb: int = 100
    file_max_files: int = 10
    file_compress: bool = True

    # Console destination
    console_use_colors: bool = True
    console_format: str = "pretty"  # "pretty" or "json"
    console_detail_level: str = "compact"  # "full", "compact", "minimal"

    # SIEM
    siem_adapter: object | None = None  # ElasticsearchSIEMAdapter

    # Auto-forwarding
    auto_forward_threshold: AuditSeverity = AuditSeverity.HIGH
    compliance_logger: object | None = None  # audit_compliance logger

    # Encryption
    encryption_enabled: bool = True
```text

### Environment Variables

```bash
# Encryption keys
export AUDIT_ENCRYPTION_KEY="your-secure-key-material"
export AUDIT_SALT="your-secure-salt"

# Database
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db"  # pragma: allowlist secret
```text

## Domain Model

### Core Entities

**RequestAuditEvent** (Aggregate Root)

- Core event: `event_type`, `severity`, `outcome`, `timestamp`
- Request context: `method`, `endpoint`, `source_ip`, `user_agent`
- Actor info: `user_id`, `username`, `session_id`, `api_key_id`
- Resource info: `resource_type`, `resource_id`, `action`
- Performance: `duration_ms`, `response_size`
- Correlation: `correlation_id`, `security_event_id`

**ApiCallEvent** (specialization)

- Adds: `target_service`, `target_endpoint`

**MiddlewareAuditEvent** (specialization)

- Adds: `middleware_name`, `middleware_stage`

### Value Objects (Immutable)

- **RequestContext**: Request metadata
- **ResponseMetadata**: Response details
- **PerformanceMetrics**: Timing and performance data
- **ActorInfo**: User/service identity
- **ResourceInfo**: Resource being accessed
- **ServiceContext**: Service metadata

## Database Schema

### audit_logs Table

```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(36) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    message TEXT,

    -- Actor
    user_id VARCHAR(255),
    username VARCHAR(255),
    session_id VARCHAR(255),
    api_key_id VARCHAR(255),
    client_id VARCHAR(255),

    -- Request
    source_ip INET,
    user_agent TEXT,
    request_id VARCHAR(255),
    method VARCHAR(10),
    endpoint VARCHAR(500),

    -- Resource
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    action VARCHAR(255),

    -- Context
    service_name VARCHAR(100),
    environment VARCHAR(50),
    correlation_id VARCHAR(255),
    trace_id VARCHAR(255),

    -- Performance
    duration_ms FLOAT,
    response_size INTEGER,
    status_code INTEGER,

    -- Error
    error_code VARCHAR(100),
    error_message TEXT,

    -- Additional
    details JSONB,
    encrypted_fields JSONB,
    security_event_id VARCHAR(36),
    event_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    INDEX idx_event_id (event_id),
    INDEX idx_event_type (event_type),
    INDEX idx_severity (severity),
    INDEX idx_timestamp (timestamp),
    INDEX idx_user_id (user_id),
    INDEX idx_service_name (service_name),
    INDEX idx_correlation_id (correlation_id)
);
```text

## Event Types (80+)

### Authentication & Authorization

- `AUTH_LOGIN_SUCCESS`, `AUTH_LOGIN_FAILURE`, `AUTH_LOGOUT`
- `AUTH_TOKEN_CREATED`, `AUTH_TOKEN_REFRESHED`, `AUTH_TOKEN_REVOKED`
- `AUTHZ_ACCESS_GRANTED`, `AUTHZ_ACCESS_DENIED`
- `AUTHZ_PERMISSION_CHANGED`, `AUTHZ_ROLE_ASSIGNED`

### API & Service Operations

- `API_REQUEST`, `API_RESPONSE`, `API_ERROR`, `API_RATE_LIMITED`
- `SERVICE_CALL`, `SERVICE_ERROR`, `SERVICE_TIMEOUT`

### Data Operations

- `DATA_CREATE`, `DATA_READ`, `DATA_UPDATE`, `DATA_DELETE`
- `DATA_EXPORT`, `DATA_IMPORT`, `DATA_BACKUP`, `DATA_RESTORE`

### Security Events

- `SECURITY_INTRUSION_ATTEMPT`, `SECURITY_MALICIOUS_REQUEST`
- `SECURITY_VULNERABILITY_DETECTED`, `SECURITY_POLICY_VIOLATION`

### System Events

- `SYSTEM_STARTUP`, `SYSTEM_SHUTDOWN`, `SYSTEM_CONFIG_CHANGE`
- `SYSTEM_ERROR`, `SYSTEM_HEALTH_CHECK`

[See `mmf_new/core/domain/audit_types.py` for complete list]

## Migration from Old API

### Old API (src/marty_msf/framework/audit)

```python
from marty_msf.framework.audit import AuditLogger, AuditEvent

logger = AuditLogger(destinations=[file_dest, db_dest])
event = AuditEvent(event_type=AuditEventType.API_REQUEST, ...)
await logger.log_event(event)
```text

### New API (mmf_new/services/audit)

```python
from mmf_new.services.audit import audit_context, LogRequestCommand

async with audit_context(config, session_factory) as audit_service:
    command = LogRequestCommand(event_type=AuditEventType.API_REQUEST, ...)
    response = await audit_service.log_request(command)
```text

## Testing

### Unit Tests

Test domain logic in isolation:

```python
def test_audit_event_should_forward():
    event = RequestAuditEvent(severity=AuditSeverity.HIGH)
    assert event.should_forward_to_compliance() == True
```text

### Integration Tests

Test with real components (TODO):

```python
async def test_log_request_with_destinations(audit_service):
    command = LogRequestCommand(...)
    response = await audit_service.log_request(command)
    assert response.event_id is not None
```text

## Next Steps

1. **Middleware Adapters** - Port FastAPI and gRPC middleware (task 16)
2. **Integration Tests** - Comprehensive test coverage (tasks 20-21)
3. **Performance Testing** - Validate batching and throughput
4. **Monitoring** - Add Prometheus metrics
5. **Documentation** - API documentation and examples

## Benefits of Hexagonal Architecture

1. **Testability**: Domain logic can be tested without infrastructure
2. **Flexibility**: Easy to swap implementations (e.g., different databases)
3. **Maintainability**: Clear separation of concerns
4. **Evolution**: New destinations can be added without changing domain
5. **Independence**: Business rules don't depend on frameworks

## Code Reuse Summary

- **85% code reuse** from original implementation
- **Event types**: All 80+ event types preserved
- **Destinations**: All 4 destinations implemented
- **Encryption**: Same Scrypt + AES-256 encryption
- **Batching**: Enhanced with configurable modes
- **New features**: Auto-forwarding, correlation tracking, independent failures

## Architecture Decisions

### Event Type Consolidation (Option A - Selected)

Kept separate enums (`AuditEventType` vs `SecurityEventType`) with mapping layer for separation of concerns.

### Destination Configuration (Option B - Selected)

YAML/config-based destination enablement with explicit
`enabled_destinations` list.

### Auto-Forwarding Performance (Option A - Selected)

Async fire-and-forget for audit_compliance forwarding to prevent blocking
on SIEM availability.

---

**Status**: Core implementation complete (19/21 tasks)
**Remaining**: Middleware adapters, integration tests
**Ready for**: Review, testing, and gradual rollout
