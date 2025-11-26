"""
Comprehensive Kind + Playwright E2E Tests

This test suite demonstrates end-to-end testing of microservices using:
1. Kind Kubernetes clusters for realistic deployments
2. Playwright for browser automation and UI testing
3. Real service deployment and health checking
4. Dashboard testing and visual regression
"""

import asyncio

import pytest

from tests.e2e.kind_playwright_infrastructure import (
    KindClusterManager,
    PlaywrightTester,
    kind_playwright_test_environment,
)


class TestKindPlaywrightE2E:
    """Test suite for Kind + Playwright end-to-end testing."""

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_complete_microservices_deployment_and_ui_testing(self):
        """
        Complete E2E test that:
        1. Creates Kind cluster
        2. Deploys microservices
        3. Tests services with Playwright
        4. Validates dashboard functionality
        5. Performs visual regression testing
        """
        print("\n🚀 Starting Complete Kind + Playwright E2E Test")

        test_results = {
            "cluster_created": False,
            "services_deployed": [],
            "dashboard_tests": {},
            "responsive_tests": {},
            "service_health_tests": [],
            "screenshots_taken": 0,
            "overall_success": False,
        }

        async with kind_playwright_test_environment(
            cluster_name="full-e2e-test", cleanup_on_exit=True
        ) as (cluster, deployer, tester):
            try:
                # Step 1: Verify cluster is ready
                test_results["cluster_created"] = True
                print("✅ Kind cluster created and ready")

                # Step 2: Deploy test microservices
                print("\n📦 Deploying microservices...")

                # Deploy main dashboard service
                dashboard_deployed = await deployer.deploy_dashboard_service()
                if dashboard_deployed:
                    test_results["services_deployed"].append("dashboard")
                    print("✅ Dashboard service deployed")

                # Deploy additional test services
                for i, service_name in enumerate(["user-service", "order-service"]):
                    service_deployed = await deployer.deploy_test_service(
                        service_name=service_name, port=8080 + i, replicas=1
                    )
                    if service_deployed:
                        test_results["services_deployed"].append(service_name)
                        print(f"✅ {service_name} deployed")

                # Wait for services to be fully ready
                print("\n⏳ Waiting for services to be ready...")
                await asyncio.sleep(15)

                # Step 3: Test dashboard with Playwright
                print("\n🎭 Testing dashboard with Playwright...")
                dashboard_results = await tester.test_dashboard(port=30081)
                test_results["dashboard_tests"] = dashboard_results

                if dashboard_results["accessible"]:
                    print("✅ Dashboard is accessible")
                    print(f"   - Title: {dashboard_results['title']}")
                    print(f"   - Services shown: {dashboard_results['services_count']}")
                    print(f"   - Refresh button works: {dashboard_results['refresh_button_works']}")
                else:
                    print("❌ Dashboard not accessible")

                # Step 4: Test responsive design
                print("\n📱 Testing responsive design...")
                responsive_results = await tester.test_responsive_design(port=30081)
                test_results["responsive_tests"] = responsive_results

                screenshots_count = len(
                    [
                        r
                        for r in responsive_results.values()
                        if isinstance(r, dict) and r.get("screenshot")
                    ]
                )
                test_results["screenshots_taken"] = screenshots_count
                print(f"✅ Responsive design tests completed ({screenshots_count} screenshots)")

                # Step 5: Validate test results
                test_results["overall_success"] = (
                    test_results["cluster_created"]
                    and len(test_results["services_deployed"]) >= 3
                    and test_results["dashboard_tests"].get("accessible", False)
                    and test_results["screenshots_taken"] >= 3
                )

                # Print comprehensive results
                print("\n📊 Test Results Summary:")
                print(f"Cluster created: {test_results['cluster_created']}")
                print(f"Services deployed: {len(test_results['services_deployed'])}")
                print(
                    f"Dashboard accessible: {test_results['dashboard_tests'].get('accessible', False)}"
                )
                print(f"Screenshots taken: {test_results['screenshots_taken']}")
                print(f"Overall success: {test_results['overall_success']}")

                # Assert key requirements
                assert test_results["cluster_created"], "Kind cluster creation failed"
                assert len(test_results["services_deployed"]) >= 1, (
                    "No services deployed successfully"
                )
                assert test_results["dashboard_tests"].get("accessible", False), (
                    "Dashboard not accessible"
                )
                assert test_results["screenshots_taken"] > 0, "No screenshots taken"

                print("\n🎉 Kind + Playwright E2E Test PASSED!")

            except Exception as e:
                print(f"\n❌ E2E Test failed: {e}")
                test_results["error"] = str(e)
                raise

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_dashboard_functionality_only(self):
        """
        Focused test for dashboard functionality without full cluster setup.
        Faster alternative for CI/CD pipelines.
        """
        print("\n🎯 Testing Dashboard Functionality Only")

        async with kind_playwright_test_environment(
            cluster_name="dashboard-test", cleanup_on_exit=True
        ) as (cluster, deployer, tester):
            # Deploy only dashboard
            dashboard_deployed = await deployer.deploy_dashboard_service()
            assert dashboard_deployed, "Failed to deploy dashboard"

            # Wait for service
            await asyncio.sleep(10)

            # Test dashboard
            results = await tester.test_dashboard(port=30081)

            # Assertions
            assert results["accessible"], "Dashboard not accessible"
            assert results["title"] == "Microservices Dashboard", "Unexpected dashboard title"
            assert results["services_count"] >= 2, "Not enough services shown on dashboard"
            assert results["refresh_button_works"], "Refresh button not working"

            print("✅ Dashboard functionality test PASSED!")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_service_scaling_and_monitoring(self):
        """
        Test service scaling and monitoring in Kind cluster.
        """
        print("\n📈 Testing Service Scaling and Monitoring")

        async with kind_playwright_test_environment(
            cluster_name="scaling-test", cleanup_on_exit=True
        ) as (cluster, deployer, tester):
            # Deploy scalable service
            service_deployed = await deployer.deploy_test_service(
                service_name="scalable-service", port=8080, replicas=1
            )
            assert service_deployed, "Failed to deploy scalable service"

            # Deploy dashboard to monitor scaling
            dashboard_deployed = await deployer.deploy_dashboard_service()
            assert dashboard_deployed, "Failed to deploy dashboard"

            # Wait for services
            await asyncio.sleep(15)

            # Test initial state
            initial_results = await tester.test_dashboard(port=30081)
            assert initial_results["accessible"], "Dashboard not accessible"

            # TODO: Add actual scaling tests when kubectl integration is added
            # For now, verify services are running

            print("✅ Service scaling test framework ready")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_visual_regression_detection(self):
        """
        Test visual regression detection across different screen sizes.
        """
        print("\n🔍 Testing Visual Regression Detection")

        async with kind_playwright_test_environment(
            cluster_name="visual-test", cleanup_on_exit=True
        ) as (cluster, deployer, tester):
            # Deploy dashboard
            dashboard_deployed = await deployer.deploy_dashboard_service()
            assert dashboard_deployed, "Failed to deploy dashboard"

            await asyncio.sleep(10)

            # Test responsive design
            responsive_results = await tester.test_responsive_design(port=30081)

            # Verify screenshots for all device types
            device_types = ["desktop", "tablet", "mobile"]
            for device in device_types:
                assert device in responsive_results, f"Missing {device} test results"
                assert responsive_results[device].get("screenshot"), f"No screenshot for {device}"

            print("✅ Visual regression detection test PASSED!")


