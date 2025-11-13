# Enhanced Security Architecture - OPA Integration

## Overview

The Marty Microservices Framework's enhanced security system integrates with **OPA (Open Policy Agent)** as the primary policy engine for enterprise-grade authorization decisions. This document outlines the simplified, production-ready security architecture focused on OPA integration.

## Security Architecture Principles

### 1. Policy as Code with OPA

- **Principle**: Authorization policies defined in Rego language and version-controlled
- **Implementation**: OPA service with Git-based policy management
- **Benefits**: Auditability, consistency, industry-standard approach

### 2. Unified Security Framework

- **Principle**: Single, cohesive security system with OPA at the core
- **Implementation**: Enhanced security decorators that integrate RBAC, ABAC, and OPA evaluation
- **Benefits**: Reduced complexity, consistent security model, easier maintenance

### 3. Zero Trust Security Model

- **Principle**: Never trust, always verify through policy evaluation
- **Implementation**: Every request is authenticated and authorized via OPA
- **Benefits**: Reduced attack surface, fine-grained control

### 4. Comprehensive Audit Trail

- **Principle**: All security decisions are logged and auditable
- **Implementation**: Multi-sink audit logging with OPA decision tracking
- **Benefits**: Compliance, debugging, security monitoring

## Enhanced Security Components

### 1. Core Security Framework

The enhanced security framework provides:

```python
from marty_msf.security import (
    configure_opa_service,
    requires_auth,
    SecurityManager,
    SecurityAuditor
)

# Configure OPA integration
configure_opa_service(
    url="http://opa-policy-engine:8181",
    policy_path="v1/data/authz/allow",
    timeout=5.0
)

# Use enhanced decorators
@requires_auth(method="opa")
async def protected_resource():
    return {"message": "Access granted"}
```

### 2. Enhanced Security Decorators

**Key Features:**

- JWT token validation with comprehensive claims verification
- RBAC (Role-Based Access Control) integration
- ABAC (Attribute-Based Access Control) support
- OPA policy evaluation
- Comprehensive error handling and audit logging

**Available Decorators:**

```python
@requires_auth(method="jwt")              # JWT validation only
@requires_auth(method="rbac", roles=["admin"])  # RBAC check
@requires_auth(method="abac", policy="resource_access")  # ABAC policy
@requires_auth(method="opa")              # OPA policy evaluation
@requires_role("admin")                   # Role requirement
@requires_permission("users:read")       # Permission check
```

### 3. OPA Policy Engine Integration

**Architecture:**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Application   │────│  Security Layer  │────│   OPA Service   │
│                 │    │                  │    │                 │
│  @requires_auth │    │ SecurityManager  │    │  Policy Engine  │
│     decorators  │    │   JWT + RBAC     │    │   Rego Policies │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Audit System   │
                       │  Multi-sink Log  │
                       └──────────────────┘
```

**Policy Evaluation Flow:**

1. Request arrives with JWT token
2. SecurityManager validates token and extracts claims
3. RBAC/ABAC checks performed if configured
4. OPA policy evaluation with full context
5. Decision logged to audit system
6. Access granted or denied based on policy result

### 4. RBAC (Role-Based Access Control)

**Features:**

- Hierarchical role inheritance
- Permission pattern matching with wildcards
- Role metadata and caching
- Integration with OPA policies

**Example Usage:**

```python
from marty_msf.security.rbac import RBACManager, Role, Permission

# Define permissions and roles
rbac = RBACManager()
await rbac.add_permission(Permission("users:read", "Read user data"))
await rbac.add_permission(Permission("users:*", "All user operations"))

admin_role = Role("admin", "Administrator", permissions=["users:*"])
await rbac.add_role(admin_role)
```

### 5. ABAC (Attribute-Based Access Control)

**Features:**

- Attribute condition evaluation
- Policy effect determination
- Context-aware access control
- Dynamic attribute evaluation

**Example Usage:**

```python
from marty_msf.security.abac import ABACManager, ABACPolicy

# Define ABAC policy
policy = ABACPolicy(
    name="resource_owner_access",
    resource_pattern="profile:*",
    action_pattern="read",
    conditions=[
        AttributeCondition("principal.id", "equals", "resource.owner_id")
    ],
    effect=PolicyEffect.ALLOW
)

abac = ABACManager()
await abac.add_policy(policy)
```

### 6. Comprehensive Audit Logging

**Features:**

- Multiple audit sinks (file, syslog, elasticsearch)
- Structured security event logging
- Async processing for performance
- Automatic correlation with security decisions

**Audit Event Structure:**

```python
@dataclass
class SecurityAuditEvent:
    event_id: str
    timestamp: datetime
    event_type: str
    principal: Dict[str, Any]
    resource: str
    action: str
    decision: str
    context: Dict[str, Any]
    metadata: Dict[str, Any]
```

## OPA Integration Details

### 1. Service Deployment

**Kubernetes:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opa-policy-engine
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: opa
        image: openpolicyagent/opa:0.67.1-envoy
        args: ["run", "--server", "--addr=0.0.0.0:8181"]
```

