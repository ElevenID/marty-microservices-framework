# MMF Plugin Strategy

## Overview

The Marty Microservices Framework (MMF) implements a robust plugin architecture that supports domain-driven plugin development with comprehensive integration capabilities. This strategy emphasizes plugins as domain bundles with entry-point registration and automated service generation.

## Plugin Architecture Principles

### Domain Bundle Approach

- **Plugins represent business domains**, not individual services
- **Multiple services per plugin** when they share domain boundaries
- **Single entry point registration** per domain with multiple service exposures
- **Shared configuration** and lifecycle management within domain boundaries

### Two Plugin Types

#### 1. Service Plugins (MMFPlugin)

Domain bundles that provide business logic and services:

```
plugins/<domain-plugin>/
├── __init__.py                     # Plugin package entry point
├── plugin.py                       # MMFPlugin implementation
├── services/                       # Business service implementations
├── models/                         # Domain models
├── api/                           # API endpoints (if needed)
└── config/                        # Plugin configuration
```

#### 2. Gateway Plugins (Middleware)

Cross-cutting concern handlers for the API gateway:

- Authentication and authorization
- Rate limiting and throttling
- Request/response transformation
- Logging and monitoring

## Architecture Components

### 1. Plugin Discovery and Registration

#### Entry Point Registration

```toml
# In pyproject.toml
[project.entry-points."mmf.plugins"]
payment_processing = "plugins.payment_processing:PaymentPlugin"
inventory_mgmt = "plugins.inventory_management:InventoryPlugin"
```

#### Plugin Base Class

- **Interface**: `MMFPlugin` from `src/marty_msf/framework/plugins/core.py`
- **Required Methods**:
  - `get_metadata()`: Returns plugin name, version, dependencies
  - `get_service_definitions()`: Returns available services
  - Optional: `initialize()`, `shutdown()`, `get_configuration_schema()`
- **Usage**:

  ```bash
  python3 scripts/generate_plugin_service.py --name payment-service --plugin production_payment
  ```

#### Generated Service Features

- Plugin integration manager
- Automatic plugin loading on startup
- Plugin-specific configuration
- Health checks including plugin status
- Documentation for plugin usage

## Configuration Flow

### 1. Plugin Discovery

```yaml
# config/base.yaml
plugins:
  enabled: true
  auto_discovery: true
  discovery_paths:
    - "./plugins"
    - "/opt/mmf/plugins"
  config_dir: "./config/plugins"
```

### 2. Plugin Loading

```yaml
# Environment-specific loading
default_plugins:
  - name: "production_payment"
    enabled: true
    priority: 100
```

### 3. Plugin Configuration

```yaml
# config/plugins/production_payment_service.yaml
default:
  enabled: true
  auto_load: true

service:
  name: "production-payment-service"
  port: 8080

payment:
  provider: "stripe"
  fraud_detection_enabled: true
```

## Development Workflow

### 1. Plugin Development

1. Create plugin directory structure
2. Implement `MMFPlugin` subclass
3. Define service definitions and routes
4. Add configuration schema
5. Register entry point in `pyproject.toml`

### 2. Service Generation

1. Use generator script with plugin parameter
2. Configure plugin settings for environment
3. Test plugin integration
4. Deploy with plugin auto-loading

### 3. Testing and Verification

- **Import Test**: Verify plugin can be imported
- **Metadata Test**: Check plugin metadata structure
- **Service Test**: Validate service definitions
- **Configuration Test**: Ensure config files are properly structured

## Key Benefits

### 1. Auto-Loading Architecture

- **Entry Point Discovery**: Plugins discovered via `importlib.metadata`
- **Configuration-Driven**: Plugin loading controlled by config files
- **Environment-Aware**: Different loading strategies per environment

### 2. Enterprise Integration

- **Security**: Sandboxing and signature verification in production
- **Monitoring**: Plugin health checks and metrics
- **Lifecycle Management**: Proper initialization and shutdown

### 3. Developer Experience

- **Generator Scripts**: Automated service creation with plugin integration
- **Configuration Management**: Centralized plugin configuration
- **Documentation**: Clear integration guides and examples

## Production Deployment

### 1. Security Configuration

```yaml
# config/production.yaml
plugins:
  security:
    require_signature: true
    sandboxing:
      enabled: true
      resource_limits:
        memory_mb: 256
        cpu_percent: 30
```

### 2. Monitoring Integration

- Plugin status in health checks
- Metrics collection for plugin performance
- Audit logging for plugin operations

### 3. Deployment Process

1. Build service with plugin dependencies
2. Configure plugin settings per environment
3. Deploy with framework auto-loading
4. Monitor plugin integration health

## Example Usage

### Creating a New Service with Plugin

```bash
# Generate service with plugin integration
python3 scripts/generate_plugin_service.py \
  --name payment-service \
  --plugin production_payment \
  --type fastapi

# Service includes:
# - Plugin integration manager
# - Auto-loading configuration
# - Plugin-specific routes
# - Health checks with plugin status
```

### Plugin Configuration

```yaml
# Service-specific plugin config
plugin_settings:
  production_payment:
    enabled: true
    service_integration: true
    service_specific:
      name: "payment-service"
      fraud_detection_threshold: 0.7
```

## Next Steps

1. **Service Generation**: Use generator scripts to create services with plugin integration
2. **Configuration Tuning**: Adjust plugin settings for specific environments
3. **Testing**: Implement comprehensive plugin integration tests
4. **Monitoring**: Set up plugin performance and health monitoring
5. **Documentation**: Create deployment and operations guides

This refined plugin strategy provides a production-ready foundation for extending the MMF framework while maintaining clean separation of concerns, enterprise security, and operational visibility.
