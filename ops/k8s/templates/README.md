# Kubernetes Templates for Phase 2 Enterprise Infrastructure

This directory contains Kubernetes deployment templates that support the Phase 2 enterprise infrastructure components:

## Infrastructure Components

### Phase 2 Infrastructure Support

- **ConfigMaps**: Environment-specific configuration for ConfigManager
- **Secrets**: Secure secret management for SecretManager
- **Services**: Load balancing and service discovery for API Gateway
- **Deployments**: Container orchestration with Phase 2 component initialization
- **PersistentVolumes**: Storage for cache backends and event stores
- **NetworkPolicies**: Secure communication between microservices

### Supported Backends

- **Redis**: Caching and message broker support
- **RabbitMQ**: Enterprise message queuing
- **PostgreSQL**: Database and event store backend
- **Prometheus**: Metrics collection for monitoring

## Template Structure

```
templates/
├── namespace.yaml              # Namespace with labels
├── configmap-enterprise.yaml  # Phase 2 configuration
├── secrets-enterprise.yaml    # Phase 2 secrets management
├── service-deployment.yaml    # Microservice deployment
├── service-service.yaml       # Service discovery
├── ingress-gateway.yaml       # API Gateway ingress
├── redis-deployment.yaml      # Redis for caching/messaging
├── rabbitmq-deployment.yaml   # RabbitMQ for messaging
├── monitoring-stack.yaml      # Prometheus/Grafana stack
└── network-policies.yaml      # Security policies
```

## Usage

These templates are designed to be used with Helm for parameter substitution and environment-specific configurations.

Deploy with environment-specific values:

```bash
helm template my-service ./k8s/templates \
  --values ./k8s/values/development.yaml \
  --set service.name=user-management \
  --set image.tag=v1.0.0
```

## Environment Configuration

Each environment should have specific configurations:

- **Development**: In-memory backends, debug enabled
- **Testing**: Lightweight Redis, minimal resources
- **Production**: Full Redis cluster, RabbitMQ cluster, monitoring enabled
