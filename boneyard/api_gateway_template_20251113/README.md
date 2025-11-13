# Enterprise API Gateway Service

A comprehensive API Gateway implementation built on the Marty microservices framework, providing enterprise-grade features for routing, service discovery, load balancing, and resilience patterns.

## Features

### Core Capabilities

- **Dynamic Service Discovery**: In-memory service registry with extensible backend support
  - ⚠️ **Note**: Consul, etcd, and Kubernetes backends are currently stub implementations
  - Production deployments should implement real backend connectors as needed
- **Load Balancing**: Multiple strategies including round-robin, least connections, and weighted distribution
- **Circuit Breaker**: Automatic failure detection and recovery
- **Rate Limiting**: Per-IP and per-user request throttling
- **Authentication**: JWT and API key support
- **Response Caching**: Redis-backed caching with configurable TTL
- **Request/Response Transformation**: Middleware for data transformation
- **CORS Support**: Configurable cross-origin resource sharing

### Monitoring & Observability

- **Metrics**: Prometheus-compatible metrics collection
- **Distributed Tracing**: Jaeger integration for request tracing
- **Health Checks**: Service and dependency health monitoring
- **Structured Logging**: JSON-formatted logs with correlation IDs

### Resilience Patterns

- **Circuit Breakers**: Prevent cascading failures
- **Retries**: Configurable retry policies with exponential backoff
- **Timeouts**: Request-level timeout management
- **Bulkhead Isolation**: Resource isolation for stability

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (for service discovery backends)
- Redis (for caching)

### Installation

1. **Clone and Install Dependencies**

```bash
git clone <repository>
cd api-gateway-service
pip install -e .
```

2. **Start Required Services**

```bash
# Start Consul for service discovery
docker run -d --name consul -p 8500:8500 consul:latest

# Start Redis for caching
docker run -d --name redis -p 6379:6379 redis:latest
```

3. **Configure the Gateway**

```python
# config.py - Customize for your environment
from config import create_development_config

config = create_development_config()
# Modify routes, authentication, etc.
```

4. **Run the Gateway**

```bash
python main.py
```

The gateway will be available at `http://localhost:8080`

## Configuration

### Environment Variables

```bash
# Service Discovery
CONSUL_HOST=localhost
CONSUL_PORT=8500
CONSUL_TOKEN=optional-token

# Authentication
JWT_SECRET=your-jwt-secret-key
JWT_ALGORITHM=HS256

# Caching
REDIS_HOST=localhost
REDIS_PORT=6379

# Monitoring
JAEGER_ENDPOINT=http://localhost:14268/api/traces
METRICS_PORT=9090
```

### Route Configuration

```python
from config import RouteDefinition, RateLimitConfig, CircuitBreakerConfig

# Define custom routes
routes = [
    RouteDefinition(
        name="user_api",
        path_pattern="/api/v1/users/**",
        target_service="user-service",
        methods=["GET", "POST", "PUT", "DELETE"],
        require_auth=True,
        rate_limit=RateLimitConfig(requests_per_second=100),
        circuit_breaker=CircuitBreakerConfig(failure_threshold=5),
        enable_caching=True,
        cache_ttl=300
    )
]
```

## API Endpoints

### Core Gateway Endpoints

- `GET /health` - Gateway health status
- `GET /metrics` - Prometheus metrics
- `GET /routes` - Configured routes summary
- `GET /services` - Discovered services
- `GET /services/{service_name}` - Service instances

### Service Routing

All configured routes are automatically handled:

- `/{route_pattern}` - Routed to target services
- Authentication, rate limiting, and circuit breaking applied per route

## Service Discovery

### Current Implementation

The gateway currently uses an in-memory service registry for development and testing:

```python
service_discovery = ServiceDiscoveryConfig(
    type=ServiceDiscoveryType.IN_MEMORY,
    health_check_interval=30
)
```

### Future Backend Support (Stub Implementations)

⚠️ **Development Status**: The following backends have placeholder implementations:

```python
# Consul integration (stub - requires implementation)
service_discovery = ServiceDiscoveryConfig(
    type=ServiceDiscoveryType.CONSUL,
    consul_host="localhost",
    consul_port=8500,
    health_check_interval=30
)

# Kubernetes integration (stub - requires implementation)
service_discovery = ServiceDiscoveryConfig(
    type=ServiceDiscoveryType.KUBERNETES,
    namespace="default",
    health_check_interval=30
)
```

