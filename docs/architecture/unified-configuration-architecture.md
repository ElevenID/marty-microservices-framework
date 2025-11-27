# Unified Configuration and Secret Management Architecture

This document describes the architecture of the Unified Configuration and Secret Management System, which provides a cloud-agnostic approach to configuration and secrets handling across different hosting environments.

## Architecture Overview

The Unified Configuration System is designed as a multi-layer architecture that abstracts away the complexity of different hosting environments and secret management solutions:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Layer                            │
│  ┌─────────────────────────┐   ┌─────────────────────────────┐  │
│  │     Service Code        │   │    Configuration Models     │  │
│  │  (FastAPI, gRPC, etc.)  │───│     (Pydantic Models)      │  │
│  └─────────────────────────┘   └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────┐
│                Unified Configuration Layer                      │
│  ┌─────────────────────────┐   ┌─────────────────────────────┐  │
│  │ UnifiedConfigurationMgr │   │   Environment Detector      │  │
│  │  - Config Loading       │───│   - Auto-detection          │  │
│  │  - Secret Resolution    │   │   - Backend Selection       │  │
│  │  - Type Validation      │   │   - Health Monitoring       │  │
│  └─────────────────────────┘   └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────┐
│                    Backend Layer                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │   Vault     │ │     AWS     │ │     GCP     │ │   Azure   │ │
│  │  Backend    │ │  Secrets    │ │   Secret    │ │    Key    │ │
│  │             │ │  Manager    │ │  Manager    │ │   Vault   │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │ Kubernetes  │ │Environment  │ │    File     │ │  Memory   │ │
│  │  Secrets    │ │ Variables   │ │   Backend   │ │  Backend  │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────┐
│                 Infrastructure Layer                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │ Self-Hosted │ │     AWS     │ │     GCP     │ │   Azure   │ │
│  │    / K8s    │ │Environment  │ │Environment  │ │Environment│ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Principles

### 1. Cloud Agnostic

- **Multi-Cloud Support**: Works seamlessly across AWS, GCP, Azure, and self-hosted environments
- **Automatic Detection**: Automatically detects the hosting environment and selects appropriate backends
- **Fallback Strategies**: Configurable fallback chains for high availability

### 2. Flexible Backend Architecture

- **Pluggable Backends**: Easy to add new secret management systems
- **Optional Dependencies**: Cloud SDKs are optional dependencies, loaded only when needed
- **Backend Health Monitoring**: Continuous health checking of all configured backends

### 3. Developer Experience

- **Secret References**: Simple `${SECRET:key}` syntax in configuration files
- **Type Safety**: Pydantic models for configuration validation
- **Hierarchical Configuration**: Environment-specific overrides (base → environment → secrets)

## Environment Detection

The system automatically detects the hosting environment using various indicators:

```python
class EnvironmentDetector:
    @staticmethod
    def detect_hosting_environment() -> HostingEnvironment:
        # AWS Detection
        if 'AWS_EXECUTION_ENV' in os.environ:
            return HostingEnvironment.AWS

        # GCP Detection
        if 'GOOGLE_CLOUD_PROJECT' in os.environ:
            return HostingEnvironment.GOOGLE_CLOUD

        # Azure Detection
        if 'AZURE_CLIENT_ID' in os.environ:
            return HostingEnvironment.AZURE

        # Kubernetes Detection
        if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount'):
            return HostingEnvironment.KUBERNETES

        # Docker Detection
        if os.path.exists('/.dockerenv'):
            return HostingEnvironment.DOCKER

        return HostingEnvironment.SELF_HOSTED
```

## Backend Selection Strategy

Based on the detected environment, the system recommends appropriate backends:

| Environment | Primary Backend | Secondary Backends |
|-------------|----------------|-------------------|
| AWS | AWS Secrets Manager | Environment Variables, Files |
| Google Cloud | GCP Secret Manager | Environment Variables, Files |
| Azure | Azure Key Vault | Environment Variables, Files |
| Kubernetes | Kubernetes Secrets, Vault | Environment Variables |
| Self-Hosted | Vault | Files, Environment Variables |
| Local Dev | Files | Environment Variables, Memory |

## Configuration Loading Strategy

### Hierarchical Loading

1. **Base Configuration**: `config/base.yaml`
2. **Environment Override**: `config/{environment}.yaml`
3. **Environment Variables**: Service-specific prefixes
4. **Secret Resolution**: Replace `${SECRET:key}` references

### Example Configuration Flow

