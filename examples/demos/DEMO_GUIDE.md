# MMF Demonstrations

This directory contains comprehensive demonstrations of all Marty Microservices Framework (MMF) capabilities, organized for different user needs and experience levels.

## 🚀 Quick Start (5 minutes)

**New to MMF?** Start here for an immediate overview:

```bash
# Run the quick start demo
python quick_start_demo.py

# Or with detailed output
python quick_start_demo.py --verbose
```

This demonstrates core capabilities in under 5 minutes:

- Database operations (PostgreSQL)
- Cache operations (Redis)
- Message processing
- Health monitoring
- Basic resilience patterns

## 🎯 Comprehensive Demos

For deeper exploration of specific MMF features:

```bash
# List all available demos
python runner/petstore_demo_runner.py --list

# Run specific feature demos
python runner/petstore_demo_runner.py --demo core          # Core framework features
python runner/petstore_demo_runner.py --demo resilience    # Resilience patterns
python runner/petstore_demo_runner.py --demo api-docs      # API documentation
python runner/petstore_demo_runner.py --demo ml            # ML integration
python runner/petstore_demo_runner.py --demo service-mesh  # Service mesh features
python runner/petstore_demo_runner.py --demo scaling       # Operational scaling

# Run all demos (45-60 minutes)
python runner/petstore_demo_runner.py --demo all
```

## 🏪 Petstore Domain Example

**Path:** `petstore_domain/`
**Time:** 2-3 hours to fully explore
**Complexity:** ⭐⭐⭐

Complete real-world example demonstrating enterprise patterns:

- ✅ **Full Microservices Architecture**: Multiple interconnected services
- ✅ **Production Patterns**: Repository pattern, domain modeling, event sourcing
- ✅ **ML Integration**: Pet recommendation engine with confidence scoring
- ✅ **Resilience Patterns**: Circuit breakers, timeouts, bulkheads
- ✅ **Observability**: Metrics, tracing, health checks, analytics
- ✅ **API Documentation**: Auto-generated OpenAPI specs with contract testing
- ✅ **Container Orchestration**: Docker Compose and Kubernetes manifests
- ✅ **Service Mesh Ready**: Istio configuration for advanced networking

### Quick Petstore Demo

```bash
cd petstore_domain

# Basic functionality demo (3 minutes)
python experience_polish_demo.py --scenario quick

# ML recommendations demo (2 minutes)
python dev/experience_polish_demo.py --scenario ml-demo

# Error resilience demo (5 minutes)
python experience_polish_demo.py --scenario error-demo --errors

# Full experience with analytics (10 minutes)
python experience_polish_demo.py --scenario full --customers 3 --export-data
```

## 📊 Demo Comparison

| Demo Type | Duration | Complexity | Use Case |
|-----------|----------|------------|----------|
| **Quick Start** | 5 min | ⭐ | First introduction to MMF |
| **Feature Demos** | 5-15 min each | ⭐⭐ | Learn specific capabilities |
| **Petstore Domain** | 2-3 hours | ⭐⭐⭐ | Production patterns & integration |

## 🎯 What Each Demo Shows

### Quick Start Demo

- Basic CRUD operations
- Caching strategies
- Message handling
- Health monitoring
- Simple resilience

### Core Framework Demo

- PostgreSQL integration with connection pooling
- Redis caching with expiration policies
- Message queue processing with retry logic
- Comprehensive health check system
- Configuration management

### Resilience Demo

- Circuit breaker patterns
- Timeout and retry strategies
- Bulkhead isolation
- Graceful degradation
- Error recovery mechanisms

### API Documentation Demo

- Automatic OpenAPI generation
- Contract testing with validation
- Interactive documentation UI
- Schema validation
- API versioning strategies

### ML Integration Demo

- Model serving infrastructure
- Real-time inference pipelines
- Recommendation engines
- Model monitoring and metrics
- A/B testing capabilities

### Service Mesh Demo

- Istio service mesh integration
- Distributed tracing with Jaeger
- Traffic management policies
- Security policies and mTLS
- Observability with Prometheus/Grafana

### Operational Scaling Demo

- Load testing scenarios
- Auto-scaling policies
- Performance optimization
- Resource monitoring
- Capacity planning

## 🛠️ Prerequisites

**Minimal (Quick Start & Feature Demos):**

- Python 3.8+
- Docker and Docker Compose
- Basic services (PostgreSQL, Redis)

**Full Experience (Petstore Domain):**

- All minimal requirements
- Kubernetes cluster (Kind/Minikube for local)
- Optional: Istio for service mesh features
- Optional: Prometheus/Grafana for observability

## 📚 Documentation

Each demo includes:

- **README.md**: Setup and usage instructions
- **API_INTEGRATION_README.md**: API documentation features
- **IMPLEMENTATION_SUMMARY.md**: Technical implementation details
- **SECURITY_GUIDE.md**: Security patterns and practices

## 🚀 Getting Started

1. **First Time Users**: Start with `python quick_start_demo.py`
2. **Feature Exploration**: Use `python runner/petstore_demo_runner.py --list`
3. **Deep Dive**: Explore the `petstore_domain/` directory
4. **Production Ready**: Study patterns in petstore for your own services

## 💡 Tips for Success

- Start with the quick demo to get familiar with MMF concepts
- Use the verbose flag (`-v`) for detailed output during demos
- Each demo is designed to be independent - run them in any order
- The petstore domain serves as a comprehensive reference implementation
- Check the generated reports and analytics after running demos

## 🔧 Demo Runner Features

The consolidated demo runners provide:

- **Rich Console Output**: Beautiful, formatted progress indicators
- **Error Handling**: Graceful failures with helpful error messages
- **Performance Metrics**: Real-time performance monitoring
- **Export Capabilities**: Save demo results for analysis
- **Interactive Prompts**: User-guided demonstration flow
- **Prerequisites Checking**: Automatic validation of required services

## 📈 Performance Insights

The demos collect and display:

- **Response Times**: API call latency measurements
- **Throughput Metrics**: Requests per second capabilities
- **Resource Usage**: CPU, memory, and network utilization
- **Error Rates**: Success/failure ratios with categorization
- **Cache Performance**: Hit/miss ratios and response times
- **Database Metrics**: Query performance and connection pooling

## 🌟 Advanced Features Demonstrated

- **Event-Driven Architecture**: Async message processing
- **Domain-Driven Design**: Clean architectural patterns
- **CQRS Implementation**: Command/Query separation
- **Event Sourcing**: Audit trails and state reconstruction
- **Circuit Breaker Patterns**: Fault tolerance mechanisms
- **Distributed Tracing**: Request flow visualization
- **Auto-scaling Policies**: Dynamic resource management
- **Security Patterns**: Authentication, authorization, encryption

---

Ready to explore MMF? Start with `python quick_start_demo.py` and dive in! 🚀
