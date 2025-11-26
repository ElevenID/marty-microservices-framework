"""
Comprehensive examples for the Enhanced Monitoring and Observability Framework.

This module demonstrates various usage patterns and best practices
for implementing advanced monitoring in microservices.
"""

import asyncio
import builtins
import logging
from typing import Any

import aioredis

# FastAPI example
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mmf_new.framework.observability.monitoring import (
    AlertLevel,
    AlertRule,
    BusinessMetric,
    DatabaseHealthCheck,
    ExternalServiceHealthCheck,
    MetricAggregation,
    MonitoringMiddlewareConfig,
    initialize_custom_metrics,
    initialize_monitoring,
    record_error_rate,
    record_response_time_sla,
    record_revenue,
    record_transaction_result,
    record_user_registration,
    setup_fastapi_monitoring,
)
from mmf_new.framework.observability.monitoring.core import (
    HealthCheck,
    HealthCheckResult,
    HealthStatus,
)

# Database example
try:
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False


# Redis example

# Framework imports

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Example 1: Basic Monitoring Setup
async def basic_monitoring_example():
    """Demonstrate basic monitoring setup and usage."""

    print("\n=== Basic Monitoring Example ===")

    # Initialize monitoring with Prometheus
    monitoring_manager = initialize_monitoring(
        service_name="example-service",
        use_prometheus=True,
        jaeger_endpoint="http://localhost:14268/api/traces",
    )

    # Add basic health checks
    if SQLALCHEMY_AVAILABLE:
        engine = create_engine("sqlite:///examples/monitoring.db")
        SessionLocal = sessionmaker(bind=engine)

        monitoring_manager.add_health_check(DatabaseHealthCheck("database", SessionLocal))

    # Add external service health check
    monitoring_manager.add_health_check(
        ExternalServiceHealthCheck("external_api", "https://httpbin.org/status/200")
    )

    # Record some sample metrics
    await monitoring_manager.record_request("GET", "/api/users", 200, 0.150)
    await monitoring_manager.record_request("POST", "/api/users", 201, 0.250)
    await monitoring_manager.record_request("GET", "/api/users/123", 404, 0.050)
    await monitoring_manager.record_error("ValidationError")
    await monitoring_manager.set_active_connections(15)

    # Perform health checks
    health_status = await monitoring_manager.get_service_health()
    print(f"Service Health: {health_status['status']}")
    print(f"Health Checks: {len(health_status['checks'])}")

    # Get metrics (if Prometheus is available)
    metrics_text = monitoring_manager.get_metrics_text()
    if metrics_text:
        newline_char = "\n"
        print(f"Metrics collected: {len(metrics_text.split(newline_char))} lines")

    print("Basic monitoring example completed")