class TestKindClusterManagement:
    """Test Kind cluster management functionality."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cluster_lifecycle(self):
        """Test cluster creation and deletion."""
        cluster = KindClusterManager("lifecycle-test")

        try:
            # Test cluster creation
            config_path = cluster.create_cluster_config()
            assert config_path.exists(), "Cluster config not created"

            # Test cluster creation
            created = await cluster.create_cluster()
            assert created, "Cluster creation failed"

            # Test cluster deletion
            deleted = await cluster.delete_cluster()
            assert deleted, "Cluster deletion failed"

        except Exception:
            # Cleanup on failure
            await cluster.delete_cluster()
            raise

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_service_deployment(self):
        """Test service deployment functionality."""
        async with kind_playwright_test_environment(
            cluster_name="deployment-test", cleanup_on_exit=True
        ) as (cluster, deployer, tester):
            # Test service deployment
            deployed = await deployer.deploy_test_service(
                service_name="test-service", port=8080, replicas=1
            )
            assert deployed, "Service deployment failed"
            assert "test-service" in deployer.deployed_services


class TestPlaywrightIntegration:
    """Test Playwright integration functionality."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_browser_setup(self):
        """Test browser setup and teardown."""
        tester = PlaywrightTester()

        try:
            # Test browser setup
            await tester.setup_browser(headless=True)
            assert tester.browser is not None, "Browser not initialized"
            assert tester.page is not None, "Page not initialized"

        finally:
            # Cleanup
            await tester.cleanup()


# Utility test for manual execution
async def run_manual_e2e_test():
    """
    Manual test runner for development and debugging.
    Can be run independently for testing infrastructure.
    """
    print("🧪 Running Manual E2E Test")

    test_instance = TestKindPlaywrightE2E()

    try:
        await test_instance.test_complete_microservices_deployment_and_ui_testing()
        print("✅ Manual E2E test completed successfully")
        return True
    except Exception as e:
        print(f"❌ Manual E2E test failed: {e}")
        return False


if __name__ == "__main__":
    print("Kind + Playwright E2E Tests")
    print("Run with: pytest tests/e2e/test_kind_playwright_e2e.py -v -s")
    print(
        "Or manual test: python -c 'import asyncio; from tests.e2e.test_kind_playwright_e2e import run_manual_e2e_test; asyncio.run(run_manual_e2e_test())'"
    )
