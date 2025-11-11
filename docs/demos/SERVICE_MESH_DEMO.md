# Service Mesh Integration Demo

This demo showcases the comprehensive service mesh integration capabilities of the Marty Microservices Framework, demonstrating how to deploy, configure, and operate services with Istio or Linkerd.

## 🎯 Demo Objectives

1. **Service Mesh Installation**: Deploy Istio or Linkerd with MMF integration
2. **Traffic Management**: Configure circuit breakers, retries, and rate limiting
3. **Fault Injection**: Demonstrate chaos engineering capabilities
4. **Observability**: Monitor service mesh metrics and policies
5. **CLI Integration**: Use MMF CLI for service mesh operations

## 🔧 Prerequisites

- Kubernetes cluster (Kind, Minikube, or cloud provider)
- MMF CLI installed (`pip install marty-microservices-framework`)
- kubectl configured for your cluster
- Docker for building service images

## 🚀 Quick Start

### 1. Setup Kubernetes Cluster

```bash
# Create Kind cluster with service mesh support
kind create cluster --name mmf-demo --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
  - containerPort: 15021
    hostPort: 15021
    protocol: TCP
EOF
```

### 2. Install Service Mesh

Choose your preferred service mesh:

#### Option A: Istio

```bash
# Install Istio service mesh
marty service-mesh install --mesh-type istio --enable-monitoring

# Verify installation
marty service-mesh status --mesh-type istio
```

#### Option B: Linkerd

```bash
# Install Linkerd service mesh
marty service-mesh install --mesh-type linkerd --enable-monitoring

# Verify installation
marty service-mesh status --mesh-type linkerd
```

### 3. Deploy Demo Services

```bash
# Create demo namespace
kubectl create namespace demo-services

# Generate service manifests with service mesh integration
marty migrate generate-overlay \
  --service-name payment-service \
  --environment dev \
  --service-mesh istio \
  --enable-circuit-breaker \
  --enable-retry-policies \
  --enable-rate-limiting \
  --enable-fault-injection

# Deploy the services
kubectl apply -k k8s/overlays/dev/
```

### 4. Apply Traffic Policies

```bash
# Apply comprehensive service mesh policies
marty service-mesh apply-policies \
  --service-name payment-service \
  --mesh-type istio \
  --enable-circuit-breaker \
  --enable-retry \
  --enable-rate-limit \
  --enable-fault-injection
```

## 📊 Demo Scenarios

### Scenario 1: Circuit Breaker Protection

1. **Generate Load**: Send requests to trigger circuit breaker

   ```bash
   # Generate normal load
   kubectl run load-generator --rm -i --tty --image=busybox -- /bin/sh
   while true; do wget -qO- http://payment-service/api/v1/payments; sleep 1; done
   ```

2. **Trigger Failures**: Introduce service failures

   ```bash
   # Scale down backend to trigger circuit breaker
   kubectl scale deployment payment-service --replicas=0
   ```

3. **Monitor Circuit Breaker**: Watch metrics and policy enforcement

   ```bash
   # Check circuit breaker status
   kubectl get destinationrules.networking.istio.io -o yaml

   # View service mesh metrics
   kubectl port-forward -n istio-system service/grafana 3000:3000
   # Open http://localhost:3000 (Istio Service Mesh dashboard)
   ```

### Scenario 2: Fault Injection Testing

1. **Enable Chaos Headers**: Add chaos engineering headers

   ```bash
   # Inject 5% latency
   curl -H "x-chaos-enabled: true" http://payment-service/api/v1/payments

   # Inject 1% errors
   curl -H "x-chaos-error: true" http://payment-service/api/v1/payments
   ```

2. **Monitor Impact**: Observe service behavior under induced faults

   ```bash
   # Watch service logs
   kubectl logs -f deployment/payment-service

   # Check retry attempts
   kubectl logs -f deployment/payment-service -c istio-proxy | grep retry
   ```

### Scenario 3: Rate Limiting

1. **Generate Burst Traffic**: Test rate limiting policies

   ```bash
   # Generate burst requests
   seq 1 200 | xargs -I {} -P 20 curl http://payment-service/api/v1/payments
   ```

2. **Observe Rate Limiting**: Check enforcement

   ```bash
   # Check rate limit headers in response
   curl -I http://payment-service/api/v1/payments

   # View Envoy rate limiting stats
   kubectl exec deployment/payment-service -c istio-proxy -- curl localhost:15000/stats | grep rate_limit
   ```

### Scenario 4: mTLS Security

1. **Verify mTLS**: Check mutual TLS enforcement

   ```bash
   # Check TLS certificates
   kubectl exec deployment/payment-service -c istio-proxy -- openssl s_client -connect user-service:8080 -servername user-service
   ```

2. **Test Security Policies**: Verify authorization

   ```bash
   # Check authorization policies
   kubectl get authorizationpolicies.security.istio.io -o yaml

   # Test unauthorized access
   kubectl run test-pod --rm -i --tty --image=curlimages/curl -- curl http://payment-service/admin
   ```

## 🔍 Monitoring and Observability

### Grafana Dashboards

Access service mesh dashboards:

