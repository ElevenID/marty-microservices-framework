# Marty MMF Plugin System

This document provides a comprehensive guide to the Marty Microservices Framework (MMF) plugin system and how Marty's trust and PKI services have been migrated to work as plugins within the MMF ecosystem.

## Overview

The MMF plugin system enables external applications to integrate seamlessly with MMF infrastructure while maintaining clean separation of concerns. Marty's trust and PKI services have been transformed from standalone microservices into MMF plugins, allowing them to leverage MMF's comprehensive infrastructure capabilities.

## Plugins as Domain Bundles

In MMF, treat a plugin as a domain bundle rather than a single service. A plugin packages a cohesive domain (capabilities, policies, and data contracts) and may expose one or more services that share the same domain boundaries and runtime concerns.

- Scope: A plugin owns a domain area (e.g., payments, trust/PKI, identity) and groups closely related services, models, and configuration.
- Multiple services: A single plugin can register multiple services/endpoints. Prefer adding services to an existing plugin when they share domain rules, dependencies, and lifecycle.
- Entry points: Register the plugin once via `pyproject.toml` entry points and let it expose several service definitions through the plugin API.
- Configuration: Keep domain-level configuration in a single plugin config file with per‑service subsections when needed.
- Testing: Co-locate domain tests (unit/integration) with the plugin; test services together when they share domain logic.

When to create a new plugin vs. add a service:

- Create a new plugin when you need a separate domain boundary, distinct deployment cadence/ownership, or non-overlapping dependencies/security posture.
- Add a new service to an existing plugin when the functionality is part of the same domain model, reuses the same infra and policies, or benefits from shared configuration and tests.

## Architecture

### Plugin System Components

```
MMF Plugin Architecture
├── Core Plugin System
│   ├── MMFPlugin (Base class)
│   ├── PluginContext (Infrastructure access)
│   ├── PluginManager (Lifecycle management)
│   └── ServiceRegistry (Service management)
├── Plugin Discovery
│   ├── DirectoryPluginDiscoverer
│   ├── PackagePluginDiscoverer
│   └── CompositePluginDiscoverer
├── Configuration Management
│   ├── PluginConfig (Extended service config)
│   ├── PluginConfigManager (Multi-plugin config)
│   └── MartyTrustPKIConfig (Marty-specific config)
└── Service Decorators
    ├── @plugin_service
    ├── @requires_auth
    ├── @track_metrics
    ├── @trace_operation
    └── @event_handler
```

## Plugin Types

MMF supports two distinct types of plugins that serve different purposes:

### Service Plugins (MMFPlugin)

Service plugins are domain bundles that provide business logic and services. They are the primary extension mechanism for adding domain-specific functionality to MMF applications.

**Characteristics:**

- **Location**: Top-level `plugins/<domain-plugin>/` directories
- **Registration**: Via entry points in `pyproject.toml`
- **Interface**: Implement the `MMFPlugin` base class
- **Purpose**: Provide business services and domain logic
- **Scope**: Own a complete business domain (e.g., payments, identity, trust/PKI)
- **Lifecycle**: Managed by MMF's PluginManager

**Example:**

```python
# plugins/payment_processing/plugin.py
from marty_msf.framework.plugins.core import MMFPlugin

class PaymentProcessingPlugin(MMFPlugin):
    def get_metadata(self):
        return {
            "name": "payment-processing",
            "version": "1.0.0",
            "description": "Payment processing domain logic"
        }

    def get_service_definitions(self):
        return [
            {"name": "payment-service", "class": PaymentService},
            {"name": "billing-service", "class": BillingService}
        ]
```

**Entry Point Registration:**

```toml
[project.entry-points."mmf.plugins"]
payment_processing = "plugins.payment_processing:PaymentProcessingPlugin"
```

### Gateway Plugins (Middleware)

Gateway plugins are middleware-like components that handle cross-cutting concerns at the API gateway level. They process requests and responses for all traffic flowing through the gateway.

**Characteristics:**

- **Location**: Gateway configuration and middleware directories
- **Registration**: Via gateway configuration, not entry points
- **Interface**: Implement gateway middleware interfaces
- **Purpose**: Handle cross-cutting concerns (auth, logging, rate limiting, etc.)
- **Scope**: Operate on HTTP requests/responses across all services
- **Lifecycle**: Managed by the API Gateway

