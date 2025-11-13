# Marty Microservices Framework Architecture

This document provides a comprehensive overview of the Marty Microservices Framework architecture, design principles, and component interactions.

## 🏗️ High-Level Architecture

The Marty Microservices Framework follows a layered, plugin-based architecture designed for enterprise-grade microservices:

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   FastAPI   │  │    gRPC     │  │      Hybrid         │ │
│  │  Services   │  │  Services   │  │     Services        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│                   Framework Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Auth/Authz  │  │  Database   │  │    Configuration    │ │
│  │ Middleware  │  │  Manager    │  │      Manager        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Observability│  │  Resilience │  │     Event Bus       │ │
│  │   System    │  │  Patterns   │  │    & Messaging      │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│                    Plugin Layer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Plugin    │  │   Plugin    │  │      Plugin         │ │
│  │  Manager    │  │ Discovery   │  │    Lifecycle        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│                Infrastructure Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Kubernetes  │  │ Service     │  │     Monitoring      │ │
│  │ Deployment  │  │   Mesh      │  │    & Logging        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🧱 Core Components

### 1. Application Layer

#### Service Templates

- **FastAPI Services**: REST API microservices with automatic documentation
- **gRPC Services**: High-performance RPC services with protocol buffers
- **Hybrid Services**: Combined REST and gRPC endpoints in a single service

#### Key Features

- Automatic dependency injection
- Built-in health checks and metrics endpoints
- Standardized error handling and logging
- Hot-reloadable configuration

### 2. Framework Layer

#### Authentication & Authorization (`src/framework/security/`)

- JWT token validation and generation
- Role-based access control (RBAC)
- Rate limiting and throttling
- Audit logging for security events

#### Database Management (`src/framework/database/`)

- Connection pooling and management
- Transaction handling with async support
- Repository pattern implementation
- Database migration utilities
- Multi-database support (PostgreSQL, MySQL, MongoDB)

#### Configuration Management (`src/framework/config/`)

The MMF provides a comprehensive unified configuration management system that supports multiple deployment environments and plugin architectures:

**Core Features:**

- **Hierarchical Configuration Loading**: Base configurations with environment-specific overrides (base.yaml → development.yaml → environment variables)
- **Secret Reference System**: Unified secret management with `${SECRET:key}` syntax across multiple backends (Vault, AWS Secrets Manager, Azure Key Vault, etc.)
- **Cloud-Agnostic Design**: Automatic detection and configuration for AWS, GCP, Azure, Kubernetes, and self-hosted environments
- **Plugin Configuration Loading**: Dedicated plugin configuration discovery and loading from plugin directories
- **Hot Reload Support**: Runtime configuration updates without service restart
- **Configuration Templates**: Reusable patterns for common service types (gRPC, FastAPI, hybrid)

**Plugin Configuration Strategy:**
The framework supports plugin-based configuration loading that enables modular architecture and business domain separation:

1. **Plugin Discovery**: Automatic discovery of plugin configurations in designated plugin directories
2. **Hierarchical Plugin Loading**: Plugin configs loaded with same hierarchy as main config (base → environment → overrides)
3. **Plugin Dependency Resolution**: Automatic resolution of plugin dependencies and load order
4. **Namespace Isolation**: Plugin configurations are namespaced to prevent conflicts
5. **Runtime Plugin Management**: Dynamic plugin enabling/disabling without framework restart

#### Enhanced Event Bus & Messaging (`src/framework/events/`)

The MMF provides a comprehensive event-driven architecture with enterprise-grade features:

**Enhanced Event Bus System:**

- **Event Persistence**: Transactional outbox pattern for guaranteed event delivery
- **Dead Letter Queue**: Automatic handling of failed events with retry mechanisms
- **Event Routing**: Intelligent event filtering and routing based on metadata
- **Circuit Breaker**: Fault tolerance for event handlers with automatic recovery
- **Event Replay**: Ability to replay events from persistence layer for recovery
- **Multiple Backends**: Support for in-memory, database, and Kafka backends

**Event Types:**

- **Domain Events**: Business domain-specific events with aggregate context
- **Integration Events**: Cross-service communication events
- **System Events**: Infrastructure and operational events
- **Plugin Events**: Plugin lifecycle and communication events
- **Workflow Events**: Workflow orchestration and state management events

**Plugin Event Subscription:**

- **Fault-Tolerant Subscriptions**: Circuit breaker and retry mechanisms for plugin handlers
- **Event Filtering**: Advanced filtering based on event types, sources, tags, and custom predicates
- **Subscription Management**: Dynamic subscription/unsubscription with persistence
- **Health Monitoring**: Plugin health checks and automatic subscription management
- **Metrics Collection**: Comprehensive metrics for plugin event processing

#### Workflow Engine & Saga Orchestration (`src/framework/workflow/`)

The MMF includes a sophisticated workflow engine supporting long-running business processes:

**Workflow Engine Features:**

- **Declarative DSL**: Fluent interface for defining complex workflows
- **Saga Orchestration**: Distributed transaction management with compensation
- **Step Types**: Action, Decision, Parallel, Wait, and Compensation steps
- **State Persistence**: Workflow state persistence for recovery and monitoring
- **Event-Driven Execution**: Integration with event bus for workflow triggers
- **Timeout Handling**: Configurable timeouts with automatic failure handling
- **Retry Logic**: Built-in retry mechanisms with exponential backoff

**Saga Pattern Support:**

- **Compensating Transactions**: Automatic rollback with compensation logic
- **Forward Recovery**: Failure handling with step-by-step recovery
- **Parallel Execution**: Concurrent step execution with wait strategies
- **Decision Points**: Conditional workflow branching based on context
- **Long-Running Processes**: Support for workflows spanning hours or days

**Plugin Configuration Structure:**

```yaml
# plugins/my-plugin.yaml
default:
  enabled: true
  version: "1.0.0"
  dependencies: ["security", "database"]

  # Plugin-specific configuration
  settings:
    timeout_seconds: 30
    max_retries: 3

  # Integration with framework components
  database:
    use_mmf_database: true
    schema_prefix: "plugin_"
```

**Configuration Loading Process:**

