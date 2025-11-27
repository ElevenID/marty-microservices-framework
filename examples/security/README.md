# Security Examples - Marty Microservices Framework

This directory contains examples demonstrating the **Unified Security Framework** and enhanced security capabilities.

## 🚀 **Updated Examples (Current)**

### ✅ `test_unified_framework.py`

Simple test showing the unified security framework initialization and basic authorization check.

### ✅ `basic_security_example.py`

FastAPI integration example using the unified security framework with RBAC policies.

### ✅ `unified_security_demo.py`

Comprehensive demonstration of unified security capabilities including RBAC, ABAC, service mesh security, and compliance scanning.

### ✅ `enhanced_service_mesh_demo.py`

Service mesh integration with real-time security policy enforcement and monitoring.

## ⚠️ **Legacy Examples (Need Updates)**

### `complete_integration_example.py`

**Status:** Uses deprecated APIs - needs migration to Unified Security Framework

## 🔄 **Migration Summary**

The security framework has been **consolidated** into a unified architecture:

**Before (Deprecated):**

- Multiple competing implementations
- Scattered security components
- Complex integration patterns

**After (Unified):**

- Single `UnifiedSecurityFramework`
- Consistent API across all security operations
- Pluggable identity providers and policy engines
- **Policy Templates**: Reusable policy templates for common scenarios

## Quick Start

### 1. HashCorp Vault Setup

```bash
# Start Vault in dev mode
vault server -dev

# Enable KV secrets engine
vault secrets enable -path=secret kv-v2

# Store some test secrets
vault kv put secret/api_keys/service1 value="sk-test-key-12345"
vault kv put secret/jwt_secret value="super-secret-jwt-key"
vault kv put secret/database_url value="postgresql://user:pass@localhost/db"
```

### 2. Basic Integration

```python
from marty_msf.security.secrets import VaultClient, VaultConfig, SecretManager
from marty_msf.security.authorization import PolicyManager, PolicyEngineEnum

# Initialize Vault client
vault_config = VaultConfig(
    url="http://localhost:8200",
    auth_method=VaultAuthMethod.TOKEN,
    token="hvs.dev-token"
)
vault_client = VaultClient(vault_config)
await vault_client.authenticate()

# Initialize secret manager
secret_manager = SecretManager(
    service_name="my_service",
    vault_client=vault_client
)

# Initialize policy manager
policy_manager = PolicyManager(primary_engine=PolicyEngineEnum.BUILTIN)

# Get secrets
api_key = await secret_manager.get_secret("api_keys/service1")
jwt_secret = await secret_manager.get_secret("jwt_secret")
```

## Policy Examples

### RBAC Policy (Built-in Engine)

```json
{
  "id": "user_management_rbac",
  "name": "User Management RBAC",
  "rules": [
    {
      "resource": "/api/v1/users/*",
      "action": "GET",
      "principal": {
        "roles": ["admin", "user"]
      }
    },
    {
      "resource": "/api/v1/users/*",
      "action": "POST",
      "principal": {
        "roles": ["admin"]
      }
    },
    {
      "resource": "/api/v1/users/profile",
      "action": "*",
      "principal": {
        "type": "user"
      }
    }
  ]
}
```

### ABAC Policy (OPA Rego)

```rego
package authz

import future.keywords.if
import future.keywords.in

default allow = false

# Allow admin users to access all resources
allow if {
    "admin" in input.principal.roles
}

# Allow users to access their own profile
allow if {
    input.action == "GET"
    input.resource == "/api/v1/users/profile"
    input.principal.type == "user"
}

# Time-based access restrictions
allow if {
    input.action == "GET"
    input.resource == "/api/v1/reports/*"
    "analyst" in input.principal.roles
    business_hours
}

business_hours if {
    hour := time.clock(time.now_ns())[0]
    hour >= 9
    hour <= 17
}

# IP-based restrictions
allow if {
    input.action in ["GET", "POST"]
    input.resource == "/api/v1/sensitive/*"
    "security_team" in input.principal.roles
    trusted_network
}

trusted_network if {
    net.cidr_contains("10.0.0.0/8", input.environment.source_ip)
}
```

