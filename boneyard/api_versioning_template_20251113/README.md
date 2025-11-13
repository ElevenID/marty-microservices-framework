# API Versioning & Contract Testing Template

This template provides a comprehensive API versioning and contract testing framework for microservices. It ensures API stability, backward compatibility, and consumer-driven contract validation.

## Features

### 🔄 API Versioning Strategies

- **URL Path Versioning**: `/v1/users`, `/v2/users`
- **Header Versioning**: `Accept: application/vnd.api+json;version=1`
- **Query Parameter**: `/users?version=1`
- **Media Type**: `Accept: application/vnd.api.v1+json`
- **Custom Header**: `X-API-Version: 1`

### 📋 Contract Management

- **Automatic Contract Generation**: From OpenAPI specifications
- **Contract Registry**: Store and manage API contracts
- **Schema Validation**: Request/response validation against contracts
- **Version Comparison**: Detect breaking and compatible changes
- **Contract Caching**: High-performance contract storage

### 🧪 Contract Testing

- **Provider Testing**: Validate API implementations against contracts
- **Consumer Testing**: Consumer-driven contract validation
- **Automated Testing**: Scheduled contract validation
- **Test Reporting**: Comprehensive test results and metrics
- **Failure Recovery**: Retry mechanisms for failed tests

### 🔍 Breaking Change Detection

- **Schema Analysis**: Detect structural changes
- **Compatibility Checking**: Version-to-version comparison
- **Impact Assessment**: Analyze consumer impact
- **Change Classification**: Breaking vs. compatible changes
- **Deprecation Management**: Controlled API deprecation

### 📊 Monitoring & Observability

- **Prometheus Metrics**: API usage, version adoption, test results
- **Distributed Tracing**: OpenTelemetry integration
- **Structured Logging**: Comprehensive audit trails
- **Health Checks**: Service health and readiness probes
- **Performance Monitoring**: Request latency and throughput

## Quick Start

### 1. Basic Setup

```python
from main import create_versioned_app, VersioningStrategy

# Create versioned FastAPI app
app = create_versioned_app(
    service_name="user-service",
    versioning_strategy=VersioningStrategy.URL_PATH,
    default_version="v1"
)

# Define versioned endpoints
@app.get("/v1/users/{user_id}")
async def get_user_v1(user_id: int):
    return {"id": user_id, "name": "John Doe"}

@app.get("/v2/users/{user_id}")
async def get_user_v2(user_id: int):
    return {
        "id": user_id,
        "first_name": "John",
        "last_name": "Doe",
        "created_at": "2023-01-01T00:00:00Z"
    }
```

### 2. Register API Contract

```python
import httpx

# Register provider contract
contract_data = {
    "service_name": "user-service",
    "version": "v1",
    "openapi_spec": {
        "openapi": "3.0.0",
        "info": {"title": "User Service", "version": "1.0.0"},
        "paths": {
            "/users/{user_id}": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "name": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    "endpoints": [
        {
            "path": "/users/{user_id}",
            "method": "GET",
            "response_schemas": {
                "200": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"}
                    },
                    "required": ["id", "name"]
                }
            }
        }
    ]
}

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8060/api/contracts",
        json=contract_data
    )
    print(f"Contract registered: {response.json()}")
```

### 3. Register Consumer Contract

```python
# Register consumer-driven contract
consumer_contract = {
    "consumer_name": "mobile-app",
    "provider_service": "user-service",
    "provider_version": "v1",
    "expectations": [
        {
            "endpoint": "/users/{user_id}",
            "method": "GET",
            "response_format": "json",
            "required_fields": ["id", "name"]
        }
    ],
    "test_cases": [
        {
            "name": "Get user by ID",
            "path": "/users/1",
            "method": "GET",
            "expectations": {
                "status_code": 200,
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"}
                    },
                    "required": ["id", "name"]
                }
            }
        }
    ]
}

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8060/api/consumer-contracts",
        json=consumer_contract
    )
```

### 4. Test Contracts