# Example 2: Custom Business Metrics
async def business_metrics_example():
    """Demonstrate custom business metrics and SLA monitoring."""

    print("\n=== Business Metrics Example ===")

    # Initialize custom metrics manager
    custom_metrics = initialize_custom_metrics()

    # Register custom business metrics
    custom_metrics.business_metrics.register_metric(
        BusinessMetric(
            name="order_processing_time",
            description="Time to process orders",
            unit="seconds",
            labels=["order_type", "priority"],
            sla_target=30.0,
            sla_operator="<=",
        )
    )

    custom_metrics.business_metrics.register_metric(
        BusinessMetric(
            name="customer_satisfaction",
            description="Customer satisfaction score",
            unit="score",
            sla_target=4.5,
            sla_operator=">=",
        )
    )

    # Add custom alert rules
    custom_metrics.add_alert_rule(
        AlertRule(
            name="slow_order_processing",
            metric_name="order_processing_time",
            condition=">",
            threshold=45.0,
            level=AlertLevel.WARNING,
            description="Order processing is slower than expected",
            aggregation=MetricAggregation.AVERAGE,
        )
    )

    # Add alert subscriber
    def alert_handler(alert):
        print(f"🚨 ALERT: {alert.message} (Level: {alert.level.value})")

    custom_metrics.add_alert_subscriber(alert_handler)

    # Start monitoring
    await custom_metrics.start_monitoring()

    # Simulate business metrics
    print("Recording business metrics...")

    # Record order processing times
    for i in range(10):
        processing_time = 25.0 + (i * 3)  # Gradually increasing processing time
        custom_metrics.record_business_metric(
            "order_processing_time",
            processing_time,
            {"order_type": "standard", "priority": "normal"},
        )

        # Record customer satisfaction
        satisfaction = 4.8 - (i * 0.1)  # Gradually decreasing satisfaction
        custom_metrics.record_business_metric("customer_satisfaction", satisfaction)

        await asyncio.sleep(0.1)  # Small delay between recordings

    # Wait for alert evaluation
    await asyncio.sleep(2)

    # Get metrics summary
    summary = custom_metrics.get_metrics_summary()
    print(f"Business Metrics: {list(summary['business_metrics'].keys())}")
    print(f"SLA Status: {len(summary['sla_status'])} metrics monitored")
    print(f"Active Alerts: {len(summary['active_alerts'])}")

    # Stop monitoring
    await custom_metrics.stop_monitoring()

    print("Business metrics example completed")


# Example 3: FastAPI Integration
def create_fastapi_monitoring_example():
    """Create FastAPI application with comprehensive monitoring."""

    print("\n=== FastAPI Monitoring Integration Example ===")

    app = FastAPI(title="Monitoring Example API")

    # Initialize monitoring
    monitoring_manager = initialize_monitoring(service_name="fastapi-example", use_prometheus=True)

    # Initialize custom metrics
    custom_metrics = initialize_custom_metrics()

    # Configure monitoring middleware
    config = MonitoringMiddlewareConfig()
    config.collect_request_metrics = True
    config.collect_response_metrics = True
    config.collect_error_metrics = True
    config.slow_request_threshold_seconds = 0.5
    config.enable_tracing = True

    # Setup monitoring middleware
    setup_fastapi_monitoring(app, config)

    @app.on_event("startup")
    async def startup():
        # Add health checks
        monitoring_manager.add_health_check(
            ExternalServiceHealthCheck("external_service", "https://httpbin.org/status/200")
        )

        # Start custom metrics monitoring
        await custom_metrics.start_monitoring()

        print("FastAPI monitoring initialized")

    @app.on_event("shutdown")
    async def shutdown():
        await custom_metrics.stop_monitoring()
        print("FastAPI monitoring shutdown")

    @app.get("/api/users/{user_id}")
    async def get_user(user_id: str):
        # Simulate processing time
        processing_time = 0.1 if user_id != "slow" else 1.5
        await asyncio.sleep(processing_time)

        # Record business metrics
        await record_response_time_sla(processing_time * 1000, 1000)  # Convert to ms

        if user_id == "error":
            await record_error_rate(True)
            raise HTTPException(status_code=500, detail="Simulated error")

        await record_error_rate(False)
        return {"id": user_id, "name": f"User {user_id}"}

    @app.post("/api/users")
    async def create_user(user_data: builtins.dict[str, Any]):
        # Simulate user registration
        await record_user_registration("api", "direct")

        # Simulate transaction
        success = user_data.get("email") != "invalid@example.com"
        await record_transaction_result(success)

        if not success:
            raise HTTPException(status_code=400, detail="Invalid user data")

        return {"id": "new_user", "status": "created"}

    @app.post("/api/orders")
    async def create_order(order_data: builtins.dict[str, Any]):
        # Simulate order processing
        processing_time = 20.0 + (len(order_data.get("items", [])) * 5)

        # Record business metric
        custom_metrics = initialize_custom_metrics()
        custom_metrics.record_business_metric(
            "order_processing_time",
            processing_time,
            {
                "order_type": order_data.get("type", "standard"),
                "priority": "normal",
            },
        )

        # Simulate revenue
        amount = order_data.get("total", 100.0)
        await record_revenue(amount, "USD", "api")

        return {"id": "order_123", "status": "processing"}

    print("FastAPI monitoring example application created")
    print("Available endpoints:")
    print("  GET /health - Health check")
    print("  GET /health/detailed - Detailed health check")
    print("  GET /metrics - Prometheus metrics")
    print("  GET /api/users/{user_id} - Get user (try 'slow' or 'error')")
    print("  POST /api/users - Create user")
    print("  POST /api/orders - Create order")

    return app


