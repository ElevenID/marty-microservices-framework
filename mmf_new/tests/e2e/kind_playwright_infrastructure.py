"""
Kind + Playwright E2E Test Infrastructure

This module provides utilities for running comprehensive end-to-end tests that:
1. Create Kind Kubernetes clusters
2. Deploy microservices to the cluster
3. Use Playwright to test deployed services via browser automation
4. Clean up resources after testing
"""

import asyncio
import subprocess
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import docker
import yaml
from kubernetes import client, config
from playwright.async_api import Browser, Page, async_playwright


class KindClusterManager:
    """Manages Kind Kubernetes clusters for E2E testing."""

    def __init__(self, cluster_name: str = "e2e-test-cluster"):
        self.cluster_name = cluster_name
        self.cluster_config_path: Path | None = None
        self.kubectl_context = f"kind-{cluster_name}"
        self.docker_client = docker.from_env()

    def create_cluster_config(
        self,
        control_plane_port: int = 30080,
        dashboard_port: int = 30081,
        metrics_port: int = 30082,
    ) -> Path:
        """Create Kind cluster configuration with proper port mappings."""
        config_content = {
            "kind": "Cluster",
            "apiVersion": "kind.x-k8s.io/v1alpha4",
            "name": self.cluster_name,
            "nodes": [
                {
                    "role": "control-plane",
                    "kubeadmConfigPatches": [
                        """kind: InitConfiguration
nodeRegistration:
  kubeletExtraArgs:
    node-labels: "ingress-ready=true" """
                    ],
                    "extraPortMappings": [
                        {"containerPort": 80, "hostPort": control_plane_port, "protocol": "TCP"},
                        {"containerPort": 8080, "hostPort": dashboard_port, "protocol": "TCP"},
                        {"containerPort": 9090, "hostPort": metrics_port, "protocol": "TCP"},
                    ],
                },
                {"role": "worker", "labels": {"node-type": "worker"}},
            ],
            "networking": {"apiServerAddress": "127.0.0.1"},
        }

        # Write to temporary file
        config_file = Path(tempfile.mkdtemp()) / "kind-config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        self.cluster_config_path = config_file
        return config_file

    async def create_cluster(self, wait_timeout: int = 120) -> bool:
        """Create Kind cluster and wait for it to be ready."""
        try:
            # Check if cluster already exists
            result = subprocess.run(["kind", "get", "clusters"], capture_output=True, text=True)

            if self.cluster_name in result.stdout:
                print(f"Cluster {self.cluster_name} already exists, deleting first...")
                await self.delete_cluster()

            # Create cluster config if not exists
            if not self.cluster_config_path:
                self.create_cluster_config()

            print(f"Creating Kind cluster: {self.cluster_name}")
            create_cmd = [
                "kind",
                "create",
                "cluster",
                "--name",
                self.cluster_name,
                "--config",
                str(self.cluster_config_path),
                "--wait",
                f"{wait_timeout}s",
            ]

            result = subprocess.run(create_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"Failed to create cluster: {result.stderr}")
                return False

            # Load kubeconfig
            self._load_kubeconfig()

            # Wait for nodes to be ready
            await self._wait_for_nodes_ready(timeout=wait_timeout)

            print(f"✅ Kind cluster {self.cluster_name} created successfully")
            return True

        except Exception as e:
            print(f"❌ Error creating cluster: {e}")
            return False

    async def delete_cluster(self) -> bool:
        """Delete the Kind cluster."""
        try:
            result = subprocess.run(
                ["kind", "delete", "cluster", "--name", self.cluster_name],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                print(f"Warning: Failed to delete cluster: {result.stderr}")
                return False

            print(f"✅ Kind cluster {self.cluster_name} deleted successfully")
            return True

        except Exception as e:
            print(f"❌ Error deleting cluster: {e}")
            return False

    def _load_kubeconfig(self):
        """Load kubeconfig for the Kind cluster."""
        try:
            # Load config from default location
            config.load_kube_config(context=self.kubectl_context)
        except Exception as e:
            print(f"Warning: Could not load kubeconfig: {e}")

    async def _wait_for_nodes_ready(self, timeout: int = 120):
        """Wait for all nodes to be in Ready state."""
        try:
            v1 = client.CoreV1Api()
            start_time = time.time()

            while time.time() - start_time < timeout:
                nodes = v1.list_node()
                ready_nodes = 0

                for node in nodes.items:
                    for condition in node.status.conditions:
                        if condition.type == "Ready" and condition.status == "True":
                            ready_nodes += 1
                            break

                if ready_nodes == len(nodes.items):
                    print(f"✅ All {ready_nodes} nodes are ready")
                    return

                print(f"Waiting for nodes... ({ready_nodes}/{len(nodes.items)} ready)")
                await asyncio.sleep(5)

            raise TimeoutError(f"Nodes not ready after {timeout}s")

        except Exception as e:
            print(f"Error waiting for nodes: {e}")
            raise


class MicroserviceDeployer:
    """Deploys and manages microservices in Kind cluster."""

    def __init__(self, cluster_manager: KindClusterManager):
        self.cluster_manager = cluster_manager
        self.deployed_services: list[str] = []

    async def deploy_test_service(
        self, service_name: str = "test-microservice", port: int = 8080, replicas: int = 2
    ) -> bool:
        """Deploy a test microservice to the cluster."""
        try:
            # Create deployment YAML
            deployment = self._create_deployment_yaml(service_name, port, replicas)
            service_yaml = self._create_service_yaml(service_name, port)

            # Apply manifests
            apps_v1 = client.AppsV1Api()
            core_v1 = client.CoreV1Api()

            # Create deployment
            apps_v1.create_namespaced_deployment(namespace="default", body=deployment)

            # Create service
            core_v1.create_namespaced_service(namespace="default", body=service_yaml)

            # Wait for deployment to be ready
            await self._wait_for_deployment_ready(service_name)

            self.deployed_services.append(service_name)
            print(f"✅ Service {service_name} deployed successfully")
            return True

        except Exception as e:
            print(f"❌ Error deploying service {service_name}: {e}")
            return False

    async def deploy_dashboard_service(self, port: int = 8080) -> bool:
        """Deploy a dashboard service for testing with Playwright."""
        dashboard_html = self._create_dashboard_html()

        # Create ConfigMap with dashboard HTML
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "dashboard-html"},
            "data": {"index.html": dashboard_html},
        }

        # Create deployment that serves the HTML
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "dashboard"},
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": "dashboard"}},
                "template": {
                    "metadata": {"labels": {"app": "dashboard"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "nginx",
                                "image": "nginx:alpine",
                                "ports": [{"containerPort": 80}],
                                "volumeMounts": [
                                    {"name": "html", "mountPath": "/usr/share/nginx/html"}
                                ],
                            }
                        ],
                        "volumes": [{"name": "html", "configMap": {"name": "dashboard-html"}}],
                    },
                },
            },
        }

        # Create NodePort service
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "dashboard"},
            "spec": {
                "selector": {"app": "dashboard"},
                "ports": [{"port": 80, "targetPort": 80, "nodePort": 30081, "protocol": "TCP"}],
                "type": "NodePort",
            },
        }

        try:
            core_v1 = client.CoreV1Api()
            apps_v1 = client.AppsV1Api()

            # Create ConfigMap
            core_v1.create_namespaced_config_map(namespace="default", body=configmap)

            # Create deployment
            apps_v1.create_namespaced_deployment(namespace="default", body=deployment)

            # Create service
            core_v1.create_namespaced_service(namespace="default", body=service)

            # Wait for deployment
            await self._wait_for_deployment_ready("dashboard")

            self.deployed_services.append("dashboard")
            print("✅ Dashboard service deployed successfully")
            return True

        except Exception as e:
            print(f"❌ Error deploying dashboard: {e}")
            return False

    def _create_deployment_yaml(self, name: str, port: int, replicas: int) -> dict:
        """Create Kubernetes deployment YAML."""
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name},
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": {"app": name}},
                "template": {
                    "metadata": {"labels": {"app": name}},
                    "spec": {
                        "containers": [
                            {
                                "name": name,
                                "image": "nginx:alpine",
                                "ports": [{"containerPort": port}],
                                "env": [
                                    {"name": "SERVICE_NAME", "value": name},
                                    {"name": "SERVICE_PORT", "value": str(port)},
                                ],
                            }
                        ]
                    },
                },
            },
        }

    def _create_service_yaml(self, name: str, port: int) -> dict:
        """Create Kubernetes service YAML."""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name},
            "spec": {
                "selector": {"app": name},
                "ports": [{"port": port, "targetPort": port, "protocol": "TCP"}],
                "type": "ClusterIP",
            },
        }

    def _create_dashboard_html(self) -> str:
        """Create HTML dashboard for Playwright testing."""
        return """<!DOCTYPE html>
<html>
<head>
    <title>Microservices Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .service { border: 1px solid #ccc; margin: 10px; padding: 15px; border-radius: 5px; }
        .status { font-weight: bold; }
        .healthy { color: green; }
        .unhealthy { color: red; }
        .metrics { margin-top: 10px; }
        #refresh-btn { background: blue; color: white; padding: 10px; border: none; cursor: pointer; }
    </style>
</head>
<body>
    <h1>Microservices Dashboard</h1>
    <button id="refresh-btn" onclick="refreshData()">Refresh</button>

    <div id="services">
        <div class="service">
            <h3>Test Service</h3>
            <div class="status healthy">Status: Healthy</div>
            <div class="metrics">
                <div>CPU: 25%</div>
                <div>Memory: 128MB</div>
                <div>Requests/sec: 45</div>
            </div>
        </div>

        <div class="service">
            <h3>Database Service</h3>
            <div class="status healthy">Status: Healthy</div>
            <div class="metrics">
                <div>CPU: 15%</div>
                <div>Memory: 512MB</div>
                <div>Connections: 12</div>
            </div>
        </div>
    </div>

    <script>
        function refreshData() {
            console.log('Refreshing dashboard data...');
            // In real scenario, this would fetch from API
            document.getElementById('refresh-btn').textContent = 'Refreshed!';
            setTimeout(() => {
                document.getElementById('refresh-btn').textContent = 'Refresh';
            }, 2000);
        }

        // Auto-refresh every 30 seconds
        setInterval(refreshData, 30000);
    </script>
</body>
</html>"""

    async def _wait_for_deployment_ready(self, name: str, timeout: int = 120):
        """Wait for deployment to be ready."""
        apps_v1 = client.AppsV1Api()
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                deployment = apps_v1.read_namespaced_deployment(name=name, namespace="default")

                if (
                    deployment.status.ready_replicas
                    and deployment.status.ready_replicas == deployment.spec.replicas
                ):
                    print(f"✅ Deployment {name} is ready")
                    return

                print(f"Waiting for deployment {name}...")
                await asyncio.sleep(5)

            except Exception as e:
                print(f"Error checking deployment {name}: {e}")
                await asyncio.sleep(5)

        raise TimeoutError(f"Deployment {name} not ready after {timeout}s")

    async def cleanup_services(self):
        """Clean up deployed services."""
        try:
            apps_v1 = client.AppsV1Api()
            core_v1 = client.CoreV1Api()

            for service_name in self.deployed_services:
                try:
                    # Delete deployment
                    apps_v1.delete_namespaced_deployment(name=service_name, namespace="default")

                    # Delete service
                    core_v1.delete_namespaced_service(name=service_name, namespace="default")

                    print(f"✅ Cleaned up service: {service_name}")

                except Exception as e:
                    print(f"Warning: Could not clean up {service_name}: {e}")

            # Clean up ConfigMaps
            try:
                core_v1.delete_namespaced_config_map(name="dashboard-html", namespace="default")
            except Exception as cleanup_error:
                print(f"Warning: Could not remove dashboard ConfigMap: {cleanup_error}")

            self.deployed_services.clear()

        except Exception as e:
            print(f"Error during cleanup: {e}")