```python
# Test provider contract
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8060/api/test-contracts/user-service/v1?base_url=http://user-service:8080"
    )
    test_results = response.json()
    print(f"Contract tests: {test_results['passed_tests']}/{test_results['total_tests']} passed")
```

### 5. Check Compatibility

```python
# Check compatibility between versions
async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://localhost:8060/api/compatibility/user-service/v1/v2"
    )
    compatibility = response.json()

    if not compatibility['compatible']:
        print(f"Breaking changes detected: {compatibility['changes']['breaking_changes']}")
    else:
        print("Versions are compatible")
```

## Configuration

### Environment Variables

```bash
# Basic settings
SERVICE_NAME=api-versioning-service
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8060

# Versioning configuration
VERSIONING__STRATEGY=url_path
VERSIONING__DEFAULT_VERSION=v1
VERSIONING__SUPPORTED_VERSIONS=["v1", "v2"]

# Contract storage
CONTRACTS__STORAGE_BACKEND=postgresql
STORAGE__POSTGRES_HOST=localhost
STORAGE__POSTGRES_DB=api_contracts

# Testing configuration
TESTING__ENABLED=true
TESTING__AUTO_TEST_ON_DEPLOY=true
TESTING__TEST_TIMEOUT=30

# Security
SECURITY__ENABLE_AUTHENTICATION=false
SECURITY__REQUIRE_HTTPS=true
SECURITY__RATE_LIMITING_ENABLED=true

# Monitoring
MONITORING__METRICS_ENABLED=true
MONITORING__TRACING_ENABLED=true
MONITORING__LOG_LEVEL=INFO
```

### Configuration File

```python
from config import APIVersioningSettings

# Load configuration
settings = APIVersioningSettings()

# Environment-specific configs
if settings.environment == "production":
    settings.security.require_https = True
    settings.performance.worker_processes = 4
```

## Storage Backends

### PostgreSQL

```python
# PostgreSQL configuration
CONTRACTS__STORAGE_BACKEND=postgresql
STORAGE__POSTGRES_HOST=localhost
STORAGE__POSTGRES_PORT=5432
STORAGE__POSTGRES_DB=api_contracts
STORAGE__POSTGRES_USER=postgres
STORAGE__POSTGRES_PASSWORD=password
```

### MongoDB

```python
# MongoDB configuration
CONTRACTS__STORAGE_BACKEND=mongodb
STORAGE__MONGODB_URL=mongodb://localhost:27017
STORAGE__MONGODB_DATABASE=api_contracts
```

### Redis

```python
# Redis configuration
CONTRACTS__STORAGE_BACKEND=redis
STORAGE__REDIS_URL=redis://localhost:6379/0
```

### File Storage

```python
# File storage configuration
CONTRACTS__STORAGE_BACKEND=file
STORAGE__FILE_STORAGE_PATH=./contracts
STORAGE__FILE_BACKUP_ENABLED=true
```

## Advanced Usage

### Custom Version Extraction

```python
from main import VersionExtractor, VersioningStrategy

class CustomVersionExtractor(VersionExtractor):
    def extract_version(self, request):
        # Custom version extraction logic
        subdomain = request.url.hostname.split('.')[0]
        if subdomain.startswith('v'):
            return subdomain
        return self.default_version

# Use custom extractor
app.state.version_extractor = CustomVersionExtractor(
    VersioningStrategy.CUSTOM_HEADER,
    "v1"
)
```

### Contract Middleware

```python
from main import ContractValidator

async def contract_validation_middleware(request, call_next):
    """Validate all requests against contracts."""
    version = request.state.api_version
    service_name = "user-service"

    # Validate request
    validator = ContractValidator(app.state.contract_registry)
    errors = await validator.validate_request(request, version, service_name)

    if errors and app.state.strict_validation:
        return JSONResponse(
            status_code=400,
            content={"errors": errors}
        )

    response = await call_next(request)

    # Validate response
    response_errors = await validator.validate_response(
        response, request, version, service_name
    )

    if response_errors:
        # Log validation errors
        logger.warning("Response validation failed", errors=response_errors)

    return response

app.middleware("http")(contract_validation_middleware)
```