# Create the FastAPI app
app = create_fastapi_monitoring_example()


# Example 4: Advanced Health Checks
async def advanced_health_checks_example():
    """Demonstrate advanced health check patterns."""

    print("\n=== Advanced Health Checks Example ===")

    monitoring_manager = initialize_monitoring("health-check-example")

    # Import the base health check class

    # Custom health check class
    class CustomServiceHealthCheck(HealthCheck):
        def __init__(self, name: str):
            super().__init__(name)
            self.call_count = 0

        async def check(self) -> HealthCheckResult:
            self.call_count += 1

            # Simulate varying health status
            if self.call_count % 5 == 0:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Periodic failure simulation",
                    details={"call_count": self.call_count},
                )
            if self.call_count % 3 == 0:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message="Performance degradation detected",
                    details={"call_count": self.call_count},
                )
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Service operating normally",
                details={"call_count": self.call_count},
            )

    # Add various health checks
    monitoring_manager.add_health_check(CustomServiceHealthCheck("custom_service"))
    monitoring_manager.add_health_check(
        ExternalServiceHealthCheck("httpbin", "https://httpbin.org/delay/1")
    )

    # Perform health checks multiple times
    for i in range(8):
        health_status = await monitoring_manager.get_service_health()
        print(f"Health Check {i + 1}: {health_status['status']}")

        for check_name, check_result in health_status["checks"].items():
            print(f"  {check_name}: {check_result['status']} - {check_result['message']}")

        await asyncio.sleep(1)

    print("Advanced health checks example completed")


# Example 5: Performance Monitoring
async def performance_monitoring_example():
    """Demonstrate performance monitoring and metrics collection."""

    print("\n=== Performance Monitoring Example ===")

    monitoring_manager = initialize_monitoring("performance-example")
    custom_metrics = initialize_custom_metrics()

    # Add performance-focused alert rules
    custom_metrics.add_alert_rule(
        AlertRule(
            name="high_response_time",
            metric_name="response_time_sla",
            condition="<",
            threshold=90.0,
            level=AlertLevel.WARNING,
            description="Response time SLA below 90%",
        )
    )

    await custom_metrics.start_monitoring()

    # Simulate various performance scenarios
    scenarios = [
        {"name": "Fast responses", "response_times": [50, 75, 100, 80, 90]},
        {"name": "Mixed performance", "response_times": [200, 500, 800, 300, 1200]},
        {"name": "Slow responses", "response_times": [1500, 2000, 1800, 2200, 1900]},
    ]

    for scenario in scenarios:
        print(f"\nTesting scenario: {scenario['name']}")

        for response_time in scenario["response_times"]:
            # Record request metrics
            status_code = 200 if response_time < 2000 else 500
            await monitoring_manager.record_request(
                "GET", "/api/test", status_code, response_time / 1000
            )

            # Record SLA compliance
            await record_response_time_sla(response_time, 1000)

            # Record error if applicable
            await record_error_rate(status_code >= 500)

            await asyncio.sleep(0.1)

        # Wait for metrics aggregation
        await asyncio.sleep(2)

        # Check SLA status
        summary = custom_metrics.get_metrics_summary()
        sla_status = summary.get("sla_status", {}).get("response_time_sla")
        if sla_status:
            print(
                f"  SLA Status: {sla_status['current_value']:.1f}% (Target: {sla_status['sla_target']}%)"
            )
            print(f"  SLA Met: {sla_status['sla_met']}")

    await custom_metrics.stop_monitoring()
    print("Performance monitoring example completed")


