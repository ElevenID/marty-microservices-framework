# Enterprise Audit Logging Framework

A comprehensive audit logging solution for microservices that provides structured event tracking, multiple destinations, encryption, and compliance features.

## Features

- **Structured Audit Events**: Rich event data model with correlation IDs and metadata
- **Multiple Destinations**: File, database, console, and SIEM integration
- **Encryption**: Automatic encryption of sensitive data fields
- **Middleware Integration**: Automatic logging for FastAPI and gRPC applications
- **Performance**: Asynchronous logging with batching and queuing
- **Compliance**: GDPR, SOX, HIPAA-ready with retention policies
- **Search & Analytics**: Event search and statistical reporting
- **Anomaly Detection**: Built-in security anomaly detection

## Quick Start

### Basic Setup

```python
import asyncio
from framework.audit import (
    AuditConfig, AuditContext, AuditEventType,
    audit_context
)

async def main():
    # Configure audit logging
    config = AuditConfig()
    config.enable_file_logging = True
    config.enable_console_logging = True

    # Create service context
    context = AuditContext(
        service_name="my-service",
        service_version="1.0.0",
        environment="production"
    )

    # Use audit logging
    async with audit_context(config, context) as audit_logger:
        await audit_logger.log_auth_event(
            AuditEventType.USER_LOGIN,
            user_id="user123",
            source_ip="192.168.1.100"
        )

asyncio.run(main())
```

### FastAPI Integration

```python
from fastapi import FastAPI
from framework.audit import setup_fastapi_audit_middleware

app = FastAPI()

# Add audit middleware
setup_fastapi_audit_middleware(app)

@app.get("/api/users/{user_id}")
async def get_user(user_id: str):
    # Requests are automatically audited
    return {"id": user_id, "name": f"User {user_id}"}
```

## Configuration

### AuditConfig

```python
config = AuditConfig()

# Destinations
config.enable_file_logging = True
config.enable_database_logging = True
config.enable_console_logging = False  # For development
config.enable_siem_logging = True

# File settings
config.log_file_path = Path("logs/audit.log")
config.max_file_size = 100 * 1024 * 1024  # 100MB
config.max_files = 10

# Security
config.encrypt_sensitive_data = True

# Performance
config.async_logging = True
config.batch_size = 100
config.flush_interval_seconds = 30

# Retention
config.retention_days = 365
config.auto_cleanup = True

# Filtering
config.min_severity = AuditSeverity.INFO
config.excluded_event_types = [AuditEventType.HEARTBEAT]
```

### AuditContext

```python
context = AuditContext(
    service_name="user-service",
    service_version="2.1.0",
    environment="production",
    node_id="us-east-1-node-03",
    compliance_requirements=["SOX", "GDPR"]
)
```

## Event Types

The framework supports various audit event types:

- **Authentication**: `USER_LOGIN`, `USER_LOGOUT`, `AUTH_SUCCESS`, `AUTH_FAILURE`
- **Authorization**: `ACCESS_GRANTED`, `ACCESS_DENIED`, `PERMISSION_CHECK`
- **Data Operations**: `DATA_CREATE`, `DATA_READ`, `DATA_UPDATE`, `DATA_DELETE`, `DATA_EXPORT`
- **API Operations**: `API_REQUEST`, `API_RESPONSE`
- **Security**: `SECURITY_VIOLATION`, `SUSPICIOUS_ACTIVITY`, `RATE_LIMIT_EXCEEDED`
- **System**: `SYSTEM_STARTUP`, `SYSTEM_SHUTDOWN`, `CONFIGURATION_CHANGE`
- **Business**: `BUSINESS_LOGIC`, `TRANSACTION`, `WORKFLOW`
- **Compliance**: `COMPLIANCE_CHECK`, `DATA_RETENTION`, `PRIVACY_ACCESS`

## Logging Methods

### Authentication Events