## Security Patterns

### 1. Service-to-Service Authentication

```python
# Service A calling Service B with mTLS
from marty_msf.security.gateway_integration import EnhancedSecurityMiddleware

# Configure mTLS
middleware = await create_enhanced_security_middleware(
    vault_config={
        "url": "http://vault:8200",
        "auth_method": "kubernetes",
        "role": "service-a"
    },
    require_mtls=True
)

# Add to FastAPI app
app.add_middleware(EnhancedSecurityMiddleware, middleware)
```

### 2. Zero Trust Network Access

```python
# Zero trust policy for microservice communication
policy = {
    "id": "zero_trust_service_access",
    "rules": [
        {
            "resource": "grpc:PaymentService/*",
            "action": "call",
            "principal": {
                "type": "service",
                "certificate_fingerprint": "sha256:abc123..."
            },
            "environment": {
                "service": "user-service"
            }
        }
    ]
}

await policy_manager.load_policy("zero_trust", json.dumps(policy))
```

### 3. Dynamic Secret Rotation

```python
# Automatic secret rotation
from marty_msf.security.secrets import SecretType

# Set up secret with rotation
await secret_manager.set_secret(
    key="database_password",
    value="initial-password",
    secret_type=SecretType.PASSWORD,
    rotation_interval=timedelta(days=30)
)

# Check for secrets needing rotation
secrets_to_rotate = secret_manager.get_secrets_needing_rotation()
for secret_key in secrets_to_rotate:
    await secret_manager.rotate_secret(secret_key)
```

## Infrastructure Requirements

### Vault Setup

```yaml
# vault-config.yml
ui = true
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = 1
}

storage "file" {
  path = "/vault/data"
}

# Enable required auth methods
auth {
  kubernetes {
    kubernetes_host = "https://kubernetes.default.svc"
  }

  approle {
    role_id_file = "/vault/config/role-id"
    secret_id_file = "/vault/config/secret-id"
  }
}

# Enable secret engines
secrets {
  kv-v2 "secret" {}
  pki "pki" {}
  database "database" {}
  transit "transit" {}
}
```

### OPA Deployment

```yaml
# opa-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opa
spec:
  replicas: 1
  selector:
    matchLabels:
      app: opa
  template:
    metadata:
      labels:
        app: opa
    spec:
      containers:
      - name: opa
        image: openpolicyagent/opa:latest
        args:
          - "run"
          - "--server"
          - "--bundle"
          - "/policies"
        ports:
        - containerPort: 8181
        volumeMounts:
        - name: policies
          mountPath: /policies
      volumes:
      - name: policies
        configMap:
          name: opa-policies
```

## Best Practices

### 1. Secret Management

- Use Vault for all sensitive data
- Implement automatic secret rotation
- Never store secrets in code or configuration files
- Use different secret backends for different environments

### 2. Policy Management

- Use OPA for complex attribute-based policies
- Keep policies version controlled
- Test policies thoroughly before deployment
- Monitor policy evaluation performance

### 3. Certificate Management

- Use short-lived certificates (24-48 hours)
- Implement automatic certificate rotation
- Use separate CAs for different environments
- Monitor certificate expiration

### 4. Audit and Compliance

- Log all authentication and authorization events
- Implement centralized log collection
- Set up alerting for security events
- Regular security audits and reviews

## Troubleshooting

### Common Issues

1. **Vault Authentication Failures**
   - Check Vault server connectivity
   - Verify authentication credentials
   - Ensure required auth methods are enabled

2. **Policy Evaluation Errors**
   - Validate policy syntax
   - Check policy engine connectivity
   - Review policy evaluation logs

3. **Certificate Issues**
   - Verify certificate validity
   - Check certificate chain
   - Ensure proper certificate rotation

## Testing

Run the security test suite:

```bash
# Unit tests
pytest tests/security/

# Integration tests
pytest tests/integration/security/

# Security audit
python scripts/security_audit.py
```