```yaml
# base.yaml
database:
  host: "localhost"
  password: "${SECRET:database/password}"

# production.yaml
database:
  host: "${SECRET:database/host}"  # Override with secret
  ssl_mode: "require"
```

## Secret Backend Implementations

### Cloud-Native Backends

#### AWS Secrets Manager

- **Authentication**: IAM roles, profiles, or environment variables
- **Features**: Automatic rotation, versioning, cross-region replication
- **Dependency**: `boto3` (optional)

#### GCP Secret Manager

- **Authentication**: Service accounts, ADC, or environment variables
- **Features**: Versioning, IAM integration, audit logging
- **Dependency**: `google-cloud-secret-manager` (optional)

#### Azure Key Vault

- **Authentication**: Managed identity, service principal, or Azure CLI
- **Features**: Hardware security modules, certificate management
- **Dependency**: `azure-keyvault-secrets` (optional)

### Self-Hosted Backends

#### HashCorp Vault

- **Authentication**: Multiple methods (AppRole, Kubernetes, AWS IAM, etc.)
- **Features**: Dynamic secrets, encryption-as-a-service, audit logging
- **Integration**: Uses existing MMF Vault client

#### Kubernetes Secrets

- **Authentication**: Service account tokens
- **Features**: Namespace isolation, automatic mounting
- **Dependency**: `kubernetes` client (optional)

### Development Backends

#### File Backend

- **Storage**: Local filesystem with restricted permissions
- **Use Case**: Local development, testing
- **Security**: File permissions (0600)

#### Environment Variables

- **Storage**: Process environment
- **Use Case**: Development, simple deployments
- **Prefix**: Service-specific prefixes

## Security Considerations

### Secret Protection

- **In-Memory Caching**: TTL-based caching with automatic expiration
- **Encryption at Rest**: Relies on backend encryption (Vault, cloud services)
- **Audit Logging**: Access tracking for compliance

### Access Control

- **Least Privilege**: Each backend uses minimal required permissions
- **Authentication**: Uses platform-native authentication mechanisms
- **Authorization**: Backend-specific access controls

### Secret Rotation

- **Automatic Detection**: Identifies secrets needing rotation
- **Configurable Intervals**: Per-secret rotation schedules
- **Health Monitoring**: Tracks secret freshness and backend health

## Usage Patterns

### Auto-Detection Pattern (Recommended)

```python
config_manager = create_unified_config_manager(
    service_name="my-service",
    config_class=ServiceConfig,
    strategy=ConfigurationStrategy.AUTO_DETECT
)
```

### Explicit Configuration Pattern

```python
config_manager = create_unified_config_manager(
    service_name="my-service",
    config_class=ServiceConfig,
    strategy=ConfigurationStrategy.EXPLICIT,
    enable_aws_secrets=True,
    enable_vault=True,
    vault_config={"url": "https://vault.company.com"}
)
```

### Multi-Cloud Pattern

```python
config_manager = create_unified_config_manager(
    service_name="multi-cloud-service",
    config_class=ServiceConfig,
    strategy=ConfigurationStrategy.FALLBACK,
    enable_aws_secrets=True,
    enable_gcp_secrets=True,
    enable_azure_keyvault=True,
    enable_vault=True  # Self-hosted fallback
)
```

## Integration Points

### Service Templates

- **FastAPI Services**: Startup event integration
- **gRPC Services**: Async initialization patterns
- **Background Jobs**: Configuration loading in workers

### Framework Integration

- **Observability**: Configuration metrics and health checks
- **Plugin System**: Plugin-specific configuration loading
- **Database Connections**: Secret-based connection strings

## Monitoring and Operations

### Health Checks

- Backend connectivity monitoring
- Secret freshness tracking
- Configuration validation status

### Metrics

- Secret access patterns
- Backend response times
- Configuration reload frequencies

### Alerting

- Backend failures
- Secret expiration warnings
- Configuration validation errors

## Future Enhancements

### Planned Features

- **Configuration Hot Reloading**: Runtime configuration updates
- **Secret Encryption**: Client-side encryption for additional security
- **Configuration Versioning**: Track configuration changes over time
- **GUI Management**: Web interface for configuration management

### Additional Backends

- **Consul**: HashCorp Consul KV store integration
- **etcd**: etcd key-value store support
- **Database**: Database-backed configuration storage

This architecture ensures that the Marty Microservices Framework can handle configuration and secrets management across any hosting environment while maintaining security, reliability, and developer productivity.
