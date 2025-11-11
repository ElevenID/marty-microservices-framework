# Architecture

The template adheres to a layered design so business logic, transport, and infrastructure concerns remain isolated.

## Components

- **Protobuf contracts (`proto/`)** — canonical API specification; regenerate stubs via `make proto`.
- **Service layer (`src/microservice_template/service/`)** — request handlers implement generated gRPC interfaces. All domain logic lives here.
- **Server bootstrap (`src/microservice_template/server.py`)** — composes settings, instrumentation, and transport runtime.
- **Observability (`src/microservice_template/observability/`)** — structured logging, metrics collection, and tracing exporters.
- **Configuration (`src/microservice_template/config/`)** — pydantic settings for 12-factor alignment.
- **Tests (`tests/`)** — split by unit/integration/e2e/build markers to enforce the testing pyramid.

## Data Flow

1. `main.py` loads typed settings, initialises logging + tracing, then runs the async gRPC server.
2. Incoming RPCs hit `GreeterService`, which emits structured logs, traces, and metrics.
3. Metrics flow to Prometheus via the embedded HTTP exporter; traces ship to the OTLP collector deployment.
4. Kubernetes manifests wire configuration/telemetry while GitHub Actions enforces quality gates and release automation.

## Extending

- Add new protobuf definitions and regenerate stubs.
- Implement new servicers under `service/` and register them in `server.py`.
- Extend settings using Pydantic models; env vars automatically pick up new fields.
- Add background jobs or schedulers by composing additional asyncio tasks inside `main.py`.
