# API Documentation Infrastructure and Contract Testing

## Overview

The Marty framework now includes comprehensive API documentation generation and contract testing capabilities that support both REST and gRPC services. This infrastructure enables unified documentation across service types and consumer-driven contract testing for reliable service integration.

## Architecture Components

### Documentation System

#### Unified Documentation Generator

- **Location**: `/mmf/framework/documentation/api_docs.py`
- **Purpose**: Generate unified documentation across REST and gRPC APIs
- **Key Classes**:
  - `APIDocumentationManager`: Orchestrates documentation generation
  - `OpenAPIGenerator`: REST/FastAPI documentation with OpenAPI specs
  - `GRPCDocumentationGenerator`: Protocol buffer and gRPC service documentation
  - `UnifiedDocumentationGenerator`: Combined documentation for hybrid services

#### Templates and Themes

- **Location**: `/mmf/framework/documentation/templates/`
- **Purpose**: HTML and Markdown templates for documentation rendering
- **Features**:
  - Bootstrap-based responsive design
  - Interactive client examples
  - Multi-format output (HTML, Markdown, OpenAPI)
  - Support for multiple themes (Redoc, Swagger UI, Stoplight)

#### API Version Management

- **Location**: Integrated in documentation system
- **Purpose**: Track API versions, deprecations, and migration paths
- **Features**:
  - Version registration and tracking
  - Deprecation date management
  - Migration guide integration
  - Status tracking (active, deprecated, retired)

### Contract Testing Framework

#### Enhanced Contract Testing

- **Location**: `/mmf/framework/testing/grpc_contract_testing.py`
- **Purpose**: Consumer-driven contract testing for gRPC services
- **Key Classes**:
  - `GRPCContractBuilder`: Fluent API for contract creation
  - `GRPCContractValidator`: Contract verification against live services
  - `GRPCContractRepository`: Contract storage and retrieval
  - `EnhancedContractManager`: Unified REST and gRPC contract management

#### Contract Types

1. **REST Contracts**: Based on Pact specifications
2. **gRPC Contracts**: Protocol buffer-based contract definitions
3. **Unified Contracts**: Combined specifications for hybrid services

### CLI Integration

#### Command Structure

```bash
marty api <subcommand> [options]
```

#### Available Commands

- `docs`: Generate comprehensive API documentation
- `create-contract`: Create new consumer-driven contracts
- `test-contracts`: Verify contracts against running services
- `list-contracts`: Display available contracts
- `register-version`: Register API versions for tracking
- `list-versions`: Show API version status
- `generate-grpc-contract`: Auto-generate contracts from proto files
- `generate-contract-docs`: Create documentation from contracts
- `monitor-contracts`: Continuous contract compliance monitoring

## Implementation Decisions

### Technology Choices

#### Documentation Generation

- **Jinja2 Templates**: Flexible template engine for custom documentation formats
- **OpenAPI 3.0**: Standard REST API documentation format
- **Protocol Buffers**: Type-safe gRPC service definitions
- **Bootstrap 5**: Modern responsive UI framework

#### Contract Testing

- **Pact-Compatible**: REST contract format compatible with Pact ecosystem
- **Custom gRPC Format**: Protocol buffer-based contract specifications
- **JSON Storage**: Human-readable contract file format
- **Validation Engine**: Type-aware contract verification

### Design Patterns

#### Builder Pattern

Used for contract creation with fluent APIs:

```python
contract = grpc_contract("consumer", "provider", "service", "1.0.0")
    .interaction("Get user profile")
    .upon_calling("GetUser")
    .with_request({"user_id": "123"})
    .will_respond_with({"name": "John", "email": "john@example.com"})
    .build()
```

#### Strategy Pattern

Multiple documentation generators for different service types:

- `OpenAPIGenerator` for REST APIs
- `GRPCDocumentationGenerator` for gRPC services
- `UnifiedDocumentationGenerator` for hybrid services

#### Repository Pattern

Contract storage abstraction:

- `ContractRepository` for REST contracts
- `GRPCContractRepository` for gRPC contracts
- Unified interface for contract operations

## Integration Points

### Service Discovery

- Automatic service endpoint detection
- Configuration-based service mapping
- Runtime service registry integration

### CI/CD Pipeline

- Contract test execution in build pipelines
- Documentation generation automation
- Version compatibility checking
- Breaking change detection

### Monitoring

- Continuous contract validation
- Service compatibility monitoring
- API deprecation tracking
- Performance impact analysis

## Usage Patterns

### Documentation Generation

```bash
# Generate unified docs for all services
marty api docs -s ./services/user-service -s ./services/order-service

# Generate with specific theme
marty api docs -s ./src --theme swagger-ui --no-examples

# Use configuration file
marty api docs -s ./services -c ./api-docs-config.yaml
```

### Contract Testing

```bash
# Create REST contract
marty api create-contract -c web-frontend -p user-service --type rest

# Create gRPC contract from proto
marty api create-contract -c order-service -p payment-service --type grpc --service-name PaymentService

# Verify contracts
marty api test-contracts -p user-service -u http://localhost:8080
marty api test-contracts -p payment-service -g localhost:50051
```

### Version Management

```bash
# Register new version
marty api register-version -s user-service -v 2.0.0

# Mark version as deprecated
marty api register-version -s user-service -v 1.0.0 --status deprecated -d 2024-12-31

# List versions
marty api list-versions -s user-service
```

## Benefits

### Developer Experience

- **Unified Documentation**: Single source for all API documentation
- **Interactive Examples**: Working code samples and test cases
- **Version Tracking**: Clear migration paths and deprecation timelines
- **Automated Generation**: Documentation stays up-to-date with code changes

### Quality Assurance

- **Contract Testing**: Prevents breaking changes between services
- **Type Safety**: Protocol buffer validation for gRPC services
- **Continuous Monitoring**: Ongoing contract compliance verification
- **Early Detection**: Catch integration issues before deployment

### Operational Excellence

- **Standardization**: Consistent documentation and testing approaches
- **Automation**: Reduced manual effort for documentation and testing
- **Observability**: Clear visibility into API evolution and compatibility
- **Compliance**: Automated tracking of deprecation and migration timelines

## Future Enhancements

### Planned Features

- **API Gateway Integration**: Automatic route and policy documentation
- **GraphQL Support**: Documentation and contract testing for GraphQL APIs
- **AsyncAPI Integration**: Documentation for event-driven APIs
- **Performance Testing**: Integration with load testing frameworks

### Extension Points

- **Custom Validators**: Pluggable contract validation logic
- **Additional Themes**: Support for more documentation themes
- **Integration Plugins**: Connectors for external tools and services
- **Advanced Analytics**: API usage and evolution metrics

## Configuration

### Documentation Configuration

```yaml
# api-docs-config.yaml
output_dir: "./docs/api"
theme: "redoc"
include_examples: true
generate_postman: true
generate_grpc_docs: true
generate_unified_docs: true
services:
  - name: "user-service"
    path: "./services/user-service"
    type: "fastapi"
  - name: "payment-service"
    path: "./services/payment-service"
    type: "grpc"
```

### Contract Testing Configuration

```yaml
# contract-config.yaml
contracts_dir: "./contracts"
verification_level: "strict"
providers:
  - name: "user-service"
    rest_url: "http://localhost:8080"
    grpc_address: "localhost:50051"
  - name: "order-service"
    rest_url: "http://localhost:8081"
monitoring:
  interval: 300
  webhook_url: "https://hooks.slack.com/..."
```

This infrastructure provides a comprehensive foundation for API documentation and contract testing that scales with the microservices architecture while maintaining developer productivity and service reliability.
