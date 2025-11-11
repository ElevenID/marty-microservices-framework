# Helm to Kustomize Migration Guide

This guide provides comprehensive instructions for migrating from Helm charts to Kustomize manifests using the Marty Microservices Framework (MMF).

## Overview

The migration process converts existing Helm charts to Kustomize manifests while maintaining functional parity and introducing MMF best practices. This enables:

- Simplified deployment management
- Better GitOps integration
- Enhanced security and observability
- Standardized microservice patterns

## Prerequisites

Before starting the migration, ensure you have:

### Required Tools

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Install kustomize
curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash

# Install helm (for rendering existing charts)
curl https://get.helm.sh/helm-v3.12.0-linux-amd64.tar.gz | tar xz
```

### MMF Installation

```bash
# Install MMF CLI
pip install marty-microservices-framework

# Verify installation
marty --version
```

## Migration Process

### Step 1: Assessment

First, assess your Helm chart's compatibility with MMF patterns:

```bash
marty migrate check-compatibility \
  --service-name my-service \
  --chart-path ./helm/my-service
```

This command analyzes your Helm chart and provides a compatibility report showing:

- Components that can be automatically migrated
- Components requiring manual intervention
- Recommended migration approach

### Step 2: Backup Current Deployment

Before migration, create a backup of your current deployment:

```bash
# Export current Helm deployment
helm get all my-service -n production > backup/helm-deployment.yaml

# Export current Kubernetes resources
kubectl get all -n production -l app=my-service -o yaml > backup/k8s-resources.yaml
```

### Step 3: Convert Helm Chart to Kustomize

Use the MMF conversion tool to automatically convert your Helm chart:

```bash
marty migrate helm-to-kustomize \
  --helm-chart-path ./helm/my-service \
  --output-path ./k8s/my-service \
  --service-name my-service \
  --values-file ./helm/values-dev.yaml \
  --values-file ./helm/values-prod.yaml \
  --validate
```

This command:

- Renders your Helm templates with provided values
- Converts them to Kustomize base manifests
- Generates environment-specific overlays
- Validates the conversion output

### Step 4: Review Generated Structure

The conversion creates the following structure:

```
k8s/my-service/
├── base/
│   ├── kustomization.yaml      # Base resource list
│   ├── deployment.yaml         # Enhanced deployment with security
│   ├── service.yaml           # Service definition
│   ├── configmap.yaml         # Configuration
│   ├── serviceaccount.yaml    # RBAC setup
│   ├── servicemonitor.yaml    # Prometheus monitoring
│   ├── podmonitor.yaml        # Pod-level metrics
│   ├── hpa.yaml              # Auto-scaling
│   ├── pdb.yaml              # Pod disruption budget
│   └── networkpolicy.yaml    # Network security
├── overlays/
│   ├── dev/
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   └── patch-deployment.yaml
│   ├── staging/
│   └── prod/
└── README.md
```

### Step 5: Customize for Your Service

#### Update Service-Specific Configuration

1. **Replace Template Placeholders:**

   ```bash
   # Replace microservice-template with your service name
   find k8s/my-service -type f -name "*.yaml" -exec sed -i 's/microservice-template/my-service/g' {} \;
   ```

2. **Configure Environment Variables:**
   Edit the ConfigMap and add your service-specific environment variables:

   ```yaml
   # base/configmap.yaml
   data:
     environment: "production"
     database_host: "db.internal"
     redis_url: "redis://cache.internal:6379"
   ```

3. **Set Resource Limits:**
   Adjust resource requests and limits based on your service requirements:

   ```yaml
   # overlays/prod/patch-deployment.yaml
   spec:
     template:
       spec:
         containers:
         - name: my-service
           resources:
             requests:
               cpu: 500m
               memory: 1Gi
             limits:
               cpu: 2000m
               memory: 4Gi
   ```

#### Configure Marty-Specific Features

For services that need database migrations or advanced patterns:

```bash
marty migrate generate-overlay \
  --service-name my-service \
  --environment marty-prod \
  --use-marty-patterns
```

This generates overlays with:

- Database migration jobs
- Persistent volume claims
- Enhanced observability
- Service mesh integration

### Step 6: Validate Migration

Test the generated manifests:

```bash
# Validate Kustomize build
kustomize build k8s/my-service/overlays/dev

# Compare with original Helm output
marty migrate validate-migration \
  --original-path ./helm/my-service \
  --migrated-path ./k8s/my-service/overlays/dev \
  --namespace my-service-dev
```

### Step 7: Deploy to Development

Deploy to a development environment first:

```bash
# Create namespace
kubectl create namespace my-service-dev

# Deploy using Kustomize
kustomize build k8s/my-service/overlays/dev | kubectl apply -f -

