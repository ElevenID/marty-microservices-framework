# OPA Policy Engine Service

This directory contains the configuration for the Open Policy Agent (OPA) service that provides enterprise-grade policy evaluation for the Marty Microservices Framework.

## Overview

OPA (Open Policy Agent) is the industry standard for policy as code. It provides:

- **Unified Policy Language**: Rego language for expressing complex authorization policies
- **High Performance**: Fast policy evaluation with caching
- **Cloud Native**: Kubernetes-ready with health checks and metrics
- **Audit Trail**: Decision logging for compliance and debugging

## Quick Start

### Local Development

1. **Start OPA using Docker Compose:**

   ```bash
   cd ops/dev
   docker-compose -f docker-compose.opa.yml up -d
   ```

2. **Verify OPA is running:**

   ```bash
   curl http://localhost:8181/health
   ```

3. **Test a policy evaluation:**

   ```bash
   curl -X POST http://localhost:8181/v1/data/authz/allow \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "principal": {"id": "user123", "roles": ["user"]},
         "resource": "profile",
         "action": "read",
         "resource_owner": "user123"
       }
     }'
   ```

### Kubernetes Deployment

1. **Apply the OPA deployment:**

   ```bash
   kubectl apply -f ops/k8s/opa-deployment.yaml
   ```

2. **Verify deployment:**

   ```bash
   kubectl get pods -n marty-services -l app=opa-policy-engine
   ```

3. **Access OPA service:**

   ```bash
   kubectl port-forward -n marty-services svc/opa-policy-engine 8181:8181
   ```

## Configuration

### Policy Engine Integration

Configure the Marty security framework to use OPA:

```python
from marty_msf.security import configure_opa_service

# Configure OPA service
configure_opa_service(
    url="http://opa-policy-engine:8181",
    policy_path="v1/data/authz/allow",
    timeout=5.0
)
```

### Using in Decorators

```python
from marty_msf.security import requires_auth

@requires_auth(method="opa")
async def protected_endpoint(current_user: dict):
    return {"message": "Access granted"}
```

## Policy Structure

The default policy (`authz.rego`) includes:

### 1. Admin Access

- Admins can perform any action on any resource

### 2. Resource Owner Access

- Users can read/update their own resources

### 3. Public Resource Access

- Anyone can read public resources

### 4. Role-Based Access

- Different roles have different permissions on resource types

### 5. Service-to-Service

- Inter-service communication policies

## Policy Examples

### Allow user to read their own profile

```rego
allow if {
    input.principal.id == input.resource_owner
    input.action == "read"
    input.resource_type == "profile"
}
```

### Role-based permissions

```rego
allow if {
    some role in input.principal.roles
    role_permissions[role][input.resource_type][_] == input.action
}
```

## Monitoring

### Health Checks

- **Liveness**: `GET /health`
- **Readiness**: `GET /health?bundle=true`

### Metrics

OPA exposes Prometheus metrics at `/metrics`

### Decision Logs

All authorization decisions are logged for audit purposes.

## Security Considerations

1. **Network Security**: OPA should only be accessible within the service mesh
2. **Policy Updates**: Use GitOps for policy management
3. **Decision Logging**: Ensure logs are sent to secure storage
4. **Resource Limits**: Configure appropriate CPU/memory limits

## Development

### Testing Policies Locally

1. **Install OPA CLI:**

   ```bash
   curl -L -o opa https://openpolicyagent.org/downloads/v0.67.1/opa_darwin_amd64
   chmod +x opa
   sudo mv opa /usr/local/bin
   ```

2. **Test policies:**

   ```bash
   cd ops/dev/policies
   opa test .
   ```

3. **Evaluate specific input:**

   ```bash
   opa eval -d authz.rego "data.authz.allow" --input input.json
   ```

### Policy Updates

1. Update the policy files in `ops/dev/policies/` or `ops/k8s/opa-deployment.yaml`
2. Restart the OPA service to load new policies
3. Test the policy changes thoroughly before deploying to production

## Troubleshooting

### Common Issues

1. **Policy not loading**: Check ConfigMap and pod logs
2. **Connection refused**: Verify service is running and ports are correct
3. **Policy evaluation errors**: Check Rego syntax and test policies

### Debug Commands

```bash
# Check OPA logs
docker logs marty-opa

# Or in Kubernetes
kubectl logs -n marty-services deployment/opa-policy-engine

# Inspect policies
curl http://localhost:8181/v1/policies

# Get policy decision with reasoning
curl -X POST http://localhost:8181/v1/data/authz \
  -H "Content-Type: application/json" \
  -d '{"input": {...}, "explain": "full"}'
```
