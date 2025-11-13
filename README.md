# Marty Microservices Framework

**Feature overview.** Marty Microservices Framework (MMF) is designed to meet all of the core needs of a microservice-based system. It bundles an [API gateway](https://github.com/burdettadam/marty-microservices-framework#features) for intelligent routing and load-balancing, [service discovery](https://github.com/burdettadam/marty-microservices-framework#features) via Consul, and centralized [configuration management](https://github.com/burdettadam/marty-microservices-framework#features) with hot-reload. Built-in [event streaming](https://github.com/burdettadam/marty-microservices-framework#features) uses Kafka for asynchronous messaging, while [database integration](https://github.com/burdettadam/marty-microservices-framework#features) provides multi-database support with connection pooling and [distributed caching](https://github.com/burdettadam/marty-microservices-framework#features) via Redis. The framework offers [real-time metrics and profiling](https://github.com/burdettadam/marty-microservices-framework#observability), with Prometheus, Grafana and Jaeger providing metrics, dashboards and distributed tracing. A rich [CLI and project scaffolding](https://github.com/burdettadam/marty-microservices-framework#development-experience) system generates FastAPI, gRPC or hybrid services, manages dependencies and automates Docker/Kubernetes deployment. The [security module](https://github.com/burdettadam/marty-microservices-framework#security) supplies JWT-based auth, OAuth2/OpenID Connect integration, rate limiting, DDoS protection, zero-trust components and certificate management. MMF also includes a comprehensive [test suite](https://github.com/burdettadam/marty-microservices-framework#testing) (unit, integration and e2e), extensive [documentation and guides](https://github.com/burdettadam/marty-microservices-framework/tree/main/docs), [operations templates](https://github.com/burdettadam/marty-microservices-framework/tree/main/devops/kubernetes) for Kubernetes, service-mesh configs, dashboards and CI/CD pipelines, and [sample domain services](https://github.com/burdettadam/marty-microservices-framework/tree/main/examples/demos/petstore_domain) such as order, payment and inventory to illustrate patterns. These features collectively aim to give plugin authors and service teams everything they need out of the box.

**Technical stack.** MMF is built with Python 3.10+, using [FastAPI](https://fastapi.tiangolo.com/) for HTTP endpoints and [gRPC](https://grpc.io/) for high-performance RPC, and provides [Jinja-based templates](https://github.com/burdettadam/marty-microservices-framework/tree/main/templates) for scaffolding new services. Service discovery uses [Consul](https://developer.hashicorp.com/consul/docs), while event-driven communication relies on [Kafka](https://kafka.apache.org/); data is persisted in multiple databases (e.g., PostgreSQL) with built-in connection pooling and augmented with a [Redis](https://redis.io/) cache. Observability is handled by [Prometheus](https://prometheus.io/) for metrics, [Grafana](https://grafana.com/) for dashboards and [Jaeger](https://www.jaegertracing.io/) for distributed tracing, all running inside a local or cloud [Kubernetes](https://kubernetes.io/) cluster. The framework’s CLI (based on [Typer](https://typer.tiangolo.com/)) orchestrates code generation, dependency management, Docker builds and Kubernetes deployments, while the security layer integrates JWT and OAuth2/OIDC providers and includes rate-limiting and certificate management. Operations tooling includes [Kubernetes manifests](https://github.com/burdettadam/marty-microservices-framework/tree/main/devops/kubernetes), [service-mesh configuration](https://github.com/burdettadam/marty-microservices-framework/tree/main/docs/architecture), monitoring dashboards and CI/CD pipelines. Together, this stack ensures that MMF can deliver the full set of microservices features listed above with minimal additional setup.

## 📁 Project Structure

```
.
├── README.md
├── Makefile
├── pyproject.toml
├── docs/                       # Documentation
│   ├── guides/                 # Development guides
│   ├── architecture/           # Architecture documentation
│   └── demos/                  # Demo documentation & quickstarts
├── src/                        # Source code
│   └── marty_msf/              # Main framework package
│       ├── framework/          # Core framework modules
│       ├── cli/                # Command-line interface
│       ├── security/           # Security modules
│       └── observability/      # Monitoring & observability
├── services/                   # Service templates & examples
│   ├── fastapi/                # FastAPI service templates
│   ├── grpc/                   # gRPC service templates
│   ├── hybrid/                 # Hybrid service templates
│   └── shared/                 # Shared service components & Jinja assets
├── examples/                   # Usage examples
│   ├── demos/                  # Demo applications
│   │   ├── order-service/      # Order service demo
│   │   ├── payment-service/    # Payment service demo
│   │   ├── inventory-service/  # Inventory service demo
│   │   └── runner/             # Demo runner scripts
│   └── notebooks/              # Jupyter notebooks for tutorials
├── ops/                        # Operations & deployment
│   ├── k8s/                    # Kubernetes manifests
│   ├── service-mesh/           # Service mesh configuration
│   ├── dashboards/             # Monitoring dashboards
│   └── ci-cd/                  # CI/CD pipelines
├── scripts/                    # Utility scripts
│   ├── dev/                    # Development scripts
│   └── tooling/                # Build & maintenance tools
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── e2e/                    # End-to-end tests
│   └── quality/                # Code quality & lint tests
├── tools/                      # Development tools
│   └── scaffolding/            # Project generators & templates
└── var/                        # Runtime files (gitignored logs, pids, reports)
```

## 🚀 Quick Start - Local Development Environment

### Get Started in 2 Minutes

```bash
# 1. Clone and setup
git clone https://github.com/your-org/marty-microservices-framework.git
cd marty-microservices-framework
make setup

# 2. Start local Kubernetes cluster with full observability stack
make kind-up
```

**That's it!** You now have a complete local development environment running:

- 🎯 **Prometheus**: <http://localhost:9090> (metrics & monitoring)
- 📊 **Grafana**: <http://localhost:3000> (dashboards - login: admin/admin)
- ☸️ **Kubernetes cluster**: Full local cluster for development
- 🔍 **Complete observability stack**: Logging, metrics, tracing

### Other Development Commands

```bash
# Check cluster status
make kind-status

# View logs
make kind-logs

# Stop the cluster
make kind-down

# Restart everything
make kind-restart
```

## 🧪 End-to-End Testing

The framework includes comprehensive automated E2E testing using KIND (Kubernetes in Docker):

```bash
# Run full E2E test suite (complete validation)
make test-e2e

# Quick E2E tests for development (faster iteration)
make test-e2e-quick

# Smoke tests only (basic health checks)
make test-e2e-smoke

# Development mode (keep cluster for debugging)
make test-e2e-dev

# Clean up all test resources
make test-e2e-clean
```

**Test Coverage**: 21/23 tests passing (91.3% success rate)

- ✅ Health checks, authentication, user management
- ✅ Kubernetes deployment, service discovery, ingress
- ✅ Docker containerization, cluster orchestration
- ✅ Hexagonal architecture validation

See [E2E Testing Documentation](docs/E2E_TESTING_FRAMEWORK.md) for detailed information.

## 🛠️ Create Your First Service

```bash
# Generate a FastAPI service
make generate TYPE=fastapi NAME=my-api

# Generate a gRPC service
make generate TYPE=grpc NAME=my-grpc-service

# Generate a hybrid service (FastAPI + gRPC)
make generate TYPE=hybrid NAME=my-hybrid-service
```

## 📚 Framework Components

### Core Framework (`src/marty_msf/framework/`)

- **API Gateway**: Intelligent routing and load balancing
- **Service Discovery**: Consul-based service registration
- **Configuration Management**: Centralized config with hot-reload
- **Event Streaming**: Kafka integration for messaging
- **Database Integration**: Multi-database support with connection pooling
- **Caching**: Redis-based distributed caching
- **Performance Monitoring**: Real-time metrics and profiling

### CLI Tools (`src/marty_msf/cli/`)

- Project scaffolding and code generation
- Service templates and boilerplate
- Dependency management
- Docker and Kubernetes deployment automation
- Configuration validation and management

### Security (`src/marty_msf/security/`)

- JWT-based authentication and authorization
- OAuth2 and OpenID Connect integration
- Rate limiting and DDoS protection
- Zero-trust networking components
- Certificate management

### Observability (`src/marty_msf/observability/`)

- Prometheus metrics collection
- Grafana dashboard templates
- Distributed tracing with Jaeger
- Structured logging
- Performance analytics and alerting

## 🎯 Running Demo Applications

The framework includes several demo applications to showcase different patterns:

```bash
# Run the complete store demo (order, payment, inventory services)
cd examples/demos/runner
./start_demo.sh

# Stop the demo
./stop_demo.sh
```

### Demo Services

- **Order Service**: Handles order processing and workflow
- **Payment Service**: Manages payment processing and transactions
- **Inventory Service**: Tracks inventory levels and stock management

## 🧪 Testing

The framework includes comprehensive testing at multiple levels:

```bash
# Run unit tests
make test-unit

# Run integration tests
make test-integration

# Run end-to-end tests
make test-e2e

# Run all tests with coverage
make test-all
```

## 📖 Documentation

- **[Architecture Guide](docs/architecture/)**: System design and patterns
- **[Development Guides](docs/guides/)**: Setup and development workflows
- **[Demo Documentation](docs/demos/)**: Tutorial walkthroughs
- **[API Reference](docs/api/)**: Complete API documentation

## 🛠️ Development

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- kubectl
- Make

### Development Setup

```bash
# Install development dependencies
make install-dev

# Set up pre-commit hooks
make setup-hooks

# Run code quality checks
make lint

# Run security scans
make security
```

## 🚢 Deployment

The framework supports multiple deployment targets:

```bash
# Deploy to local Kubernetes
make deploy-local

# Deploy to staging
make deploy-staging

# Deploy to production
make deploy-prod
```

## 📋 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

- 📧 Email: <team@marty-msf.com>
- 🐛 Issues: [GitHub Issues](https://github.com/marty-framework/marty-microservices-framework/issues)
- 📖 Documentation: [marty-msf.readthedocs.io](https://marty-msf.readthedocs.io)
