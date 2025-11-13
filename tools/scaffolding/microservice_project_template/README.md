# Microservice Template

A production-ready Python microservice template with gRPC, observability, analytics capabilities, and Kubernetes deployment.

## ✨ Features

### 🚀 Core Infrastructure

- **AsyncIO gRPC server** with health checks and graceful shutdown
- **Observability**: Structured logging, OpenTelemetry tracing, Prometheus metrics
- **Configuration management** with environment-based settings
- **Docker containerization** with multi-stage builds

### 📊 Analytics Capabilities

- **Statistical analysis** with pandas, numpy, scipy
- **Data visualization** with matplotlib and seaborn
- **Machine learning** with scikit-learn clustering
- **gRPC endpoints** for:
  - Sample data generation
  - Correlation analysis with heatmaps
  - K-means clustering with visualizations
  - Distribution analysis with statistical tests

### ☸️ Kubernetes Ready

- **KinD cluster** setup for local development
- **Kustomize manifests** for environment-specific deployments
- **Health probes** for liveness and readiness
- **ConfigMaps** for environment configuration
- **ServiceMonitor** for Prometheus scraping

### 🛠️ Developer Experience

- **UV package management** for fast dependency resolution
- **Ruff** for linting and formatting
- **MyPy** for static type checking
- **pytest** with async support and coverage
- **GitHub Actions** CI/CD pipeline
- **Make targets** for common tasks

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [UV](https://github.com/astral-sh/uv) package manager
- Docker
- [KinD](https://kind.sigs.k8s.io/) for local Kubernetes

### 1. Setup Development Environment

```bash
# Install dependencies
make install

# Generate protobuf files
make generate

# Run tests
make test

# Check code quality
make lint
make typecheck
```

### 2. Run Locally

```bash
# Start the server
make run

# In another terminal, test with the demo client
uv run python examples/analytics_demo.py
```

### 3. Docker Development

```bash
# Build image
make docker-build

# Run with Docker
docker run -p 50051:50051 -p 9000:9000 -p 8080:8080 microservice-template:latest
```

### 4. Kubernetes Development

```bash
# Start KinD cluster and deploy
make kind-up

# Test the deployed service
kubectl port-forward -n microservice-template-dev svc/microservice-template 30001:50051 &
uv run python examples/analytics_demo.py --target localhost:30001

# Check health endpoints
kubectl port-forward -n microservice-template-dev svc/microservice-template 8080:8080 &
curl http://localhost:8080/health/live
curl http://localhost:8080/health/ready

# View metrics
curl http://localhost:8080/metrics

# Clean up
make kind-down
```

## 📊 Analytics Endpoints

The service provides several analytics endpoints accessible via gRPC:

### `GenerateSampleData`

Creates sample datasets for analysis:

```python
request = greeter_pb2.SampleDataRequest(n_samples=1000, seed=42)
response = await stub.GenerateSampleData(request)
```

### `AnalyzeCorrelation`

Performs correlation analysis with visualization:

```python
request = greeter_pb2.CorrelationRequest(data_csv=csv_data)
response = await stub.AnalyzeCorrelation(request)
```

### `AnalyzeClustering`

K-means clustering with silhouette analysis:

```python
request = greeter_pb2.ClusteringRequest(data_csv=csv_data, n_clusters=3)
response = await stub.AnalyzeClustering(request)
```

### `AnalyzeDistribution`

Statistical distribution analysis:

```python
request = greeter_pb2.DistributionRequest(values=data, column_name="age")
response = await stub.AnalyzeDistribution(request)
```

## 🏗️ Architecture

```
├── src/microservice_template/
│   ├── config.py              # Configuration management
│   ├── main.py               # Application entry point
│   ├── server.py             # gRPC server setup
│   ├── service/
│   │   ├── greeter.py        # Main service implementation
│   │   └── analytics.py      # Analytics service logic
│   ├── observability/
│   │   ├── health.py         # HTTP health endpoints
│   │   ├── metrics.py        # Prometheus metrics
│   │   └── tracing.py        # OpenTelemetry setup
│   └── proto/               # Generated protobuf files
├── k8s/                     # Kubernetes manifests
├── examples/                # Demo clients
├── tests/                   # Test suites
└── docs/                   # Documentation
```

## 🔧 Configuration

The service uses environment variables for configuration:

```bash
# gRPC Settings
APP_GRPC_HOST=0.0.0.0
APP_GRPC_PORT=50051

# Metrics Settings
APP_METRICS_HOST=0.0.0.0
APP_METRICS_PORT=9000

# Tracing Settings
APP_TRACING_ENDPOINT=http://jaeger:4317

# Environment
APP_ENVIRONMENT=development
APP_LOG_LEVEL=INFO
```

## 📈 Observability

### Metrics

Available at `http://localhost:9000/metrics`:

- Request duration histograms
- Request count by method and status
- Process metrics (CPU, memory)
- Python-specific metrics

### Health Checks

- **Liveness**: `http://localhost:8080/health/live`
- **Readiness**: `http://localhost:8080/health/ready`
- **Custom checks**: Extensible health check system

### Tracing

OpenTelemetry spans for:

- gRPC method calls
- Analytics operations
- Database queries (when applicable)

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-integration
make test-e2e

# Run with coverage
make test-coverage
```

## 📦 Deployment

### Environment Overlays

- `k8s/overlays/dev/` - Development configuration
- `k8s/overlays/prod/` - Production configuration

### CI/CD

GitHub Actions workflow includes:

- Code quality checks (lint, typecheck)
- Unit and integration tests
- Docker image building
- Security scanning

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and quality checks
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.
