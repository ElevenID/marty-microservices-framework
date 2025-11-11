# Service Creation Guide

## Quick Start

### 1. Create Service Using CLI

```bash
# Create a FastAPI service
marty new fastapi-service my-user-service --author "Your Name" --email "you@example.com"

# Create a gRPC service
marty new grpc-service my-payment-service --author "Your Name"

# Create a hybrid service (FastAPI + gRPC)
marty new hybrid-service my-order-service --author "Your Name"
```

### 2. Manual Service Creation

If you need to create a service manually:

```bash
# Copy service template
cp -r services/fastapi/template my-new-service
cd my-new-service

# Update configuration
# Replace {{SERVICE_NAME}} with your_service_name
# Replace {{SERVICE_NAME_PASCAL}} with YourServiceName
# Replace {{SERVICE_NAME_UPPER}} with YOUR_SERVICE_NAME
```

## Essential Patterns

### Configuration

```python
from marty_msf.framework.config import create_service_config

# Load configuration
config = create_service_config("your_service")
```

### Database Integration

```python
from marty_msf.framework.database import DatabaseManager

# Initialize database
db_manager = DatabaseManager(config.database.your_service)
```

### Observability

```python
from marty_msf.observability import init_observability
from marty_msf.framework.logging import UnifiedServiceLogger

# Initialize observability
init_observability(config.observability)
logger = UnifiedServiceLogger("your-service")
```

### Service Discovery

```python
from marty_msf.framework.discovery import ServiceDiscoveryManager, ServiceInstance

# Register service
discovery = ServiceDiscoveryManager()
await discovery.register_service(ServiceInstance(
    name="your-service",
    host="localhost",
    port=8080
))
```

## Project Structure

```
my-service/
├── src/
│   └── main.py                 # Service entry point
├── config/
│   ├── base.yaml              # Base configuration
│   ├── development.yaml       # Development overrides
│   └── production.yaml        # Production overrides
├── tests/
│   ├── unit/                  # Unit tests
│   └── integration/           # Integration tests
├── k8s/                       # Kubernetes manifests
├── Dockerfile                 # Container definition
└── requirements.txt           # Dependencies
```

## Best Practices

### Configuration

- Use environment-specific config files
- Keep secrets in environment variables
- Validate configuration on startup

### Error Handling

- Use structured logging with correlation IDs
- Implement circuit breakers for external calls
- Return consistent error formats

### Testing

- Write tests before implementation
- Test with real dependencies when possible
- Include integration tests for critical paths

### Security

- Enable authentication by default
- Use TLS for all communications
- Validate all inputs

### Observability

- Include correlation IDs in all logs
- Export metrics for monitoring
- Implement health checks

## Common Commands

```bash
# Build service
marty build

# Run locally
marty run --env development

# Run tests
marty test

# Deploy to Kubernetes
marty deploy --env staging

# Generate API documentation
marty api docs

# Check service health
marty health-check
```

For detailed CLI usage, see [CLI Documentation](CLI_README.md).
