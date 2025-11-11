# Experience Polish Usage Guide

## Quick Start Commands

### 1. Run Complete Demo

```bash
# Navigate to project root
cd /path/to/marty-microservices-framework

# Install dependencies
pip install -r requirements.txt

# Run the complete customer journey
python docs/demos/experience_polish_demo.py --scenario complete_journey --with-ml --track-messages
```

### 2. Start Jupyter Analytics

```bash
# Install Jupyter dependencies
pip install jupyter plotly pandas numpy

# Launch notebook
jupyter notebook docs/demos/experience-polish-analytics.ipynb
```

### 3. Deploy Operational Infrastructure

```bash
# Apply scaling configurations
kubectl apply -f docs/demos/operational-scaling/hpa-vpa-manifests.yaml

# Apply Istio service mesh policies
kubectl apply -f docs/demos/operational-scaling/canary-deployment-istio.yaml

# Import Grafana dashboard
kubectl apply -f docs/demos/operational-scaling/grafana-dashboard.yaml
```

### 4. Start ML Advisor Service

```bash
# Launch the ML recommendation sidecar
python docs/demos/ml_pet_advisor.py

# Test the service
curl http://localhost:8001/recommend/user/123
```

## Demo Scenarios

### Error Injection and Recovery

```bash
python docs/demos/experience_polish_demo.py --scenario error_recovery --inject-payment-failure
```

### Load Testing

```bash
python docs/demos/experience_polish_demo.py --scenario stress_test --concurrent-users 50
```

### Scaling Demonstration

```bash
python docs/demos/experience_polish_demo.py --scenario scaling_test --burst-load
```

## Monitoring Access

### Grafana Dashboard

- Import: `docs/demos/operational-scaling/grafana-dashboard.yaml`
- Access: <http://localhost:3000> (after port-forward)

### Prometheus Alerts

- Rules: Included in grafana-dashboard.yaml
- Thresholds: Error rate >5%, Latency >1s P95

## File Structure

```
docs/demos/
├── README.md                           # This comprehensive guide
├── USAGE.md                           # Quick reference commands
├── experience_polish_demo.py          # CLI demonstration script
├── ml_pet_advisor.py                  # ML recommendation service
├── experience-polish-analytics.ipynb  # Jupyter analytics notebook
└── operational-scaling/
    ├── hpa-vpa-manifests.yaml        # Kubernetes autoscaling
    ├── canary-deployment-istio.yaml  # Service mesh policies
    └── grafana-dashboard.yaml        # Monitoring dashboard
```
