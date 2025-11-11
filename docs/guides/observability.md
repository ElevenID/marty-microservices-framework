# Observability Guide

## Overview

MMF provides comprehensive observability with monitoring, tracing, and logging capabilities using industry-standard tools and practices.

## Quick Setup

### Deploy Infrastructure

```bash
# Deploy observability stack
kubectl apply -f ops/k8s/observability/

# Verify deployment
kubectl get pods -n observability

# Port forward to access dashboards
kubectl port-forward -n observability service/grafana 3000:3000
kubectl port-forward -n observability service/jaeger 16686:16686
```

### Enable in Service

```python
from marty_msf.observability import init_observability
from marty_msf.framework.logging import UnifiedServiceLogger

# Initialize observability
config = create_service_config("your_service")
init_observability(config.observability)

# Create logger with correlation support
logger = UnifiedServiceLogger("your-service")
```

## Components

### 1. Metrics (Prometheus)

- **Application metrics**: Request rates, response times, error rates
- **Business metrics**: Custom domain-specific metrics
- **Infrastructure metrics**: CPU, memory, network usage
- **SLI/SLO tracking**: Service level indicators and objectives

### 2. Distributed Tracing (Jaeger)

- **Automatic instrumentation**: FastAPI, gRPC, HTTP clients, databases
- **Correlation tracking**: Multi-dimensional request context
- **Dependency mapping**: Service interaction visualization
- **Performance analysis**: Bottleneck identification

### 3. Centralized Logging (ELK Stack)

- **Structured logging**: JSON format with correlation IDs
- **Log aggregation**: Centralized collection from all services
- **Search and analysis**: Full-text search and filtering
- **Alert integration**: Log-based alerting

### 4. Dashboards (Grafana)

- **Service overview**: High-level health and performance
- **Plugin debugging**: Plugin-specific troubleshooting
- **Infrastructure monitoring**: System resource usage
- **Business intelligence**: Domain-specific KPIs

### 5. SLO/SLI Framework

- **SLI Collection**: Automated Service Level Indicator measurement
- **Error Budget**: Budget tracking and burn rate analysis
- **Compliance Reporting**: Automated SLO compliance assessment

## Quick Start

### 1. Deploy Monitoring Stack

```bash
# Start Prometheus with enhanced configuration
cd observability/monitoring
docker-compose -f docker-compose.prometheus.yml up -d

# Verify Prometheus is running
curl http://localhost:9090/api/v1/query?query=up
```

### 2. Deploy Distributed Tracing

```bash
# Start Jaeger with Elasticsearch backend
cd observability/tracing
docker-compose -f docker-compose.jaeger.yml up -d

# Verify Jaeger UI
open http://localhost:16686
```

### 3. Deploy Logging Stack

```bash
# Start ELK stack
cd observability/logging
docker-compose -f docker-compose.elk.yml up -d

# Verify Kibana
open http://localhost:5601
```

### 4. Instrument Your Services

```python
# Add observability to your microservices
from marty_microservices_framework.observability.tracing import DistributedTracing
from marty_microservices_framework.observability.logging import create_structured_logger
from marty_microservices_framework.observability.metrics import BusinessMetricsCollector

# Initialize observability
tracing = DistributedTracing("my-service")
logger = create_structured_logger("my-service")
metrics = BusinessMetricsCollector("my-service")

# Use in your application
@tracing.trace_function
async def process_order(order_id: str):
    with logger.context(order_id=order_id):
        logger.info("Processing order", category=LogCategory.BUSINESS)

        # Business metrics
        metrics.track_conversion("order_started", user_id="user123")

        # Your business logic here

        metrics.track_revenue(99.99, "USD", "order_completed")
```

## Configuration

### Prometheus Configuration

```yaml
# observability/monitoring/prometheus/enhanced_prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "recording_rules.yml"
  - "slo_rules.yml"
  - "enhanced_alert_rules.yml"

scrape_configs:
  - job_name: 'kubernetes-services'
    kubernetes_sd_configs:
      - role: service
    relabel_configs:
      - source_labels: [__meta_kubernetes_service_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

### Logging Configuration

```python
# Structured logging setup
from marty_microservices_framework.observability.logging import StructuredLogger

logger = StructuredLogger(
    name="my-service",
    service_name="my-service",
    environment="production",
    log_level=LogLevel.INFO
)

# Context-aware logging
with logger.context(user_id="user123", correlation_id="abc-123"):
    logger.info("User authenticated", category=LogCategory.SECURITY)
    logger.business("Purchase completed",
                   event_type="transaction",
                   amount=99.99,
                   currency="USD")
```

### Tracing Configuration

```python
# OpenTelemetry tracing setup
from marty_microservices_framework.observability.tracing import DistributedTracing

tracing = DistributedTracing(
    service_name="my-service",
    jaeger_endpoint="http://jaeger:14268/api/traces"
)