```bash
# Istio dashboards
kubectl port-forward -n istio-system service/grafana 3000:3000

# Linkerd dashboards
kubectl port-forward -n linkerd-viz service/grafana 3000:3000
```

Available dashboards:

- **Service Mesh Overview**: Overall mesh health and performance
- **Service Details**: Per-service metrics and policies
- **Workload Details**: Pod-level metrics and sidecar stats
- **Performance**: Latency, throughput, and error rates

### Jaeger Tracing

View distributed traces:

```bash
# Access Jaeger UI
kubectl port-forward -n istio-system service/jaeger 16686:16686
# Open http://localhost:16686
```

### Prometheus Metrics

Query service mesh metrics:

```bash
# Access Prometheus
kubectl port-forward -n istio-system service/prometheus 9090:9090
# Open http://localhost:9090
```

Useful queries:

- `istio_requests_total`: Total request count
- `istio_request_duration_milliseconds`: Request latency
- `envoy_cluster_outlier_detection_ejections_active`: Circuit breaker ejections

## 🧪 Advanced Testing

### Chaos Engineering

Comprehensive fault injection testing:

```bash
# Create chaos testing script
cat > chaos-test.sh << 'EOF'
#!/bin/bash

echo "🔬 Starting Chaos Engineering Tests..."

# Test 1: Latency injection
echo "Test 1: Latency injection (5% of requests)"
kubectl patch virtualservice payment-service-fault-injection --type=merge -p='
spec:
  http:
  - match:
    - headers:
        x-chaos-enabled:
          exact: "true"
    fault:
      delay:
        percentage:
          value: 5.0
        fixedDelay: 5s'

# Test 2: Error injection
echo "Test 2: Error injection (2% of requests)"
kubectl patch virtualservice payment-service-fault-injection --type=merge -p='
spec:
  http:
  - match:
    - headers:
        x-chaos-error:
          exact: "true"
    fault:
      abort:
        percentage:
          value: 2.0
        httpStatus: 503'

# Test 3: Circuit breaker triggering
echo "Test 3: Circuit breaker stress test"
seq 1 1000 | xargs -I {} -P 50 curl -H "x-chaos-enabled: true" http://payment-service/api/v1/payments

echo "✅ Chaos tests completed"
EOF

chmod +x chaos-test.sh
./chaos-test.sh
```

### Performance Testing

Load testing with service mesh policies:

```bash
# Install k6 for load testing
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: k6-test-script
data:
  test.js: |
    import http from 'k6/http';
    import { check } from 'k6';

    export let options = {
      stages: [
        { duration: '2m', target: 100 },
        { duration: '5m', target: 100 },
        { duration: '2m', target: 200 },
        { duration: '5m', target: 200 },
        { duration: '2m', target: 0 },
      ],
    };

    export default function() {
      let response = http.get('http://payment-service/api/v1/payments');
      check(response, {
        'status is 200': (r) => r.status === 200,
        'response time < 500ms': (r) => r.timings.duration < 500,
      });
    }
---
apiVersion: batch/v1
kind: Job
metadata:
  name: k6-load-test
spec:
  template:
    spec:
      containers:
      - name: k6
        image: grafana/k6:latest
        command: ['k6', 'run', '/scripts/test.js']
        volumeMounts:
        - name: k6-script
          mountPath: /scripts
      volumes:
      - name: k6-script
        configMap:
          name: k6-test-script
      restartPolicy: Never
EOF
```

## 📈 Metrics and Alerts

### Custom Alerts

Set up service mesh-specific alerts:

```bash
# Apply service mesh alerting rules
kubectl apply -f ops/service-mesh/monitoring/service-mesh-alerts.yml
```

Alert examples:

- **High error rate**: >5% error rate for 2 minutes
- **Circuit breaker triggered**: Circuit breaker state changes
- **mTLS failures**: Non-mTLS traffic detected
- **High latency**: P99 latency >1s for 5 minutes

### SLI/SLO Monitoring

Service Level Indicators and Objectives:

```yaml
# Example SLO configuration
slos:
  payment-service:
    availability: 99.9%
    latency_p95: 200ms
    latency_p99: 500ms
    error_rate: <1%
```

## 🧹 Cleanup

Remove demo resources:

```bash
# Remove demo services
kubectl delete namespace demo-services

# Remove service mesh (optional)
marty service-mesh uninstall --mesh-type istio  # or linkerd

# Delete Kind cluster
kind delete cluster --name mmf-demo
```

## 📚 Additional Resources

- [Service Mesh Architecture Documentation](../architecture/architecture.md#service-mesh-support)
- [CLI Reference](../guides/CLI_README.md)
- [Troubleshooting Guide](../guides/TROUBLESHOOTING.md)
- [Performance Tuning](../guides/performance-tuning.md)

## 🎉 Next Steps

1. **Production Deployment**: Apply learnings to production environments
2. **Custom Policies**: Create service-specific traffic policies
3. **Integration Testing**: Incorporate service mesh testing into CI/CD
4. **Advanced Observability**: Set up custom dashboards and alerts
5. **Security Hardening**: Implement zero-trust security policies

This demo demonstrates the complete service mesh integration capabilities of the Marty Microservices Framework, providing a foundation for building resilient, observable, and secure microservices at scale.