1. Load framework base configuration (`config/base.yaml`)
2. Apply environment-specific overrides (`config/{environment}.yaml`)
3. Discover and load plugin configurations (`plugins/*.yaml`)
4. Resolve secret references using configured backends
5. Apply environment variable overrides
6. Validate final configuration against schemas

**Benefits:**

- **Framework Separation**: Business logic configs separated from framework patterns
- **Plugin Modularity**: Plugins can be independently configured and managed
- **Environment Consistency**: Same configuration patterns across all environments
- **Secret Security**: Unified secret management with multiple backend support
- **Developer Experience**: Clear configuration structure with validation and documentation

#### Observability (`src/marty_msf/observability/`)

- **Enhanced Unified OpenTelemetry System**: Complete observability orchestration with standardized defaults across all services
- **Multi-dimensional Correlation Tracking**: Request, user, session, plugin, and operation correlation with automatic propagation
- **Zero-config Instrumentation**: Automatic OpenTelemetry instrumentation for FastAPI, gRPC, databases, HTTP clients, and caching layers
- **Standardized Prometheus Metrics**: Consistent metric collection with MMF-specific labels and business metrics
- **Distributed Tracing with Jaeger**: Complete request flow tracking across microservices with plugin interaction visibility
- **Structured Logging with Context**: Correlation ID injection and trace context propagation in all log entries
- **Default Grafana Dashboards**: Pre-built dashboards for service monitoring, plugin debugging, and performance analysis
- **Plugin Developer Debugging**: Specialized tooling for troubleshooting plugin interactions and microservice dependencies
- **Intelligent Alerting**: Environment-aware alert rules for service health, performance, and plugin operations
- **Enhanced Middleware & Interceptors**: Ready-to-use correlation middleware for FastAPI and gRPC with graceful fallbacks

#### Resilience Patterns (`src/framework/resilience/`)

The framework provides enterprise-grade resilience patterns for building fault-tolerant microservices with comprehensive performance and resilience hardening:

**Core Patterns:**

- **Circuit Breakers**: Automatic fault tolerance with configurable failure thresholds and recovery timeouts
- **Retry Mechanisms**: Intelligent retry with exponential backoff, jitter, and circuit breaker integration
- **Bulkhead Isolation**: Resource isolation using thread pools and semaphores to prevent cascade failures
- **Timeout Management**: Comprehensive timeout handling with dependency-specific configurations
- **Fallback Strategies**: Graceful degradation with cached responses, default values, and alternative flows

**Connection Pooling Layer (2024 Enhancement):**

- **HTTP Connection Pools**: Standardized HTTP client pooling with health monitoring and automatic recovery
- **Redis Connection Pools**: Redis cluster and sentinel support with background health checking
- **Database Connection Pools**: Integration with existing SQLAlchemy pools and enhanced monitoring
- **Unified Pool Management**: Centralized ConnectionPoolManager with metrics collection and lifecycle management
- **Health Monitoring**: Background health checks with configurable intervals and automatic bad connection replacement

**Middleware Integration:**

- **ResilienceMiddleware**: FastAPI middleware for automatic resilience pattern application
- **Zero-Configuration Setup**: Default resilience protection for all endpoints without code changes
- **Request-Level Isolation**: Automatic timeout, rate limiting, and bulkhead application
- **Circuit Breaker Integration**: Middleware-level circuit breaker protection with graceful error handling

**Load Testing Framework:**

- **Comprehensive Load Testing**: Multiple test types (load, spike, endurance, chaos)
- **Resilience Validation**: Validates circuit breakers, bulkheads, and connection pools under load
- **Realistic Traffic Simulation**: User session simulation with think times and realistic patterns
- **Performance Metrics**: Response time percentiles, throughput, error rates, and resilience pattern effectiveness

**External Dependency Management:**

- **Bulkhead Isolation per Dependency**: Separate resource pools for different external services (database, APIs, cache)
- **Configurable Timeout Strategies**: Dependency-specific timeouts (database: 10s, APIs: 15s, cache: 2s)
- **Circuit Breaker Integration**: Automatic circuit breaking based on failure rates and thresholds
- **Adaptive Configurations**: Environment-specific settings (development, testing, production)

**Implementation Features:**

- **Thread-Pool Bulkheads**: For CPU-intensive operations with configurable worker limits
- **Semaphore Bulkheads**: For I/O operations with high concurrency support
- **Connection Pool Health Checks**: Real-time monitoring of pool health and automatic recovery
- **Comprehensive Metrics**: Prometheus-compatible metrics for all resilience patterns
- **Health Checks**: Integrated health monitoring with resilience pattern statistics

**Configuration Example:**

```yaml
resilience:
  connection_pools:
    http:
      external_api:
        base_url: "https://api.example.com"
        max_connections: 50
        health_check_interval: 60
    redis:
      main_cache:
        host: "localhost"
        port: 6379
        max_connections: 20

  bulkheads:
    database:
      max_concurrent: 10
      timeout_seconds: 10.0
      enable_circuit_breaker: true
    external_api:
      max_concurrent: 15
      timeout_seconds: 15.0
      circuit_breaker_failure_threshold: 3

  middleware:
    timeout: 30.0
    rate_limit_requests: 100
    rate_limit_window: 60
```

**Usage Patterns:**

```python
# Initialize connection pools and middleware
from marty_msf.framework.resilience import (
    ConnectionPoolManager, ResilienceMiddleware
)

# Set up FastAPI app with automatic resilience
app = FastAPI()
app.add_middleware(ResilienceMiddleware)

# Use connection pools in services
pool_manager = ConnectionPoolManager()
await pool_manager.create_http_pool("api", base_url="https://api.example.com")

@app.get("/data")
async def get_data():
    async with pool_manager.get_http_pool("api") as client:
        response = await client.get("/data")
        return response.json()

# Direct resilience decorators for specific functions
@database_call(dependency_name="user_db", operation_name="get_user")
async def get_user(user_id: str) -> dict:
    # Database call automatically protected by bulkhead and timeout
    return await db.get_user(user_id)
```

#### Event-Driven Architecture (`src/framework/events/`)

- Event bus for inter-service communication
- Message queue integration (Kafka, RabbitMQ)
- Event sourcing capabilities
- CQRS pattern support

#### **Extended Messaging System (`src/framework/messaging/`)**

The framework provides a comprehensive, unified messaging system supporting multiple backends and messaging patterns for enterprise-grade microservices communication.

