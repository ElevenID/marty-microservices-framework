# Kind + Playwright E2E Testing

This directory contains comprehensive end-to-end tests that combine **Kind Kubernetes clusters** with **Playwright browser automation** for realistic microservices testing.

## 🎯 Overview

Unlike traditional E2E tests that use mocks, these tests:

1. **Create real Kubernetes clusters** using Kind
2. **Deploy actual microservices** to the cluster
3. **Test deployed services** via browser automation with Playwright
4. **Validate UI functionality** and responsive design
5. **Clean up resources** automatically after testing

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Kind Cluster  │    │   Microservices  │    │   Playwright    │
│                 │    │                  │    │                 │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │Control Plane│ │◄──►│ │  Dashboard   │ │◄──►│ │   Browser   │ │
│ └─────────────┘ │    │ │   Service    │ │    │ │ Automation  │ │
│ ┌─────────────┐ │    │ └──────────────┘ │    │ └─────────────┘ │
│ │   Worker    │ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │    Node     │ │    │ │    User      │ │    │ │Screenshot & │ │
│ └─────────────┘ │    │ │   Service    │ │    │ │  Regression │ │
└─────────────────┘    │ └──────────────┘ │    │ │   Testing   │ │
                       └──────────────────┘    └─────────────────┘
```

## 📦 Prerequisites

### 1. Install Required Tools

```bash
# Install Kind (Kubernetes in Docker)
# macOS
brew install kind

# Linux
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Windows
curl.exe -Lo kind-windows-amd64.exe https://kind.sigs.k8s.io/dl/v0.20.0/kind-windows-amd64
Move-Item .\\kind-windows-amd64.exe c:\\some-dir-in-your-PATH\\kind.exe
```

### 2. Install Python Dependencies

```bash
# Install development dependencies including Playwright
uv sync --extra dev

# Install Playwright browsers
uv run playwright install chromium

# Verify installations
kind version
uv run python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"
```

### 3. Docker Setup

```bash
# Ensure Docker is running
docker ps

# Pull required images (optional - will be pulled automatically)
docker pull nginx:alpine
docker pull kindest/node:v1.27.3
```

## 🚀 Quick Start

### Run Complete E2E Test Suite

```bash
# Run all Kind + Playwright E2E tests
uv run pytest tests/e2e/test_kind_playwright_e2e.py -v -s

# Run with specific markers
uv run pytest tests/e2e/test_kind_playwright_e2e.py -m "e2e" -v -s

# Run individual test
uv run pytest tests/e2e/test_kind_playwright_e2e.py::TestKindPlaywrightE2E::test_complete_microservices_deployment_and_ui_testing -v -s
```

### Run Manual Test (for debugging)

```bash
# Run manual test with detailed output
uv run python -c "
import asyncio
from tests.e2e.test_kind_playwright_e2e import run_manual_e2e_test
asyncio.run(run_manual_e2e_test())
"
```

### Quick Infrastructure Test

```bash
# Test just the infrastructure setup
uv run python -c "
import asyncio
from tests.e2e.kind_playwright_infrastructure import run_basic_kind_playwright_test
asyncio.run(run_basic_kind_playwright_test())
"
```

## 🧪 Test Scenarios

### 1. Complete Microservices E2E Test

**File**: `test_kind_playwright_e2e.py::test_complete_microservices_deployment_and_ui_testing`

**What it does**:

- Creates Kind cluster with control plane + worker nodes
- Deploys dashboard service and multiple microservices
- Tests dashboard accessibility and functionality
- Performs responsive design testing (desktop/tablet/mobile)
- Takes screenshots for visual regression testing
- Validates service health and UI interactions

**Duration**: ~3-5 minutes

### 2. Dashboard Functionality Test

**File**: `test_kind_playwright_e2e.py::test_dashboard_functionality_only`

**What it does**:

- Quick cluster setup with dashboard only
- Tests core dashboard functionality
- Validates UI elements and interactions
- Faster alternative for CI/CD pipelines

**Duration**: ~1-2 minutes

### 3. Service Scaling and Monitoring

**File**: `test_kind_playwright_e2e.py::test_service_scaling_and_monitoring`

**What it does**:

- Deploys scalable services
- Tests monitoring dashboard
- Framework for scaling validation (extensible)

**Duration**: ~2-3 minutes

### 4. Visual Regression Detection

**File**: `test_kind_playwright_e2e.py::test_visual_regression_detection`

**What it does**:

- Tests responsive design across device types
- Takes baseline screenshots
- Compares visual layouts
- Detects UI regressions

**Duration**: ~1-2 minutes

## 📊 Test Output & Reports

### Test Results Location

```
tests/e2e/
├── test_screenshots/          # Playwright screenshots
│   ├── dashboard_1697123456.png
│   ├── dashboard_desktop_*.png
│   ├── dashboard_tablet_*.png
│   └── dashboard_mobile_*.png
├── test_results/             # JSON test reports
└── cluster_logs/             # Kind cluster logs
```

### Sample Test Output

```
🚀 Starting Complete Kind + Playwright E2E Test

