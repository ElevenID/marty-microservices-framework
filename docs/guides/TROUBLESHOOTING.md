# Migration Troubleshooting Guide

This guide covers common issues encountered during Helm to Kustomize migration and their solutions.

## Common Migration Issues

### 1. Helm Template Rendering Errors

**Issue:** Converter fails to render Helm templates

```
Error: Failed to render Helm templates: template: my-service/templates/deployment.yaml:15:14: executing "my-service/templates/deployment.yaml" at <.Values.missing>: nil pointer evaluating interface {}.missing
```

**Solutions:**

- Ensure all required values files are provided with `--values-file`
- Check for missing required values in your values.yaml files
- Use `helm template` manually to debug template issues

**Example:**

```bash
# Test Helm rendering first
helm template my-service ./helm/my-service -f values-dev.yaml

# Then run conversion
marty migrate helm-to-kustomize --helm-chart-path ./helm/my-service --values-file values-dev.yaml
```

### 2. Kustomize Build Failures

**Issue:** Generated Kustomize manifests fail to build

```
Error: accumulating resources: accumulation err='accumulating resources from 'serviceaccount.yaml': ...'
```

**Solutions:**

- Validate individual YAML files: `kubectl apply --dry-run=client -f file.yaml`
- Check for duplicate resource names across files
- Ensure all referenced resources exist in the kustomization.yaml

**Example:**

```bash
# Check each overlay individually
kustomize build k8s/my-service/base
kustomize build k8s/my-service/overlays/dev
```

### 3. Missing Container Images

**Issue:** Deployment fails with ImagePullBackOff

```
Failed to pull image "microservice-template:latest": rpc error: code = NotFound desc = image not found
```

**Solutions:**

- Update image references in overlays
- Ensure image exists in registry
- Check image pull secrets if using private registry

**Example:**

```bash
# Update image in overlay
cd k8s/my-service/overlays/prod
kustomize edit set image microservice-template=my-registry/my-service:v1.0.0
```

### 4. ConfigMap/Secret Issues

**Issue:** Pods fail to start due to missing configuration

```
Error: couldn't find key environment in ConfigMap my-service-config
```

**Solutions:**

- Verify ConfigMap generator configuration
- Check that all required keys are defined
- Ensure proper merge behavior for generated ConfigMaps

**Example:**

```yaml
# In kustomization.yaml
configMapGenerator:
  - name: my-service-config
    behavior: merge
    literals:
      - environment=production
      - missing_key=missing_value
```

### 5. Network Policy Blocking Traffic

**Issue:** Services cannot communicate after migration

```
Error: dial tcp 10.0.0.5:8080: i/o timeout
```

**Solutions:**

- Review NetworkPolicy rules
- Temporarily disable NetworkPolicy for testing
- Check service discovery and DNS resolution

**Example:**

```bash
# Test without NetworkPolicy
kubectl delete networkpolicy my-service
# If it works, update NetworkPolicy rules
```

### 6. Monitoring/Metrics Not Working

**Issue:** Prometheus not scraping metrics after migration

**Solutions:**

- Verify ServiceMonitor/PodMonitor configuration
- Check Prometheus operator is installed
- Ensure metrics endpoint is accessible

**Example:**

```bash
# Test metrics endpoint
kubectl port-forward pod/my-service-xxx 9000:9000
curl http://localhost:9000/metrics
```

## Migration-Specific Issues

### 1. Complex Helm Template Logic

**Issue:** Helm charts with complex template logic don't convert well

**Solutions:**

- Simplify templates before conversion
- Handle complex logic manually in Kustomize patches
- Consider using multiple overlays for different configurations

### 2. Helm Hooks Not Supported

**Issue:** Helm hooks (pre-install, post-upgrade) don't have Kustomize equivalent

**Solutions:**

- Convert hooks to Kubernetes Jobs
- Use init containers for pre-deployment tasks
- Implement post-deployment verification as separate jobs

**Example:**

```yaml
# Convert Helm hook to Job
apiVersion: batch/v1
kind: Job
metadata:
  name: my-service-migration
spec:
  template:
    spec:
      containers:
      - name: migration
        image: my-service:latest
        command: ["python", "manage.py", "migrate"]
      restartPolicy: OnFailure
```