```python
await audit_logger.log_auth_event(
    AuditEventType.USER_LOGIN,
    user_id="user123",
    outcome=AuditOutcome.SUCCESS,
    source_ip="192.168.1.100",
    details={"method": "password", "mfa": True}
)
```

### API Events

```python
await audit_logger.log_api_event(
    method="POST",
    endpoint="/api/users",
    status_code=201,
    user_id="user123",
    duration_ms=45.2,
    request_size=1024,
    response_size=512
)
```

### Data Events

```python
await audit_logger.log_data_event(
    AuditEventType.DATA_UPDATE,
    resource_type="user",
    resource_id="123",
    action="update_profile",
    user_id="user123",
    changes={"email": "new@example.com"}
)
```

### Security Events

```python
await audit_logger.log_security_event(
    AuditEventType.SECURITY_VIOLATION,
    "Multiple failed login attempts",
    severity=AuditSeverity.HIGH,
    source_ip="192.168.1.200",
    details={"attempts": 5, "timeframe": "5min"}
)
```

### Custom Events

```python
builder = audit_logger.create_event_builder()

event = (builder
    .event_type(AuditEventType.BUSINESS_LOGIC)
    .message("Payment processed successfully")
    .user("customer123")
    .action("process_payment")
    .severity(AuditSeverity.MEDIUM)
    .outcome(AuditOutcome.SUCCESS)
    .resource("payment", "pay-789")
    .performance(duration_ms=250.0)
    .detail("amount", 99.99)
    .detail("currency", "USD")
    .sensitive_detail("card_number", "****-****-****-1234")
    .build())

await audit_logger.log_event(event)
```

## Destinations

### File Destination

```python
from framework.audit import FileAuditDestination

destination = FileAuditDestination(
    log_file_path=Path("audit.log"),
    max_file_size=100 * 1024 * 1024,  # 100MB
    max_files=10,
    encrypt_sensitive=True
)
```

Features:

- Automatic log rotation
- Compression of old files
- Encryption of sensitive fields
- JSON and text formats

### Database Destination

```python
from framework.audit import DatabaseAuditDestination

destination = DatabaseAuditDestination(
    db_session=session,
    encrypt_sensitive=True,
    batch_size=100
)
```

Features:

- Batch processing for performance
- Structured queries
- Automatic table creation
- Encryption support

### SIEM Destination

```python
from framework.audit import SIEMAuditDestination

destination = SIEMAuditDestination(
    siem_endpoint="https://siem.company.com/api/events",
    api_key="your-api-key",
    batch_size=50
)
```

Features:

- REST API integration
- Batch uploading
- Retry logic
- Standard SIEM formats

## Middleware

### FastAPI Middleware

```python
from framework.audit import (
    setup_fastapi_audit_middleware,
    AuditMiddlewareConfig
)

# Configure middleware
config = AuditMiddlewareConfig()
config.log_requests = True
config.log_responses = True
config.log_headers = True
config.exclude_paths = ["/health", "/metrics"]
config.slow_request_threshold_ms = 1000.0
config.detect_anomalies = True

# Setup middleware
setup_fastapi_audit_middleware(app, config)
```

Automatically logs:

- HTTP requests and responses
- Authentication events
- Slow requests
- Security anomalies
- Error conditions

### gRPC Interceptor

```python
from framework.audit import setup_grpc_audit_interceptor

server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
setup_grpc_audit_interceptor(server, config)
```

## Search and Analytics

### Event Search

```python
# Search by criteria
async for event in audit_logger.search_events(
    event_type=AuditEventType.API_REQUEST,
    user_id="user123",
    start_time=datetime.now() - timedelta(hours=24),
    limit=100
):
    print(f"Event: {event.action} at {event.timestamp}")
```

### Statistics

```python
stats = await audit_logger.get_audit_statistics(
    start_time=datetime.now() - timedelta(days=7)
)

print(f"Total events: {stats['total_events']}")
print(f"Security events: {stats['security_events']}")
print(f"Event breakdown: {stats['event_counts']}")
```

## Security Features

### Encryption

Sensitive data is automatically encrypted using AES-256:

