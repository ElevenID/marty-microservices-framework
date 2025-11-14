# Enhanced Monitoring and Observability Framework

A comprehensive monitoring solution for microservices that provides advanced metrics collection, distributed tracing, health checks, business metrics, and alert management.

## 🎯 Features

- **Prometheus Integration**: Production-ready metrics collection with Prometheus
- **Distributed Tracing**: OpenTelemetry integration with Jaeger support
- **Health Check Framework**: Comprehensive health monitoring for services and dependencies
- **Custom Business Metrics**: Track business KPIs and SLAs
- **Alert Management**: Rule-based alerting with multiple notification channels
- **Middleware Integration**: Automatic instrumentation for FastAPI and gRPC
- **Performance Monitoring**: Request timing, error rates, and resource utilization
- **SLA Monitoring**: Track and alert on service level agreements

## 🚀 Quick Start

### Basic Setup

```python
from marty_msf.framework.monitoring import initialize_monitoring

# Initialize monitoring with Prometheus
manager = initialize_monitoring(
    service_name="my-service",
    use_prometheus=True,
    jaeger_endpoint="http://localhost:14268/api/traces"
)

# Record metrics
await manager.record_request("GET", "/api/users", 200, 0.150)
await manager.record_error("ValidationError")
await manager.set_active_connections(15)
```

### FastAPI Integration

```python
from fastapi import FastAPI
from marty_msf.framework.monitoring import setup_fastapi_monitoring

app = FastAPI()

# Add monitoring middleware
setup_fastapi_monitoring(app)

# Automatic metrics collection for all endpoints
@app.get("/api/users/{user_id}")
async def get_user(user_id: str):
    return {"id": user_id, "name": f"User {user_id}"}
```

## 📊 Core Components

### 1. Monitoring Manager

Central manager for all monitoring activities:

```python
from marty_msf.framework.monitoring import MonitoringManager, initialize_monitoring

# Initialize
manager = initialize_monitoring("my-service")

# Record metrics
await manager.record_request("POST", "/api/orders", 201, 0.250)
await manager.record_error("DatabaseError")

# Get service health
health = await manager.get_service_health()
print(f"Service status: {health['status']}")
```

### 2. Health Checks

Comprehensive health monitoring:

```python
from marty_msf.framework.monitoring import (
    DatabaseHealthCheck,
    RedisHealthCheck,
    ExternalServiceHealthCheck
)

# Add health checks
manager.add_health_check(
    DatabaseHealthCheck("database", db_session_factory)
)

manager.add_health_check(
    RedisHealthCheck("redis", redis_client)
)

manager.add_health_check(
    ExternalServiceHealthCheck("api", "https://api.example.com/health")
)

# Check health
results = await manager.perform_health_checks()
```

### 3. Custom Business Metrics

Track business KPIs and SLAs:

```python
from marty_msf.framework.monitoring import (
    initialize_custom_metrics,
    BusinessMetric,
    record_user_registration,
    record_transaction_result
)

# Initialize custom metrics
custom_metrics = initialize_custom_metrics()

# Register business metrics
custom_metrics.business_metrics.register_metric(
    BusinessMetric(
        name="order_processing_time",
        description="Time to process orders",
        unit="seconds",
        sla_target=30.0,
        sla_operator="<="
    )
)

# Record metrics
await record_user_registration("web", "email")
await record_transaction_result(success=True)
custom_metrics.record_business_metric("order_processing_time", 25.5)
```

### 4. Alert Management

Rule-based alerting system:

```python
from marty_msf.framework.monitoring import AlertRule, AlertLevel, MetricAggregation

# Add alert rules
custom_metrics.add_alert_rule(
    AlertRule(
        name="high_error_rate",
        metric_name="error_rate",
        condition=">",
        threshold=5.0,
        level=AlertLevel.CRITICAL,
        description="Error rate above 5%",
        aggregation=MetricAggregation.AVERAGE
    )
)

# Subscribe to alerts
def alert_handler(alert):
    print(f"ALERT: {alert.message}")
    # Send to Slack, email, PagerDuty, etc.

custom_metrics.add_alert_subscriber(alert_handler)
```

## 🔧 Configuration

### Monitoring Middleware Configuration

