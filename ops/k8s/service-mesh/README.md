# Istio Service Mesh Configuration

This directory contains the complete Istio service mesh configuration for Phase 2 microservices infrastructure, providing advanced traffic management, security, and observability capabilities.

## Quick Start

```bash
# Deploy the complete service mesh configuration
kubectl apply -f gateway/
kubectl apply -f traffic/
kubectl apply -f security/
kubectl apply -f observability/

# Verify installation
kubectl get gateway,virtualservice,destinationrule,peerauthentication,authorizationpolicy -n microservices-prod
```

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Internet      │────▶│  Istio Gateway   │────▶│  VirtualService │
│   Traffic       │    │  (TLS/mTLS)      │    │  (Routing)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Service Mesh Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ API Gateway │  │ Microservice│  │ Microservice│              │
│  │   (Phase2)  │  │     A       │  │     B       │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│         │                │               │                      │
│         └────────────────┼───────────────┘                      │
│                          │                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │    Redis    │  │  RabbitMQ   │  │ PostgreSQL  │              │
│  │  (Cache)    │  │ (Messaging) │  │ (Database)  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Observability & Security Layer                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Prometheus  │  │   Grafana   │  │   Jaeger    │              │
│  │ (Metrics)   │  │ (Dashboard) │  │ (Tracing)   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
service-mesh/
├── README.md                     # This comprehensive guide
├── gateway/
│   └── istio-gateway.yaml       # Gateway configuration for external access
├── traffic/
│   └── virtual-services.yaml   # Traffic routing and load balancing
├── security/
│   └── authentication-policies.yaml  # mTLS and authorization policies
└── observability/
    └── telemetry.yaml          # Metrics, logging, and tracing configuration
```

## Usage

Install Istio service mesh:

```bash
istioctl install --set values.defaultRevision=default
```

Enable sidecar injection:

```bash
kubectl label namespace microservices-dev istio-injection=enabled
kubectl label namespace microservices-test istio-injection=enabled
kubectl label namespace microservices-prod istio-injection=enabled
```

Deploy service mesh configuration:

```bash
kubectl apply -f service-mesh/gateway/
kubectl apply -f service-mesh/traffic/
kubectl apply -f service-mesh/security/
kubectl apply -f service-mesh/observability/
```

## Integration with Phase 2

The service mesh is specifically configured to support:

- Configuration management service discovery
- Cache backend traffic policies
- Message queue connection pooling
- Event streaming flow control
- API gateway load balancing
- Monitoring and alerting integration
