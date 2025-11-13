# Observability Stack

The template ships with sensible defaults for logs, metrics, and traces. All components can be swapped for organisation-specific tooling.

## Logging

- Structured JSON logs are produced via `structlog`.
- Each entry includes service name, log level, iso8601 timestamps, and optional trace identifiers.
- Configure verbosity using `APP_LOG_LEVEL`.

## Metrics

- Prometheus metrics served on `APP_METRICS_PORT` (default `9000`).
- Key series:
  - `grpc_server_requests_total{method,code}` — request throughput
  - `grpc_server_handling_seconds_bucket` — latency histogram
  - `service_health_status` — readiness flag for dashboards/alerts
- `ops/k8s/observability/prometheus.yaml` sets up a Prometheus deployment scraping metrics via Kubernetes service discovery.

## Tracing

- OpenTelemetry exporter configured in `observability/tracing.py`.
- Controlled via `APP_TRACING_ENABLED` and `APP_TRACING_ENDPOINT` environment variables.
- Collector deployment (`ops/k8s/observability/otel-collector.yaml`) fans out to logging and OTLP backends.

## Dashboards

- Grafana deployment with a starter dashboard showing request rate and latency percentiles.
- Update `grafana-dashboards` ConfigMap to add panels for business metrics.

## Alerting Hooks

- Extend the Prometheus configuration with alerting rules in `prometheus.yaml` once SLOs are defined.
- Grafana can integrate with Alertmanager, PagerDuty, Slack, etc.; configure contact points within Grafana.

## Local Workflow

1. `make kind-up` to install the microservice plus observability stack.
2. Port-forward Grafana (`kubectl port-forward svc/grafana -n monitoring 3000:3000`) and Prometheus (`kubectl port-forward svc/prometheus -n monitoring 9090:9090`).
3. Exercise the service via tests or `grpcurl` to watch metrics and traces populate.
