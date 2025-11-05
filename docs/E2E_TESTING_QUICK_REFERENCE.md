# MMF E2E Testing Quick Reference

## Quick Start

```bash
# Run full e2e test suite
./tests/e2e/kind/automated/e2e-test.sh

# Run with local test runner (recommended for development)
./tests/e2e/kind/test-e2e.sh

# Quick development tests
./tests/e2e/kind/test-e2e.sh -m quick -k

# Clean up all test resources
./tests/e2e/kind/test-e2e.sh -m clean
```

## Test Modes

| Mode | Description | Duration | Use Case |
|------|-------------|----------|----------|
| `full` | Complete test suite | ~5 min | CI/CD, release validation |
| `quick` | Essential tests only | ~2 min | Development iteration |
| `smoke` | Basic health checks | ~30 sec | Quick validation |
| `clean` | Resource cleanup | ~10 sec | Environment reset |

## Available Scripts

### Main Test Scripts
- `tests/e2e/kind/automated/e2e-test.sh` - Core e2e test runner
- `tests/e2e/kind/test-e2e.sh` - Local development runner
- `scripts/generate-report.sh` - Test report generator

### GitHub Actions
- `.github/workflows/e2e-tests.yml` - Automated CI/CD testing

## Common Commands

```bash
# Check running clusters
kind get clusters

# Monitor test cluster
kubectl cluster-info --context kind-mmf-e2e-test

# View application logs
kubectl logs -n mmf-system -l app=identity-service -f

# Port forward for manual testing
kubectl port-forward -n mmf-system svc/identity-service 8000:80

# Clean up specific cluster
kind delete cluster --name mmf-e2e-test

# Remove test images
docker rmi mmf/identity-service:e2e-test
```

## Test Results Interpretation

### Success Indicators
- ✅ Green checkmarks for passed tests
- 🎉 "All tests passed!" message
- Exit code 0

### Failure Indicators
- ❌ Red X marks for failed tests
- 💥 "Some tests failed" message
- Exit code 1
- Detailed error messages in output

### Expected Failures
- Empty Credentials: Returns validation error (working as designed)
- Resource Monitoring: Metrics server not available in KIND (expected)

## Development Workflow

1. **Make code changes** in `mmf_new/` or `platform_core/`
2. **Run quick tests**: `./tests/e2e/kind/test-e2e.sh -m quick -k`
3. **Debug if needed**: Use port-forward and logs
4. **Run full suite**: `./tests/e2e/kind/test-e2e.sh` before committing
5. **Clean up**: `./tests/e2e/kind/test-e2e.sh -m clean`

## Troubleshooting

### Cannot create cluster
```bash
# Check Docker is running
docker info

# Clean up existing clusters
kind delete clusters --all
```

### Tests timeout
```bash
# Check cluster resources
kubectl get pods --all-namespaces
kubectl get nodes

# Increase timeout in deploy/e2e-config.env
```

### Port conflicts
```bash
# Use different cluster name
./tests/e2e/kind/test-e2e.sh -c my-test-cluster
```

### Image build fails
```bash
# Check Dockerfile and requirements
docker build -t test-image .

# Clean Docker cache
docker system prune -f
```

## Integration with IDE

### VS Code Tasks
Add to `.vscode/tasks.json`:
```json
{
  "label": "Run E2E Tests",
  "type": "shell",
  "command": "./tests/e2e/kind/test-e2e.sh",
  "args": ["-m", "quick", "-v"],
  "group": "test"
}
```

### Test Discovery
- Tests are automatically discovered by the framework
- No need to manually register new test cases
- API endpoints are tested systematically

## Performance Benchmarks

### Typical Execution Times (MacBook Pro M1)
- Cluster creation: 30-45 seconds
- Image build: 20-30 seconds
- Application deployment: 15-20 seconds
- API tests: 5-10 seconds
- Cleanup: 5-10 seconds

### Resource Usage
- RAM: ~2GB for KIND cluster
- CPU: Moderate during build, minimal during tests
- Disk: ~500MB for images and logs

## Next Steps

After successful e2e tests:
1. **Migrate more services** from `mmf/` to `mmf_new/`
2. **Add service-specific tests** for each migrated component
3. **Implement integration tests** between services
4. **Add performance benchmarks** for SLA validation
5. **Set up production deployment** using proven patterns