**Core Components:**

##### Unified Event Bus (`unified_event_bus.py`)

- **Single API for All Patterns**: Unified interface supporting pub/sub, request/response, stream processing, and point-to-point messaging
- **Backend Abstraction**: Automatic backend selection based on messaging pattern and requirements
- **Pattern-Specific Optimizations**: Each pattern uses the most appropriate backend automatically
- **Smart Backend Selection**: Uses PatternSelector for intelligent backend recommendation

##### Supported Backends

1. **NATS Backend** (`nats_backend.py`)
   - High-performance, low-latency messaging
   - JetStream support for stream processing
   - Request/response with built-in timeouts
   - Excellent for micro-service communication

2. **AWS SNS Backend** (`aws_sns_backend.py`)
   - Cloud-native pub/sub and broadcast messaging
   - FIFO topics with exactly-once delivery
   - Message filtering and attributes
   - Dead letter queue support

3. **RabbitMQ Backend** (Enhanced existing implementation)
   - Complex routing and exchange patterns
   - Message persistence and clustering
   - Priority queues and TTL support
   - Traditional enterprise messaging

4. **Kafka Backend** (Enhanced existing implementation)
   - High-throughput stream processing
   - Event replay capabilities
   - Partitioned topics for scalability
   - Real-time analytics pipelines

5. **Redis Backend** (Enhanced existing implementation)
   - Lightweight pub/sub for caching scenarios
   - Streams for simple event processing
   - In-memory performance

##### Messaging Patterns

**Publish/Subscribe Pattern:**

```python
# Publish domain events
await event_bus.publish_event(
    event_type="user_registered",
    data={"user_id": "123", "email": "user@example.com"}
)

# Subscribe to events
await event_bus.subscribe_to_events(
    event_types=["user_registered", "user_updated"],
    handler=handle_user_events
)
```

**Request/Response Pattern:**

```python
# Send query and get response
response = await event_bus.query(
    query_type="get_user_profile",
    data={"user_id": "123"},
    target_service="user_service"
)
```

**Stream Processing Pattern:**

```python
# Process event streams in batches
await event_bus.process_stream(
    stream_name="analytics_events",
    processor=process_analytics_batch,
    consumer_group="analytics_processor",
    batch_size=100
)
```

**Point-to-Point Pattern:**

```python
# Send commands to specific services
await event_bus.send_command(
    command_type="process_payment",
    data={"order_id": "123", "amount": 99.99},
    target_service="payment_service"
)
```

##### Enhanced Saga Integration (`saga_integration.py`)

**Distributed Saga Orchestration:**

- **Enhanced Saga Orchestrator**: Uses unified event bus for saga coordination
- **Multi-Backend Saga Support**: Saga events can use different backends for different steps
- **Compensation Logic**: Automatic compensation handling with event-driven rollback
- **Saga State Management**: Persistent saga state with event sourcing

**Example Saga Implementation:**

```python
class OrderProcessingSaga:
    def __init__(self):
        self.steps = [
            {"step_name": "validate_order", "service": "order_service"},
            {"step_name": "reserve_inventory", "service": "inventory_service"},
            {"step_name": "process_payment", "service": "payment_service"},
            {"step_name": "ship_order", "service": "shipping_service"}
        ]

# Create distributed saga manager
saga_manager = create_distributed_saga_manager(event_bus)
saga_manager.register_saga("order_processing", OrderProcessingSaga)

# Start saga
saga_id = await saga_manager.create_and_start_saga(
    "order_processing",
    {"order_id": "123", "customer_id": "456"}
)
```

##### Pattern Selection Guidelines

**Backend Selection Matrix:**

| Use Case | Scale | Recommended Backend | Pattern |
|----------|-------|-------------------|---------|
| Real-time notifications | High | NATS | Pub/Sub |
| Task queues | Medium | RabbitMQ | Point-to-Point |
| Analytics processing | High | Kafka | Stream Processing |
| Micro-service communication | Medium | NATS | Request/Response |
| Cloud-native pub/sub | Any | AWS SNS | Pub/Sub |
| Financial transactions | High | Kafka + NATS | Stream + Request/Response |

**When to Use Each Pattern:**

- **Pub/Sub**: Multiple services need to react to the same event (user registration, order updates)
- **Request/Response**: Immediate response required (authentication, payment authorization)
- **Stream Processing**: Continuous data flows with ordering (analytics, financial transactions)
- **Point-to-Point**: Task processing with guaranteed delivery (background jobs, email sending)

##### Configuration and Deployment

**Backend Configuration:**

```python
# Configure multiple backends
nats_config = NATSConfig(servers=["nats://localhost:4222"])
aws_config = AWSSNSConfig(region_name="us-east-1")

event_bus.register_backend(MessageBackendType.NATS, NATSBackend(nats_config))
event_bus.register_backend(MessageBackendType.AWS_SNS, AWSSNSBackend(aws_config))
```

**Infrastructure Requirements:**

- **NATS**: Lightweight, minimal infrastructure
- **AWS SNS**: Managed service, no infrastructure needed
- **RabbitMQ**: Cluster deployment with persistence
- **Kafka**: High-availability cluster with storage
- **Redis**: In-memory cluster for caching scenarios

**Deployment Strategy:**

- **Development**: In-memory backend for testing
- **Staging**: Single-node NATS for integration testing
- **Production**: Multi-backend setup based on use case requirements

#### **Data Consistency Patterns (`src/marty_msf/patterns/`)**

- **Saga Orchestration**: Long-running transaction coordination with compensation handlers
- **Transactional Outbox Pattern**: ACID-compliant event publishing with reliability guarantees
- **CQRS (Command Query Responsibility Segregation)**: Optimized read/write model separation
- **Event Sourcing Integration**: State reconstruction from event streams with snapshot support

##### Kafka Infrastructure Decision

The framework adopts **Apache Kafka with KRaft mode** for production event streaming:

- **Modern KRaft Mode**: Uses Kafka's new consensus protocol (KIP-500) eliminating Zookeeper dependency
- **Simplified Operations**: Reduces infrastructure complexity and operational overhead
- **Better Performance**: Improved startup times and reduced resource consumption
- **Future-Proof**: Zookeeper-based deployments are deprecated in Kafka 4.0+

