# Local Development

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management
- Docker (optional, for container builds)
- KinD + kubectl (optional, for local Kubernetes)

## Workflow

1. `make bootstrap` — resolve dependencies and create the project-local virtualenv via uv.
2. `make proto` — regenerate gRPC stubs if `.proto` files change.
3. `make test` — run unit + integration tests (`pytest -m "not build"`).
4. `make typecheck` / `make lint` — enforce mypy + ruff.
5. `make run` — start the gRPC server locally.
6. `make docker-build` — build the runtime image.

## Testing Strategy

- Unit tests stub external dependencies and focus on pure logic.
- Integration tests spin up the gRPC server in-process and assert request/response flows.
- End-to-end tests drive the CLI entrypoint with a timed shutdown window.
- Build tests ensure packaging succeeds, failing CI if distribution artifacts cannot be produced.

## Helpful Commands

- `uv run python -m microservice_template.main health` — on-demand health probe.
- `grpcurl -plaintext localhost:50051 microservice.template.v1.GreeterService/HealthCheck` — manual smoke test (requires `grpcurl`).
- `scripts/tag_release.sh 0.1.0` — create and push an annotated git tag.

## Environment Variables

Override defaults by exporting any `APP_*` variables, e.g.:

```bash
export APP_LOG_LEVEL=DEBUG
export APP_TRACING_ENABLED=false
```