# Example 6: Alerting and Notifications
async def alerting_example():
    """Demonstrate alerting and notification patterns."""

    print("\n=== Alerting and Notifications Example ===")

    custom_metrics = initialize_custom_metrics()

    # Alert notification handlers
    def email_alert_handler(alert):
        print(f"📧 EMAIL ALERT: {alert.message}")
        print(f"   Level: {alert.level.value}")
        print(f"   Time: {alert.timestamp}")

    def slack_alert_handler(alert):
        print(f"💬 SLACK ALERT: {alert.message}")
        print(f"   Metric: {alert.metric_value} vs threshold {alert.threshold}")

    def pagerduty_alert_handler(alert):
        if alert.level in [AlertLevel.CRITICAL]:
            print(f"📟 PAGERDUTY ALERT: {alert.message}")
            print("   On-call engineer notified!")

    # Subscribe to alerts
    custom_metrics.add_alert_subscriber(email_alert_handler)
    custom_metrics.add_alert_subscriber(slack_alert_handler)
    custom_metrics.add_alert_subscriber(pagerduty_alert_handler)

    # Add test alert rules
    custom_metrics.add_alert_rule(
        AlertRule(
            name="test_warning",
            metric_name="error_rate",
            condition=">",
            threshold=2.0,
            level=AlertLevel.WARNING,
            description="Test warning alert",
        )
    )

    custom_metrics.add_alert_rule(
        AlertRule(
            name="test_critical",
            metric_name="error_rate",
            condition=">",
            threshold=5.0,
            level=AlertLevel.CRITICAL,
            description="Test critical alert",
        )
    )

    await custom_metrics.start_monitoring()

    # Simulate increasing error rates
    error_rates = [1.0, 2.5, 4.0, 6.0, 3.0, 1.5, 0.5]

    for error_rate in error_rates:
        print(f"\nSimulating error rate: {error_rate}%")
        custom_metrics.record_business_metric("error_rate", error_rate)

        await asyncio.sleep(2)  # Wait for alert evaluation

        # Check active alerts
        summary = custom_metrics.get_metrics_summary()
        active_alerts = summary.get("active_alerts", [])
        print(f"Active alerts: {len(active_alerts)}")

    await custom_metrics.stop_monitoring()
    print("Alerting example completed")


# Main example runner
async def run_all_monitoring_examples():
    """Run all monitoring examples."""

    print("Starting Enhanced Monitoring Framework Examples")
    print("=" * 60)

    try:
        # Run basic examples
        await basic_monitoring_example()
        await business_metrics_example()
        await advanced_health_checks_example()
        await performance_monitoring_example()
        await alerting_example()

        print("\n" + "=" * 60)
        print("All monitoring examples completed successfully!")

        print("\nTo test FastAPI monitoring integration:")
        print("1. pip install 'fastapi[all]' prometheus_client aioredis")
        print("2. uvicorn framework.monitoring.examples:app --reload")
        print("3. Visit http://localhost:8000/docs")
        print("4. Check metrics at http://localhost:8000/metrics")
        print("5. Check health at http://localhost:8000/health")

        print("\nMonitoring Features Demonstrated:")
        print("✅ Prometheus metrics collection")
        print("✅ Custom business metrics")
        print("✅ Health check framework")
        print("✅ SLA monitoring")
        print("✅ Alert management")
        print("✅ Performance monitoring")
        print("✅ FastAPI middleware integration")

    except Exception as e:
        print(f"Error running monitoring examples: {e}")
        logger.exception("Example execution failed")


if __name__ == "__main__":
    # Run examples
    asyncio.run(run_all_monitoring_examples())