**Alternative Configurations Evaluated:**

- **Bitnami Kafka**: Rejected due to unstable `latest` tag and Zookeeper dependency
- **Confluent Platform 6.x**: Rejected due to outdated version and Zookeeper requirement
- **Wurstmeister Kafka**: Rejected due to deprecated/unmaintained image
- **Apache Kafka without Zookeeper**: Rejected to maintain production parity

**Selected**: Confluent Platform 7.4.0 + Zookeeper for production parity across all environments

**Configuration Location**: `ops/k8s/observability/kafka.yaml` (used for both development and production)

### 3. Plugin Layer

#### Plugin Management (`src/framework/plugins/`)

- Dynamic plugin discovery and loading
- Lifecycle management (initialize, start, stop)
- Dependency resolution between plugins
- Hot-pluggable architecture

#### Extension Points

- Custom middleware registration
- Database provider plugins
- Authentication provider plugins
- Monitoring and metrics plugins

### 4. Infrastructure Layer

#### Kubernetes Integration

- Helm charts for service deployment
- Kustomize configurations for environment management
- Health check and readiness probes
- Resource management and scaling

#### Message Streaming Infrastructure

- **Apache Kafka (KRaft Mode)**: Production event streaming without Zookeeper
- **Development Configuration**: Single-node setup with auto-topic creation
- **Production Configuration**: Multi-node setup with observability integration
- **High Availability**: Replication and persistence configured for durability

#### Service Mesh Support

The framework provides a **plugin-based service mesh architecture** that generates customized deployment scripts for each project:

**Framework-Generated Architecture:**

- **Core Library**: Reusable service mesh functions in `src/marty_msf/framework/service_mesh/`
- **Project Generation**: Automatic deployment script generation with project-specific configuration
- **Plugin Extensions**: Customizable hooks for domain-specific requirements
- **Dual Mesh Strategy**: First-class support for both Istio and Linkerd

**Generated Deployment Structure:**

```
project/
├── deploy-service-mesh.sh          # Generated deployment script
├── k8s/service-mesh/              # Production manifests
│   ├── istio-production.yaml
│   ├── istio-security.yaml
│   ├── istio-traffic-management.yaml
│   ├── istio-gateways.yaml
│   ├── istio-cross-cluster.yaml
│   ├── linkerd-production.yaml
│   ├── linkerd-security.yaml
│   └── linkerd-traffic-management.yaml
└── plugins/
    └── service-mesh-extensions.sh  # Project-specific customizations
```

**Framework Library Functions:**

- **Core Deployment**: `msf_deploy_service_mesh()` - Main deployment orchestration
- **Mesh Management**: `msf_deploy_istio_production()`, `msf_deploy_linkerd_production()`
- **Configuration**: `msf_apply_manifest()`, `msf_create_namespace()`, `msf_enable_mesh_injection()`
- **Validation**: `msf_check_prerequisites()`, `msf_validate_config()`, `msf_verify_deployment()`
- **Generation**: `msf_generate_deployment_script()`, `msf_generate_plugin_template()`

**Plugin Hook System:**

```bash
# Override in plugins/service-mesh-extensions.sh
plugin_pre_deploy_hook() {
    # Project-specific pre-deployment setup
    # Example: create custom certificates, secrets
}

plugin_custom_configuration() {
    # Apply domain-specific policies and configurations
    # Example: custom authorization, traffic rules
}

plugin_post_deploy_hook() {
    # Post-deployment integrations
    # Example: monitoring setup, external services
}
```

**Service Mesh Features:**

- **Production-Ready Manifests**: Enterprise-grade configurations with mTLS, authorization policies
- **Circuit Breakers**: Automatic failure detection and service protection with configurable thresholds
- **Advanced Traffic Management**: Retry policies, rate limiting, fault injection, canary deployments
- **Cross-Cluster Support**: Multi-cluster communication with east-west gateways
- **Security Policies**: Strict mTLS, JWT authentication, network policies, authorization rules
- **Observability Integration**: Comprehensive metrics, distributed tracing, structured logging

**Operational Benefits:**

- **Project Isolation**: Each project gets customized deployment scripts and configurations
- **Framework Dependency**: Projects depend on stable framework library for core functionality
- **Extensibility**: Plugin system allows domain-specific customizations without framework changes
- **Consistency**: Standardized deployment patterns across all projects with customization flexibility
- **Maintainability**: Framework updates automatically benefit all projects, custom logic stays isolated

**Deployment Workflow:**

1. **Generation**: Framework generates deployment script and plugin template for project
2. **Customization**: Developers implement project-specific logic in plugin extensions
3. **Configuration**: Add production manifests to `k8s/service-mesh/` directory
4. **Deployment**: Execute `./deploy-service-mesh.sh` with project-specific parameters
5. **Management**: Framework library handles core deployment logic, plugins handle customizations

**Example Usage:**

```bash
# Generate for new project
python -c "
from marty_msf.framework.service_mesh import ServiceMeshManager
manager = ServiceMeshManager()
manager.generate_deployment_script('petstore', './petstore-project', 'api.petstore.com')
"

# Deploy with customizations
cd petstore-project
./deploy-service-mesh.sh --mesh-type istio --domain api.petstore.com --enable-multicluster
```

**CLI Integration:**

The framework provides comprehensive CLI commands for service mesh management through the `marty` command:

```bash
# Generate service mesh deployment for a new project
uv run marty service-mesh generate \
    --project-name petstore \
    --output-dir ./petstore-project \
    --domain api.petstore.com \
    --mesh-type istio \
    --namespace petstore

# Check service mesh status
uv run marty service-mesh status --mesh-type istio --namespace petstore

# Install service mesh (development/testing)
uv run marty service-mesh install --mesh-type istio --namespace petstore --enable-monitoring
```

**CLI Command Structure:**

- **`marty service-mesh generate`**: Creates customized deployment scripts and manifests
  - Generates project-specific deployment script with framework dependency
  - Creates plugin template for domain-specific customizations
  - Copies production-ready Kubernetes manifests to project
  - Configures proper namespace, domain, and mesh type settings

- **`marty service-mesh install`**: Development/testing mesh installation
  - Installs mesh control plane with basic configuration
  - Enables sidecar injection for specified namespace
  - Applies MMF production manifests for enhanced security and policies
  - Provides monitoring and observability setup options