```python
# Sensitive fields are encrypted
builder.sensitive_detail("ssn", "123-45-6789")
builder.sensitive_detail("credit_card", "4111-1111-1111-1111")
```

### Anomaly Detection

Built-in detection for:

- Multiple authentication failures
- Large data exports
- Unusual access patterns
- Rate limit violations
- Suspicious IP addresses

### Access Control

Audit logs are protected with:

- File permissions (600)
- Database access controls
- Encrypted sensitive fields
- Immutable logging options

## Compliance

### GDPR Compliance

```python
# Data subject access
events = audit_logger.search_events(user_id="subject123")

# Data retention
await audit_logger.cleanup_old_events(older_than_days=365)

# Privacy events
await audit_logger.log_system_event(
    AuditEventType.PRIVACY_ACCESS,
    "Data subject access request processed",
    details={"subject_id": "user123", "data_exported": True}
)
```

### SOX Compliance

```python
# Financial transaction auditing
await audit_logger.log_data_event(
    AuditEventType.TRANSACTION,
    resource_type="financial_record",
    resource_id="txn-789",
    action="create",
    user_id="accountant123",
    changes={"amount": 1000.00, "account": "revenue"}
)
```

### HIPAA Compliance

```python
# Healthcare data access
await audit_logger.log_data_event(
    AuditEventType.DATA_ACCESS,
    resource_type="patient_record",
    resource_id="patient-456",
    action="view",
    user_id="doctor123",
    changes={"fields_accessed": ["diagnosis", "treatment"]}
)
```

## Performance

### Asynchronous Logging

```python
config.async_logging = True
config.flush_interval_seconds = 30
```

Benefits:

- Non-blocking event logging
- Batch processing
- Queue management
- Background flushing

### Batching

```python
config.batch_size = 100
```

Features:

- Efficient database writes
- Reduced I/O operations
- Configurable batch sizes
- Automatic flushing

### Sampling

```python
middleware_config.sample_rate = 0.1  # Log 10% of requests
```

## Error Handling

The framework provides robust error handling:

- **Graceful Degradation**: Continues operation if destinations fail
- **Error Isolation**: Destination failures don't affect others
- **Retry Logic**: Automatic retries for transient failures
- **Fallback Logging**: Standard logging for framework errors

## Best Practices

### 1. Service Context

Always provide comprehensive service context:

```python
context = AuditContext(
    service_name="payment-service",
    service_version="1.2.3",
    environment="production",
    node_id="us-west-2-node-01"
)
```

### 2. Structured Events

Use structured event builders for consistency:

```python
event = (builder
    .event_type(AuditEventType.BUSINESS_LOGIC)
    .message("Order processed")
    .user(user_id)
    .resource("order", order_id)
    .build())
```

### 3. Sensitive Data

Mark sensitive data for encryption:

```python
builder.sensitive_detail("payment_token", token)
```

### 4. Performance

Configure for your environment:

```python
# High-throughput service
config.async_logging = True
config.batch_size = 500
config.flush_interval_seconds = 10

# Low-latency service
config.async_logging = False
config.min_severity = AuditSeverity.MEDIUM
```

### 5. Monitoring

Monitor audit system health:

```python
stats = await audit_logger.get_audit_statistics()
if stats['error_events'] > threshold:
    # Alert operations team
```

## Integration Examples

See the `examples.py` file for comprehensive integration examples including:

- Basic audit logging setup
- FastAPI integration
- Database integration
- Performance testing
- Compliance scenarios
- Custom event building

## Dependencies

Required packages:

- `cryptography` - For encryption features
- `sqlalchemy` - For database destinations
- `fastapi` - For FastAPI middleware (optional)
- `grpc` - For gRPC interceptor (optional)

Install with:

```bash
pip install cryptography sqlalchemy
# Optional dependencies
pip install 'fastapi[all]' grpcio grpcio-tools
```

## License

This audit logging framework is part of the Marty Microservices Framework and follows the same licensing terms.