**Docker Compose (Development):**

```yaml
services:
  opa:
    image: openpolicyagent/opa:0.67.1-envoy
    ports: ["8181:8181"]
    command: ["run", "--server", "--addr=0.0.0.0:8181"]
```

### 2. Policy Structure

**Example Authorization Policy (Rego):**

```rego
package authz

default allow := false

# Admin access
allow if {
    input.principal.roles[_] == "admin"
}

# Resource owner access
allow if {
    input.principal.id == input.resource_owner
    input.action in ["read", "update"]
}

# Role-based permissions
allow if {
    some role in input.principal.roles
    role_permissions[role][input.resource_type][_] == input.action
}
```

### 3. Security Manager Integration

The SecurityManager coordinates all security components:

```python
class SecurityManager:
    def __init__(self):
        self.jwt_service = JWTService()
        self.rbac_manager = RBACManager()
        self.abac_manager = ABACManager()
        self.auditor = SecurityAuditor()
        self.opa_service = get_policy_service()

    async def evaluate_access(self, context: SecurityContext) -> bool:
        # Validate JWT token
        claims = await self.jwt_service.validate_token(context.token)

        # Perform RBAC/ABAC checks
        rbac_allowed = await self.rbac_manager.check_access(...)
        abac_allowed = await self.abac_manager.evaluate(...)

        # OPA policy evaluation
        opa_response = await self.opa_service.evaluate_policy(...)

        # Log decision
        await self.auditor.log_event(...)

        return opa_response.allow
```

## Security Configuration

### 1. Application Setup

```python
from marty_msf.security import configure_opa_service

# Configure security system
configure_opa_service(
    url="http://opa-policy-engine:8181",
    policy_path="v1/data/authz/allow"
)
```

### 2. FastAPI Integration

```python
from fastapi import FastAPI, Depends
from marty_msf.security import requires_auth, get_current_user

app = FastAPI()

@app.get("/protected")
@requires_auth(method="opa")
async def protected_endpoint(current_user = Depends(get_current_user)):
    return {"user": current_user, "message": "Access granted"}
```

### 3. Environment Configuration

```yaml
# config/production.yaml
security:
  opa:
    url: "http://opa-policy-engine:8181"
    policy_path: "v1/data/authz/allow"
    timeout: 5.0

  jwt:
    secret_key: "${JWT_SECRET_KEY}"
    algorithm: "HS256"
    expire_minutes: 60

  audit:
    sinks:
      - type: "file"
        path: "/var/log/security/audit.log"
      - type: "syslog"
        facility: "auth"
```

## Benefits of OPA Integration

### 1. Industry Standard

- OPA is the CNCF graduated project for policy as code
- Widely adopted in cloud-native environments
- Excellent tooling and community support

### 2. Separation of Concerns

- Policies are external to application code
- Version-controlled policy management
- Independent policy testing and validation

### 3. Performance

- High-performance policy evaluation
- Built-in caching mechanisms
- Horizontal scaling support

### 4. Flexibility

- Rego language supports complex authorization logic
- Dynamic policy updates without code changes
- Integration with external data sources

### 5. Observability

- Comprehensive decision logging
- Metrics and health checks
- Integration with monitoring systems

## Migration Guide

### From Basic Auth to Enhanced Security

1. **Install dependencies:**

   ```bash
   uv add aiohttp
   ```

2. **Update imports:**

   ```python
   # Old
   from marty_msf.authentication import requires_auth

   # New
   from marty_msf.security import requires_auth, configure_opa_service
   ```

3. **Configure OPA:**

   ```python
   configure_opa_service(url="http://localhost:8181")
   ```

4. **Update decorators:**

   ```python
   # Enhanced with OPA
   @requires_auth(method="opa")
   async def my_endpoint():
       pass
   ```

### Policy Development Workflow

1. **Develop policies locally:**

   ```bash
   opa test ops/dev/policies/
   ```

2. **Test with sample data:**

   ```bash
   opa eval -d authz.rego "data.authz.allow" --input test-input.json
   ```

3. **Deploy to staging:**

   ```bash
   kubectl apply -f ops/k8s/opa-deployment.yaml
   ```

4. **Validate in staging environment**

5. **Deploy to production with GitOps**

## Security Best Practices

### 1. Policy Management

- Store policies in version control
- Use GitOps for policy deployment
- Implement policy review process
- Test policies thoroughly

### 2. Network Security

- Restrict OPA access to service mesh only
- Use mTLS for OPA communication
- Implement network policies

### 3. Monitoring

- Monitor OPA health and performance
- Alert on policy evaluation failures
- Track decision patterns for anomalies

### 4. Incident Response

- Implement graceful degradation
- Maintain audit logs for investigation
- Have policy rollback procedures

This enhanced security architecture provides enterprise-grade authorization with OPA while maintaining simplicity and ease of adoption.