# Automatic FastAPI instrumentation
app = FastAPI()
tracing.instrument_fastapi(app)

# Manual span creation
@tracing.trace_function
async def complex_operation():
    with tracing.start_span("database_query") as span:
        span.set_attribute("query.table", "users")
        # Database operation
        pass
```

## Monitoring and Alerting

### SLO Configuration

```python
# Define Service Level Objectives
from marty_microservices_framework.observability.slo import SLOManager

slo_manager = SLOManager()

# Register SLOs for your service
slo_manager.register_default_slos("my-service")

# Custom SLO
custom_slo = SLODefinition(
    name="my_service_custom_latency",
    service_name="my-service",
    sli=SLISpecification(
        name="custom_latency",
        sli_type=SLIType.LATENCY,
        description="Custom latency SLI",
        target_threshold=200.0,  # 200ms
        query="histogram_quantile(0.95, rate(custom_duration_bucket[5m]))"
    ),
    target=SLOTarget(
        target=99.5,  # 99.5%
        window="7d",
        priority=SLOPriority.HIGH
    )
)

slo_manager.tracker.register_slo(custom_slo)
```

### Alert Rules

Key alert rules included:

- **Service Health**: High error rates, service unavailability
- **Performance**: Response time degradation, throughput issues
- **SLO Violations**: Error budget burn rate, target breaches
- **Security**: Authentication failures, unauthorized access
- **Business**: Revenue anomalies, conversion drops

### Dashboards

Pre-configured dashboards available in Grafana:

1. **Service Overview**: Service health, request rates, error rates
2. **Performance**: Latency percentiles, throughput, resource usage
3. **SLO Dashboard**: SLO compliance, error budgets, burn rates
4. **Business Metrics**: Revenue, conversions, user engagement
5. **Infrastructure**: Kubernetes cluster health, resource usage

## Log Analysis

### Structured Logging

All logs follow structured JSON format:

```json
{
  "timestamp": "2023-12-01T12:34:56.789Z",
  "level": "INFO",
  "service_name": "user-service",
  "message": "User authenticated successfully",
  "category": "security",
  "context": {
    "user_id": "user123",
    "correlation_id": "abc-123",
    "trace_id": "def456"
  },
  "fields": {
    "authentication_method": "oauth2",
    "source_ip": "192.168.1.100"
  }
}
```

### Log Categories

- **Application**: General application logs
- **Security**: Authentication, authorization, security events
- **Performance**: Response times, resource usage
- **Business**: Revenue, conversions, user actions
- **Infrastructure**: System health, deployments
- **Audit**: Compliance, data access, changes
- **Access**: HTTP requests, API calls
- **Error**: Exceptions, failures, critical issues

### Real-time Analysis

The logging system provides real-time analysis capabilities:

```python
# Real-time log analysis
from marty_microservices_framework.observability.logging.analysis import LogAnalyzer

analyzer = LogAnalyzer()

# Process log stream
async for log_line in log_stream:
    event = await analyzer.process_log_event(log_line)

    # Automatic pattern detection and alerting
    # Security event detection
    # Performance analysis
    # Business intelligence extraction
```

## Business Metrics

### Revenue Tracking

```python
from marty_microservices_framework.observability.metrics import BusinessMetricsCollector

metrics = BusinessMetricsCollector("payment-service")

# Track revenue events
metrics.track_revenue(
    amount=99.99,
    currency="USD",
    event_type="subscription_purchase",
    user_id="user123"
)

# Track conversions
metrics.track_conversion(
    funnel_step="checkout_completed",
    user_id="user123",
    conversion_value=99.99
)

# Track user engagement
metrics.track_user_engagement(
    user_id="user123",
    action="feature_used",
    feature_name="advanced_analytics"
)
```

### Business Health Scoring

```python
# Automatic business health calculation
health_score = metrics.calculate_business_health()
print(f"Business Health Score: {health_score}")

# Health factors:
# - Revenue trends
# - User engagement
# - Conversion rates
# - Retention metrics
# - Feature adoption
```

## Distributed Tracing

### Trace Context Propagation

```python
# Automatic context propagation
from marty_microservices_framework.observability.tracing import DistributedTracing

tracing = DistributedTracing("order-service")

@tracing.trace_function
async def process_order(order_id: str):
    # Trace context automatically propagated

    # Call another service - trace context propagated
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://payment-service/charge",
            json={"order_id": order_id},
            headers=tracing.get_trace_headers()  # Propagate context
        ) as response:
            # Response will be part of the same trace
            pass
```

### Custom Spans

```python
# Custom span creation
with tracing.start_span("database_operation") as span:
    span.set_attribute("db.table", "orders")
    span.set_attribute("db.query", "SELECT * FROM orders WHERE id = ?")

    # Database operation
    result = await db.fetch_order(order_id)

    span.set_attribute("db.rows_affected", len(result))

    if not result:
        span.set_status(StatusCode.ERROR, "Order not found")