- **`marty service-mesh status`**: Health and status monitoring
  - Checks control plane deployment status
  - Verifies sidecar injection configuration
  - Reports mesh connectivity and component health
  - Validates production manifest applications

**Integration with Development Workflow:**

```bash
# 1. Project initialization
uv run marty service-mesh generate --project-name my-service --output-dir ./my-service

# 2. Customize deployment (edit generated plugin template)
cd my-service
editor plugins/service-mesh-extensions.sh

# 3. Deploy to development cluster
./deploy-service-mesh.sh --dry-run  # Validate configuration
./deploy-service-mesh.sh            # Deploy to cluster

# 4. Verify deployment
uv run marty service-mesh status --mesh-type istio --namespace my-service
```

**Production Deployment Workflow:**

The generated deployment scripts are designed for production use with CI/CD pipelines:

```bash
# CI/CD Pipeline Integration
- name: Deploy Service Mesh
  run: |
    cd ${{ github.workspace }}/my-service
    ./deploy-service-mesh.sh \
      --mesh-type istio \
      --cluster-name production-cluster \
      --domain api.mycompany.com \
      --enable-multicluster \
      --enable-observability
```

**Generated Project Structure:**

```
my-service/
├── deploy-service-mesh.sh              # Main deployment script
├── k8s/service-mesh/                   # Production manifests
│   ├── istio-production.yaml           # Control plane configuration
│   ├── istio-security.yaml             # mTLS and authorization policies
│   ├── istio-traffic-management.yaml   # Circuit breakers, retries, rate limiting
│   ├── istio-gateways.yaml             # Ingress/egress gateway configuration
│   ├── istio-cross-cluster.yaml        # Multi-cluster communication
│   ├── linkerd-production.yaml         # Alternative Linkerd configuration
│   ├── linkerd-security.yaml           # Linkerd security policies
│   └── linkerd-traffic-management.yaml # Linkerd traffic management
└── plugins/
    └── service-mesh-extensions.sh      # Project-specific customizations
```

**Framework Integration Benefits:**

- **Zero-Configuration Start**: Generated scripts work out-of-the-box with sensible defaults
- **Production-Ready**: Enterprise-grade security and policies included by default
- **Customization Freedom**: Plugin system allows unlimited domain-specific extensions
- **Framework Evolution**: Projects automatically benefit from framework improvements
- **Consistent Patterns**: Standardized deployment approach across all services
- **Development Efficiency**: Reduces service mesh setup from days to minutes

#### Kustomize Integration

- **Environment Management**: Streamlined configuration across dev/staging/prod
- **Service Mesh Overlays**: Automated generation of mesh-specific configurations
- **Policy Templates**: Reusable templates for common resilience patterns
- **GitOps Ready**: Declarative configurations for continuous deployment

## 🔧 Design Principles

### 1. Modularity

- **Loose Coupling**: Components interact through well-defined interfaces
- **High Cohesion**: Related functionality is grouped together
- **Plugin Architecture**: Extensible through plugins without core changes

### 2. Scalability

- **Horizontal Scaling**: Services can be scaled independently
- **Asynchronous Processing**: Non-blocking I/O and async/await patterns
- **Resource Efficiency**: Optimized for containerized environments

### 3. Reliability

- **Fault Tolerance**: Graceful handling of failures with resilience patterns
- **Observability**: Comprehensive monitoring and debugging capabilities
- **Testing**: Built-in testing framework with multiple test types

### 4. Security

- **Defense in Depth**: Multiple layers of security controls
- **Zero Trust**: No implicit trust between components
- **Compliance**: Built-in support for security standards and auditing

### 5. Fail-Fast Dependency Management

- **No Silent Degradation**: Services fail immediately if required dependencies are missing
- **Explicit Dependencies**: All required components must be available at startup
- **Clear Error Messages**: Missing dependencies result in immediate, descriptive failures
- **Predictable Behavior**: Services either work fully or fail clearly - no partial functionality
- **Development Safety**: Prevents deployment of misconfigured services to production

**Design Rationale**: The framework follows a fail-fast approach for dependency management to ensure:

- **Operational Clarity**: Teams know immediately when dependencies are missing
- **Production Safety**: Prevents silent failures that could cause subtle bugs
- **Configuration Validation**: Forces proper environment setup during deployment
- **Debugging Efficiency**: Clear error messages reduce troubleshooting time

This approach replaces previous graceful degradation patterns where services would continue running with reduced functionality when optional dependencies were missing.

## 🔄 Request Flow

### Typical Request Lifecycle

1. **Ingress**: Request enters through load balancer/ingress controller
2. **Service Mesh**: Traffic routing and security policies applied
3. **Authentication**: JWT validation and user context establishment
4. **Authorization**: Permission checks against RBAC policies
5. **Rate Limiting**: Request throttling and quota enforcement
6. **Business Logic**: Core service logic execution
7. **Database Operations**: Transactional data operations
8. **Event Publishing**: Asynchronous event notifications
9. **Response**: Structured response with proper error handling
10. **Observability**: Metrics, traces, and logs captured

## 📊 Data Flow Patterns

### 1. Synchronous Communication

- **REST APIs**: HTTP/HTTPS for external interfaces
- **gRPC**: High-performance internal service communication
- **GraphQL**: Flexible data querying (optional)

### 2. Asynchronous Communication

- **Event Bus**: In-memory event routing
- **Message Queues**: Persistent message delivery
- **Event Sourcing**: Immutable event logging

### 3. Data Persistence

- **Transactional Data**: ACID-compliant database operations
- **Event Store**: Immutable event history
- **Caching**: Redis/Memcached for performance optimization

## 🛡️ Security Architecture

### Multi-Layer Security Model

1. **Network Security**: TLS/mTLS encryption, network policies
2. **Authentication**: JWT tokens, OAuth2/OIDC integration
3. **Authorization**: RBAC with fine-grained permissions
4. **Data Protection**: Encryption at rest and in transit
5. **Audit Trail**: Comprehensive security event logging

## 🔍 Monitoring & Observability

## 🔭 Enhanced Observability Architecture

The MMF provides a **comprehensive observability system** built on OpenTelemetry standards with enhanced defaults, offering complete monitoring, debugging, and performance analysis capabilities across all microservices with specialized plugin debugging support.