✅ Kind cluster created and ready

📦 Deploying microservices...
✅ Dashboard service deployed
✅ user-service deployed
✅ order-service deployed

⏳ Waiting for services to be ready...

🎭 Testing dashboard with Playwright...
✅ Dashboard is accessible
   - Title: Microservices Dashboard
   - Services shown: 2
   - Refresh button works: True

📱 Testing responsive design...
✅ Responsive design tests completed (3 screenshots)

📊 Test Results Summary:
Cluster created: True
Services deployed: 3
Dashboard accessible: True
Screenshots taken: 3
Overall success: True

🎉 Kind + Playwright E2E Test PASSED!
```

## 🛠️ Infrastructure Components

### KindClusterManager

Manages Kubernetes cluster lifecycle:

```python
cluster = KindClusterManager("test-cluster")
await cluster.create_cluster()  # Creates cluster with proper port mappings
await cluster.delete_cluster()  # Cleans up resources
```

### MicroserviceDeployer

Handles service deployment:

```python
deployer = MicroserviceDeployer(cluster)
await deployer.deploy_dashboard_service()  # Deploys dashboard with NodePort
await deployer.deploy_test_service("api-service", port=8080)  # Deploys custom service
```

### PlaywrightTester

Performs browser automation:

```python
tester = PlaywrightTester()
await tester.setup_browser()
results = await tester.test_dashboard(port=30081)  # Tests dashboard functionality
responsive = await tester.test_responsive_design()  # Tests responsive layouts
```

## 🔧 Configuration

### Cluster Configuration

The Kind cluster is configured with:

- **Control plane**: 1 node with ingress-ready label
- **Worker nodes**: 1 node for realistic scheduling
- **Port mappings**:
  - 30080 → 80 (HTTP traffic)
  - 30081 → 8080 (Dashboard)
  - 30082 → 9090 (Metrics)

### Service Configuration

Services are deployed with:

- **Dashboard**: nginx serving custom HTML dashboard
- **Test Services**: nginx with custom configuration
- **NodePort services**: Accessible from host machine
- **Health checks**: Built-in service monitoring

### Playwright Configuration

Browser testing includes:

- **Headless mode**: Configurable for CI/CD vs debugging
- **Multiple viewports**: Desktop (1200x800), Tablet (768x1024), Mobile (375x667)
- **Screenshot capture**: Automatic for visual regression
- **Network monitoring**: Request/response validation

## 🐛 Troubleshooting

### Common Issues

**1. Kind cluster creation fails**

```bash
# Check Docker is running
docker ps

# Check Kind version
kind version

# Manual cluster creation
kind create cluster --name debug-cluster
```

**2. Services not accessible**

```bash
# Check cluster status
kubectl get nodes
kubectl get pods -A

# Check service endpoints
kubectl get services
kubectl describe service dashboard
```

**3. Playwright browser issues**

```bash
# Reinstall browsers
uv run playwright install chromium

# Test browser setup
uv run python -c "
import asyncio
from playwright.async_api import async_playwright
async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        print('Browser OK')
        await browser.close()
asyncio.run(test())
"
```

**4. Port conflicts**

```bash
# Check what's using the ports
lsof -i :30080
lsof -i :30081

# Kill conflicting processes or change port mappings
```

### Debug Mode

Run tests with debug settings:

```bash
# Run with debug output
uv run pytest tests/e2e/test_kind_playwright_e2e.py -v -s --tb=long

