# Marty Microservices Framework - Observability

This document describes how to use the unified observability features in the Marty Microservices Framework.

## Overview

The framework provides unified metrics and tracing setup to eliminate per-service duplication. All services can use the same observability infrastructure with automatic HTTP/gRPC request metrics, custom application metrics, and distributed tracing.

## Quick Start

### Basic Service Initialization

```python
from marty_microservices_framework import init_observability

# Initialize all observability components
monitor = init_observability("my-service")

# Your service code here...

# Cleanup on shutdown
monitor.stop_monitoring()
```

### Using Custom Metrics

```python
from marty_microservices_framework import get_framework_metrics

# Get framework metrics instance
metrics = get_framework_metrics("my-service")

# Record document processing
metrics.record_document_processed("passport", "success")

# Record processing time
metrics.record_processing_time("passport", 0.5)

# Set gauge values
metrics.set_active_connections(10)
metrics.set_queue_size("processing_queue", 5)
```

### HTTP/gRPC Metrics Middleware

#### FastAPI Services

```python
from fastapi import FastAPI
from marty_microservices_framework import create_fastapi_metrics_middleware

app = FastAPI()
app.middleware("http")(create_fastapi_metrics_middleware("my-service"))
```

#### gRPC Services

```python
from marty_microservices_framework import create_grpc_metrics_interceptor

# Add to your gRPC server interceptors
interceptor = create_grpc_metrics_interceptor("my-service")
server = grpc.aio.server(interceptors=[interceptor])
```

### Manual Tracing

```python
from marty_microservices_framework import traced_operation, trace_function

# Context manager for operations
with traced_operation("database_query", table="users") as span:
    span.set_attribute("query_type", "select")
    # Your database code here

# Decorator for functions
@trace_function("my_operation")
def my_function():
    pass
```

## Metrics Available

### Automatic Request Metrics

- `mmf_requests_total`: Total requests (counter)
- `mmf_request_duration_seconds`: Request duration (histogram)
- `mmf_errors_total`: Total errors (counter)

### Custom Application Metrics

- `mmf_documents_processed_total`: Documents processed (counter)
- `mmf_processing_duration_seconds`: Processing time (histogram)
- `mmf_active_connections`: Active connections (gauge)
- `mmf_queue_size`: Queue sizes (gauge)

### System Metrics

- CPU, memory, disk, and network usage metrics

## Configuration

Observability is configured via environment variables:

### Tracing (OpenTelemetry)

- `OTEL_TRACING_ENABLED`: Enable/disable tracing (default: false)
- `OTEL_SERVICE_NAME`: Service name
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP endpoint (default: localhost:4317)
- `OTEL_CONSOLE_EXPORT`: Enable console export (default: false)

### Metrics

Metrics use Prometheus client library. No additional configuration needed - metrics are automatically registered.

## Migration from Per-Service Setup

To migrate from per-service metrics:

1. Remove custom Prometheus setup code
2. Replace with `init_observability()` call
3. Use `get_framework_metrics()` for custom metrics
4. Add metrics middleware to HTTP/gRPC servers

The framework handles all the heavy lifting for metrics collection and tracing setup.
