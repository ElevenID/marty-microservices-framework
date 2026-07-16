# Marty Microservices Framework

**Enterprise-grade Python Microservices Platform**

Marty Microservices Framework (MMF) is a "batteries-included" platform designed to accelerate microservices development. It implements **Hexagonal Architecture (Ports and Adapters)** to ensure modularity, testability, and long-term maintainability.

## 🚀 Key Features

* **Hexagonal Architecture**: Clean separation of Domain, Application, and Infrastructure layers.
* **Core Infrastructure**: API Gateway, Service Discovery (Consul), and Configuration Management.
* **Data & Messaging**: Database integration (SQLAlchemy), Caching (Redis), and Event Streaming (Kafka).
* **Observability**: Built-in support for Prometheus, Grafana, and Jaeger (OpenTelemetry).
* **Security**: Comprehensive identity management (JWT, OAuth2/OIDC) and policy enforcement.
* **Developer Experience**: CLI tools, project scaffolding, and comprehensive testing utilities.

## 📁 Project Structure

The project follows a strict Hexagonal Architecture:

```
mmf/                        # Core Framework & Services
├── services/                   # Domain Services (Bounded Contexts)
│   ├── identity/               # Identity & Access Management
│   └── audit/                  # Audit Logging
├── core/                       # Platform Contracts & Interfaces
└── framework/                  # Shared Infrastructure Implementations
    ├── gateway/                # API Gateway
    ├── security/               # Security Utilities
    └── observability/          # Telemetry & Tracing
```

## 🛠️ Getting Started

### Prerequisites

* Python 3.11+
* Docker & Docker Compose

### Installation

```bash
pip install -e .
```

### Running Tests

```bash
pytest
```

## 🏗️ Architecture

MMF enforces a strict dependency rule:
**Domain** <- **Application** <- **Infrastructure**

* **Domain**: Pure business logic, no external dependencies.
* **Application**: Use cases orchestrating domain objects.
* **Infrastructure**: Adapters for external systems (Databases, APIs, Web).

## 📚 Documentation

Detailed documentation is available in the `docs/` directory.

* [Architecture Standards](docs/architecture/STANDARDS.md) - Strict guidelines for Hexagonal Architecture.
* [Core Migration Guide](docs/CORE_MIGRATION_GUIDE.md) - Guide for migrating legacy code.
* [Standardization Plan](docs/STANDARDIZATION_PLAN.md) - Roadmap for framework standardization.

## 💡 Examples

Explore the `examples/` directory for practical implementations:

* **Authentication**: `authentication_examples.py`, `jwt_auth_demo.py`, `mfa_authentication_example.py`
* **Domains**: `petstore_domain/`, `video_streaming_domain/`, `production-payment-service/`
* **Resilience**: `resilience/`, `resilience_test.py`
* **Security**: `security/`, `security_recovery_demo.py`
* **Kubernetes**: `k8s/`

## ⚠️ Legacy Code

Legacy components from the previous monolithic architecture have been moved to `boneyard/`.

## License

This repository is licensed under the GNU Affero General Public License v3.0 only (`AGPL-3.0-only`). See [`LICENSE`](LICENSE).

## Production Use

This framework is published as open-source software, but production deployments still require careful configuration of secrets, databases, network boundaries, backups, monitoring, data retention, and dependency review. Validate your deployment and supply-chain controls before using it in production.