```python
from marty_msf.framework.monitoring import MonitoringMiddlewareConfig

config = MonitoringMiddlewareConfig()

# Metrics collection
config.collect_request_metrics = True
config.collect_response_metrics = True
config.collect_error_metrics = True

# Performance
config.slow_request_threshold_seconds = 1.0
config.sample_rate = 1.0  # Monitor 100% of requests

# Health endpoints
config.health_endpoint = "/health"
config.metrics_endpoint = "/metrics"
config.detailed_health_endpoint = "/health/detailed"

# Distributed tracing
config.enable_tracing = True
config.trace_all_requests = True

# Filtering
config.exclude_paths = ["/favicon.ico", "/robots.txt"]
```

## 📈 Metrics Types

### Default Service Metrics

Automatically collected:

- `requests_total` - Total number of requests
- `request_duration_seconds` - Request duration histogram
- `active_connections` - Number of active connections
- `errors_total` - Total number of errors
- `health_check_duration` - Health check duration

### Custom Metrics

Define your own metrics:

```python
from marty_msf.framework.monitoring import MetricDefinition, MetricType

# Define custom metric
custom_metric = MetricDefinition(
    name="business_transactions",
    metric_type=MetricType.COUNTER,
    description="Number of business transactions",
    labels=["transaction_type", "status"]
)

# Register with monitoring manager
manager.register_metric(custom_metric)

# Use the metric
await manager.collector.increment_counter(
    "business_transactions",
    labels={"transaction_type": "payment", "status": "success"}
)
```

## 🏥 Health Checks

### Built-in Health Checks

#### Database Health Check

```python
from marty_msf.framework.monitoring import DatabaseHealthCheck

health_check = DatabaseHealthCheck("database", db_session_factory)
manager.add_health_check(health_check)
```

#### Redis Health Check

```python
from marty_msf.framework.monitoring import RedisHealthCheck

health_check = RedisHealthCheck("redis", redis_client)
manager.add_health_check(health_check)
```

#### External Service Health Check

```python
from marty_msf.framework.monitoring import ExternalServiceHealthCheck

health_check = ExternalServiceHealthCheck(
    "payment_api",
    "https://api.payment.com/health",
    timeout_seconds=5.0
)
manager.add_health_check(health_check)
```

### Custom Health Checks

```python
from marty_msf.framework.monitoring import HealthCheck, HealthCheckResult, HealthStatus

class CustomHealthCheck(HealthCheck):
    def __init__(self, name: str):
        super().__init__(name)

    async def check(self) -> HealthCheckResult:
        # Your custom health check logic
        try:
            # Check your service
            is_healthy = await check_my_service()

            if is_healthy:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Service is operating normally"
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message="Service is experiencing issues"
                )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}"
            )

# Add custom health check
manager.add_health_check(CustomHealthCheck("my_service"))
```

## 📊 Business Metrics & SLA Monitoring

### Predefined Business Metrics

The framework includes common business metrics:

```python
# User activity
await record_user_registration("mobile", "oauth")

# Transaction monitoring
await record_transaction_result(success=True)

# Performance SLA
await record_response_time_sla(response_time_ms=450, sla_threshold_ms=1000)

# Error tracking
await record_error_rate(error_occurred=False)

# Revenue tracking
await record_revenue(amount=99.99, currency="USD", source="web")
```

### SLA Monitoring

```python
# Register metric with SLA
metric = BusinessMetric(
    name="api_response_time",
    description="API response time",
    unit="milliseconds",
    sla_target=500.0,
    sla_operator="<="
)

custom_metrics.business_metrics.register_metric(metric)

# Check SLA status
sla_status = custom_metrics.business_metrics.evaluate_sla("api_response_time")
print(f"SLA Met: {sla_status['sla_met']}")
```

## 🚨 Alerting

### Alert Rules

```python
from marty_msf.framework.monitoring import AlertRule, AlertLevel, MetricAggregation

# Performance alert
performance_alert = AlertRule(
    name="slow_response_time",
    metric_name="response_time_sla",
    condition="<",
    threshold=95.0,
    level=AlertLevel.WARNING,
    description="Response time SLA below 95%",
    aggregation=MetricAggregation.AVERAGE,
    window_minutes=5
)

# Error rate alert
error_alert = AlertRule(
    name="high_error_rate",
    metric_name="error_rate",
    condition=">",
    threshold=2.0,
    level=AlertLevel.CRITICAL,
    description="Error rate above 2%",
    evaluation_interval_seconds=30
)

custom_metrics.add_alert_rule(performance_alert)
custom_metrics.add_alert_rule(error_alert)
```

