"""
Custom metrics collection and alerting framework.

This module provides advanced metrics collection capabilities including
custom business metrics, SLA monitoring, and alert management.
"""

import asyncio
import builtins
import logging
import statistics
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from mmf_new.framework.infrastructure.dependency_injection import (
    get_service_optional,
    register_instance,
)

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class MetricAggregation(Enum):
    """Types of metric aggregation."""

    SUM = "sum"
    AVERAGE = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    PERCENTILE_95 = "p95"
    PERCENTILE_99 = "p99"


@dataclass
class AlertRule:
    """Definition of an alert rule."""

    name: str
    metric_name: str
    condition: str  # e.g., "> 100", "< 0.95", "== 0"
    threshold: float
    level: AlertLevel
    description: str
    aggregation: MetricAggregation = MetricAggregation.AVERAGE
    window_minutes: int = 5
    evaluation_interval_seconds: int = 60
    enabled: bool = True


@dataclass
class Alert:
    """An active alert."""

    rule_name: str
    level: AlertLevel
    message: str
    metric_value: float
    threshold: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: builtins.dict[str, str] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: datetime | None = None


@dataclass
class BusinessMetric:
    """Business-specific metric definition."""

    name: str
    description: str
    unit: str
    labels: builtins.list[str] = field(default_factory=list)
    sla_target: float | None = None
    sla_operator: str = ">="  # ">=", "<=", "==", "!=", ">", "<"


class MetricBuffer:
    """Time-windowed buffer for metric values."""

    def __init__(self, window_minutes: int = 5, max_points: int = 1000):
        self.window_minutes = window_minutes
        self.max_points = max_points
        self.values: deque = deque(maxlen=max_points)
        self._lock = threading.Lock()

    def add_value(self, value: float, timestamp: datetime | None = None):
        """Add a value to the buffer."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        with self._lock:
            self.values.append((timestamp, value))
            self._cleanup_old_values()

    def _cleanup_old_values(self):
        """Remove values outside the time window."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=self.window_minutes)

        while self.values and self.values[0][0] < cutoff_time:
            self.values.popleft()

    def get_values(self) -> builtins.list[float]:
        """Get current values in the window."""
        with self._lock:
            self._cleanup_old_values()
            return [value for _, value in self.values]

    def aggregate(self, aggregation: MetricAggregation) -> float | None:
        """Aggregate values according to the specified method."""
        values = self.get_values()
        if not values:
            return None

        if aggregation == MetricAggregation.SUM:
            return sum(values)
        if aggregation == MetricAggregation.AVERAGE:
            return statistics.mean(values)
        if aggregation == MetricAggregation.MIN:
            return min(values)
        if aggregation == MetricAggregation.MAX:
            return max(values)
        if aggregation == MetricAggregation.COUNT:
            return float(len(values))
        if aggregation == MetricAggregation.PERCENTILE_95:
            return statistics.quantiles(values, n=20)[18] if len(values) >= 20 else max(values)
        if aggregation == MetricAggregation.PERCENTILE_99:
            return statistics.quantiles(values, n=100)[98] if len(values) >= 100 else max(values)

        return None


