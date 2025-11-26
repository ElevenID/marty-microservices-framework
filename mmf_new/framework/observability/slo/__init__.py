"""
Service Level Objective (SLO) and Service Level Indicator (SLI) Tracking System
for Marty Microservices Framework

Provides comprehensive SLO/SLI management including:
- SLI measurement and collection
- SLO definition and tracking
- Error budget calculation and monitoring
- Burn rate analysis and alerting
- Dashboard integration and reporting
- Automated S        # Metrics
        self.registry = CollectorRegistry()
        self.slo_compliance_gauge = Gauge(
            "marty_slo_compliance",
            "SLO compliance percentage",
            ["slo_name", "service"],
            registry=self.registry,
        )ance assessment
"""

import asyncio
import builtins
import importlib.util
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

# Required external dependencies
import aiohttp
from prometheus_client import CollectorRegistry, Counter, Gauge


class SLIType(Enum):
    """Types of Service Level Indicators"""

    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    CORRECTNESS = "correctness"
    FRESHNESS = "freshness"
    COVERAGE = "coverage"


class SLOPriority(Enum):
    """SLO priority levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class SLISpecification:
    """Service Level Indicator specification"""

    name: str
    sli_type: SLIType
    description: str
    query: str  # Prometheus query or calculation method
    unit: str = ""
    good_threshold: float | None = None  # For binary SLIs
    target_threshold: float | None = None  # For latency SLIs
    window: str = "5m"  # Time window for calculation

    def to_dict(self) -> builtins.dict[str, Any]:
        return asdict(self)


@dataclass
class SLOTarget:
    """Service Level Objective target"""

    target: float  # Target percentage (e.g., 99.9)
    window: str  # Time window (e.g., "30d", "7d", "1h")
    priority: SLOPriority = SLOPriority.MEDIUM

    def to_dict(self) -> builtins.dict[str, Any]:
        return asdict(self)


@dataclass
class SLODefinition:
    """Complete SLO definition"""

    name: str
    service_name: str
    sli: SLISpecification
    target: SLOTarget
    description: str = ""
    tags: builtins.dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> builtins.dict[str, Any]:
        return asdict(self)


@dataclass
class SLIMeasurement:
    """SLI measurement data point"""

    timestamp: datetime
    value: float
    good_events: int | None = None
    total_events: int | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "good_events": self.good_events,
            "total_events": self.total_events,
        }


@dataclass
class ErrorBudget:
    """Error budget calculation and tracking"""

    slo_name: str
    target_percentage: float
    window_duration: str
    budget_remaining: float
    budget_consumed: float
    total_budget: float
    last_updated: datetime
    burn_rate: float = 0.0
    projected_exhaustion: datetime | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            "slo_name": self.slo_name,
            "target_percentage": self.target_percentage,
            "window_duration": self.window_duration,
            "budget_remaining": self.budget_remaining,
            "budget_consumed": self.budget_consumed,
            "total_budget": self.total_budget,
            "last_updated": self.last_updated.isoformat(),
            "burn_rate": self.burn_rate,
            "projected_exhaustion": self.projected_exhaustion.isoformat()
            if self.projected_exhaustion
            else None,
        }


@dataclass
class SLOAlert:
    """SLO alert configuration and tracking"""

    name: str
    slo_name: str
    alert_type: str  # "burn_rate", "budget_exhaustion", "target_breach"
    threshold: float
    window: str
    severity: str
    enabled: bool = True
    last_triggered: datetime | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return asdict(self)


class SLICollector:
    """
    Service Level Indicator collector

    Collects SLI measurements from various sources:
    - Prometheus metrics
    - Application logs
    - HTTP probes
    - Custom measurements
    """

    def __init__(
        self,
        prometheus_url: str = "http://localhost:9090",
        redis_host: str = "localhost",
        redis_port: int = 6379,
    ):
        self.prometheus_url = prometheus_url
        self.redis_host = redis_host
        self.redis_port = redis_port

        # SLI measurement cache
        self.measurements: builtins.dict[str, builtins.list[SLIMeasurement]] = {}

        # Metrics for tracking SLI collection
        self.registry = CollectorRegistry()
        self.sli_collection_counter = Counter(
            "marty_sli_collections_total",
            "Total SLI collections",
            ["slo_name", "sli_type"],
            registry=self.registry,
        )
        self.sli_value_gauge = Gauge(
            "marty_sli_current_value",
            "Current SLI value",
            ["slo_name", "sli_type"],
            registry=self.registry,
        )

    async def collect_sli(self, slo: SLODefinition) -> SLIMeasurement | None:
        """Collect SLI measurement for a given SLO"""
        try:
            measurement = None

            if slo.sli.sli_type == SLIType.AVAILABILITY:
                measurement = await self._collect_availability_sli(slo)
            elif slo.sli.sli_type == SLIType.LATENCY:
                measurement = await self._collect_latency_sli(slo)
            elif slo.sli.sli_type == SLIType.ERROR_RATE:
                measurement = await self._collect_error_rate_sli(slo)
            elif slo.sli.sli_type == SLIType.THROUGHPUT:
                measurement = await self._collect_throughput_sli(slo)
            else:
                measurement = await self._collect_custom_sli(slo)

            if measurement:
                # Store measurement
                if slo.name not in self.measurements:
                    self.measurements[slo.name] = []
                self.measurements[slo.name].append(measurement)

                # Keep only recent measurements (last 1000)
                if len(self.measurements[slo.name]) > 1000:
                    self.measurements[slo.name] = self.measurements[slo.name][-1000:]

                # Update metrics
                self.sli_collection_counter.labels(
                    slo_name=slo.name, sli_type=slo.sli.sli_type.value
                ).inc()

                self.sli_value_gauge.labels(slo_name=slo.name, sli_type=slo.sli.sli_type.value).set(
                    measurement.value
                )

            return measurement

        except Exception as e:
            print(f"Error collecting SLI for {slo.name}: {e}")
            return None

    async def _collect_availability_sli(self, slo: SLODefinition) -> SLIMeasurement | None:
        """Collect availability SLI"""
        # Example: Calculate uptime from successful vs failed requests
        query = (
            slo.sli.query
            or f"""
        sum(rate(http_requests_total{{service="{slo.service_name}",code!~"5.."}}[{slo.sli.window}])) /
        sum(rate(http_requests_total{{service="{slo.service_name}"}}[{slo.sli.window}]))
        """
        )

        result = await self._query_prometheus(query)
        if result and len(result) > 0:
            value = float(result[0]["value"][1]) * 100  # Convert to percentage
            return SLIMeasurement(timestamp=datetime.now(), value=value)
        return None

    async def _collect_latency_sli(self, slo: SLODefinition) -> SLIMeasurement | None:
        """Collect latency SLI"""
        # Example: Calculate percentage of requests under threshold
        threshold = slo.sli.target_threshold or 500  # 500ms default

        query = (
            slo.sli.query
            or f"""
        histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket{{service="{slo.service_name}"}}[{slo.sli.window}])) by (le)
        ) * 1000
        """
        )

        result = await self._query_prometheus(query)
        if result and len(result) > 0:
            p95_latency = float(result[0]["value"][1])
            # Calculate percentage of requests under threshold
            value = 100.0 if p95_latency <= threshold else 0.0
            return SLIMeasurement(timestamp=datetime.now(), value=value)
        return None

    async def _collect_error_rate_sli(self, slo: SLODefinition) -> SLIMeasurement | None:
        """Collect error rate SLI"""
        query = (
            slo.sli.query
            or f"""
        (
            sum(rate(http_requests_total{{service="{slo.service_name}",code=~"5.."}}[{slo.sli.window}])) /
            sum(rate(http_requests_total{{service="{slo.service_name}"}}[{slo.sli.window}]))
        ) * 100
        """
        )

        result = await self._query_prometheus(query)
        if result and len(result) > 0:
            error_rate = float(result[0]["value"][1])
            # Convert error rate to success rate (SLI)
            value = 100.0 - error_rate
            return SLIMeasurement(timestamp=datetime.now(), value=value)
        return None

    async def _collect_throughput_sli(self, slo: SLODefinition) -> SLIMeasurement | None:
        """Collect throughput SLI"""
        query = (
            slo.sli.query
            or f"""
        sum(rate(http_requests_total{{service="{slo.service_name}"}}[{slo.sli.window}]))
        """
        )

        result = await self._query_prometheus(query)
        if result and len(result) > 0:
            value = float(result[0]["value"][1])
            return SLIMeasurement(timestamp=datetime.now(), value=value)
        return None

    async def _collect_custom_sli(self, slo: SLODefinition) -> SLIMeasurement | None:
        """Collect custom SLI using provided query"""
        if not slo.sli.query:
            return None

        result = await self._query_prometheus(slo.sli.query)
        if result and len(result) > 0:
            value = float(result[0]["value"][1])
            return SLIMeasurement(timestamp=datetime.now(), value=value)
        return None

    async def _query_prometheus(self, query: str) -> builtins.list[builtins.dict[str, Any]] | None:
        """Query Prometheus and return results"""
        try:
            async with aiohttp.ClientSession() as session:
                params = {"query": query}
                async with session.get(
                    f"{self.prometheus_url}/api/v1/query", params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", {}).get("result", [])
        except Exception as e:
            print(f"Error querying Prometheus: {e}")

        return None


class SLOTracker:
    """
    Service Level Objective tracker

    Tracks SLO compliance, error budgets, and burn rates
    """

    def __init__(self, collector: SLICollector):
        self.collector = collector
        self.slos: builtins.dict[str, SLODefinition] = {}
        self.error_budgets: builtins.dict[str, ErrorBudget] = {}
        self.alerts: builtins.dict[str, builtins.list[SLOAlert]] = {}

        # Metrics
        self.registry = CollectorRegistry()
        self.slo_compliance_gauge = Gauge(
            "marty_slo_compliance_percentage",
            "SLO compliance percentage",
            ["slo_name", "service"],
            registry=self.registry,
        )
        self.error_budget_gauge = Gauge(
            "marty_slo_error_budget_remaining",
            "Error budget remaining",
            ["slo_name", "service"],
            registry=self.registry,
        )
        self.burn_rate_gauge = Gauge(
            "marty_slo_burn_rate",
            "Error budget burn rate",
            ["slo_name", "service"],
            registry=self.registry,
        )

    def register_slo(self, slo: SLODefinition):
        """Register a new SLO for tracking"""
        self.slos[slo.name] = slo

        # Initialize error budget
        self.error_budgets[slo.name] = ErrorBudget(
            slo_name=slo.name,
            target_percentage=slo.target.target,
            window_duration=slo.target.window,
            budget_remaining=100.0 - slo.target.target,
            budget_consumed=0.0,
            total_budget=100.0 - slo.target.target,
            last_updated=datetime.now(),
        )

        # Setup default alerts
        self.alerts[slo.name] = self._create_default_alerts(slo)

        print(f"Registered SLO: {slo.name} for service {slo.service_name}")

    def _create_default_alerts(self, slo: SLODefinition) -> builtins.list[SLOAlert]:
        """Create default alerts for an SLO"""
        alerts = []

        # Fast burn rate alert (2% budget consumed in 1 hour)
        alerts.append(
            SLOAlert(
                name=f"{slo.name}_fast_burn",
                slo_name=slo.name,
                alert_type="burn_rate",
                threshold=2.0,  # 2% per hour
                window="1h",
                severity="critical",
            )
        )

        # Slow burn rate alert (10% budget consumed in 6 hours)
        alerts.append(
            SLOAlert(
                name=f"{slo.name}_slow_burn",
                slo_name=slo.name,
                alert_type="burn_rate",
                threshold=10.0,  # 10% in 6 hours
                window="6h",
                severity="warning",
            )
        )

        # Budget exhaustion alert (90% budget consumed)
        alerts.append(
            SLOAlert(
                name=f"{slo.name}_budget_exhaustion",
                slo_name=slo.name,
                alert_type="budget_exhaustion",
                threshold=90.0,  # 90% consumed
                window="1h",
                severity="critical",
            )
        )

        return alerts

    async def track_slo(self, slo_name: str) -> builtins.dict[str, Any] | None:
        """Track a specific SLO"""
        if slo_name not in self.slos:
            return None

        slo = self.slos[slo_name]

        # Collect current SLI measurement
        measurement = await self.collector.collect_sli(slo)
        if not measurement:
            return None

        # Calculate compliance
        compliance = await self._calculate_compliance(slo_name, slo.target.window)

        # Update error budget
        await self._update_error_budget(slo_name, compliance)

        # Check alerts
        await self._check_alerts(slo_name)

        # Update metrics
        self.slo_compliance_gauge.labels(slo_name=slo_name, service=slo.service_name).set(
            compliance
        )

        budget = self.error_budgets[slo_name]
        self.error_budget_gauge.labels(slo_name=slo_name, service=slo.service_name).set(
            budget.budget_remaining
        )

        self.burn_rate_gauge.labels(slo_name=slo_name, service=slo.service_name).set(
            budget.burn_rate
        )

        return {
            "slo_name": slo_name,
            "service_name": slo.service_name,
            "current_measurement": measurement.to_dict(),
            "compliance": compliance,
            "error_budget": self.error_budgets[slo_name].to_dict(),
            "target": slo.target.target,
            "status": "healthy" if compliance >= slo.target.target else "at_risk",
        }

    async def _calculate_compliance(self, slo_name: str, window: str) -> float:
        """Calculate SLO compliance over time window"""
        if slo_name not in self.collector.measurements:
            return 0.0

        measurements = self.collector.measurements[slo_name]
        if not measurements:
            return 0.0

        # For now, use simple average of recent measurements
        # In production, this should consider the time window properly
        recent_measurements = measurements[-100:]  # Last 100 measurements
        if recent_measurements:
            return statistics.mean(m.value for m in recent_measurements)

        return 0.0

    async def _update_error_budget(self, slo_name: str, current_compliance: float):
        """Update error budget based on current compliance"""
        if slo_name not in self.error_budgets:
            return

        budget = self.error_budgets[slo_name]
        slo = self.slos[slo_name]

        # Calculate budget consumption
        target = slo.target.target
        if current_compliance < target:
            # We're below target, consuming error budget
            shortfall = target - current_compliance
            budget.budget_consumed = min(budget.total_budget, budget.budget_consumed + shortfall)
            budget.budget_remaining = budget.total_budget - budget.budget_consumed

        # Calculate burn rate (budget consumed per hour)
        time_diff = (datetime.now() - budget.last_updated).total_seconds() / 3600  # hours
        if time_diff > 0:
            consumption_rate = shortfall / time_diff if current_compliance < target else 0
            budget.burn_rate = consumption_rate

            # Project budget exhaustion
            if budget.burn_rate > 0:
                hours_to_exhaustion = budget.budget_remaining / budget.burn_rate
                budget.projected_exhaustion = datetime.now() + timedelta(hours=hours_to_exhaustion)
            else:
                budget.projected_exhaustion = None

        budget.last_updated = datetime.now()

    async def _check_alerts(self, slo_name: str):
        """Check and trigger SLO alerts"""
        if slo_name not in self.alerts:
            return

        budget = self.error_budgets[slo_name]
        current_time = datetime.now()

        for alert in self.alerts[slo_name]:
            if not alert.enabled:
                continue

            should_trigger = False

            if alert.alert_type == "burn_rate":
                # Check if burn rate exceeds threshold
                should_trigger = budget.burn_rate >= alert.threshold

            elif alert.alert_type == "budget_exhaustion":
                # Check if budget consumption exceeds threshold
                consumption_percentage = (budget.budget_consumed / budget.total_budget) * 100
                should_trigger = consumption_percentage >= alert.threshold

            elif alert.alert_type == "target_breach":
                # Check if current SLI is below target
                slo = self.slos[slo_name]
                current_compliance = await self._calculate_compliance(slo_name, "1h")
                should_trigger = current_compliance < slo.target.target

            # Trigger alert if conditions met and not in cooldown
            if should_trigger:
                cooldown_minutes = 60 if alert.severity == "critical" else 180
                if alert.last_triggered is None or current_time - alert.last_triggered >= timedelta(
                    minutes=cooldown_minutes
                ):
                    await self._trigger_alert(alert, budget)
                    alert.last_triggered = current_time

    async def _trigger_alert(self, alert: SLOAlert, budget: ErrorBudget):
        """Trigger an SLO alert"""
        alert_data = {
            "alert_name": alert.name,
            "slo_name": alert.slo_name,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "threshold": alert.threshold,
            "current_burn_rate": budget.burn_rate,
            "budget_remaining": budget.budget_remaining,
            "timestamp": datetime.now().isoformat(),
            "message": f"SLO Alert: {alert.name} - {alert.alert_type} threshold {alert.threshold} exceeded",
        }

        print(f"🚨 SLO ALERT: {alert_data['message']}")

        # Send alert to monitoring system
        # In production, integrate with PagerDuty, Slack, etc.

    def get_slo_status(self, slo_name: str) -> builtins.dict[str, Any] | None:
        """Get current status of an SLO"""
        if slo_name not in self.slos:
            return None

        slo = self.slos[slo_name]
        budget = self.error_budgets.get(slo_name)

        return {
            "slo": slo.to_dict(),
            "error_budget": budget.to_dict() if budget else None,
            "alerts": [alert.to_dict() for alert in self.alerts.get(slo_name, [])],
            "recent_measurements": [
                m.to_dict() for m in self.collector.measurements.get(slo_name, [])[-10:]
            ],
        }

    def list_slos(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """List all registered SLOs with their current status"""
        result = {}
        for name in self.slos.keys():
            status = self.get_slo_status(name)
            if status is not None:
                result[name] = status
        return result


class SLOManager:
    """
    Complete SLO management system

    Orchestrates SLI collection, SLO tracking, and reporting
    """

    def __init__(
        self,
        prometheus_url: str = "http://localhost:9090",
        redis_host: str = "localhost",
        redis_port: int = 6379,
        collection_interval: int = 60,  # seconds
    ):
        self.collector = SLICollector(prometheus_url, redis_host, redis_port)
        self.tracker = SLOTracker(self.collector)
        self.collection_interval = collection_interval
        self.running = False

    def register_default_slos(self, service_name: str):
        """Register default SLOs for a service"""

        # Availability SLO (99.9% uptime)
        availability_slo = SLODefinition(
            name=f"{service_name}_availability",
            service_name=service_name,
            sli=SLISpecification(
                name=f"{service_name}_uptime",
                sli_type=SLIType.AVAILABILITY,
                description="Service availability percentage",
                query="",  # Will use default
                unit="%",
            ),
            target=SLOTarget(target=99.9, window="30d", priority=SLOPriority.CRITICAL),
            description=f"99.9% availability for {service_name}",
            tags={"team": "platform", "criticality": "high"},
        )

        # Latency SLO (95% of requests under 500ms)
        latency_slo = SLODefinition(
            name=f"{service_name}_latency",
            service_name=service_name,
            sli=SLISpecification(
                name=f"{service_name}_p95_latency",
                sli_type=SLIType.LATENCY,
                description="95th percentile latency under 500ms",
                query="",  # Will use default
                target_threshold=500.0,
                unit="ms",
            ),
            target=SLOTarget(target=95.0, window="7d", priority=SLOPriority.HIGH),
            description=f"95% of requests under 500ms for {service_name}",
        )

        # Error rate SLO (99% success rate)
        error_rate_slo = SLODefinition(
            name=f"{service_name}_error_rate",
            service_name=service_name,
            sli=SLISpecification(
                name=f"{service_name}_success_rate",
                sli_type=SLIType.ERROR_RATE,
                description="Request success rate",
                query="",  # Will use default
                unit="%",
            ),
            target=SLOTarget(target=99.0, window="7d", priority=SLOPriority.HIGH),
            description=f"99% success rate for {service_name}",
        )

        # Register all SLOs
        self.tracker.register_slo(availability_slo)
        self.tracker.register_slo(latency_slo)
        self.tracker.register_slo(error_rate_slo)

        print(f"Registered default SLOs for {service_name}")

    async def start_monitoring(self):
        """Start continuous SLO monitoring"""
        self.running = True
        print(f"Starting SLO monitoring (interval: {self.collection_interval}s)")

        while self.running:
            try:
                # Track all registered SLOs
                for slo_name in self.tracker.slos.keys():
                    result = await self.tracker.track_slo(slo_name)
                    if result:
                        status = result.get("status", "unknown")
                        compliance = result.get("compliance", 0)
                        print(f"SLO {slo_name}: {compliance:.2f}% compliance - {status}")

                # Wait for next collection
                await asyncio.sleep(self.collection_interval)

            except Exception as e:
                print(f"Error in SLO monitoring loop: {e}")
                await asyncio.sleep(5)  # Short retry delay

    def stop_monitoring(self):
        """Stop SLO monitoring"""
        self.running = False
        print("Stopped SLO monitoring")

    def generate_slo_report(self) -> builtins.dict[str, Any]:
        """Generate comprehensive SLO report"""
        slos = self.tracker.list_slos()

        report = {
            "timestamp": datetime.now().isoformat(),
            "total_slos": len(slos),
            "slos": slos,
            "summary": {"healthy": 0, "at_risk": 0, "critical": 0},
        }

        # Calculate summary statistics
        for _slo_name, slo_data in slos.items():
            if slo_data and slo_data.get("error_budget"):
                budget_remaining = slo_data["error_budget"]["budget_remaining"]
                if budget_remaining > 50:
                    report["summary"]["healthy"] += 1
                elif budget_remaining > 10:
                    report["summary"]["at_risk"] += 1
                else:
                    report["summary"]["critical"] += 1

        return report


# Example usage
async def main():
    """Example usage of SLO management system"""

    # Create SLO manager
    manager = SLOManager(collection_interval=30)  # 30 second intervals for demo

    # Register SLOs for example services
    services = ["user-service", "payment-service", "order-service"]
    for service in services:
        manager.register_default_slos(service)

    # Start monitoring in background
    monitoring_task = asyncio.create_task(manager.start_monitoring())

    # Run for a while and generate reports
    try:
        await asyncio.sleep(90)  # Run for 90 seconds

        # Generate and display report
        report = manager.generate_slo_report()
        print("\n=== SLO REPORT ===")
        print(f"Timestamp: {report['timestamp']}")
        print(f"Total SLOs: {report['total_slos']}")
        print(f"Summary: {report['summary']}")

        for slo_name, slo_data in report["slos"].items():
            if slo_data and slo_data.get("error_budget"):
                budget = slo_data["error_budget"]
                print(f"\n{slo_name}:")
                print(f"  Budget Remaining: {budget['budget_remaining']:.2f}%")
                print(f"  Burn Rate: {budget['burn_rate']:.2f}%/hour")

    finally:
        manager.stop_monitoring()
        monitoring_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
