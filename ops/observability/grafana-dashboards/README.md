# MMF Observability Grafana Dashboards

This directory contains standardized Grafana dashboard templates for Marty Microservices Framework (MMF) services with comprehensive OpenTelemetry integration.

## Available Dashboards

### 1. MMF Service Overview (`mmf-service-overview.json`)

**Purpose**: Primary operational dashboard for service monitoring
**Key Features**:

- Request rate, error rate, and response time metrics
- Service health and uptime tracking
- Resource utilization (CPU, memory)
- Database connection pool monitoring
- Active request tracking

**Target Audience**: DevOps teams, SREs, service owners

### 2. MMF Distributed Tracing Analysis (`mmf-tracing-analysis.json`)

**Purpose**: Deep-dive tracing analysis for debugging distributed requests
**Key Features**:

- Trace duration percentiles across services
- Service dependency mapping
- Correlation ID coverage tracking
- Span error analysis
- Cross-service communication patterns
- Direct link to Jaeger UI

**Target Audience**: Developers, debugging teams, performance engineers

### 3. MMF Plugin Developer Troubleshooting (`mmf-plugin-troubleshooting.json`)

**Purpose**: Specialized dashboard for plugin developers and troubleshooting
**Key Features**:

- Plugin lifecycle event tracking
- Plugin operation performance metrics
- Dependency health monitoring
- Error log analysis with Loki integration
- Resource consumption by plugin
- Correlation ID tracking for plugin interactions

**Target Audience**: Plugin developers, framework maintainers

## Installation Instructions

### Prerequisites

- Grafana instance with Prometheus and Loki data sources configured
- OpenTelemetry metrics being collected by Prometheus
- Logs flowing to Loki (optional for some dashboards)

### Import Steps

1. **Via Grafana UI**:

   ```bash
   # Navigate to Grafana -> Dashboards -> Import
   # Upload the JSON file or paste the contents
   # Configure data source mappings
   ```

2. **Via API**:

   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -d @mmf-service-overview.json \
     http://your-grafana-instance/api/dashboards/db
   ```

3. **Via Provisioning** (Recommended for automated deployments):

   ```yaml
   # /etc/grafana/provisioning/dashboards/mmf-dashboards.yaml
   apiVersion: 1
   providers:
     - name: 'mmf-dashboards'
       orgId: 1
       folder: 'MMF'
       folderUid: 'mmf'
       type: file
       disableDeletion: false
       updateIntervalSeconds: 10
       allowUiUpdates: true
       options:
         path: /var/lib/grafana/dashboards/mmf
   ```

### Data Source Configuration

The dashboards expect the following data source variables:

- `${DS_PROMETHEUS}`: Prometheus data source UID
- `${DS_LOKI}`: Loki data source UID (for plugin troubleshooting dashboard)

## Metrics Requirements

### Standard MMF Service Metrics

The dashboards expect these metrics to be available:

```prometheus
# HTTP Metrics
http_requests_total{service_name, method, endpoint, status}
http_request_duration_seconds{service_name, method, endpoint}
http_requests_active{service_name}

# Service Health
up{service_name, instance}

# Resource Metrics
process_cpu_seconds_total{service_name}
process_resident_memory_bytes{service_name}

# Database Metrics
db_connections_active{service_name}
db_connections_idle{service_name}
db_connections_total{service_name}

# Tracing Metrics
trace_duration_seconds{service_name}
traces_active{service_name}
spans_created_total{service_name}
spans_error_total{service_name}
operation_duration_seconds{service_name, operation_name}
service_calls_total{source_service, target_service}

# Plugin Metrics
plugin_status{service_name, plugin_name, plugin_version}
plugin_lifecycle_events_total{service_name, plugin_name, event_type}
plugin_operation_duration_seconds{service_name, plugin_name, operation}
plugin_dependency_health{service_name, plugin_name, dependency_name}
plugin_memory_usage_bytes{service_name, plugin_name}
plugin_cpu_usage_percent{service_name, plugin_name}

# Correlation Tracking
requests_with_correlation_id{service_name}
requests_total{service_name}
plugin_requests_with_correlation{service_name, plugin_name}
plugin_requests_total{service_name, plugin_name}
```

### Log Requirements (Loki)

For the plugin troubleshooting dashboard:

```json
{
  "service_name": "your-service",
  "level": "ERROR|WARN|INFO",
  "message": "log message",
  "correlation_id": "correlation-id",
  "plugin_name": "plugin-name",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Customization

### Adding Custom Panels

1. Export the dashboard as JSON
2. Add your custom panel configuration
3. Re-import the dashboard

### Service-Specific Customizations

Each dashboard supports service filtering via the `$service` template variable. You can:

- Create service-specific copies
- Add service-specific thresholds
- Include service-specific alerting rules

### Alerting Integration

The dashboards include threshold configurations that can be used with Grafana alerting:

- Response time thresholds: 50ms (warning), 200ms (critical)
- Error rate thresholds: 1% (warning), 5% (critical)
- Resource usage thresholds: 70% (warning), 90% (critical)

## Best Practices

### Dashboard Organization

- Use folder structure: `MMF/Service Overview`, `MMF/Debugging`, etc.
- Tag dashboards consistently: `marty-msf`, `microservices`, `opentelemetry`
- Set appropriate refresh intervals (30s-5m depending on use case)

### Performance Considerations

- Use appropriate time ranges (1h for operations, 24h for trends)
- Limit the number of series in high-cardinality queries
- Use recording rules for complex calculations

### Team Access

- Service Overview: Operations team, on-call engineers
- Tracing Analysis: Development teams, debugging specialists
- Plugin Troubleshooting: Plugin developers, framework team

## Troubleshooting

### Common Issues

1. **No Data Displayed**:
   - Verify data source configuration
   - Check metric names match your instrumentation
   - Ensure time range includes data

2. **High Query Load**:
   - Reduce dashboard refresh frequency
   - Optimize PromQL queries
   - Use recording rules for complex calculations

3. **Missing Correlations**:
   - Verify correlation ID implementation
   - Check label consistency across services
   - Ensure proper trace context propagation

### Support

For issues with the dashboards:

1. Check the MMF documentation
2. Verify your observability implementation against the unified observability module
3. Open an issue in the MMF repository with dashboard export and error details
