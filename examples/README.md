# Marty Microservices Framework - Examples

This directory contains example implementations demonstrating the framework adoption flow: **clone → generate → add business logic**.

## Framework Adoption Flow

The Marty Microservices Framework is designed for a streamlined adoption process:

1. **Clone** the framework repository
2. **Generate** a new service using the production service generator
3. **Add** your specific business logic to the generated structure

## Examples Structure

### Framework Examples

- **`demos/`**: Interactive demonstrations and walkthroughs
- **`extended_messaging/`**: Advanced messaging patterns
- **`security/`**: Security configuration examples

### Business Domain Examples

#### Petstore Domain (`petstore_domain/`)

A complete business domain example demonstrating:

- **Plugin Configuration**: Business-specific plugin configurations separated from framework
- **Domain Architecture**: How to structure a complete business domain using MMF
- **Plugin Integration**: Examples of Marty Trust PKI and payment service plugins
- **Configuration Patterns**: Plugin-based configuration loading and management

**Plugin Configuration Structure:**

```
petstore_domain/
├── plugins/                    # Plugin configurations
│   ├── marty.yaml             # Marty Trust PKI plugin
│   └── production_payment_service.yaml  # Payment service plugin
├── services/                   # Domain service implementations
├── config/                     # Domain-specific configuration
└── docs/                       # Domain documentation
```

### Production Payment Service (`production-payment-service/`)

A complete, production-ready payment processing service that demonstrates:

A complete, production-ready payment processing service that demonstrates:

- **Framework Adoption Flow**: Generated using `uv run python scripts/dev/generate_service.py production payment-service`
- **Business Logic Integration**: Payment processing with fraud detection and bank API integration
- **Comprehensive Patterns**: All Marty framework patterns implemented:
  - Structured logging with correlation IDs
  - Prometheus metrics integration
  - Health checks and readiness probes
  - Configuration management
  - Error handling and audit logging
  - Service mesh ready
  - Docker containerization
  - Kubernetes deployment manifests

#### Key Features Demonstrated

- **Payment Processing**: Complete payment flow with fraud checks and bank API integration
- **Audit Logging**: Comprehensive audit trails for compliance and debugging
- **Performance Simulation**: Deliberate bottlenecks for performance analysis and monitoring
- **Error Handling**: Proper HTTP status codes and error responses
- **Observability**: Metrics, logging, and tracing ready
- **Production Ready**: Docker, Kubernetes, and service mesh configurations

#### Quick Start

```bash
cd examples/production-payment-service

# Install dependencies
uv sync

# Run the service
python main.py

# Test the service
curl http://localhost:8002/health
curl http://localhost:8002/docs
```

#### API Endpoints

- `POST /api/v1/payments/process` - Process a payment
- `POST /api/v1/payments/{id}/rollback` - Rollback a payment
- `GET /api/v1/payments/{id}` - Get payment details
- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /metrics` - Prometheus metrics
- `GET /docs` - API documentation

## Creating Your Own Service

To create your own production-ready service:

1. **Generate a new service**:

   ```bash
   uv run python scripts/dev/generate_service.py production your-service-name --description "Your service description" --http-port 8003
   ```

2. **Review the generated structure**:
   - `main.py` - Service entry point with FastAPI app
   - `app/services/your_service_service.py` - Business logic implementation
   - `app/api/routes.py` - API endpoints
   - `app/models/` - Data models and validation
   - `app/core/config.py` - Configuration management
   - `tests/` - Unit and integration tests
   - `Dockerfile` - Production-ready containerization
   - `k8s/` - Kubernetes deployment manifests

3. **Add your business logic**:
   - Implement your specific operations in the service class
   - Define your API endpoints in routes.py
   - Add your data models in models/
   - Configure environment-specific settings

4. **Follow the established patterns**:
   - Use correlation IDs for request tracking
   - Add comprehensive audit logging
   - Implement proper error handling
   - Add metrics for observability
   - Include health checks

## Additional Examples

More examples will be added to demonstrate:

- gRPC services
- Hybrid HTTP/gRPC services
- Database integration patterns
- External API integration
- Event-driven architectures
- Service mesh configurations

## Support

For more information:

- See the main framework README
- Check the `docs/` directory for detailed guides
- Review the generated service README files
- Examine the production payment service as a reference implementation

The Marty Microservices Framework is designed to accelerate your microservice development while maintaining production-ready quality and comprehensive observability.