```

## Security and Compliance

### Security Event Monitoring

```python
# Security event logging
logger.security(
    "Failed login attempt",
    security_event="authentication_failure",
    user_id="user123",
    source_ip="192.168.1.100"
)

# Audit logging
logger.audit(
    "User data accessed",
    action="data_read",
    resource="user_profile",
    user_id="admin123",
    success=True
)
```

### Data Privacy

- Log data retention policies
- PII data masking
- Audit trail compliance
- GDPR compliance features

## Performance Optimization

### Query Optimization

```yaml
# Prometheus recording rules for efficient queries
groups:
  - name: sli_calculations
    interval: 30s
    rules:
      - record: marty:sli:availability:5m
        expr: sum(rate(http_requests_total{code!~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

      - record: marty:sli:latency_p95:5m
        expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

### Log Processing Optimization

- Structured logging for efficient parsing
- Log sampling for high-volume services
- Asynchronous log processing
- Buffer management and backpressure handling

## Troubleshooting

### Common Issues

1. **High Memory Usage in Elasticsearch**

   ```bash
   # Adjust JVM heap size
   ES_JAVA_OPTS="-Xms2g -Xmx2g"
   ```

2. **Logstash Processing Delays**

   ```yaml
   # Increase pipeline workers
   pipeline.workers: 8
   pipeline.batch.size: 2000
   ```

3. **Prometheus High Cardinality**

   ```yaml
   # Limit metric cardinality
   metric_relabel_configs:
     - source_labels: [__name__]
       regex: 'high_cardinality_metric.*'
       action: drop
   ```

4. **Jaeger Storage Issues**

   ```bash
   # Clean old traces
   curl -X DELETE "http://elasticsearch:9200/jaeger-*-$(date -d '7 days ago' +%Y-%m-%d)*"
   ```

### Health Checks

```bash
# Prometheus health
curl http://localhost:9090/-/healthy

# Elasticsearch health
curl http://localhost:9200/_cluster/health

# Jaeger health
curl http://localhost:14269/

# Kibana health
curl http://localhost:5601/api/status
```

## Integration Examples

### FastAPI Integration

```python
from fastapi import FastAPI
from marty_microservices_framework.observability.logging import setup_fastapi_logging
from marty_microservices_framework.observability.tracing import DistributedTracing

app = FastAPI()

# Setup observability
logger = setup_fastapi_logging(app, "my-service")
tracing = DistributedTracing("my-service")
tracing.instrument_fastapi(app)

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    with logger.context(user_id=user_id):
        logger.info("Fetching user data")

        # Business logic with automatic tracing
        user = await fetch_user(user_id)

        logger.business("User data accessed",
                       event_type="data_access",
                       entity_type="user",
                       entity_id=user_id)

        return user
```

### gRPC Integration

```python
from marty_microservices_framework.observability.tracing.examples import TracedGRPCService

class UserService(TracedGRPCService):
    def __init__(self):
        super().__init__("user-service")

    async def GetUser(self, request, context):
        with self.start_span("get_user") as span:
            span.set_attribute("user.id", request.user_id)

            # Service logic
            user = await self.fetch_user(request.user_id)

            return UserResponse(user=user)
```

## Best Practices

### Observability Strategy

1. **Three Pillars Approach**: Metrics, Logs, Traces working together
2. **Context Correlation**: Use correlation IDs across all telemetry
3. **Sampling Strategy**: Balance observability with performance
4. **Alert Hierarchy**: Critical, Warning, Info alert levels
5. **SLO-driven Monitoring**: Focus on user experience

### Development Workflow

1. **Observability First**: Add observability during development
2. **Local Testing**: Use docker-compose for local observability stack
3. **Staging Validation**: Validate observability in staging environment
4. **Production Monitoring**: Continuous monitoring and alerting

### Security Considerations

1. **Data Classification**: Classify and protect sensitive log data
2. **Access Control**: Role-based access to observability tools
3. **Audit Trail**: Audit access to sensitive monitoring data
4. **Encryption**: Encrypt telemetry data in transit and at rest

## Next Steps

Phase 2 Enhanced Observability is now complete! The system provides:

✅ **Advanced Monitoring** with Prometheus, recording rules, and intelligent alerting
✅ **Distributed Tracing** with OpenTelemetry and Jaeger
✅ **Centralized Logging** with ELK/EFK stack and real-time analysis
✅ **Business Intelligence** with comprehensive metrics collection
✅ **SLO/SLI Tracking** with automated compliance monitoring

**Ready for Phase 3: Advanced Security & Compliance** 🚀

This phase will build upon the observability foundation to implement:

- Zero-trust security architecture
- Advanced threat detection
- Compliance automation
- Security monitoring integration
- Identity and access management

The observability infrastructure from Phase 2 will provide the visibility needed for effective security monitoring and compliance reporting in Phase 3.
