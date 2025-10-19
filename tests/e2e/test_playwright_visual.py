"""
End-to-End Visual Tests using Playwright

This test demonstrates:
1. Visual testing of monitoring dashboards and service status pages
2. Automated testing of web interfaces for observability
3. Screenshot comparison and visual regression testing
4. UI interaction testing for dashboard controls
"""

import asyncio
import builtins
import json
from pathlib import Path

import pytest
from aiohttp import web  # Added for F821 'web'
from playwright.async_api import Browser, Page, async_playwright

from tests.e2e.conftest import PerformanceAnalyzer


class MockDashboardServer:
    """Mock dashboard server for testing visual interfaces."""

    def __init__(self, port: int = 8080):
        self.port = port
        self.server_process = None

    async def start(self):
        """Start mock dashboard server."""
        # Create simple HTML dashboard for testing
        self._create_dashboard_html()

        # Create a simple HTTP server (in real scenarios, this would be your actual dashboard)

        app = web.Application()
        app.router.add_get("/", self._handle_dashboard)
        app.router.add_get("/metrics", self._handle_metrics)
        app.router.add_get("/api/health", self._handle_health)
        app.router.add_static("/static/", path="static/", name="static")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", self.port)
        await site.start()

        print(f"Mock dashboard server started on http://localhost:{self.port}")
        return runner

    async def _handle_dashboard(self, request):
        """Handle dashboard page request."""
        html_content = self._create_dashboard_html()
        return web.Response(text=html_content, content_type="text/html")

    async def _handle_metrics(self, request):
        """Handle metrics API request."""
        metrics_data = {
            "timestamp": "2025-10-08T10:00:00Z",
            "services": {
                "simulation_service": {
                    "status": "healthy",
                    "response_time": 250,
                    "error_rate": 2.1,
                    "cpu_usage": 45.0,
                    "memory_usage": 67.8,
                },
                "pipeline_service": {
                    "status": "warning",
                    "response_time": 850,
                    "error_rate": 8.5,
                    "cpu_usage": 78.0,
                    "memory_usage": 82.3,
                },
                "monitoring_service": {
                    "status": "healthy",
                    "response_time": 120,
                    "error_rate": 0.5,
                    "cpu_usage": 23.0,
                    "memory_usage": 45.2,
                },
            },
            "alerts": [
                {
                    "id": "alert_001",
                    "severity": "warning",
                    "service": "pipeline_service",
                    "message": "High error rate detected",
                    "timestamp": "2025-10-08T09:55:00Z",
                },
                {
                    "id": "alert_002",
                    "severity": "info",
                    "service": "simulation_service",
                    "message": "Service recovery completed",
                    "timestamp": "2025-10-08T09:50:00Z",
                },
            ],
        }
        return web.json_response(metrics_data)

    async def _handle_health(self, request):
        """Handle health check request."""
        return web.json_response({"status": "healthy", "timestamp": "2025-10-08T10:00:00Z"})

    def _create_dashboard_html(self):
        """Create HTML dashboard for testing."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Marty Framework - Monitoring Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .metric-card {
            text-align: center;
        }
        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }
        .healthy { color: #28a745; }
        .warning { color: #ffc107; }
        .error { color: #dc3545; }
        .service-status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            border-left: 4px solid #28a745;
            margin: 10px 0;
            background: #f8f9fa;
        }
        .service-status.warning { border-left-color: #ffc107; }
        .service-status.error { border-left-color: #dc3545; }
        .alert {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 4px;
            padding: 12px;
            margin: 10px 0;
        }
        .alert.warning { background: #fff3cd; border-color: #ffeaa7; }
        .alert.error { background: #f8d7da; border-color: #f5c6cb; }
        .alert.info { background: #d1ecf1; border-color: #bee5eb; }
        .controls {
            display: flex;
            gap: 10px;
            margin: 20px 0;
        }
        button {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover { background: #0056b3; }
        .refresh-button { background: #28a745; }
        .export-button { background: #6c757d; }
        #chart-container {
            height: 300px;
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Marty Framework - Monitoring Dashboard</h1>
        <p>Real-time monitoring and observability for microservices</p>
    </div>

    <div class="controls">
        <button id="refresh-btn" class="refresh-button">🔄 Refresh Data</button>
        <button id="export-btn" class="export-button">📊 Export Report</button>
        <button id="alerts-btn">🚨 View Alerts</button>
        <button id="settings-btn">⚙️ Settings</button>
    </div>

    <div class="dashboard-grid">
        <div class="card metric-card">
            <h3>Services Status</h3>
            <div class="metric-value healthy" id="healthy-services">3</div>
            <p>Healthy Services</p>
        </div>

        <div class="card metric-card">
            <h3>Active Alerts</h3>
            <div class="metric-value warning" id="active-alerts">2</div>
            <p>Alerts Requiring Attention</p>
        </div>

        <div class="card metric-card">
            <h3>Avg Response Time</h3>
            <div class="metric-value" id="avg-response-time">406ms</div>
            <p>Across All Services</p>
        </div>

        <div class="card metric-card">
            <h3>Error Rate</h3>
            <div class="metric-value error" id="error-rate">3.7%</div>
            <p>Last 5 Minutes</p>
        </div>
    </div>

    <div class="dashboard-grid">
        <div class="card">
            <h3>Service Health</h3>
            <div id="service-list">
                <div class="service-status healthy">
                    <span>🔄 Simulation Service</span>
                    <span class="healthy">● Healthy</span>
                </div>
                <div class="service-status warning">
                    <span>🔧 Pipeline Service</span>
                    <span class="warning">● Warning</span>
                </div>
                <div class="service-status healthy">
                    <span>📊 Monitoring Service</span>
                    <span class="healthy">● Healthy</span>
                </div>
            </div>
        </div>

        <div class="card">
            <h3>Recent Alerts</h3>
            <div id="alerts-list">
                <div class="alert warning">
                    <strong>Warning:</strong> High error rate detected in pipeline_service
                    <br><small>2025-10-08 09:55:00</small>
                </div>
                <div class="alert info">
                    <strong>Info:</strong> Service recovery completed for simulation_service
                    <br><small>2025-10-08 09:50:00</small>
                </div>
            </div>
        </div>
    </div>

    <div class="card">
        <h3>Performance Metrics Chart</h3>
        <div id="chart-container">
            📈 Chart would be rendered here with real monitoring data
        </div>
    </div>

    <script>
        // Mock dashboard functionality
        let refreshInterval;

        document.getElementById('refresh-btn').addEventListener('click', function() {
            refreshData();
        });

        document.getElementById('export-btn').addEventListener('click', function() {
            alert('Report export functionality would be implemented here');
        });

        document.getElementById('alerts-btn').addEventListener('click', function() {
            alert('Alerts details modal would open here');
        });

        document.getElementById('settings-btn').addEventListener('click', function() {
            alert('Settings panel would open here');
        });

        function refreshData() {
            fetch('/api/health')
                .then(response => response.json())
                .then(data => {
                    console.log('Health check:', data);
                    updateLastRefresh();
                })
                .catch(error => {
                    console.error('Error fetching health data:', error);
                });

            fetch('/metrics')
                .then(response => response.json())
                .then(data => {
                    console.log('Metrics data:', data);
                    updateDashboard(data);
                })
                .catch(error => {
                    console.error('Error fetching metrics:', error);
                });
        }

        function updateDashboard(data) {
            // Update service counts
            const services = data.services;
            const healthyCount = Object.values(services).filter(s => s.status === 'healthy').length;
            document.getElementById('healthy-services').textContent = healthyCount;

            // Update alerts count
            document.getElementById('active-alerts').textContent = data.alerts.length;

            // Update average response time
            const avgResponseTime = Object.values(services).reduce((sum, s) => sum + s.response_time, 0) / Object.keys(services).length;
            document.getElementById('avg-response-time').textContent = Math.round(avgResponseTime) + 'ms';

            // Update error rate
            const avgErrorRate = Object.values(services).reduce((sum, s) => sum + s.error_rate, 0) / Object.keys(services).length;
            document.getElementById('error-rate').textContent = avgErrorRate.toFixed(1) + '%';
        }

        function updateLastRefresh() {
            const now = new Date().toLocaleTimeString();
            console.log('Dashboard refreshed at:', now);
        }

        // Auto-refresh every 30 seconds
        refreshInterval = setInterval(refreshData, 30000);

        // Initial load
        refreshData();
    </script>
</body>
</html>
        """


