# Phase 2 Enterprise Infrastructure Integration

This gRPC service template has been enhanced with Phase 2 enterprise infrastructure components, providing a complete enterprise-grade microservice scaffolding.

## Phase 2 Components Integrated

### 1. Configuration Management

- **ConfigManager**: Centralized configuration with hot-reloading
- **SecretManager**: Secure secret management with encryption
- **Environment-specific configuration**: Development, testing, production settings
- **Type-safe configuration**: Pydantic-based validation

### 2. Caching Infrastructure

- **Multi-backend support**: Redis, in-memory caching
- **Cache patterns**: Cache-aside, write-through, write-behind
- **Performance monitoring**: Cache hit/miss metrics
- **TTL management**: Configurable time-to-live settings

### 3. Message Queues

- **Multiple brokers**: RabbitMQ, Kafka, Redis, in-memory
- **Messaging patterns**: Pub/Sub, request/reply, work queues
- **Reliable delivery**: Message acknowledgments and retries
- **Health monitoring**: Queue connectivity checks

### 4. Event Streaming

- **Event sourcing**: Complete event history storage
- **CQRS patterns**: Command-query responsibility segregation
- **Stream processing**: Real-time event processing
- **Projections**: Materialized views from event streams

### 5. API Gateway Integration

- **Service discovery**: Automatic service registration
- **Load balancing**: Multiple algorithms (round-robin, weighted, etc.)
- **Rate limiting**: Configurable rate limits per service
- **Authentication**: JWT and API key support
- **Circuit breakers**: Fault tolerance patterns

## Template Features

### Enhanced Service Configuration

```python
class ServiceConfig(BaseServiceConfig):
    # Phase 2 Infrastructure Configuration
    cache_backend: str = "memory"  # or "redis"
    cache_ttl: int = 300
    message_broker: str = "memory"  # or "rabbitmq", "kafka", "redis"
    event_store_backend: str = "memory"
```

### Comprehensive Health Checks

- Service health monitoring
- Cache connectivity checks
- Message queue health verification
- Event stream monitoring
- API gateway connectivity
- Database health (if enabled)

### Enterprise Patterns Demonstration

The `ProcessData` method showcases Phase 2 infrastructure usage:

- Cache-first data retrieval
- Dynamic configuration loading
- Secure secret management
- Event publishing to streams and queues
- Comprehensive error handling

## Usage Example

### Basic Service Creation

```bash
# Generate a new service with Phase 2 infrastructure
python -m marty_microservices_framework.generators.service_generator \
    --service-name user-management \
    --service-description "User management service" \
    --grpc-port 50051 \
    --use-database
```

### Generated Service Structure

```
user-management/
├── main.py              # Phase 2 infrastructure setup
├── service.py           # Enhanced service implementation
├── config.py           # Service-specific configuration
└── __init__.py
```

### Infrastructure Components Initialization

The service automatically initializes:

1. Configuration and secret management
2. Caching infrastructure
3. Message queue connections
4. Event streaming setup
5. API gateway registration
6. Observability and monitoring

## Configuration Options

### Cache Configuration

```yaml
cache:
  backend: "redis"  # or "memory"
  redis_url: "redis://localhost:6379"
  ttl: 300
  max_size: 1000
```

### Message Queue Configuration

```yaml
messaging:
  broker: "rabbitmq"  # or "kafka", "redis", "memory"
  connection_url: "amqp://guest:guest@localhost:5672/"
  exchange: "user-management"
  queue_prefix: "user-management"
```

### Event Store Configuration

```yaml
events:
  store_backend: "memory"  # or external event store
  stream_prefix: "user-management"
  snapshot_frequency: 100
```

### API Gateway Configuration

```yaml
gateway:
  enabled: true
  discovery_endpoint: "http://localhost:8080/registry"
  health_check_interval: 30
  circuit_breaker:
    failure_threshold: 5
    timeout: 60
```

## Advanced Features

### Dynamic Configuration

Services can reload configuration without restart:

```python
# Configuration updates automatically propagated
new_config = await config_manager.get_config("processing_settings")
```

### Caching Patterns

Multiple caching patterns supported:

```python
# Cache-aside pattern
result = await cache_manager.get(key)
if not result:
    result = await fetch_data()
    await cache_manager.set(key, result)
```

### Event Sourcing

Complete event history with projections:

```python
# Publish events to stream
await event_stream_manager.publish_event(
    stream_name="user-events",
    event_type="UserCreated",
    event_data={"user_id": user_id}
)
```

### Service Discovery

Automatic registration with API gateway:

```python
# Service automatically registers with metadata
await api_gateway.register_service(
    service_name="user-management",
    service_url="grpc://localhost:50051",
    metadata={"version": "1.0.0", "phase2_enabled": True}
)
```

## Monitoring and Observability

### Metrics Collection

- Request/response metrics
- Cache hit/miss ratios
- Message queue depths
- Event processing rates
- Error rates and latencies

### Health Checks

Comprehensive health monitoring:

- Service health status
- Infrastructure component connectivity
- Resource utilization
- Performance indicators

### Distributed Tracing

OpenTelemetry integration:

- Request correlation across services
- Performance bottleneck identification
- Error propagation tracking
- Service dependency mapping

## Production Considerations

### Scalability

- Horizontal scaling support
- Load balancing integration
- Resource optimization
- Performance tuning

### Security

- Secret management encryption
- Authentication integration
- Authorization middleware
- Audit logging

### Reliability

- Circuit breaker patterns
- Retry mechanisms
- Graceful degradation
- Disaster recovery

### Operations

- Configuration management
- Zero-downtime deployments
- Monitoring and alerting
- Log aggregation

This Phase 2 integration provides a complete enterprise microservice framework with production-ready infrastructure components.