**Example:**

```python
# Gateway middleware plugin
class AuthenticationGatewayPlugin:
    async def process_request(self, request):
        # Validate authentication for all incoming requests
        pass

    async def process_response(self, response):
        # Add security headers to all responses
        pass
```

### Key Differences

| Aspect | Service Plugins (MMFPlugin) | Gateway Plugins (Middleware) |
|--------|----------------------------|------------------------------|
| **Purpose** | Business domain logic | Cross-cutting concerns |
| **Scope** | Domain-specific services | All HTTP traffic |
| **Registration** | Entry points in pyproject.toml | Gateway configuration |
| **Interface** | MMFPlugin base class | Gateway middleware interface |
| **Location** | `plugins/<domain>/` | Gateway middleware config |
| **Examples** | Payment processing, User management | Authentication, Rate limiting |

### Marty Plugin Structure

```
src/plugins/marty/
├── __init__.py              # Plugin exports
├── plugin.py                # Main plugin class
├── services.py              # Service implementations
├── plugin.yaml              # Plugin manifest
└── config/
    └── marty.yaml           # Plugin configuration
```

## Key Benefits

### Infrastructure Consolidation

**Before (Standalone Marty):**

- 20+ microservices with custom infrastructure
- Duplicate database, security, observability implementations
- Inconsistent patterns across services
- High maintenance overhead

**After (MMF Plugin):**

- Single plugin with 4 service implementations
- Unified MMF infrastructure (database, security, observability)
- Consistent patterns and best practices
- ~75% reduction in infrastructure code

### Enhanced Capabilities

1. **Unified Configuration**: Type-safe configuration with validation and hot-reloading
2. **Comprehensive Security**: Built-in authentication, authorization, and cryptographic operations
3. **Advanced Observability**: Automatic metrics, tracing, and logging
4. **Event-Driven Architecture**: Message bus integration for loose coupling
5. **Resilience Patterns**: Circuit breakers, retries, and bulkhead isolation
6. **Service Discovery**: Automatic registration and health monitoring

## Quick Start

### 1. Plugin Installation

```python
from framework.plugins import PluginManager, PluginContext
from framework.config import create_plugin_config_manager
from plugins.marty import MartyTrustPKIPlugin

# Setup configuration
config_manager = create_plugin_config_manager()

# Create plugin context with MMF services
context = PluginContext(
    config_manager=config_manager,
    database_manager=mmf_database,
    security_manager=mmf_security,
    observability_manager=mmf_observability
)

# Initialize plugin manager
plugin_manager = PluginManager(context)

# Load and start Marty plugin
marty_plugin = MartyTrustPKIPlugin()
await plugin_manager.load_plugin_instance(marty_plugin, "marty")
await plugin_manager.start_plugin("marty")
```

### 2. Service Usage

```python
# Get document signer service
doc_signer = marty_plugin.get_service("document_signer")

# Sign a document (with automatic auth, metrics, tracing)
signature_result = await doc_signer.sign_document(
    document_data=b"Document content",
    signing_algorithm="RSA-SHA256"
)

# Verify signature
is_valid = await doc_signer.verify_signature(
    document_data=b"Document content",
    signature_data=signature_result
)
```

## Configuration

### Plugin Configuration

The Marty plugin uses a hierarchical configuration system:

```yaml
# config/plugins/marty.yaml
default:
  enabled: true
  version: "1.0.0"

  # Trust anchor settings
  trust_anchor_url: "https://trust-anchor.marty.internal:8443"
  trust_anchor_timeout: 30

  # PKD settings
  pkd_url: "https://pkd.marty.internal:8443"
  pkd_cache_ttl: 3600

  # Document signer settings
  document_signer_url: "https://doc-signer.marty.internal:8443"
  signing_algorithms:
    - "RSA-SHA256"
    - "ECDSA-SHA256"

  # Security settings
  require_mutual_tls: true
  certificate_validation_enabled: true

# Environment-specific overrides
development:
  require_mutual_tls: false
  certificate_validation_enabled: false

production:
  signing_algorithms:
    - "RSA-SHA384"  # Stronger algorithms for production
    - "ECDSA-SHA384"
```