### Unified Observability Components

#### 1. **OpenTelemetry Collector** - Central Telemetry Hub

- **Multi-protocol ingestion**: OTLP, Jaeger, Zipkin support
- **Enhanced processing**: MMF-specific attribute injection and correlation tracking
- **Intelligent sampling**: Environment-aware sampling with tail sampling for important traces
- **Export flexibility**: Multiple exporters for different platforms and tools

#### 2. **Enhanced Correlation System** - Multi-dimensional Tracking

- **Request correlation**: Primary correlation ID for request flow tracking
- **User context**: User and session correlation for user journey analysis
- **Plugin debugging**: Plugin-specific correlation for interaction troubleshooting
- **Operation tracking**: Operation-level correlation for performance analysis
- **Automatic propagation**: Zero-config correlation across HTTP and gRPC boundaries

#### 3. **Metrics** - Prometheus & Monitoring

- **Standardized metrics**: Consistent metrics across all MMF services
- **Plugin metrics**: Specialized metrics for plugin operation monitoring
- **Business metrics**: Framework for custom business-specific metrics
- **Performance metrics**: Request rates, latencies, error rates, and resource utilization
- **Infrastructure metrics**: Database, cache, and messaging system metrics

#### 4. **Distributed Tracing** - Complete Request Flow Visibility

- **Service dependencies**: Automatic service interaction mapping
- **Plugin interactions**: Detailed plugin-to-plugin communication tracking
- **Performance bottlenecks**: Latency analysis across the entire request path
- **Error propagation**: Error context and root cause analysis
- **Correlation linking**: Direct links between logs, metrics, and traces

#### 5. **Structured Logging** - Context-aware Log Management

- **Automatic correlation injection**: All logs include correlation context
- **Plugin context**: Plugin-specific logging context for debugging
- **Trace correlation**: Direct links from logs to distributed traces
- **Structured format**: JSON logging with standardized fields
- **Log aggregation**: Centralized log collection and analysis

### Default Dashboards and Alerting

#### Pre-built Dashboards

1. **MMF Service Overview**: High-level service health and performance metrics
2. **MMF Plugin Debugging**: Specialized dashboard for plugin interaction analysis
3. **MMF Distributed Tracing**: Service dependency and trace analysis
4. **MMF Performance Analysis**: Deep-dive performance and bottleneck analysis

#### Intelligent Alerting

- **Environment-aware**: Different thresholds for dev/staging/production
- **Service-specific**: Customizable alerts per service type
- **Plugin monitoring**: Alerts for plugin failures and performance issues
- **Infrastructure health**: Database, cache, and messaging alerts
- **Correlation tracking**: Alerts for observability system health

### Plugin Developer Benefits

#### Enhanced Debugging Capabilities

- **Plugin interaction mapping**: Visualize how plugins communicate
- **Performance analysis**: Identify slow or failing plugin operations
- **Correlation tracking**: Follow requests through plugin chains
- **Error analysis**: Root cause analysis for plugin failures
- **Resource monitoring**: Plugin-specific resource usage tracking

#### Zero-config Integration

- **Automatic instrumentation**: No manual instrumentation required
- **Standard middleware**: Drop-in correlation middleware for all service types
- **Graceful fallbacks**: System works even if observability components are unavailable
- **Environment detection**: Automatic configuration based on deployment environment

### Architecture Benefits

1. **Unified Experience**: Consistent observability across all service types
2. **Plugin-first Design**: Specialized tooling for plugin ecosystem debugging
3. **Production Ready**: Environment-aware configuration and sampling
4. **Scalable**: Efficient data collection and processing for large deployments
5. **Extensible**: Framework for adding custom metrics and dashboards
6. **Maintainable**: Standardized configuration reduces operational overhead

### Unified Observability Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Service Templates                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   FastAPI   │  │    gRPC     │  │      Hybrid         │ │
│  │  + Unified  │  │  + Unified  │  │    + Unified        │ │
│  │ Observability│  │Observability│  │   Observability     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│          MMF Unified Observability System                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │OpenTelemetry│  │ Correlation │  │    Prometheus       │ │
│  │Orchestration│  │   Context   │  │     Metrics         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Grafana   │  │    Jaeger   │  │   Structured        │ │
│  │ Dashboards  │  │   Tracing   │  │     Logging         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Three Pillars of Observability

#### 1. **Metrics** - Prometheus & Grafana Integration

- **Automatic Collection**: HTTP request metrics, gRPC call metrics, database query metrics
- **Service-Specific Labeling**: Consistent labeling across all services with service name, version, and environment
- **Pre-built Dashboards**:
  - `mmf-service-overview.json`: Service health, performance, and infrastructure metrics
  - `mmf-tracing-analysis.json`: Distributed tracing insights and span analysis
  - `mmf-plugin-troubleshooting.json`: Plugin interaction debugging and performance monitoring
- **Custom Metrics**: Easy creation of business-specific metrics with standardized collection

#### 2. **Logs** - Structured Logging with Correlation

- **Enhanced Correlation System**: Multi-dimensional tracking with correlation_id, request_id, user_id, session_id, and trace_id
- **Automatic Context Injection**: All log messages include correlation context for end-to-end request tracking
- **Structured Format**: JSON-formatted logs with standardized fields for parsing and analysis
- **ELK/EFK Stack Ready**: Formatted for Elasticsearch, Logstash/Fluentd, and Kibana integration

#### 3. **Traces** - Distributed Tracing with Jaeger

- **Zero-Config Instrumentation**: Automatic instrumentation for FastAPI, gRPC, HTTP clients, databases, and Redis
- **OpenTelemetry Standards**: Full compliance with OpenTelemetry specifications for vendor-neutral observability
- **Span Context Propagation**: Automatic trace context propagation across service boundaries
- **Custom Span Creation**: Easy addition of business-specific spans for detailed operation tracking

### Enhanced Correlation Tracking

The MMF introduces a sophisticated correlation system that extends beyond simple correlation IDs:

```python
# Automatic correlation in all services
with with_correlation(
    operation_name="process_payment",
    correlation_id="req_123",
    user_id="user_456",
    session_id="sess_789"
):
    # All logs, metrics, and traces include full context
    result = await process_payment(payment_data)
```