### 3. Dynamic Value Generation

**Issue:** Helm's dynamic value generation not possible in Kustomize

**Solutions:**

- Use external tools for dynamic value generation
- Pre-process values before applying Kustomize
- Use init containers for runtime value generation

## Rollback Procedures

### Emergency Rollback to Helm

If critical issues occur:

```bash
# 1. Scale down Kustomize deployment
kubectl scale deployment my-service --replicas=0

# 2. Restore from Helm backup
helm upgrade my-service ./helm/my-service -f values-prod.yaml

# 3. Verify service is running
kubectl get pods -l app=my-service
```

### Partial Rollback

For gradual rollback:

```bash
# 1. Reduce Kustomize deployment replicas
kubectl patch deployment my-service -p '{"spec":{"replicas":1}}'

# 2. Deploy Helm version alongside
helm install my-service-backup ./helm/my-service -f values-prod.yaml

# 3. Switch traffic gradually
kubectl patch service my-service --type='json' -p='[{"op": "replace", "path": "/spec/selector/version", "value": "backup"}]'
```

## Debugging Tools and Commands

### 1. Validate Generated Manifests

```bash
# Check all resources in overlay
kustomize build k8s/my-service/overlays/prod | kubectl apply --dry-run=client -f -

# Validate specific resource types
kustomize build k8s/my-service/overlays/prod | kubectl apply --dry-run=client --validate=strict -f -
```

### 2. Compare Helm vs Kustomize Output

```bash
# Generate Helm output
helm template my-service ./helm/my-service -f values-prod.yaml > helm-output.yaml

# Generate Kustomize output
kustomize build k8s/my-service/overlays/prod > kustomize-output.yaml

# Compare (install yq for better YAML comparison)
diff -u helm-output.yaml kustomize-output.yaml
```

### 3. Debug Resource Issues

```bash
# Check resource status
kubectl describe deployment my-service
kubectl describe pod -l app=my-service

# Check events
kubectl get events --sort-by=.metadata.creationTimestamp

# Check logs
kubectl logs -l app=my-service --tail=100
```

### 4. Network Debugging

```bash
# Test service connectivity
kubectl run debug --image=nicolaka/netshoot -it --rm -- /bin/bash
# Inside the pod:
nslookup my-service
curl my-service:8080/health

# Check network policies
kubectl describe networkpolicy my-service
```

## Performance Considerations

### Resource Usage Comparison

Monitor resource usage before and after migration:

```bash
# Check resource usage
kubectl top pods -l app=my-service
kubectl top nodes

# Monitor over time
kubectl get pods -l app=my-service --watch
```

### Scaling Behavior

Verify auto-scaling works correctly:

```bash
# Check HPA status
kubectl get hpa my-service
kubectl describe hpa my-service

# Generate load to test scaling
kubectl run load-generator --image=busybox -it --rm -- /bin/sh
# while true; do wget -q -O- http://my-service:8080/health; done
```

## Prevention Strategies

### 1. Comprehensive Testing

- Test conversion in development first
- Use staging environment for full validation
- Perform load testing before production migration

### 2. Monitoring Setup

- Set up monitoring before migration
- Create alerts for key metrics
- Monitor during and after migration

### 3. Documentation

- Document all customizations made during conversion
- Create runbooks for common operations
- Keep migration notes for future reference

### 4. Backup Strategy

- Always backup current deployment before migration
- Test rollback procedures
- Have communication plan for issues

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [MMF GitHub Issues](https://github.com/ElevenID/marty-microservices-framework/issues)
2. Consult the [MMF Documentation](../README.md)
3. Join the community discussion forums
4. For urgent production issues, contact the platform team

## Common Questions

**Q: Can I run Helm and Kustomize deployments side by side?**
A: Yes, but they should use different namespaces or resource names to avoid conflicts.

**Q: How do I handle secrets in the migration?**
A: Secrets should be migrated separately and referenced in Kustomize manifests. Consider using external secret management tools.

**Q: What about Helm's dependency management?**
A: Dependencies should be converted to separate Kustomize bases or managed as separate services.

**Q: Can I automate the entire migration process?**
A: Partial automation is possible, but manual review and testing are always recommended for production systems.