### Configuration Management

```python
from framework.config import create_plugin_config_manager

# Create plugin-aware config manager
config_manager = create_plugin_config_manager(
    config_dir="./config",
    plugin_config_dir="./config/plugins"
)

# Get plugin configuration
marty_config = await config_manager.get_plugin_config("marty")

# Get base MMF configuration
base_config = await config_manager.get_base_config()
```

## Service Implementations

### Document Signer Service

Provides cryptographic document signing with MMF infrastructure integration:

```python
@requires_auth(roles=["document_signer"], permissions=["sign_documents"])
@track_metrics(metric_name="document_sign_requests", timing=True)
@trace_operation(operation_name="sign_document")
async def sign_document(self, document_data: bytes, signing_algorithm: str) -> Dict[str, Any]:
    """Sign document using MMF security infrastructure."""

    # Validate algorithm
    if signing_algorithm not in self.config.signing_algorithms:
        raise ValueError(f"Unsupported algorithm: {signing_algorithm}")

    # Use MMF security service
    signature = await self.context.security.sign_data(
        data=document_data,
        key_id="document_signer",
        algorithm=signing_algorithm
    )

    # Store audit record in MMF database
    await self.context.database.insert("signature_records", {
        "document_hash": hashlib.sha256(document_data).hexdigest(),
        "signature": signature,
        "algorithm": signing_algorithm,
        "timestamp": datetime.utcnow()
    })

    return {
        "signature": signature,
        "algorithm": signing_algorithm,
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Trust Anchor Service

Manages root certificates and trust relationships:

```python
@requires_auth(roles=["trust_administrator"])
@track_metrics(metric_name="trust_anchor_operations")
async def add_trust_anchor(self, certificate_data: bytes, metadata: Dict[str, Any]) -> str:
    """Add trust anchor using MMF infrastructure."""

    # Validate certificate using MMF security
    cert_info = await self.context.security.validate_certificate(certificate_data)

    # Store in MMF database with transaction support
    trust_anchor_id = await self.context.database.transaction(async_session => {
        return await async_session.insert("trust_anchors", {
            "certificate": certificate_data,
            "subject": cert_info.subject,
            "issuer": cert_info.issuer,
            "valid_from": cert_info.not_before,
            "valid_to": cert_info.not_after,
            "metadata": metadata
        })
    })

    # Invalidate cache
    if self.context.cache:
        await self.context.cache.delete_pattern("trust_anchor:*")

    return trust_anchor_id
```

### PKD Service

Public Key Directory for key distribution:

```python
@track_metrics(metric_name="pkd_lookup_requests")
async def lookup_public_key(self, subject_identifier: str) -> Optional[Dict[str, Any]]:
    """Lookup public key with MMF caching."""

    cache_key = f"pkd:key:{subject_identifier}"

    # Check MMF cache first
    if self.context.cache:
        cached_key = await self.context.cache.get(cache_key)
        if cached_key:
            return cached_key

    # Query MMF database
    key_info = await self.context.database.query_one(
        "SELECT * FROM public_keys WHERE subject = $1",
        subject_identifier
    )

    if key_info and self.context.cache:
        # Cache with TTL
        await self.context.cache.set(
            cache_key,
            key_info,
            ttl=self.config.pkd_cache_ttl
        )

    return key_info
```

## Service Decorators

The plugin system provides powerful decorators for cross-cutting concerns:

### Authentication & Authorization

```python
@requires_auth(roles=["admin"], permissions=["manage_certificates"])
async def sensitive_operation(self):
    """Automatically enforced authentication and authorization."""
    pass
```

### Metrics Collection

```python
@track_metrics(
    metric_name="certificate_operations",
    labels={"operation_type": "validation"},
    timing=True,
    counter=True
)
async def validate_certificate(self, cert_data: bytes):
    """Automatic metrics collection for performance monitoring."""
    pass