class PlaywrightTester:
    """Handles Playwright browser testing of deployed services."""

    def __init__(self, base_url: str = "http://localhost"):
        self.base_url = base_url
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.screenshots_dir = Path("test_screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)

    async def setup_browser(self, headless: bool = True):
        """Setup Playwright browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        self.page = await self.browser.new_page()

    async def test_dashboard(self, port: int = 30081) -> dict[str, Any]:
        """Test the dashboard deployed in Kind cluster."""
        url = f"{self.base_url}:{port}"
        results = {
            "url": url,
            "accessible": False,
            "title": None,
            "services_count": 0,
            "refresh_button_works": False,
            "screenshot_taken": False,
        }

        try:
            print(f"Testing dashboard at {url}")

            # Navigate to dashboard
            await self.page.goto(url, wait_until="networkidle")
            results["accessible"] = True

            # Check title
            title = await self.page.title()
            results["title"] = title
            print(f"✅ Dashboard accessible, title: {title}")

            # Count services
            services = await self.page.query_selector_all(".service")
            results["services_count"] = len(services)
            print(f"✅ Found {len(services)} services on dashboard")

            # Test refresh button
            refresh_btn = await self.page.query_selector("#refresh-btn")
            if refresh_btn:
                await refresh_btn.click()
                await asyncio.sleep(1)

                # Check if button text changed
                btn_text = await refresh_btn.inner_text()
                results["refresh_button_works"] = "Refreshed" in btn_text
                print(f"✅ Refresh button test: {results['refresh_button_works']}")

            # Take screenshot
            screenshot_path = self.screenshots_dir / f"dashboard_{int(time.time())}.png"
            await self.page.screenshot(path=screenshot_path)
            results["screenshot_taken"] = True
            results["screenshot_path"] = str(screenshot_path)
            print(f"✅ Screenshot saved: {screenshot_path}")

        except Exception as e:
            print(f"❌ Dashboard test failed: {e}")
            results["error"] = str(e)

        return results

    async def test_service_health(self, service_name: str, port: int) -> dict[str, Any]:
        """Test service health endpoint."""
        url = f"{self.base_url}:{port}/health"
        results = {
            "service": service_name,
            "url": url,
            "accessible": False,
            "status_code": None,
            "response_time_ms": None,
        }

        try:
            start_time = time.time()
            response = await self.page.goto(url)
            end_time = time.time()

            results["accessible"] = True
            results["status_code"] = response.status
            results["response_time_ms"] = round((end_time - start_time) * 1000, 2)

            print(
                f"✅ Service {service_name} health check: {response.status} ({results['response_time_ms']}ms)"
            )

        except Exception as e:
            print(f"❌ Service {service_name} health check failed: {e}")
            results["error"] = str(e)

        return results

    async def test_responsive_design(self, port: int = 30081) -> dict[str, Any]:
        """Test dashboard responsive design."""
        url = f"{self.base_url}:{port}"
        results = {
            "desktop": {"width": 1200, "height": 800, "screenshot": None},
            "tablet": {"width": 768, "height": 1024, "screenshot": None},
            "mobile": {"width": 375, "height": 667, "screenshot": None},
        }

        try:
            await self.page.goto(url, wait_until="networkidle")

            for device, dimensions in results.items():
                # Set viewport size
                await self.page.set_viewport_size(
                    width=dimensions["width"], height=dimensions["height"]
                )

                # Wait for layout adjustment
                await asyncio.sleep(1)

                # Take screenshot
                screenshot_path = (
                    self.screenshots_dir / f"dashboard_{device}_{int(time.time())}.png"
                )
                await self.page.screenshot(path=screenshot_path)
                dimensions["screenshot"] = str(screenshot_path)

                print(f"✅ {device.capitalize()} screenshot saved: {screenshot_path}")

        except Exception as e:
            print(f"❌ Responsive design test failed: {e}")
            results["error"] = str(e)

        return results

    async def cleanup(self):
        """Clean up browser resources."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, "playwright"):
            await self.playwright.stop()


@asynccontextmanager
async def kind_playwright_test_environment(
    cluster_name: str = "e2e-test", cleanup_on_exit: bool = True
):
    """
    Context manager for Kind + Playwright test environment.

    Usage:
        async with kind_playwright_test_environment() as (cluster, deployer, tester):
            # Deploy services
            await deployer.deploy_dashboard_service()

            # Test with Playwright
            results = await tester.test_dashboard()
    """
    cluster = KindClusterManager(cluster_name)
    deployer = MicroserviceDeployer(cluster)
    tester = PlaywrightTester()

    try:
        # Setup cluster
        cluster_created = await cluster.create_cluster()
        if not cluster_created:
            raise RuntimeError("Failed to create Kind cluster")

        # Setup browser
        await tester.setup_browser()

        yield cluster, deployer, tester

    finally:
        # Cleanup
        if cleanup_on_exit:
            await deployer.cleanup_services()
            await tester.cleanup()
            await cluster.delete_cluster()
        else:
            await tester.cleanup()


# Test utility functions
async def run_basic_kind_playwright_test():
    """Run a basic Kind + Playwright test."""
    async with kind_playwright_test_environment() as (cluster, deployer, tester):
        print("🚀 Starting Kind + Playwright E2E Test")

        # Deploy dashboard
        dashboard_deployed = await deployer.deploy_dashboard_service()
        if not dashboard_deployed:
            print("❌ Failed to deploy dashboard")
            return False

        # Wait for service to be accessible
        await asyncio.sleep(10)

        # Test dashboard
        dashboard_results = await tester.test_dashboard()

        # Test responsive design
        responsive_results = await tester.test_responsive_design()

        # Print results
        print("\n📊 Test Results:")
        print(f"Dashboard accessible: {dashboard_results['accessible']}")
        print(f"Services found: {dashboard_results['services_count']}")
        print(f"Refresh button works: {dashboard_results['refresh_button_works']}")
        print(
            f"Screenshots taken: {len([r for r in responsive_results.values() if 'screenshot' in r])}"
        )

        return dashboard_results["accessible"]


if __name__ == "__main__":
    print("Kind + Playwright E2E Test Infrastructure")
    print(
        "Run: python -c 'from tests.e2e.kind_playwright_infrastructure import run_basic_kind_playwright_test; import asyncio; asyncio.run(run_basic_kind_playwright_test())'"
    )