class AlertManager:
    """Manages alert rules and active alerts."""

    def __init__(self):
        self.rules: builtins.dict[str, AlertRule] = {}
        self.active_alerts: builtins.dict[str, Alert] = {}
        self.alert_history: builtins.list[Alert] = []
        self.subscribers: builtins.list[Callable[[Alert], None]] = []
        self._lock = threading.Lock()
        logger.info("Alert manager initialized")

    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        with self._lock:
            self.rules[rule.name] = rule
            logger.info(f"Added alert rule: {rule.name}")

    def remove_rule(self, rule_name: str):
        """Remove an alert rule."""
        with self._lock:
            if rule_name in self.rules:
                del self.rules[rule_name]
                logger.info(f"Removed alert rule: {rule_name}")

    def subscribe(self, callback: Callable[[Alert], None]):
        """Subscribe to alert notifications."""
        self.subscribers.append(callback)
        logger.info("Added alert subscriber")

    def evaluate_rule(self, rule: AlertRule, metric_value: float) -> Alert | None:
        """Evaluate an alert rule against a metric value."""
        if not rule.enabled:
            return None

        # Parse condition
        condition_met = False
        if rule.condition.startswith(">="):
            condition_met = metric_value >= rule.threshold
        elif rule.condition.startswith("<="):
            condition_met = metric_value <= rule.threshold
        elif rule.condition.startswith(">"):
            condition_met = metric_value > rule.threshold
        elif rule.condition.startswith("<"):
            condition_met = metric_value < rule.threshold
        elif rule.condition.startswith("=="):
            condition_met = abs(metric_value - rule.threshold) < 0.0001
        elif rule.condition.startswith("!="):
            condition_met = abs(metric_value - rule.threshold) >= 0.0001

        if condition_met:
            # Create alert if not already active
            if rule.name not in self.active_alerts:
                alert = Alert(
                    rule_name=rule.name,
                    level=rule.level,
                    message=f"{rule.description}: {metric_value} {rule.condition}",
                    metric_value=metric_value,
                    threshold=rule.threshold,
                )

                with self._lock:
                    self.active_alerts[rule.name] = alert
                    self.alert_history.append(alert)

                # Notify subscribers
                for subscriber in self.subscribers:
                    try:
                        subscriber(alert)
                    except Exception as e:
                        logger.error(f"Error notifying alert subscriber: {e}")

                logger.warning(f"Alert triggered: {alert.message}")
                return alert
        # Resolve alert if active
        elif rule.name in self.active_alerts:
            alert = self.active_alerts[rule.name]
            alert.resolved = True
            alert.resolved_at = datetime.now(timezone.utc)

            with self._lock:
                del self.active_alerts[rule.name]

            logger.info(f"Alert resolved: {rule.name}")

        return None

    def get_active_alerts(self) -> builtins.list[Alert]:
        """Get all active alerts."""
        with self._lock:
            return list(self.active_alerts.values())

    def get_alert_history(self, hours: int = 24) -> builtins.list[Alert]:
        """Get alert history for the specified time period."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [alert for alert in self.alert_history if alert.timestamp >= cutoff_time]


class BusinessMetricsCollector:
    """Collector for business-specific metrics."""

    def __init__(self):
        self.metrics: builtins.dict[str, BusinessMetric] = {}
        self.metric_buffers: builtins.dict[str, MetricBuffer] = {}
        self.alert_manager = AlertManager()
        self._lock = threading.Lock()
        logger.info("Business metrics collector initialized")

    def register_metric(self, metric: BusinessMetric):
        """Register a business metric."""
        with self._lock:
            self.metrics[metric.name] = metric
            self.metric_buffers[metric.name] = MetricBuffer()
            logger.info(f"Registered business metric: {metric.name}")

    def record_value(
        self,
        metric_name: str,
        value: float,
        labels: builtins.dict[str, str] | None = None,
    ):
        """Record a value for a business metric."""
        if metric_name not in self.metrics:
            logger.warning(f"Unknown business metric: {metric_name}")
            return

        # Create composite key with labels
        key = metric_name
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            key = f"{metric_name}#{label_str}"

        # Ensure buffer exists for this key
        if key not in self.metric_buffers:
            with self._lock:
                self.metric_buffers[key] = MetricBuffer()

        # Record value
        self.metric_buffers[key].add_value(value)
        logger.debug(f"Recorded value {value} for metric {key}")

    def get_metric_value(
        self,
        metric_name: str,
        aggregation: MetricAggregation = MetricAggregation.AVERAGE,
        labels: builtins.dict[str, str] | None = None,
    ) -> float | None:
        """Get aggregated value for a metric."""
        key = metric_name
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            key = f"{metric_name}#{label_str}"

        if key not in self.metric_buffers:
            return None

        return self.metric_buffers[key].aggregate(aggregation)

    def evaluate_sla(
        self, metric_name: str, labels: builtins.dict[str, str] | None = None
    ) -> builtins.dict[str, Any] | None:
        """Evaluate SLA for a metric."""
        if metric_name not in self.metrics:
            return None

        metric = self.metrics[metric_name]
        if metric.sla_target is None:
            return None

        current_value = self.get_metric_value(metric_name, labels=labels)
        if current_value is None:
            return None

        # Evaluate SLA condition
        sla_met = False
        if metric.sla_operator == ">=":
            sla_met = current_value >= metric.sla_target
        elif metric.sla_operator == "<=":
            sla_met = current_value <= metric.sla_target
        elif metric.sla_operator == ">":
            sla_met = current_value > metric.sla_target
        elif metric.sla_operator == "<":
            sla_met = current_value < metric.sla_target
        elif metric.sla_operator == "==":
            sla_met = abs(current_value - metric.sla_target) < 0.0001
        elif metric.sla_operator == "!=":
            sla_met = abs(current_value - metric.sla_target) >= 0.0001

        return {
            "metric_name": metric_name,
            "current_value": current_value,
            "sla_target": metric.sla_target,
            "operator": metric.sla_operator,
            "sla_met": sla_met,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_all_sla_status(self) -> builtins.dict[str, Any]:
        """Get SLA status for all metrics with SLA targets."""
        sla_results = {}

        for metric_name, metric in self.metrics.items():
            if metric.sla_target is not None:
                sla_result = self.evaluate_sla(metric_name)
                if sla_result:
                    sla_results[metric_name] = sla_result

        return sla_results


class CustomMetricsManager:
    """Manager for custom metrics, alerts, and SLA monitoring."""

    def __init__(self):
        self.business_metrics = BusinessMetricsCollector()
        self.alert_manager = AlertManager()
        self._background_task: asyncio.Task | None = None
        self._shutdown = False

        # Default business metrics
        self._register_default_business_metrics()

        # Default alert rules
        self._register_default_alert_rules()

        logger.info("Custom metrics manager initialized")

    def _register_default_business_metrics(self):
        """Register default business metrics."""
        default_metrics = [
            BusinessMetric(
                name="user_registrations",
                description="Number of user registrations",
                unit="count",
                labels=["source", "type"],
            ),
            BusinessMetric(
                name="transaction_success_rate",
                description="Success rate of transactions",
                unit="percentage",
                sla_target=99.0,
                sla_operator=">=",
            ),
            BusinessMetric(
                name="response_time_sla",
                description="Response time SLA compliance",
                unit="percentage",
                sla_target=95.0,
                sla_operator=">=",
            ),
            BusinessMetric(
                name="error_rate",
                description="Error rate percentage",
                unit="percentage",
                sla_target=1.0,
                sla_operator="<=",
            ),
            BusinessMetric(
                name="active_users",
                description="Number of active users",
                unit="count",
                labels=["period"],
            ),
            BusinessMetric(
                name="revenue",
                description="Revenue generated",
                unit="currency",
                labels=["currency", "source"],
            ),
        ]

        for metric in default_metrics:
            self.business_metrics.register_metric(metric)

    def _register_default_alert_rules(self):
        """Register default alert rules."""
        default_rules = [
            AlertRule(
                name="high_error_rate",
                metric_name="error_rate",
                condition=">",
                threshold=5.0,
                level=AlertLevel.WARNING,
                description="Error rate is above 5%",
            ),
            AlertRule(
                name="critical_error_rate",
                metric_name="error_rate",
                condition=">",
                threshold=10.0,
                level=AlertLevel.CRITICAL,
                description="Error rate is critically high (>10%)",
            ),
            AlertRule(
                name="low_transaction_success",
                metric_name="transaction_success_rate",
                condition="<",
                threshold=95.0,
                level=AlertLevel.WARNING,
                description="Transaction success rate below 95%",
            ),
            AlertRule(
                name="sla_violation",
                metric_name="response_time_sla",
                condition="<",
                threshold=90.0,
                level=AlertLevel.CRITICAL,
                description="Response time SLA compliance below 90%",
            ),
        ]

        for rule in default_rules:
            self.alert_manager.add_rule(rule)

    async def start_monitoring(self):
        """Start background monitoring task."""
        if self._background_task is None:
            self._background_task = asyncio.create_task(self._monitoring_loop())
            logger.info("Started custom metrics monitoring")

    async def stop_monitoring(self):
        """Stop background monitoring task."""
        self._shutdown = True
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped custom metrics monitoring")

    async def _monitoring_loop(self):
        """Background loop for evaluating alerts."""
        while not self._shutdown:
            try:
                # Evaluate all alert rules
                for rule in self.alert_manager.rules.values():
                    if not rule.enabled:
                        continue

                    # Get current metric value
                    metric_value = self.business_metrics.get_metric_value(
                        rule.metric_name, rule.aggregation
                    )

                    if metric_value is not None:
                        self.alert_manager.evaluate_rule(rule, metric_value)

                # Wait for next evaluation
                await asyncio.sleep(60)  # Evaluate every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)

    def record_business_metric(
        self,
        metric_name: str,
        value: float,
        labels: builtins.dict[str, str] | None = None,
    ):
        """Record a business metric value."""
        self.business_metrics.record_value(metric_name, value, labels)

    def add_alert_rule(self, rule: AlertRule):
        """Add a custom alert rule."""
        self.alert_manager.add_rule(rule)

    def add_alert_subscriber(self, callback: Callable[[Alert], None]):
        """Add alert notification subscriber."""
        self.alert_manager.subscribe(callback)

    def get_metrics_summary(self) -> builtins.dict[str, Any]:
        """Get summary of all custom metrics."""
        summary = {
            "business_metrics": {},
            "sla_status": self.business_metrics.get_all_sla_status(),
            "active_alerts": [
                {
                    "rule_name": alert.rule_name,
                    "level": alert.level.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                }
                for alert in self.alert_manager.get_active_alerts()
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Add current values for business metrics
        for metric_name in self.business_metrics.metrics:
            current_value = self.business_metrics.get_metric_value(metric_name)
            if current_value is not None:
                summary["business_metrics"][metric_name] = current_value

        return summary


def get_custom_metrics_manager() -> CustomMetricsManager | None:
    """
    Get the custom metrics manager using dependency injection.

    Returns:
        CustomMetricsManager instance or None if not registered
    """
    return get_service_optional(CustomMetricsManager)


def initialize_custom_metrics() -> CustomMetricsManager:
    """Initialize the custom metrics manager using dependency injection."""

    manager = get_service_optional(CustomMetricsManager)
    if manager is None:
        manager = CustomMetricsManager()
        register_instance(CustomMetricsManager, manager)
    return manager


# Convenience functions for common business metrics
async def record_user_registration(source: str = "web", registration_type: str = "email"):
    """Record a user registration event."""
    manager = get_custom_metrics_manager()
    if manager:
        manager.record_business_metric(
            "user_registrations", 1.0, {"source": source, "type": registration_type}
        )


async def record_transaction_result(success: bool):
    """Record a transaction result."""
    manager = get_custom_metrics_manager()
    if manager:
        # Calculate success rate (simplified - in real implementation would use proper windowing)
        success_value = 1.0 if success else 0.0
        manager.record_business_metric("transaction_success_rate", success_value * 100)


async def record_response_time_sla(response_time_ms: float, sla_threshold_ms: float = 1000):
    """Record response time SLA compliance."""
    manager = get_custom_metrics_manager()
    if manager:
        sla_met = response_time_ms <= sla_threshold_ms
        sla_value = 100.0 if sla_met else 0.0
        manager.record_business_metric("response_time_sla", sla_value)


async def record_error_rate(error_occurred: bool):
    """Record an error rate data point."""
    manager = get_custom_metrics_manager()
    if manager:
        error_value = 100.0 if error_occurred else 0.0
        manager.record_business_metric("error_rate", error_value)


async def record_revenue(amount: float, currency: str = "USD", source: str = "web"):
    """Record revenue."""
    manager = get_custom_metrics_manager()
    if manager:
        manager.record_business_metric("revenue", amount, {"currency": currency, "source": source})