# Keep cluster running for debugging
KEEP_CLUSTER=true uv run pytest tests/e2e/test_kind_playwright_e2e.py -v -s

# Run browser in non-headless mode
HEADLESS=false uv run pytest tests/e2e/test_kind_playwright_e2e.py -v -s
```

### Manual Cluster Inspection

```bash
# Connect to cluster
kubectl config use-context kind-e2e-test-cluster

# Inspect services
kubectl get all
kubectl logs -l app=dashboard

# Port forward for direct access
kubectl port-forward service/dashboard 8080:80

# Access dashboard directly
open http://localhost:8080
```

## 🚀 CI/CD Integration

### GitHub Actions Example

```yaml
name: Kind + Playwright E2E Tests

on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v6

      - name: Install Kind
        run: |
          curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
          chmod +x ./kind
          sudo mv ./kind /usr/local/bin/kind

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync --extra dev
          uv run playwright install chromium

      - name: Run E2E tests
        run: |
          uv run pytest tests/e2e/test_kind_playwright_e2e.py -v --tb=short

      - name: Upload screenshots
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-screenshots
          path: tests/e2e/test_screenshots/
```

## 🔄 Extending the Tests

### Adding New Services

```python
# In your test
async def test_my_custom_service():
    async with kind_playwright_test_environment() as (cluster, deployer, tester):
        # Deploy your service
        await deployer.deploy_test_service(
            service_name="my-api",
            port=8080,
            replicas=2
        )

        # Test with Playwright
        results = await tester.test_service_health("my-api", 30080)
        assert results["accessible"]
```

### Custom Dashboard Testing

```python
# Create custom dashboard HTML
def create_custom_dashboard():
    return """
    <html>
        <body>
            <h1>My Custom Dashboard</h1>
            <div id="metrics">Loading...</div>
        </body>
    </html>
    """

# Test custom elements
async def test_custom_elements(tester):
    await tester.page.goto("http://localhost:30081")
    metrics = await tester.page.query_selector("#metrics")
    assert metrics is not None
```

### Visual Regression Baselines

```python
# Take baseline screenshots
async def create_visual_baselines():
    async with kind_playwright_test_environment() as (_, deployer, tester):
        await deployer.deploy_dashboard_service()

        # Take baseline screenshots
        await tester.test_responsive_design()
        print("Baseline screenshots created in test_screenshots/")
```

## 📈 Performance & Scaling

### Resource Requirements

- **CPU**: 2-4 cores recommended
- **Memory**: 4-8GB for cluster + browser
- **Disk**: 2-5GB for images and logs
- **Network**: Ports 30080-30082 available

### Scaling Considerations

- **Parallel tests**: Use different cluster names
- **Resource limits**: Configure Kind node resources
- **Test isolation**: Each test gets fresh cluster
- **Cleanup**: Automatic resource cleanup prevents accumulation

### Optimization Tips

1. **Use smaller images**: nginx:alpine vs nginx
2. **Reduce wait times**: Tune readiness probes
3. **Cache images**: Pre-pull common images
4. **Parallel execution**: Run different test categories in parallel
5. **Selective cleanup**: Keep cluster between related tests

## 🤝 Contributing

When adding new E2E tests:

1. **Follow naming convention**: `test_*_e2e.py`
2. **Use proper markers**: `@pytest.mark.e2e`, `@pytest.mark.slow`
3. **Include cleanup**: Use `kind_playwright_test_environment` context manager
4. **Document scenarios**: Add clear docstrings explaining test purpose
5. **Consider CI/CD**: Ensure tests work in headless environments

## 📚 References

- [Kind Documentation](https://kind.sigs.k8s.io/)
- [Playwright Python](https://playwright.dev/python/)
- [Kubernetes Testing](https://kubernetes.io/docs/tasks/debug-application-cluster/debug-application/)
- [Visual Regression Testing](https://playwright.dev/python/docs/test-screenshots)

## 🎉 Success

You now have comprehensive Kind + Playwright E2E tests that provide:

✅ **Real Kubernetes deployments** with Kind
✅ **Browser automation** with Playwright
✅ **Visual regression testing** across devices
✅ **Automated cleanup** and resource management
✅ **CI/CD ready** with proper reporting
✅ **Extensible architecture** for custom scenarios

Happy testing! 🚀