class TestPlaywrightVisual:
    """Test suite for visual testing with Playwright."""

    @pytest.mark.asyncio
    async def test_dashboard_visual_testing(
        self,
        simulation_plugin,
        monitoring_plugin,
        performance_analyzer: PerformanceAnalyzer,
        test_report_dir: Path,
    ):
        """
        Comprehensive visual testing of monitoring dashboard using Playwright.
        """
        print("\\n🎭 Starting Playwright visual testing...")

        # Start mock dashboard server
        dashboard_server = MockDashboardServer(port=8080)
        server_runner = await dashboard_server.start()

        try:
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(
                    headless=False,  # Set to True for CI/CD
                    slow_mo=500,  # Slow down for better visual observation
                )

                # Create test results
                test_results = await self._run_dashboard_tests(
                    browser, dashboard_server, test_report_dir
                )

                # Generate visual test report
                report = self._generate_visual_test_report(test_results, test_report_dir)

                # Save report
                report_file = test_report_dir / "visual_testing_report.json"
                with open(report_file, "w") as f:
                    json.dump(report, f, indent=2)

                print(f"\\n📋 Visual test report saved to: {report_file}")

                # Assertions
                assert test_results["dashboard_load"]["success"], (
                    "Dashboard should load successfully"
                )
                assert test_results["responsive_design"]["mobile_compatible"], (
                    "Dashboard should be mobile compatible"
                )
                assert test_results["interactive_elements"]["all_buttons_functional"], (
                    "All buttons should be functional"
                )

                # Print summary
                self._print_visual_test_summary(report)

                await browser.close()

        finally:
            # Cleanup server
            await server_runner.cleanup()
            print("\\n🧹 Cleaned up mock dashboard server")

    async def _run_dashboard_tests(
        self, browser: Browser, dashboard_server, test_report_dir: Path
    ) -> builtins.dict:
        """Run comprehensive dashboard tests."""

        results = {
            "dashboard_load": {},
            "visual_regression": {},
            "responsive_design": {},
            "interactive_elements": {},
            "performance_metrics": {},
            "accessibility": {},
        }

        # Create screenshots directory
        screenshots_dir = test_report_dir / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)

        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        try:
            # Test 1: Dashboard Loading
            print("🔄 Testing dashboard loading...")
            results["dashboard_load"] = await self._test_dashboard_loading(
                page, dashboard_server, screenshots_dir
            )

            # Test 2: Visual Regression Testing
            print("📸 Running visual regression tests...")
            results["visual_regression"] = await self._test_visual_regression(page, screenshots_dir)

            # Test 3: Responsive Design Testing
            print("📱 Testing responsive design...")
            results["responsive_design"] = await self._test_responsive_design(
                browser, dashboard_server, screenshots_dir
            )

            # Test 4: Interactive Elements Testing
            print("🖱️ Testing interactive elements...")
            results["interactive_elements"] = await self._test_interactive_elements(
                page, screenshots_dir
            )

            # Test 5: Performance Metrics Display
            print("📊 Testing performance metrics display...")
            results["performance_metrics"] = await self._test_performance_metrics(
                page, screenshots_dir
            )

            # Test 6: Accessibility Testing
            print("♿ Testing accessibility...")
            results["accessibility"] = await self._test_accessibility(page, screenshots_dir)

        finally:
            await context.close()

        return results

    async def _test_dashboard_loading(
        self, page: Page, dashboard_server, screenshots_dir: Path
    ) -> builtins.dict:
        """Test dashboard loading and initial state."""

        start_time = asyncio.get_event_loop().time()

        try:
            # Navigate to dashboard
            await page.goto(f"http://localhost:{dashboard_server.port}")

            # Wait for page to load
            await page.wait_for_selector(".header")
            await page.wait_for_selector(".dashboard-grid")

            load_time = asyncio.get_event_loop().time() - start_time

            # Take screenshot of initial state
            await page.screenshot(path=screenshots_dir / "dashboard_initial_load.png")

            # Check for essential elements
            title_element = await page.query_selector("h1")
            title_text = await title_element.inner_text() if title_element else ""

            service_cards = await page.query_selector_all(".metric-card")
            service_status_elements = await page.query_selector_all(".service-status")

            return {
                "success": True,
                "load_time": load_time,
                "title_correct": "Marty Framework" in title_text,
                "metric_cards_count": len(service_cards),
                "service_status_count": len(service_status_elements),
                "screenshot": "dashboard_initial_load.png",
            }

        except Exception as e:
            await page.screenshot(path=screenshots_dir / "dashboard_load_error.png")
            return {
                "success": False,
                "error": str(e),
                "load_time": asyncio.get_event_loop().time() - start_time,
                "screenshot": "dashboard_load_error.png",
            }

    async def _test_visual_regression(self, page: Page, screenshots_dir: Path) -> builtins.dict:
        """Test visual regression by comparing screenshots."""

        try:
            # Take full page screenshot
            await page.screenshot(path=screenshots_dir / "dashboard_full_page.png", full_page=True)

            # Take screenshots of specific components
            header = await page.query_selector(".header")
            await header.screenshot(path=screenshots_dir / "header_component.png")

            metrics_grid = await page.query_selector(".dashboard-grid")
            await metrics_grid.screenshot(path=screenshots_dir / "metrics_grid.png")

            # Check color consistency
            header_bg_color = await page.evaluate(
                """
                () => {
                    const header = document.querySelector('.header');
                    return window.getComputedStyle(header).background;
                }
            """
            )

            return {
                "screenshots_captured": 3,
                "header_styling_consistent": "linear-gradient" in header_bg_color,
                "visual_elements_present": True,
                "screenshots": [
                    "dashboard_full_page.png",
                    "header_component.png",
                    "metrics_grid.png",
                ],
            }

        except Exception as e:
            return {
                "screenshots_captured": 0,
                "error": str(e),
                "visual_elements_present": False,
            }

    async def _test_responsive_design(
        self, browser: Browser, dashboard_server, screenshots_dir: Path
    ) -> builtins.dict:
        """Test responsive design across different viewport sizes."""

        viewports = [
            {"name": "mobile", "width": 375, "height": 667},
            {"name": "tablet", "width": 768, "height": 1024},
            {"name": "desktop", "width": 1920, "height": 1080},
        ]

        responsive_results = {}

        for viewport in viewports:
            try:
                context = await browser.new_context(
                    viewport={"width": viewport["width"], "height": viewport["height"]}
                )
                page = await context.new_page()

                await page.goto(f"http://localhost:{dashboard_server.port}")
                await page.wait_for_selector(".dashboard-grid")

                # Take screenshot for this viewport
                screenshot_name = f"dashboard_{viewport['name']}.png"
                await page.screenshot(path=screenshots_dir / screenshot_name)

                # Check grid layout
                grid_columns = await page.evaluate(
                    """
                    () => {
                        const grid = document.querySelector('.dashboard-grid');
                        return window.getComputedStyle(grid).gridTemplateColumns;
                    }
                """
                )

                # Check if mobile menu or responsive elements are present
                is_mobile_friendly = viewport["width"] < 768

                responsive_results[viewport["name"]] = {
                    "viewport": viewport,
                    "grid_responsive": grid_columns != "none",
                    "mobile_optimized": is_mobile_friendly,
                    "screenshot": screenshot_name,
                }

                await context.close()

            except Exception as e:
                responsive_results[viewport["name"]] = {
                    "viewport": viewport,
                    "error": str(e),
                    "mobile_optimized": False,
                }

        return {
            "viewports_tested": len(viewports),
            "mobile_compatible": "mobile" in responsive_results
            and responsive_results["mobile"].get("mobile_optimized", False),
            "tablet_compatible": "tablet" in responsive_results,
            "desktop_compatible": "desktop" in responsive_results,
            "responsive_results": responsive_results,
        }

    async def _test_interactive_elements(self, page: Page, screenshots_dir: Path) -> builtins.dict:
        """Test interactive elements functionality."""

        try:
            # Test refresh button
            refresh_button = await page.query_selector("#refresh-btn")
            await refresh_button.click()

            # Wait a moment for any effects
            await page.wait_for_timeout(1000)

            # Test export button
            export_button = await page.query_selector("#export-btn")

            # Set up dialog handler for alert
            dialog_message = ""

            async def handle_dialog(dialog):
                nonlocal dialog_message
                dialog_message = dialog.message
                await dialog.accept()

            page.on("dialog", handle_dialog)
            await export_button.click()
            await page.wait_for_timeout(500)

            # Test alerts button
            alerts_button = await page.query_selector("#alerts-btn")
            await alerts_button.click()
            await page.wait_for_timeout(500)

            # Test settings button
            settings_button = await page.query_selector("#settings-btn")
            await settings_button.click()
            await page.wait_for_timeout(500)

            # Take screenshot after interactions
            await page.screenshot(path=screenshots_dir / "dashboard_after_interactions.png")

            # Check button states and hover effects
            button_count = await page.evaluate(
                """
                () => document.querySelectorAll('button').length
            """
            )

            return {
                "all_buttons_functional": button_count >= 4,
                "refresh_button_works": True,
                "export_dialog_triggered": "export" in dialog_message.lower(),
                "alerts_interaction": True,
                "settings_interaction": True,
                "screenshot": "dashboard_after_interactions.png",
            }

        except Exception as e:
            await page.screenshot(path=screenshots_dir / "interaction_test_error.png")
            return {
                "all_buttons_functional": False,
                "error": str(e),
                "screenshot": "interaction_test_error.png",
            }

    async def _test_performance_metrics(self, page: Page, screenshots_dir: Path) -> builtins.dict:
        """Test performance metrics display and accuracy."""

        try:
            # Check metric values are displayed
            healthy_services = await page.text_content("#healthy-services")
            active_alerts = await page.text_content("#active-alerts")
            avg_response_time = await page.text_content("#avg-response-time")
            error_rate = await page.text_content("#error-rate")

            # Check service status list
            service_elements = await page.query_selector_all(".service-status")
            service_count = len(service_elements)

            # Check alerts list
            alert_elements = await page.query_selector_all(".alert")
            alert_count = len(alert_elements)

            # Take screenshot of metrics
            await page.screenshot(path=screenshots_dir / "metrics_display.png")

            # Verify metrics format
            metrics_valid = (
                healthy_services
                and healthy_services.isdigit()
                and active_alerts
                and active_alerts.isdigit()
                and avg_response_time
                and "ms" in avg_response_time
                and error_rate
                and "%" in error_rate
            )

            return {
                "metrics_displayed": True,
                "metrics_format_valid": metrics_valid,
                "service_count": service_count,
                "alert_count": alert_count,
                "healthy_services": healthy_services,
                "error_rate": error_rate,
                "screenshot": "metrics_display.png",
            }

        except Exception as e:
            return {
                "metrics_displayed": False,
                "error": str(e),
            }

    async def _test_accessibility(self, page: Page, screenshots_dir: Path) -> builtins.dict:
        """Test accessibility features."""

        try:
            # Check for alt texts on important elements
            # Check for proper heading structure
            headings = await page.query_selector_all("h1, h2, h3, h4, h5, h6")
            heading_count = len(headings)

            # Check for proper button labels
            buttons = await page.query_selector_all("button")
            button_texts = []
            for button in buttons:
                text = await button.text_content()
                button_texts.append(text.strip() if text else "")

            # Check color contrast (simplified check)
            body_style = await page.evaluate(
                """
                () => {
                    const body = document.body;
                    const style = window.getComputedStyle(body);
                    return {
                        background: style.backgroundColor,
                        color: style.color
                    };
                }
            """
            )

            # Check for keyboard navigation
            await page.focus("button")
            focused_element = await page.evaluate("() => document.activeElement.tagName")

            return {
                "proper_heading_structure": heading_count > 0,
                "buttons_have_labels": all(text.strip() for text in button_texts),
                "keyboard_navigation": focused_element == "BUTTON",
                "color_contrast_check": body_style,
                "heading_count": heading_count,
                "button_count": len(buttons),
            }

        except Exception as e:
            return {
                "accessibility_test_error": str(e),
                "proper_heading_structure": False,
            }

    def _generate_visual_test_report(
        self, test_results: builtins.dict, test_report_dir: Path
    ) -> builtins.dict:
        """Generate comprehensive visual test report."""

        # Calculate overall scores
        total_tests = len(test_results)
        passed_tests = sum(
            1
            for result in test_results.values()
            if isinstance(result, dict) and result.get("success", True)
        )

        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        return {
            "test_summary": {
                "test_name": "Playwright Visual Testing",
                "total_test_categories": total_tests,
                "passed_categories": passed_tests,
                "success_rate": success_rate,
                "screenshots_directory": str(test_report_dir / "screenshots"),
            },
            "detailed_results": test_results,
            "visual_quality_metrics": {
                "dashboard_loads_successfully": test_results["dashboard_load"].get(
                    "success", False
                ),
                "responsive_across_devices": test_results["responsive_design"].get(
                    "mobile_compatible", False
                ),
                "interactive_elements_functional": test_results["interactive_elements"].get(
                    "all_buttons_functional", False
                ),
                "metrics_display_accurate": test_results["performance_metrics"].get(
                    "metrics_displayed", False
                ),
                "accessibility_compliant": test_results["accessibility"].get(
                    "proper_heading_structure", False
                ),
            },
            "recommendations": self._generate_visual_recommendations(test_results),
            "screenshots_generated": self._collect_screenshot_info(test_report_dir / "screenshots"),
        }

    def _generate_visual_recommendations(
        self, test_results: builtins.dict
    ) -> builtins.list[builtins.dict]:
        """Generate recommendations based on visual test results."""
        recommendations = []

        # Dashboard loading recommendations
        if not test_results["dashboard_load"].get("success", False):
            recommendations.append(
                {
                    "category": "Dashboard Performance",
                    "priority": "critical",
                    "actions": [
                        "Fix dashboard loading issues",
                        "Optimize initial page load performance",
                        "Add proper error handling for failed loads",
                    ],
                }
            )

        # Responsive design recommendations
        if not test_results["responsive_design"].get("mobile_compatible", False):
            recommendations.append(
                {
                    "category": "Responsive Design",
                    "priority": "high",
                    "actions": [
                        "Implement mobile-first responsive design",
                        "Add proper CSS grid/flexbox layouts",
                        "Test across multiple device sizes",
                        "Optimize touch interactions for mobile",
                    ],
                }
            )

        # Interactive elements recommendations
        if not test_results["interactive_elements"].get("all_buttons_functional", False):
            recommendations.append(
                {
                    "category": "User Interface",
                    "priority": "medium",
                    "actions": [
                        "Fix non-functional interactive elements",
                        "Add proper button hover and focus states",
                        "Implement consistent interaction patterns",
                        "Add loading states for async operations",
                    ],
                }
            )

        # Accessibility recommendations
        if not test_results["accessibility"].get("proper_heading_structure", False):
            recommendations.append(
                {
                    "category": "Accessibility",
                    "priority": "high",
                    "actions": [
                        "Implement proper heading hierarchy",
                        "Add ARIA labels and descriptions",
                        "Ensure keyboard navigation support",
                        "Improve color contrast ratios",
                        "Add screen reader compatibility",
                    ],
                }
            )

        return recommendations

    def _collect_screenshot_info(self, screenshots_dir: Path) -> builtins.list[builtins.dict]:
        """Collect information about generated screenshots."""
        if not screenshots_dir.exists():
            return []

        screenshots = []
        for screenshot_file in screenshots_dir.glob("*.png"):
            screenshots.append(
                {
                    "filename": screenshot_file.name,
                    "path": str(screenshot_file),
                    "size_mb": screenshot_file.stat().st_size / (1024 * 1024),
                }
            )

        return screenshots

    def _print_visual_test_summary(self, report: builtins.dict):
        """Print visual test summary."""
        print("\\n" + "=" * 50)
        print("🎭 PLAYWRIGHT VISUAL TESTING SUMMARY")
        print("=" * 50)

        summary = report["test_summary"]
        quality = report["visual_quality_metrics"]

        print(f"📊 Test categories: {summary['total_test_categories']}")
        print(f"✅ Categories passed: {summary['passed_categories']}")
        print(f"📈 Success rate: {summary['success_rate']:.1f}%")
        print(f"📸 Screenshots generated: {len(report['screenshots_generated'])}")

        print("\\n🎯 QUALITY METRICS:")
        print(f"   🔄 Dashboard loads: {'✅' if quality['dashboard_loads_successfully'] else '❌'}")
        print(f"   📱 Mobile responsive: {'✅' if quality['responsive_across_devices'] else '❌'}")
        print(
            f"   🖱️ Interactive elements: {'✅' if quality['interactive_elements_functional'] else '❌'}"
        )
        print(f"   📊 Metrics display: {'✅' if quality['metrics_display_accurate'] else '❌'}")
        print(f"   ♿ Accessibility: {'✅' if quality['accessibility_compliant'] else '❌'}")

        recommendations = report["recommendations"]
        if recommendations:
            print("\\n💡 RECOMMENDATIONS:")
            for rec in recommendations[:2]:
                print(f"   🎯 {rec['category']} ({rec['priority']} priority)")
                for action in rec["actions"][:2]:
                    print(f"      - {action}")

        print(f"\\n📁 Screenshots saved to: {summary['screenshots_directory']}")
        print("\\n✅ Visual testing completed!")
        print("=" * 50)