### Alert Notifications

```python
def email_alert_handler(alert):
    """Send email alert."""
    send_email(
        to="ops@company.com",
        subject=f"Alert: {alert.rule_name}",
        body=f"{alert.message}\nValue: {alert.metric_value}\nThreshold: {alert.threshold}"
    )

def slack_alert_handler(alert):
    """Send Slack alert."""
    send_slack_message(
        channel="#alerts",
        text=f"🚨 {alert.level.value.upper()}: {alert.message}"
    )

def pagerduty_alert_handler(alert):
    """Trigger PagerDuty incident."""
    if alert.level == AlertLevel.CRITICAL:
        trigger_pagerduty_incident(
            service_key="your-service-key",  # pragma: allowlist secret
            description=alert.message,
            details={"metric_value": alert.metric_value}
        )

# Subscribe to alerts
custom_metrics.add_alert_subscriber(email_alert_handler)
custom_metrics.add_alert_subscriber(slack_alert_handler)
custom_metrics.add_alert_subscriber(pagerduty_alert_handler)
```

## 🔍 Distributed Tracing

### Automatic Instrumentation

```python
# Enable tracing during initialization
manager = initialize_monitoring(
    service_name="my-service",
    jaeger_endpoint="http://localhost:14268/api/traces"
)

# FastAPI automatic instrumentation
setup_fastapi_monitoring(app)  # Traces all requests automatically
```

### Manual Instrumentation

```python
# Trace specific operations
if manager.tracer:
    async with manager.tracer.trace_operation(
        "database_query",
        {"query": "SELECT * FROM users", "table": "users"}
    ) as span:
        result = await execute_query()
        span.set_attribute("rows_returned", len(result))
```

### Function Decorators

```python
from marty_msf.framework.monitoring import monitor_async_function

@monitor_async_function(
    operation_name="process_order",
    record_duration=True,
    record_errors=True
)
async def process_order(order_id: str):
    # Function is automatically traced and monitored
    return await do_order_processing(order_id)
```

## 📊 Metrics Endpoints

The framework automatically provides monitoring endpoints:

### Health Check Endpoints

- `GET /health` - Simple health status
- `GET /health/detailed` - Detailed health information

Example response:

```json
{
  "service": "my-service",
  "status": "healthy",
  "timestamp": "2025-10-07T10:30:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection healthy",
      "duration_ms": 5.2
    },
    "external_api": {
      "status": "healthy",
      "message": "External service responding (HTTP 200)",
      "duration_ms": 150.3
    }
  },
  "metrics": {
    "request_count": 1250,
    "error_count": 12,
    "active_connections": 8,
    "avg_request_duration": 0.145
  }
}
```

### Metrics Endpoint

- `GET /metrics` - Prometheus metrics

Example output:

```
# HELP microservice_requests_total Total number of requests
# TYPE microservice_requests_total counter
microservice_requests_total{method="GET",endpoint="/api/users",status="200"} 1250
microservice_requests_total{method="POST",endpoint="/api/users",status="201"} 89

# HELP microservice_request_duration_seconds Request duration in seconds
# TYPE microservice_request_duration_seconds histogram
microservice_request_duration_seconds_bucket{method="GET",endpoint="/api/users",le="0.1"} 800
microservice_request_duration_seconds_bucket{method="GET",endpoint="/api/users",le="0.5"} 1200
```

## 🔧 Integration Examples

### Complete FastAPI Service

