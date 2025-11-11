# Enterprise Security Framework

The Enterprise Security Framework provides comprehensive security capabilities for microservices, including authentication, authorization, rate limiting, and security middleware.

## 🔐 Features

### **Multi-Factor Authentication**

- **JWT Authentication**: Secure token-based authentication with configurable expiration
- **API Key Authentication**: Header or query parameter API key validation
- **Mutual TLS (mTLS)**: Certificate-based authentication for high-security environments

### **Role-Based Access Control (RBAC)**

- **Granular Permissions**: Resource-level permissions with read/write/delete/admin levels
- **Role Inheritance**: Hierarchical role system with permission inheritance
- **Decorators**: Simple `@require_permission` and `@require_role` decorators

### **Advanced Rate Limiting**

- **Multiple Backends**: In-memory and Redis-based rate limiting
- **Flexible Rules**: Per-endpoint, per-user, and global rate limits
- **Sliding Window**: Accurate rate limiting using sliding window algorithm

### **Security Middleware**

- **FastAPI Integration**: Drop-in middleware for FastAPI applications
- **gRPC Support**: Security interceptors for gRPC services
- **Security Headers**: Automatic security header injection

## 🚀 Quick Start

### 1. Basic Setup

```python
from framework.security import (
    SecurityConfig,
    SecurityLevel,
    JWTConfig,
    FastAPISecurityMiddleware,
    require_authentication
)
from fastapi import FastAPI, Depends

# Create security configuration
security_config = SecurityConfig(
    security_level=SecurityLevel.HIGH,
    service_name="my-service",
    jwt_config=JWTConfig(
        secret_key="your-secret-key",
        access_token_expire_minutes=30
    ),
    enable_jwt=True,
    enable_rate_limiting=True
)

# Create FastAPI app
app = FastAPI()

# Add security middleware
app.add_middleware(FastAPISecurityMiddleware, config=security_config)

# Protected endpoint
@app.get("/protected")
async def protected_endpoint(user=Depends(require_authentication)):
    return {"message": f"Hello {user.username}!"}
```

### 2. Environment-Based Configuration

```python
# Use environment variables for configuration
security_config = SecurityConfig.from_environment("my-service")

# Set environment variables:
# JWT_SECRET_KEY=your-secret-key
# SECURITY_LEVEL=high
# RATE_LIMIT_ENABLED=true
# REDIS_URL=redis://localhost:6379
```

### 3. Role-Based Authorization

```python
from framework.security import require_role_dependency, require_permission_dependency

# Require specific role
@app.get("/admin")
async def admin_endpoint(user=Depends(require_role_dependency("admin"))):
    return {"message": "Admin only"}

# Require specific permission
@app.get("/write-data")
async def write_endpoint(user=Depends(require_permission_dependency("api:write"))):
    return {"message": "Write permission required"}
```

## 📋 Configuration Options

### Security Levels

```python
class SecurityLevel(Enum):
    LOW = "low"          # Development
    MEDIUM = "medium"    # Staging
    HIGH = "high"        # Production
    CRITICAL = "critical" # High-security production
```

### JWT Configuration

```python
jwt_config = JWTConfig(
    secret_key="your-secret-key",
    algorithm="HS256",
    access_token_expire_minutes=30,
    refresh_token_expire_days=7,
    issuer="your-service",
    audience="your-audience"
)
```

### Rate Limiting Configuration

```python
rate_limit_config = RateLimitConfig(
    enabled=True,
    default_rate="100/minute",
    redis_url="redis://localhost:6379",
    per_endpoint_limits={
        "/sensitive": "10/minute",
        "/admin": "5/minute"
    },
    per_user_limits={
        "admin_user": "1000/minute"
    }
)
```

## 🔧 Authentication Methods

### JWT Authentication

```python
# Login endpoint
@app.post("/auth/login")
async def login(credentials: LoginCredentials):
    # Validate credentials
    jwt_auth = JWTAuthenticator(security_config)
    result = await jwt_auth.authenticate({
        "username": credentials.username,
        "password": credentials.password
    })

    if result.success:
        return {"access_token": result.metadata["access_token"]}
    raise HTTPException(status_code=401, detail="Invalid credentials")

# Use JWT token
# Authorization: Bearer <token>
```

### API Key Authentication

```python
# Configure API keys
api_key_config = APIKeyConfig(
    header_name="X-API-Key",
    valid_keys=["key1", "key2", "key3"]
)

# Use API key
# X-API-Key: your-api-key
```

### Mutual TLS (mTLS)

```python
# Configure mTLS
mtls_config = MTLSConfig(
    ca_cert_path="/path/to/ca.crt",
    verify_client_cert=True,
    allowed_issuers=["trusted-ca"]
)

# Client certificate automatically validated
```

## 🛡️ Authorization System

### Permission System