**Note**: For production use with external service discovery backends, you'll need to implement the actual client connections to replace the current mock implementations.

### Service Registration

Services register themselves with metadata:

```python
await discovery_manager.register_service(ServiceInstance(
    service_name="user-service",
    instance_id="user-001",
    endpoint="http://user-service:8080",
    metadata={
        "version": "1.0.0",
        "environment": "production"
    }
))
```

## Load Balancing

### Strategies

- **Round Robin**: Equal distribution across instances
- **Least Connections**: Route to instance with fewest active connections
- **Weighted Round Robin**: Distribution based on instance weights
- **Random**: Random selection
- **Consistent Hash**: Hash-based routing for session affinity

### Configuration

```python
RouteDefinition(
    name="api_route",
    load_balancing=LoadBalancingStrategy.LEAST_CONNECTIONS,
    # ... other config
)
```

## Authentication

### JWT Authentication

```python
auth = AuthConfig(
    type=AuthenticationType.JWT,
    secret_key="your-secret",
    algorithm="HS256"
)
```

### API Key Authentication

```python
auth = AuthConfig(
    type=AuthenticationType.API_KEY,
    header_name="X-API-Key"
)
```

## Rate Limiting

### Per-Route Configuration

```python
rate_limit = RateLimitConfig(
    requests_per_second=100.0,
    burst_size=200,
    window_size=60,
    enable_per_ip=True,
    enable_per_user=True
)
```

### Global Defaults

Set default rate limits in the main configuration.

## Circuit Breaker

### Configuration

```python
circuit_breaker = CircuitBreakerConfig(
    failure_threshold=5,
    timeout_seconds=30,
    half_open_max_calls=3,
    min_request_threshold=20
)
```

### States

- **Closed**: Normal operation
- **Open**: Failing fast, requests rejected
- **Half-Open**: Testing recovery

## Caching

### Response Caching

```python
caching = CachingConfig(
    enabled=True,
    default_ttl=300,
    redis_host="localhost",
    redis_port=6379
)
```

### Cache Keys

Automatic cache key generation based on:

- Request path and method
- Query parameters
- User context (optional)

## Monitoring

### Metrics

Available metrics include:

- Request count and rate
- Response time percentiles
- Error rates by service
- Circuit breaker states
- Cache hit/miss ratios

### Health Checks

```bash
# Gateway health
curl http://localhost:8080/health

# Service discovery health
curl http://localhost:8080/services
```

### Distributed Tracing

Automatic trace generation with:

- Request ID correlation
- Service-to-service tracing
- Performance analysis

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e .[dev]

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .

# Type checking
mypy .
```

## Deployment

### Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN pip install -e .

EXPOSE 8080
CMD ["python", "main.py"]
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
      - name: api-gateway
        image: api-gateway:latest
        ports:
        - containerPort: 8080
        env:
        - name: CONSUL_HOST
          value: "consul.default.svc.cluster.local"
```

## Architecture

The gateway follows a modular architecture:

```
┌─────────────────┐
│   FastAPI App   │
├─────────────────┤
│ Gateway Core    │
├─────────────────┤
│ Service Discovery│
├─────────────────┤
│ Load Balancer   │
├─────────────────┤
│ Circuit Breaker │
├─────────────────┤
│ Rate Limiter    │
├─────────────────┤
│ Auth Manager    │
└─────────────────┘
```

### Request Flow

1. Request received by FastAPI
2. Authentication validation
3. Rate limiting check
4. Route matching
5. Circuit breaker evaluation
6. Service discovery lookup
7. Load balancing selection
8. Request forwarding
9. Response caching (if enabled)
10. Response transformation

## Best Practices

### Configuration Management

- Use environment-specific configs
- Externalize secrets
- Validate configuration on startup

### Monitoring

- Set up proper alerting
- Monitor service health
- Track business metrics

### Security

- Use strong JWT secrets
- Implement proper CORS policies
- Regular security updates

### Performance

- Enable response caching
- Optimize service discovery polling
- Monitor resource usage

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run quality checks
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