```python
from fastapi import FastAPI
from marty_msf.framework.monitoring import (
    initialize_monitoring,
    initialize_custom_metrics,
    setup_fastapi_monitoring,
    MonitoringMiddlewareConfig,
    DatabaseHealthCheck,
    AlertRule,
    AlertLevel
)

app = FastAPI()

@app.on_event("startup")
async def startup():
    # Initialize monitoring
    monitoring_manager = initialize_monitoring(
        service_name="user-service",
        use_prometheus=True,
        jaeger_endpoint="http://jaeger:14268/api/traces"
    )

    # Initialize custom metrics
    custom_metrics = initialize_custom_metrics()

    # Add health checks
    monitoring_manager.add_health_check(
        DatabaseHealthCheck("database", get_db_session)
    )

    # Add alert rules
    custom_metrics.add_alert_rule(
        AlertRule(
            name="high_error_rate",
            metric_name="error_rate",
            condition=">",
            threshold=5.0,
            level=AlertLevel.CRITICAL,
            description="User service error rate too high"
        )
    )

    # Setup monitoring middleware
    config = MonitoringMiddlewareConfig()
    config.slow_request_threshold_seconds = 0.5
    setup_fastapi_monitoring(app, config)

    # Start custom metrics monitoring
    await custom_metrics.start_monitoring()

@app.on_event("shutdown")
async def shutdown():
    custom_metrics = get_custom_metrics_manager()
    if custom_metrics:
        await custom_metrics.stop_monitoring()
```

## 📋 Best Practices

### 1. Metric Naming

Follow Prometheus naming conventions:

```python
# Good
user_registrations_total
order_processing_duration_seconds
payment_success_rate

# Avoid
userRegistrations
Order-Processing-Time
payment_success_percentage
```

### 2. Label Usage

Use labels for high-cardinality dimensions:

```python
# Good - finite set of values
labels={"method": "GET", "status": "200", "endpoint": "/api/users"}

# Avoid - infinite cardinality
labels={"user_id": "12345", "request_id": "abcd-1234"}
```

### 3. Health Check Design

```python
# Design health checks to be:
# - Fast (< 5 seconds)
# - Reliable
# - Indicative of service health

class GoodHealthCheck(HealthCheck):
    async def check(self) -> HealthCheckResult:
        try:
            # Quick, essential check
            await db.execute("SELECT 1")
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Database accessible"
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database check failed: {str(e)}"
            )
```

### 4. Alert Rule Design

```python
# Effective alert rules:
# - Have clear thresholds
# - Include context
# - Are actionable

AlertRule(
    name="database_connection_failure",
    metric_name="database_health_status",
    condition="==",
    threshold=0,  # 0 = unhealthy, 1 = healthy
    level=AlertLevel.CRITICAL,
    description="Database connection failed - immediate action required",
    window_minutes=2,  # Short window for critical issues
    evaluation_interval_seconds=30
)
```

## 📦 Dependencies

Required packages:

```bash
# Core monitoring
pip install prometheus_client

# Distributed tracing (optional)
pip install opentelemetry-api opentelemetry-sdk
pip install opentelemetry-exporter-jaeger-thrift
pip install opentelemetry-instrumentation-fastapi
pip install opentelemetry-instrumentation-grpc

# FastAPI integration (optional)
pip install 'fastapi[all]'

# Redis health checks (optional)
pip install aioredis

# Database health checks (optional)
pip install sqlalchemy
```

## 🚀 Performance

The monitoring framework is designed for production use:

- **Low Overhead**: < 1ms per request for metric collection
- **Asynchronous**: Non-blocking metric recording
- **Efficient**: Batch processing for database operations
- **Scalable**: Supports high-throughput services
- **Memory Efficient**: Configurable metric buffers

## 📖 Examples

See `examples.py` for comprehensive usage examples:

- Basic monitoring setup
- Custom business metrics
- FastAPI integration
- Advanced health checks
- Performance monitoring
- Alerting and notifications

Run examples:

```bash
python -m framework.monitoring.examples
```

## 🔗 Integration with Existing Tools

### Grafana Dashboards

Use Prometheus metrics with Grafana:

```
- Request rate: rate(microservice_requests_total[5m])
- Error rate: rate(microservice_errors_total[5m]) / rate(microservice_requests_total[5m])
- Response time: histogram_quantile(0.95, microservice_request_duration_seconds_bucket)
```

### Alertmanager

Configure Prometheus Alertmanager rules:

```yaml
groups:
- name: microservice_alerts
  rules:
  - alert: HighErrorRate
    expr: rate(microservice_errors_total[5m]) / rate(microservice_requests_total[5m]) > 0.05
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
```

This monitoring framework provides enterprise-grade observability for your microservices, enabling you to track performance, detect issues, and maintain service reliability.