### Scheduled Contract Testing

```python
import asyncio
from celery import Celery

celery_app = Celery('contract_testing')

@celery_app.task
async def run_contract_tests():
    """Scheduled contract testing task."""
    tester = ContractTester(contract_registry, httpx.AsyncClient())

    # Test all registered contracts
    contracts = await contract_registry.list_contracts()

    for contract in contracts:
        results = await tester.test_provider_contract(
            contract.service_name,
            contract.version,
            f"http://{contract.service_name}:8080"
        )

        if results['status'] != 'passed':
            # Send alerts for failed tests
            await send_contract_failure_alert(results)

# Schedule every 6 hours
celery_app.conf.beat_schedule = {
    'contract-tests': {
        'task': 'run_contract_tests',
        'schedule': 21600.0,  # 6 hours
    },
}
```

## Kubernetes Deployment

```yaml
# Deploy the service
kubectl apply -f k8s/deployment.yaml

# Check deployment status
kubectl get pods -l app=api-versioning-service

# View logs
kubectl logs -l app=api-versioning-service

# Access metrics
kubectl port-forward svc/api-versioning-service 8060:80
curl http://localhost:8060/metrics
```

## Monitoring

### Prometheus Metrics

```promql
# API version usage
api_version_usage_total

# Contract validation failures
contract_validations_total{status="failed"}

# Breaking changes detected
breaking_changes_detected_total

# Test execution metrics
contract_tests_total
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "API Versioning & Contract Testing",
    "panels": [
      {
        "title": "API Version Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(api_version_usage_total[5m])",
            "legendFormat": "{{version}}"
          }
        ]
      },
      {
        "title": "Contract Test Results",
        "type": "stat",
        "targets": [
          {
            "expr": "contract_tests_total{status=\"passed\"}",
            "legendFormat": "Passed Tests"
          }
        ]
      }
    ]
  }
}
```

## Best Practices

### 1. Version Strategy Selection

- **URL Path**: Most visible, cache-friendly
- **Header**: Clean URLs, requires client modification
- **Query Parameter**: Simple implementation, less clean
- **Media Type**: RESTful, complex client implementation

### 2. Contract Design

```python
# Good: Backward compatible changes
{
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
        "email": {"type": "string"}  # Added optional field
    },
    "required": ["id", "name"]  # No new required fields
}

# Bad: Breaking changes
{
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "full_name": {"type": "string"}  # Renamed field
    },
    "required": ["id", "full_name"]  # New required field
}
```

### 3. Version Lifecycle

1. **Draft**: Development version
2. **Stable**: Production-ready version
3. **Deprecated**: Marked for removal, still supported
4. **Retired**: No longer supported

### 4. Consumer Testing

```python
# Include comprehensive test cases
test_cases = [
    {
        "name": "Get user - success",
        "path": "/users/1",
        "method": "GET",
        "expectations": {"status_code": 200}
    },
    {
        "name": "Get user - not found",
        "path": "/users/999999",
        "method": "GET",
        "expectations": {"status_code": 404}
    },
    {
        "name": "Get user - invalid ID",
        "path": "/users/invalid",
        "method": "GET",
        "expectations": {"status_code": 400}
    }
]
```

## Troubleshooting

### Common Issues

1. **Contract Validation Failures**

   ```bash
   # Check contract registry
   curl http://localhost:8060/api/contracts/user-service

   # Validate specific endpoint
   curl -X POST http://localhost:8060/api/test-contracts/user-service/v1
   ```

2. **Version Detection Problems**

   ```python
   # Debug version extraction
   version = version_extractor.extract_version(request)
   logger.info(f"Extracted version: {version}")
   ```

3. **Performance Issues**

   ```bash
   # Check metrics
   curl http://localhost:8060/metrics | grep contract

   # Monitor cache usage
   redis-cli info stats
   ```

## Contributing

1. Follow semantic versioning for API changes
2. Include comprehensive contract tests
3. Update documentation for new features
4. Monitor compatibility impact
5. Use structured logging for debugging

## License

This template is part of the Marty Microservices Framework and is licensed under the MIT License.
