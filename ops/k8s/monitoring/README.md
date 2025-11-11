# Production Monitoring Stack for Phase 2 Infrastructure

This directory contains a comprehensive monitoring and observability stack designed specifically for Phase 2 enterprise infrastructure components.

## Components

### Core Monitoring

- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **Jaeger**: Distributed tracing
- **AlertManager**: Alert routing and management

### Phase 2 Infrastructure Monitoring

- **Redis Exporter**: Cache metrics and performance
- **RabbitMQ Exporter**: Message queue metrics
- **PostgreSQL Exporter**: Database and event store metrics
- **Custom Exporters**: Phase 2 component-specific metrics

### Log Management

- **Fluent Bit**: Log collection and forwarding
- **Elasticsearch**: Log storage and indexing
- **Kibana**: Log visualization and analysis

## Dashboards

### Phase 2 Infrastructure Dashboards

1. **Cache Performance**: Redis metrics, hit/miss ratios, memory usage
2. **Message Queue Health**: RabbitMQ queues, throughput, latency
3. **Event Streaming**: Event processing rates, stream health
4. **API Gateway**: Request rates, response times, error rates
5. **Configuration Management**: Configuration changes, secret access

### Application Dashboards

1. **Service Overview**: Per-service metrics and health
2. **Performance**: Response times, throughput, errors
3. **Infrastructure**: Resource usage, scaling metrics
4. **Security**: Authentication failures, access patterns

## Alerting Rules

### Critical Alerts

- Service down/unhealthy
- Cache hit ratio below threshold
- Message queue depth exceeding limits
- High error rates
- Resource exhaustion

### Warning Alerts

- Performance degradation
- Configuration drift
- Security anomalies
- Capacity planning triggers

## Usage

Deploy the monitoring stack:

```bash
kubectl apply -f monitoring/namespace.yaml
kubectl apply -f monitoring/prometheus/
kubectl apply -f monitoring/grafana/
kubectl apply -f monitoring/jaeger/
kubectl apply -f monitoring/alertmanager/
```

Import dashboards:

```bash
kubectl apply -f monitoring/dashboards/
```

Configure alerts:

```bash
kubectl apply -f monitoring/alerts/
```