```

### Distributed Tracing

```python
@trace_operation(
    operation_name="trust_chain_validation",
    tags={"service": "trust_anchor"},
    log_inputs=False,
    log_outputs=True
)
async def validate_trust_chain(self, certificate_chain: List[bytes]):
    """Automatic distributed tracing for debugging and monitoring."""
    pass
```

### Event Handling

```python
@event_handler(
    event_type="certificate_revoked",
    retry_attempts=3,
    async_processing=True
)
async def handle_certificate_revocation(self, event):
    """Automatic event processing with retry logic."""
    pass
```

## Migration Guide

### Step 1: Analyze Current Service

Identify components to migrate:

- Business logic (keep)
- Infrastructure code (replace with MMF)
- Custom patterns (standardize with MMF)

### Step 2: Create Plugin Structure

```bash
src/plugins/your_service/
├── __init__.py
├── plugin.py          # Main plugin class
├── services.py        # Service implementations
└── plugin.yaml        # Plugin manifest
```

### Step 3: Implement Plugin Class

```python
from framework.plugins import MMFPlugin, PluginContext

class YourServicePlugin(MMFPlugin):
    async def initialize(self, context: PluginContext) -> None:
        # Initialize using MMF infrastructure
        pass

    async def start(self) -> None:
        # Start services
        pass

    async def stop(self) -> None:
        # Cleanup
        pass
```

### Step 4: Migrate Service Logic

```python
class YourService:
    def __init__(self, context: PluginContext, config):
        self.context = context  # MMF infrastructure access
        self.config = config    # Type-safe configuration

    @requires_auth(...)
    @track_metrics(...)
    @trace_operation(...)
    async def your_business_method(self, ...):
        # Use MMF infrastructure instead of custom implementations
        pass
```

### Step 5: Update Configuration

```yaml
# config/plugins/your_service.yaml
default:
  enabled: true
  # Service-specific configuration
```

## Testing

### Unit Testing

```python
import pytest
from unittest.mock import Mock

from plugins.marty.services import DocumentSignerService

@pytest.fixture
def mock_context():
    context = Mock()
    context.database = Mock()
    context.security = Mock()
    return context

@pytest.fixture
def mock_config():
    config = Mock()
    config.signing_algorithms = ["RSA-SHA256"]
    return config

async def test_document_signing(mock_context, mock_config):
    service = DocumentSignerService(mock_context, mock_config)
    await service.initialize()

    # Mock MMF security service
    mock_context.security.sign_data.return_value = b"mock_signature"

    result = await service.sign_document(b"test_document")

    assert result["signature"] == b"mock_signature"
    assert result["algorithm"] == "RSA-SHA256"
```

### Integration Testing

```python
async def test_plugin_integration():
    # Setup real MMF services for integration testing
    context = create_test_context()
    plugin = MartyTrustPKIPlugin()

    await plugin.initialize(context)
    await plugin.start()

    # Test end-to-end functionality
    doc_signer = plugin.get_service("document_signer")
    result = await doc_signer.sign_document(b"integration_test")

    assert result is not None

    await plugin.stop()
```

## Monitoring & Observability

### Health Checks

```python
# Automatic health check endpoint
GET /health

{
  "plugin": "MartyTrustPKI",
  "status": "healthy",
  "services": {
    "document_signer": {"status": "healthy"},
    "trust_anchor": {"status": "healthy"},
    "pkd": {"status": "healthy"},
    "certificate_validation": {"status": "healthy"}
  }
}
```

### Metrics

Automatic metrics collection for all services:

```
# Document signing metrics
marty_pki_document_sign_requests_total{algorithm="RSA-SHA256",status="success"} 150
marty_pki_document_sign_requests_duration_seconds{algorithm="RSA-SHA256"} 0.045

# Trust anchor metrics
marty_pki_trust_validation_requests_total{result="valid"} 89
marty_pki_trust_anchor_operations_total{operation="add"} 5

# PKD metrics
marty_pki_pkd_lookup_requests_total{cache_hit="true"} 234
```

### Distributed Tracing

Automatic trace correlation across service calls:

```
Trace: certificate_validation_flow
├── span: trust_chain_validation (trust_anchor_service)
├── span: pkd_key_lookup (pkd_service)
├── span: certificate_signature_check (document_signer)
└── span: revocation_status_check (certificate_validation)
```

## Production Deployment

### Container Configuration

```dockerfile
# MMF with Marty plugin
FROM mmf-base:latest

