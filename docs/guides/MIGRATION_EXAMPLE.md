# Migration Example: Converting Marty Services to Use MMF Observability

This example shows how to migrate existing Marty services to use the unified Marty Microservices Framework observability features.

## Before: Per-Service Metrics Setup

Here's what a typical Marty service looks like currently with per-service metrics:

```python
# OLD: Per-service metrics setup (trust_svc/metrics.py)
from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest

class TrustServiceMetrics:
    def __init__(self):
        # Service info
        self.service_info = Info("trust_service_info", "Trust service information")

        # Request metrics
        self.requests_total = Counter(
            "trust_grpc_requests_total",
            "Total gRPC requests",
            ["method", "status"]
        )

        self.request_duration = Histogram(
            "trust_grpc_request_duration_seconds",
            "gRPC request duration",
            ["method"]
        )

        # Custom business metrics
        self.certificates_processed = Counter(
            "trust_certificates_processed_total",
            "Total certificates processed",
            ["cert_type", "status"]
        )

        # Health metrics
        self.health_status = Gauge(
            "trust_service_health",
            "Service health status"
        )

    def record_request(self, method: str, status: str, duration: float):
        self.requests_total.labels(method=method, status=status).inc()
        self.request_duration.labels(method=method).observe(duration)

    def record_certificate_processed(self, cert_type: str, status: str):
        self.certificates_processed.labels(cert_type=cert_type, status=status).inc()

# OLD: Service main.py with manual setup
from trust_svc.metrics import TrustServiceMetrics
from marty_common.metrics_server import MetricsServer

def main():
    metrics = TrustServiceMetrics()
    metrics_server = MetricsServer("trust-service", 8080)

    # Manual health checks
    metrics_server.add_health_check("database", check_database_connection)

    # Start metrics server
    metrics_server.start()

    # Start gRPC server with manual interceptor
    server = grpc.aio.server(interceptors=[MetricsInterceptor(metrics)])
    # ... rest of service setup
```

## After: Using MMF Observability

Here's how the same service looks using the Marty Microservices Framework:

```python
# NEW: Using MMF observability
from marty_microservices_framework import (
    init_observability,
    get_framework_metrics,
    create_grpc_metrics_interceptor,
    traced_operation
)

def main():
    # Initialize all observability with one call
    monitor = init_observability("trust-service")

    # Get standardized metrics instance
    metrics = get_framework_metrics("trust-service")

    # Set service information
    metrics.set_service_info(version="1.2.0", build_date="2025-10-09")

    # Create gRPC server with automatic metrics
    interceptor = create_grpc_metrics_interceptor("trust-service")
    server = grpc.aio.server(interceptors=[interceptor])

    # Add custom business logic
    add_TrustServicer_to_server(TrustServicer(metrics), server)

    # Start server
    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)
    await server.start()

    # Cleanup on shutdown
    await server.wait_for_termination()
    monitor.stop_monitoring()

class TrustServicer:
    def __init__(self, metrics):
        self.metrics = metrics

    async def ProcessCertificate(self, request, context):
        # Automatic request metrics are handled by interceptor

        # Record custom business metrics
        with traced_operation("process_certificate", cert_type=request.cert_type):
            try:
                # Process certificate
                result = await self.process_certificate_logic(request)

                # Record successful processing
                self.metrics.record_document_processed("certificate", "success")

                return result

            except Exception as e:
                # Record error
                self.metrics.record_document_processed("certificate", "error")
                raise
```

## Key Benefits of Migration

### 1. **Eliminated Duplication**

- No more per-service Prometheus setup
- No more custom metrics server code
- No more manual gRPC interceptor implementation

### 2. **Standardized Metrics**

- All services use consistent metric names (`mmf_*` prefix)
- Standardized labels include `service` name automatically
- Common business metrics like `documents_processed_total`

### 3. **Automatic Instrumentation**

- HTTP/gRPC request metrics collected automatically
- OpenTelemetry tracing with zero configuration
- Health checks with sensible defaults

### 4. **Framework-Level Configuration**

- Tracing enabled/disabled via environment variables
- Metrics format and endpoints handled by framework
- Service discovery and registration patterns

## Migration Steps

### Step 1: Replace Service Metrics

```python
# Remove old imports
# from trust_svc.metrics import TrustServiceMetrics
# from marty_common.metrics_server import MetricsServer

# Add new imports
from marty_microservices_framework import init_observability, get_framework_metrics
```

### Step 2: Initialize Observability

```python
# Replace manual setup
monitor = init_observability("your-service-name")
metrics = get_framework_metrics("your-service-name")
```

### Step 3: Add Middleware

```python
# For gRPC services
from marty_microservices_framework import create_grpc_metrics_interceptor
interceptor = create_grpc_metrics_interceptor("your-service-name")
server = grpc.aio.server(interceptors=[interceptor])

# For FastAPI services (if any)
from marty_microservices_framework import create_fastapi_metrics_middleware
app.middleware("http")(create_fastapi_metrics_middleware("your-service-name"))
```

### Step 4: Replace Custom Metrics

```python
# Old way
self.certificates_processed.labels(cert_type=cert_type, status=status).inc()

# New way
metrics.record_document_processed(cert_type, status)

# Or create custom metrics
custom_counter = metrics.create_counter(
    "certificates_validated_total",
    "Total certificates validated",
    ["validation_type"]
)
custom_counter.labels(validation_type="x509", service="trust-service").inc()
```

### Step 5: Add Tracing (Optional)

```python
from marty_microservices_framework import traced_operation

with traced_operation("validate_certificate", cert_type="x509") as span:
    if span:  # Check if tracing is available
        span.set_attribute("certificate_id", cert_id)
    result = validate_certificate(cert_data)
```

## Environment Configuration

Set these environment variables to configure observability:

```bash
# Enable tracing
export OTEL_TRACING_ENABLED=true
export OTEL_SERVICE_NAME=trust-service
export OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317

# For development
export OTEL_CONSOLE_EXPORT=true
```

## Expected Results

After migration, services will have:

1. **Automatic Metrics**:
   - `mmf_requests_total{service="trust-service", method="/ProcessCertificate", status="OK"}`
   - `mmf_request_duration_seconds{service="trust-service", method="/ProcessCertificate"}`
   - `mmf_documents_processed_total{service="trust-service", document_type="certificate", status="success"}`

2. **Distributed Tracing**:
   - Automatic spans for all gRPC calls
   - Custom spans for business operations
   - Integration with Jaeger/Zipkin

3. **Health Monitoring**:
   - Default health checks (memory, disk, basic connectivity)
   - Custom health checks can be added easily
   - Prometheus health endpoint at `/health`

4. **System Metrics**:
   - CPU, memory, disk usage automatically collected
   - Network I/O statistics

This migration eliminates approximately 200-300 lines of boilerplate code per service while providing more comprehensive observability features.