**Correlation Dimensions:**

- `correlation_id`: Request-level tracking across all services
- `request_id`: Individual API call identification
- `user_id`: User-specific operation tracking
- `session_id`: Session-level behavior analysis
- `trace_id`: OpenTelemetry trace identification
- `span_id`: Individual operation span tracking

### Service Template Integration

All MMF service templates (`fastapi`, `grpc`, `hybrid`) automatically include:

1. **Unified Observability Initialization**: Zero-config setup in service startup
2. **Correlation Middleware**: Automatic correlation ID propagation for HTTP and gRPC
3. **Health Check Integration**: Observability status included in health endpoints
4. **Graceful Fallbacks**: Services function normally even when observability components are unavailable

### Plugin Developer Benefits

For plugin developers troubleshooting microservice interactions:

- **Cross-Service Tracing**: Follow requests across multiple services and plugins
- **Performance Profiling**: Identify bottlenecks in plugin execution
- **Error Analysis**: Correlate errors across the entire request lifecycle
- **Integration Testing**: Verify plugin behavior with comprehensive observability data
- **Dashboard Templates**: Ready-to-use Grafana dashboards for immediate insights

### Infrastructure Requirements

**Monitoring Stack Components:**

- **Jaeger**: Distributed tracing backend (containerized deployment available in `ops/observability/`)
- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and alerting platform with pre-configured dashboards
- **Optional**: Elasticsearch + Kibana for log aggregation and analysis

**Configuration:**

- Environment-based observability configuration with dev/staging/production profiles
- Optional dependency handling - services work without observability stack
- Configurable sampling rates and export endpoints

### Health Monitoring

- **Health Checks**: Kubernetes-compatible health endpoints with observability status
- **SLA/SLO Tracking**: Performance and availability monitoring with correlation insights
- **Alerting**: Proactive issue detection with correlation context for faster debugging
- **Plugin Monitoring**: Dedicated dashboards for plugin-specific performance and error tracking

## 🚀 Deployment Patterns

### 1. Container-First Design

- **Docker**: Containerized service packaging
- **Multi-stage Builds**: Optimized container images
- **Security Scanning**: Vulnerability detection in images

### 2. Kubernetes Native

- **Helm Charts**: Templated Kubernetes deployments
- **Operators**: Custom resource management
- **GitOps**: Declarative deployment workflows

### 3. Environment Management

- **Configuration**: Environment-specific settings
- **Secrets**: Secure credential management
- **Feature Flags**: Runtime behavior control

## 📈 Performance Considerations

### Optimization Strategies

- **Connection Pooling**: Efficient database connections
- **Caching**: Multi-level caching strategies
- **Async Processing**: Non-blocking operation patterns
- **Resource Limits**: Memory and CPU management
- **Auto-scaling**: Dynamic resource allocation

## 🔮 Extensibility

### Plugin Development

1. **Interface Implementation**: Follow framework interfaces
2. **Lifecycle Management**: Proper initialization and cleanup
3. **Configuration**: Plugin-specific configuration support
4. **Testing**: Unit and integration test requirements

### Custom Components

- **Middleware**: Request/response processing
- **Providers**: Database, authentication, monitoring providers
- **Handlers**: Custom business logic handlers
- **Validators**: Data validation and transformation

## 🔌 Adapter Readiness & Optional Extras

| Adapter | Status | Notes |
| --- | --- | --- |
| Client-side discovery | Production-ready | Uses the in-memory registry API and participates in the shared caching layer. |
| Server-side discovery | Production-ready | Communicates with HTTP discovery services; requires reachable discovery endpoint. |
| Hybrid discovery | Production-ready | Combines client- and server-side adapters; falls back automatically if the preferred path fails. |
| Service mesh discovery | Preview (stub) | Requires a Kubernetes client via `mesh_config["client_factory"]`. Set `allow_stub: True` only for local development to use the `MockKubernetesClient`, which returns no endpoints. |
| External connectors (REST, gRPC, SOAP) | Production-ready | Provide retry and circuit breaker integration out of the box. |
| Marketplace connectors marked “sandbox” | Experimental | Use behind feature flags until validation is complete. |

> **Tip:** See `src/framework/discovery/clients/service_mesh.py` for guidance on wiring a real mesh adapter and the guardrails that prevent the stub from shipping unchecked.

### Optional Dependency Groups

Heavy observability and analytics toolchains are now distributed via extras so base installations remain lightweight:

- `pip install marty-msf[observability]` – Prometheus client library and OpenTelemetry SDK/exporters.
- `pip install marty-msf[analytics]` – Data analysis and load-testing stack (NumPy, Matplotlib, Seaborn, Locust).
- `pip install marty-msf[all]` – Installs all optional extras alongside the microservices and cloud integrations.

## 📚 Related Documentation

- **[API Documentation Infrastructure](api-documentation-infrastructure.md)** - Unified API documentation and contract testing capabilities
- **[Data Consistency Patterns](../data-consistency-patterns.md)** - Comprehensive guide to saga, outbox, and CQRS patterns
- **[Plugin Development Guide](guides/plugin-system.md)**
- **[Testing Strategy](development/TESTING_STRATEGY.md)**
- **[Migration Guide](guides/MIGRATION_GUIDE.md)**
- **[Observability Setup](guides/observability.md)**
- **[CLI Usage](guides/CLI_README.md)**

## 🎯 Recent Architecture Enhancements

### Data Consistency Patterns Implementation (October 2025)

The framework has been enhanced with enterprise-grade data consistency patterns to address the challenges of distributed transaction management and reliable event publishing in microservices architectures.

#### **Key Implementation Decisions:**

1. **Saga Orchestration Enhancement**
   - **Decision**: Enhanced existing `saga.py` with advanced compensation handlers rather than creating from scratch
   - **Rationale**: Preserved existing integrations while adding enterprise features like parallel execution and state management
   - **Location**: `src/marty_msf/patterns/saga/` (enhanced existing implementation)

2. **Transactional Outbox Pattern**
   - **Decision**: Implemented comprehensive outbox pattern with batch processing and dead letter queues
   - **Rationale**: Ensures ACID compliance for business data and events, eliminates dual-write problems
   - **Features**:
     - Batch processing for performance (configurable batch sizes)
     - Dead letter queue handling for failed events
     - Multi-broker support (Kafka/RabbitMQ)
     - Retry mechanisms with exponential backoff
   - **Location**: `src/marty_msf/patterns/outbox/enhanced_outbox.py`