# Copy plugin
COPY src/plugins/marty /opt/mmf/plugins/marty
COPY config/plugins/marty.yaml /opt/mmf/config/plugins/

# Plugin will be auto-discovered and loaded
ENV MMF_PLUGIN_DISCOVERY_PATHS=/opt/mmf/plugins
ENV MMF_CONFIG_DIR=/opt/mmf/config
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mmf-marty-plugin
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mmf-marty-plugin
  template:
    spec:
      containers:
      - name: mmf
        image: mmf-marty:latest
        env:
        - name: MMF_ENVIRONMENT
          value: production
        - name: MMF_PLUGINS_ENABLED
          value: "true"
        ports:
        - containerPort: 8080
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
```

## Performance Considerations

### Resource Optimization

1. **Plugin Isolation**: Process-level isolation for security and stability
2. **Resource Limits**: Memory and CPU limits per plugin
3. **Caching Strategy**: Multi-level caching with TTL management
4. **Connection Pooling**: Shared database connections across services

### Scaling Patterns

1. **Horizontal Scaling**: Multiple plugin instances with load balancing
2. **Service Partitioning**: Individual services can be scaled independently
3. **Circuit Breakers**: Automatic failure isolation and recovery
4. **Bulkhead Pattern**: Resource isolation between service types

## Security

### Authentication & Authorization

1. **Role-Based Access Control**: Service-level and method-level permissions
2. **JWT Token Validation**: Automatic token verification and claims extraction
3. **Mutual TLS**: Certificate-based service authentication
4. **API Key Management**: Secure key distribution and rotation

### Cryptographic Operations

1. **HSM Integration**: Hardware security module support via MMF security service
2. **Key Rotation**: Automatic cryptographic key lifecycle management
3. **Certificate Validation**: X.509 certificate chain validation and revocation checking
4. **Secure Storage**: Encrypted storage for sensitive configuration and keys

## Troubleshooting

### Common Issues

1. **Plugin Loading Failures**:

   ```bash
   # Check plugin discovery paths
   export MMF_PLUGIN_DISCOVERY_PATHS=/correct/path

   # Verify plugin manifest
   cat src/plugins/marty/plugin.yaml
   ```

2. **Configuration Errors**:

   ```bash
   # Validate configuration
   mmf-cli config validate --plugin=marty

   # Check configuration loading
   mmf-cli config show --plugin=marty
   ```

3. **Service Health Issues**:

   ```bash
   # Check service health
   curl http://localhost:8080/health

   # Check plugin-specific health
   curl http://localhost:8080/plugins/marty/health
   ```

### Debug Logging

```python
# Enable debug logging for plugin system
logging.getLogger("framework.plugins").setLevel(logging.DEBUG)
logging.getLogger("plugins.marty").setLevel(logging.DEBUG)
```

## Contributing

### Plugin Development Guidelines

1. **Follow MMF Patterns**: Use established patterns for configuration, error handling, and logging
2. **Comprehensive Testing**: Include unit tests, integration tests, and contract tests
3. **Documentation**: Provide clear API documentation and usage examples
4. **Security Review**: Ensure secure coding practices and vulnerability scanning
5. **Performance Testing**: Validate performance under expected load conditions

### Code Style

```python
# Use type hints
async def process_request(self, request: RequestType) -> ResponseType:
    pass

# Use MMF decorators for cross-cutting concerns
@requires_auth(roles=["admin"])
@track_metrics(metric_name="admin_operations")
async def admin_operation(self):
    pass

# Use structured logging
logger.info("Operation completed", extra={
    "operation": "document_signing",
    "algorithm": algorithm,
    "duration": duration
})
```

## References

- [MMF Plugin API Documentation](./docs/plugin-api.md)
- [MMF Configuration Guide](./docs/configuration.md)
- [MMF Security Architecture](./docs/security.md)
- [MMF Observability Guide](./docs/observability.md)
- [Marty Migration Documentation](./MARTY_MMF_PLUGIN_STRATEGY.md)