```python
from framework.security import Permission, PermissionLevel

# Define permissions
read_permission = Permission("read", "api", PermissionLevel.READ)
write_permission = Permission("write", "api", PermissionLevel.WRITE)
admin_permission = Permission("admin", "system", PermissionLevel.ADMIN)

# Check permissions
@require_permission("api:read")
async def read_data():
    return {"data": "some data"}

@require_permission("api:write")
async def write_data():
    return {"message": "data written"}
```

### Role System

```python
from framework.security import Role, get_rbac

# Create custom roles
rbac = get_rbac()

# Create role with permissions
viewer_role = Role("viewer", description="Read-only access")
viewer_role.add_permission(read_permission)

editor_role = Role("editor", description="Read-write access")
editor_role.add_permission(read_permission)
editor_role.add_permission(write_permission)

# Register roles
rbac.register_role(viewer_role)
rbac.register_role(editor_role)

# Use roles
@require_role("editor")
async def edit_endpoint():
    return {"message": "editing allowed"}
```

## ⚡ Rate Limiting

### Basic Rate Limiting

```python
from framework.security import rate_limit, initialize_rate_limiter

# Initialize rate limiter
initialize_rate_limiter(rate_limit_config)

# Apply rate limiting
@rate_limit(endpoint="sensitive_endpoint")
async def sensitive_operation():
    return {"message": "rate limited"}

# Custom identifier
@rate_limit(identifier_func=lambda request: request.headers.get("user-id"))
async def user_specific_endpoint():
    return {"message": "per-user rate limited"}
```

### Rate Limit Responses

Rate limited requests return HTTP 429 with headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640995200
Retry-After: 60
```

## 🔒 Security Headers

Automatically applied security headers:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
```

## 🎯 gRPC Integration

```python
from framework.security import GRPCSecurityInterceptor
import grpc

# Create gRPC server with security
server = grpc.aio.server(
    interceptors=[GRPCSecurityInterceptor(security_config)]
)

# Security is automatically applied to all gRPC methods
```

## 🧪 Testing

### Test with JWT

```bash
# 1. Get JWT token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "password"}'

# 2. Use token
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/protected
```

### Test with API Key

```bash
curl -H "X-API-Key: demo-api-key-1" \
  http://localhost:8000/api/service
```

### Test Rate Limiting

```bash
# Make multiple requests quickly to trigger rate limiting
for i in {1..150}; do
  curl http://localhost:8000/api/sensitive
done
```

## 🔧 Advanced Configuration

### Custom Authentication Backend

```python
from framework.security import BaseAuthenticator

class CustomAuthenticator(BaseAuthenticator):
    async def authenticate(self, credentials):
        # Custom authentication logic
        pass

    async def validate_token(self, token):
        # Custom token validation
        pass
```

### Custom Rate Limit Backend

```python
from framework.security import RateLimitBackend

class CustomRateLimitBackend(RateLimitBackend):
    async def increment(self, key, window, limit):
        # Custom rate limiting logic
        pass

    async def reset(self, key):
        # Custom reset logic
        pass
```

## 📊 Monitoring & Observability

The security framework integrates with the observability stack:

- **Metrics**: Authentication success/failure rates, rate limit hits
- **Logging**: Security events, authentication attempts, authorization failures
- **Tracing**: Request correlation IDs through security pipeline

## 🚨 Security Best Practices

1. **Secret Management**: Never hardcode secrets, use environment variables or key vaults
2. **Token Expiration**: Use short-lived access tokens with refresh tokens
3. **Rate Limiting**: Always enable rate limiting in production
4. **HTTPS Only**: Never transmit authentication tokens over HTTP
5. **Audit Logging**: Enable comprehensive audit logging for compliance
6. **Principle of Least Privilege**: Grant minimal required permissions
7. **Regular Rotation**: Rotate secrets and certificates regularly

## 🔄 Migration from Basic Auth

```python
# Before: Basic authentication
@app.get("/api/data")
async def get_data(token: str = Depends(oauth2_scheme)):
    # Manual token validation
    user = validate_token(token)
    if not user:
        raise HTTPException(status_code=401)
    return {"data": "some data"}

# After: Enterprise Security Framework
@app.get("/api/data")
async def get_data(user=Depends(require_authentication)):
    # Automatic authentication + authorization + rate limiting
    return {"data": "some data"}
```

## 📚 Examples

See `examples/security_example.py` for a complete working example demonstrating:

- JWT and API key authentication
- Role-based authorization
- Rate limiting
- Security middleware integration
- Error handling

## 🤝 Contributing

The Enterprise Security Framework is designed to be extensible. You can:

1. Add custom authentication providers
2. Implement custom authorization logic
3. Create specialized rate limiting backends
4. Extend middleware functionality

---

*Enterprise Security Framework - Part of the Marty Microservices Framework*