# Verify deployment
kubectl get all -n my-service-dev
kubectl rollout status deployment/my-service -n my-service-dev
```

### Step 8: Functional Testing

Perform comprehensive testing:

1. **Health Checks:**

   ```bash
   kubectl port-forward svc/my-service 8080:8080 -n my-service-dev
   curl http://localhost:8080/health
   ```

2. **API Testing:**
   Run your existing test suite against the new deployment

3. **Performance Testing:**
   Compare performance metrics with the Helm deployment

### Step 9: Production Migration

Once testing is successful:

1. **Plan Downtime:**
   - Schedule maintenance window if required
   - Prepare rollback procedures

2. **Deploy to Production:**

   ```bash
   # Update image tags for production
   cd k8s/my-service/overlays/prod
   kustomize edit set image my-service=my-registry/my-service:v1.2.3

   # Deploy
   kustomize build . | kubectl apply -f -
   ```

3. **Monitor Deployment:**

   ```bash
   kubectl rollout status deployment/my-service -n my-service-prod
   kubectl get pods -n my-service-prod -w
   ```

4. **Verify Production:**
   - Check all endpoints
   - Verify metrics and logs
   - Run smoke tests

## Advanced Migration Scenarios

### Services with Custom Resources

For services using custom Kubernetes resources:

1. **Identify Custom Resources:**

   ```bash
   helm template my-service ./helm/my-service | grep -E "^kind:" | sort | uniq
   ```

2. **Manual Migration:**
   Custom resources require manual review and migration:

   ```yaml
   # Add to base/kustomization.yaml
   resources:
     - custom-resource.yaml
   ```

### Services with Complex Dependencies

For services with database dependencies or inter-service communication:

1. **Update ConfigMaps:**

   ```yaml
   # base/configmap.yaml
   data:
     database_url: "postgresql://user:pass@db.internal:5432/mydb"
     service_dependencies: "auth-service,user-service"
   ```

2. **Configure Network Policies:**

   ```yaml
   # base/networkpolicy.yaml
   spec:
     egress:
     - to:
       - podSelector:
           matchLabels:
             app: auth-service
       ports:
       - port: 50051
   ```

### Services with Persistent Storage

For stateful services:

1. **Add PVC to Base:**

   ```yaml
   # base/pvc.yaml
   apiVersion: v1
   kind: PersistentVolumeClaim
   metadata:
     name: my-service-data
   spec:
     accessModes: [ReadWriteOnce]
     resources:
       requests:
         storage: 10Gi
   ```

2. **Mount in Deployment:**

   ```yaml
   # overlays/prod/patch-deployment.yaml
   spec:
     template:
       spec:
         containers:
         - name: my-service
           volumeMounts:
           - name: data
             mountPath: /app/data
         volumes:
         - name: data
           persistentVolumeClaim:
             claimName: my-service-data
   ```

## Troubleshooting

### Common Issues and Solutions

#### 1. Image Pull Errors

```bash
# Check image references
grep -r "image:" k8s/my-service/

# Update image in overlays
kustomize edit set image my-service=correct-registry/my-service:tag
```

#### 2. Configuration Issues

```bash
# Validate ConfigMap generation
kustomize build k8s/my-service/overlays/dev | grep -A 10 "kind: ConfigMap"

# Check for missing environment variables
kubectl describe pod -l app=my-service -n my-service-dev
```

#### 3. RBAC Issues

```bash
# Check ServiceAccount permissions
kubectl auth can-i --list --as=system:serviceaccount:my-service-dev:my-service

# Review RBAC configuration
kubectl describe role my-service -n my-service-dev
```

#### 4. Network Issues

```bash
# Check NetworkPolicy
kubectl describe networkpolicy my-service -n my-service-dev

# Test connectivity
kubectl exec -it deployment/my-service -n my-service-dev -- curl other-service:8080
```

### Rollback Procedures

If issues occur during migration:

#### 1. Quick Rollback to Helm

```bash
# Remove Kustomize deployment
kubectl delete -k k8s/my-service/overlays/prod

# Restore Helm deployment
helm upgrade my-service ./helm/my-service -f values-prod.yaml
```

#### 2. Partial Rollback

```bash
# Scale down new deployment
kubectl scale deployment my-service --replicas=0 -n my-service-prod

# Scale up old deployment
kubectl scale deployment my-service-helm --replicas=3 -n my-service-prod
```

## Best Practices

### 1. Gradual Migration

- Start with non-critical services
- Test thoroughly in development
- Use blue-green deployment for production

### 2. Configuration Management

- Use separate ConfigMaps for environment-specific values
- Store secrets in Kubernetes Secrets, not ConfigMaps
- Use external secret management tools when possible

### 3. Monitoring and Observability

- Verify all monitoring works after migration
- Check that dashboards show correct metrics
- Ensure log aggregation continues working

### 4. Documentation

- Update deployment documentation
- Create runbooks for the new deployment process
- Document any manual steps required

### 5. Automation

- Integrate Kustomize deployments with CI/CD
- Use GitOps for deployment automation
- Automate rollback procedures

## Post-Migration Cleanup

After successful migration:

1. **Remove Helm Resources:**

   ```bash
   helm uninstall my-service-old
   ```

2. **Clean Up Old ConfigMaps/Secrets:**

   ```bash
   kubectl delete configmap my-service-helm-config
   ```

3. **Update CI/CD Pipelines:**
   Replace Helm commands with Kustomize in your pipelines

4. **Archive Helm Charts:**
   Move Helm charts to an archive directory for reference

## Next Steps

After completing the migration:

- Explore advanced MMF features
- Implement GitOps workflows
- Set up automated testing
- Consider service mesh integration

For more information, see:

- [MMF Configuration Guide](../configuration/README.md)
- [Deployment Best Practices](../best-practices/deployment.md)
- [Observability Setup](../observability/README.md)