3. **CQRS Templates and Implementation**
   - **Decision**: Created comprehensive CQRS templates with validation and projection builders
   - **Rationale**: Enables optimal read/write model separation with built-in caching and validation
   - **Features**:
     - Command/Query handlers with generic type support
     - Read model projections with event-driven updates
     - Validation framework for commands and queries
     - Caching layer for performance optimization
   - **Location**: `src/marty_msf/patterns/cqrs/enhanced_cqrs.py`

4. **Unified Configuration System**
   - **Decision**: Created environment-specific configuration management
   - **Rationale**: Supports development, production, and testing environments with different scaling requirements
   - **Features**: Database, event store, message broker, saga, and CQRS configurations
   - **Location**: `src/marty_msf/patterns/config.py`

#### **Architecture Impact:**

- **Reliability**: Transactional outbox ensures no lost events due to system failures
- **Scalability**: CQRS enables independent scaling of read and write operations
- **Consistency**: Saga orchestration manages complex business workflows with proper compensation
- **Observability**: Comprehensive metrics and monitoring for all data consistency operations

#### **Integration with Existing Framework:**

- **Backward Compatibility**: All existing functionality preserved
- **Plugin Integration**: Data consistency patterns available as optional framework capabilities
- **Configuration**: Unified configuration system supports existing and new patterns
- **Testing**: Comprehensive test suite demonstrates integrated usage patterns

#### **Petstore Demo Enhancement:**

The petstore domain plugin has been enhanced to demonstrate the outbox pattern:

- **New Endpoints**: `/api/v1/petstore-outbox/*` showcasing transactional outbox pattern
- **Reliable Events**: All business operations (pet creation, orders, user registration) use outbox pattern
- **Metrics**: Real-time outbox processing metrics available at `/petstore-outbox/metrics`
- **Health Checks**: Outbox-specific health checks for monitoring reliability

#### **Performance Considerations:**

- **Batch Processing**: Outbox events processed in configurable batches (default: 100 events)
- **Connection Pooling**: Optimized database and message broker connections
- **Caching**: Multi-level caching for CQRS read models
- **Async Processing**: Non-blocking outbox event processing

#### **Deployment Requirements:**

- **Database**: PostgreSQL with outbox tables for transactional guarantee
- **Message Brokers**: Kafka or RabbitMQ for reliable event delivery
- **Configuration**: Environment-specific settings for scaling and performance
- **Monitoring**: Integration with existing Prometheus/Grafana observability stack

### 🛠️ CLI Tools and Developer Experience

The framework provides comprehensive command-line tools for development, migration, and operations:

#### API Documentation and Contract Testing Commands (`marty api`)

- **docs**: Generate unified API documentation across REST and gRPC services with interactive examples
- **create-contract**: Create consumer-driven contracts for REST and gRPC APIs with interactive prompts
- **test-contracts**: Verify contracts against running services with detailed validation reports
- **list-contracts**: Display available contracts with filtering by consumer, provider, or type
- **register-version**: Register API versions with deprecation tracking and migration guides
- **list-versions**: Show API version status, deprecation timelines, and compatibility information
- **generate-grpc-contract**: Auto-generate contracts from Protocol Buffer definitions
- **generate-contract-docs**: Create human-readable documentation from contract specifications
- **monitor-contracts**: Continuous contract compliance monitoring with webhook notifications

#### Migration Commands (`marty migrate`)

- **helm-to-kustomize**: Convert Helm charts to Kustomize manifests with MMF optimizations
- **generate-overlay**: Create environment-specific Kustomize overlays with service mesh support
- **validate-migration**: Verify migration consistency and functional parity
- **check-compatibility**: Assess Helm chart migration readiness and complexity

#### Service Mesh Commands (`marty service-mesh`)

- **install**: Deploy and configure Istio or Linkerd service mesh with MMF integration
- **apply-policies**: Apply traffic policies (circuit breakers, retries, rate limiting, fault injection)
- **status**: Monitor service mesh health, injection status, and policy compliance

#### Plugin Commands (`marty plugin`)

- **create**: Generate new microservice plugins with architectural patterns
- **add-service**: Add services to existing plugins with feature integration
- **list**: Display available plugins and their configurations

#### API Documentation Features

- **Unified Documentation**: Combines REST (OpenAPI) and gRPC (Protocol Buffers) documentation into cohesive API references
- **Multi-Format Output**: Generates HTML, Markdown, Postman collections, and interactive documentation sites
- **Version Management**: Tracks API versions, deprecation schedules, and migration paths across services
- **Theme Support**: Multiple documentation themes (Redoc, Swagger UI, Stoplight) with responsive design
- **Code Examples**: Automatic generation of client examples in multiple programming languages

#### Contract Testing Capabilities

- **Consumer-Driven Contracts**: Pact-compatible REST contracts and custom gRPC contract specifications
- **Interactive Creation**: Guided contract creation with validation and type checking
- **Verification Engine**: Validates provider implementations against consumer expectations
- **Continuous Monitoring**: Automated contract testing with CI/CD integration and alerting
- **Proto Integration**: Automatic contract generation from Protocol Buffer service definitions

#### Service Generation Features

- **Architectural Patterns**: Support for layered, hexagonal, clean, and CQRS/ES architectures
- **Service Templates**: FastAPI, gRPC, and hybrid service scaffolding
- **Feature Integration**: Database, caching, authentication, and observability components
- **Service Mesh Integration**: Automatic annotation generation and policy application

#### Development Workflow Integration

- **Environment Management**: Seamless dev/staging/prod configuration management
- **Policy Templates**: Pre-configured resilience patterns for common scenarios
- **Monitoring Setup**: Automatic service mesh metrics and dashboard configuration
- **GitOps Support**: Declarative configurations ready for continuous deployment
- **Documentation Automation**: Integrated documentation generation in build pipelines
- **Contract Validation**: Automated contract testing in CI/CD workflows

---

This architecture supports the framework's mission of providing enterprise-grade microservices capabilities while maintaining developer productivity and operational excellence.
