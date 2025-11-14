"""
Advanced Observability Extensions for Marty Framework

This module extends the basic monitoring capabilities with advanced features including
distributed tracing, intelligent alerting, log aggregation, and observability analytics.
"""

import asyncio
import builtins
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

import aiohttp
import structlog
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .monitoring import Alert, AlertSeverity, HealthChecker, MetricsCollector


class TraceSpanType(Enum):
    """Types of traced spans."""

    HTTP_REQUEST = "http.request"
    DATABASE_QUERY = "db.query"
    CACHE_OPERATION = "cache.operation"
    MESSAGE_PROCESSING = "message.processing"
    BUSINESS_OPERATION = "business.operation"
    EXTERNAL_API = "external.api"


class LogAggregationLevel(Enum):
    """Log aggregation levels."""

    NONE = "none"
    SERVICE = "service"
    CLUSTER = "cluster"
    GLOBAL = "global"


@dataclass
class TraceSpan:
    """Distributed trace span."""

    trace_id: str
    span_id: str
    parent_span_id: str | None
    operation_name: str
    span_type: TraceSpanType
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    status: str = "ok"
    tags: builtins.dict[str, str] = field(default_factory=dict)
    logs: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass
class AlertRule:
    """Advanced alert rule with intelligent conditions."""

    name: str
    description: str
    severity: AlertSeverity
    metric_query: str
    condition: str
    threshold: float
    duration: timedelta
    evaluation_interval: timedelta = field(default=timedelta(seconds=30))
    labels: builtins.dict[str, str] = field(default_factory=dict)
    annotations: builtins.dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    # Advanced features
    anomaly_detection: bool = False
    baseline_period: timedelta = field(default=timedelta(hours=24))
    sensitivity: float = 0.8
    dependency_rules: builtins.list[str] = field(default_factory=list)


@dataclass
class ObservabilityMetrics:
    """Advanced observability metrics."""

    service_name: str
    timestamp: datetime

    # Performance metrics
    request_rate: float = 0.0
    error_rate: float = 0.0
    response_time_p50: float = 0.0
    response_time_p95: float = 0.0
    response_time_p99: float = 0.0

    # Resource metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_io: float = 0.0

    # Business metrics
    active_users: int = 0
    transaction_volume: float = 0.0
    business_events: builtins.dict[str, int] = field(default_factory=dict)

    # Quality metrics
    availability: float = 100.0
    reliability_score: float = 1.0
    performance_score: float = 1.0


class DistributedTracer:
    """Advanced distributed tracing with OpenTelemetry."""

    def __init__(self, service_name: str, jaeger_endpoint: str = "http://localhost:14268"):
        """Initialize distributed tracer."""
        self.service_name = service_name
        self.jaeger_endpoint = jaeger_endpoint

        # Configure OpenTelemetry
        self._setup_tracing()

        # Span storage for analytics
        self.spans: deque = deque(maxlen=10000)
        self.active_spans: builtins.dict[str, TraceSpan] = {}

        # Performance analytics
        self.span_stats = defaultdict(list)
        self.error_patterns = defaultdict(int)

    def _setup_tracing(self):
        """Setup OpenTelemetry tracing."""
        # Configure resource
        resource = Resource.create(
            {
                "service.name": self.service_name,
                "service.version": "1.0.0",
            }
        )

        # Configure tracer provider
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        # Configure Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name="localhost",
            agent_port=14268,
        )

        # Configure span processor
        span_processor = BatchSpanProcessor(jaeger_exporter)
        provider.add_span_processor(span_processor)

        # Get tracer
        self.tracer = trace.get_tracer(__name__)

        # Auto-instrument libraries
        self._auto_instrument()

    def _auto_instrument(self):
        """Auto-instrument common libraries."""
        try:
            FastAPIInstrumentor().instrument()
            AioHttpClientInstrumentor().instrument()
            SQLAlchemyInstrumentor().instrument()
        except Exception as e:
            print(f"Warning: Failed to auto-instrument libraries: {e}")

    def start_span(
        self,
        operation_name: str,
        span_type: TraceSpanType,
        parent_span_id: str | None = None,
        **tags,
    ) -> TraceSpan:
        """Start a new trace span."""
        trace_id = str(uuid4())
        span_id = str(uuid4())

        span = TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            span_type=span_type,
            start_time=datetime.now(timezone.utc),
            tags=tags,
        )

        self.active_spans[span_id] = span
        return span

    def finish_span(self, span: TraceSpan, status: str = "ok", error: str | None = None):
        """Finish a trace span."""
        span.end_time = datetime.now(timezone.utc)
        span.duration_ms = (span.end_time - span.start_time).total_seconds() * 1000
        span.status = status
        span.error = error

        # Add to storage
        self.spans.append(span)

        # Update analytics
        self._update_span_analytics(span)

        # Remove from active spans
        if span.span_id in self.active_spans:
            del self.active_spans[span.span_id]

    def _update_span_analytics(self, span: TraceSpan):
        """Update span analytics."""
        operation_key = f"{span.span_type.value}:{span.operation_name}"

        if span.duration_ms:
            self.span_stats[operation_key].append(span.duration_ms)

            # Keep only recent data
            if len(self.span_stats[operation_key]) > 1000:
                self.span_stats[operation_key] = self.span_stats[operation_key][-1000:]

        if span.error:
            self.error_patterns[span.error] += 1

    def get_trace_analytics(self) -> builtins.dict[str, Any]:
        """Get trace analytics."""
        analytics = {
            "total_spans": len(self.spans),
            "active_spans": len(self.active_spans),
            "operation_stats": {},
            "error_patterns": dict(self.error_patterns),
            "performance_summary": {},
        }

        # Operation statistics
        for operation, durations in self.span_stats.items():
            if durations:
                analytics["operation_stats"][operation] = {
                    "count": len(durations),
                    "avg_duration_ms": statistics.mean(durations),
                    "p50_duration_ms": statistics.median(durations),
                    "p95_duration_ms": self._percentile(durations, 0.95),
                    "p99_duration_ms": self._percentile(durations, 0.99),
                    "max_duration_ms": max(durations),
                    "min_duration_ms": min(durations),
                }

        return analytics

    @staticmethod
    def _percentile(data: builtins.list[float], percentile: float) -> float:
        """Calculate percentile."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]


class IntelligentAlerting:
    """Intelligent alerting system with anomaly detection."""

    def __init__(self, service_name: str):
        """Initialize intelligent alerting."""
        self.service_name = service_name
        self.alert_rules: builtins.dict[str, AlertRule] = {}
        self.active_alerts: builtins.dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=10000)

        # Anomaly detection
        self.metric_baselines: builtins.dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1440)
        )  # 24h at 1min resolution
        self.anomaly_scores: builtins.dict[str, float] = {}

        # Alert suppression
        self.suppression_rules: builtins.dict[str, timedelta] = {}
        self.last_alert_times: builtins.dict[str, datetime] = {}

        # Notification channels
        self.notification_channels: builtins.list[builtins.dict[str, Any]] = []

    def add_alert_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.alert_rules[rule.name] = rule

    def add_notification_channel(self, channel_type: str, config: builtins.dict[str, Any]):
        """Add a notification channel."""
        self.notification_channels.append({"type": channel_type, "config": config})

    async def evaluate_alerts(self, metrics: ObservabilityMetrics):
        """Evaluate all alert rules."""
        current_time = datetime.now(timezone.utc)

        # Update baselines
        self._update_baselines(metrics)

        # Evaluate each rule
        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue

            try:
                should_alert = await self._evaluate_rule(rule, metrics, current_time)

                if should_alert:
                    await self._fire_alert(rule, metrics, current_time)
                else:
                    await self._resolve_alert(rule_name, current_time)

            except Exception as e:
                print(f"Error evaluating alert rule {rule_name}: {e}")

    async def _evaluate_rule(
        self, rule: AlertRule, metrics: ObservabilityMetrics, current_time: datetime
    ) -> bool:
        """Evaluate a single alert rule."""
        # Get metric value
        metric_value = self._get_metric_value(rule.metric_query, metrics)

        if metric_value is None:
            return False

        # Standard threshold evaluation
        threshold_exceeded = self._evaluate_threshold(rule.condition, metric_value, rule.threshold)

        # Anomaly detection if enabled
        anomaly_detected = False
        if rule.anomaly_detection:
            anomaly_detected = self._detect_anomaly(
                rule.metric_query, metric_value, rule.sensitivity
            )

        # Dependency check
        dependency_satisfied = self._check_dependencies(rule.dependency_rules, current_time)

        # Final decision
        return (threshold_exceeded or anomaly_detected) and dependency_satisfied

    def _get_metric_value(self, metric_query: str, metrics: ObservabilityMetrics) -> float | None:
        """Get metric value from metrics object."""
        metric_map = {
            "request_rate": metrics.request_rate,
            "error_rate": metrics.error_rate,
            "response_time_p95": metrics.response_time_p95,
            "response_time_p99": metrics.response_time_p99,
            "cpu_usage": metrics.cpu_usage,
            "memory_usage": metrics.memory_usage,
            "availability": metrics.availability,
        }

        return metric_map.get(metric_query)

    def _evaluate_threshold(self, condition: str, value: float, threshold: float) -> bool:
        """Evaluate threshold condition."""
        if condition == "greater_than":
            return value > threshold
        if condition == "less_than":
            return value < threshold
        if condition == "equals":
            return abs(value - threshold) < 0.01
        if condition == "not_equals":
            return abs(value - threshold) >= 0.01
        return False

    def _detect_anomaly(self, metric_name: str, value: float, sensitivity: float) -> bool:
        """Detect anomalies using statistical methods."""
        baseline = self.metric_baselines[metric_name]

        if len(baseline) < 10:  # Need minimum data points
            return False

        # Calculate statistical measures
        mean_val = statistics.mean(baseline)
        std_dev = statistics.stdev(baseline) if len(baseline) > 1 else 0

        if std_dev == 0:
            return False

        # Z-score anomaly detection
        z_score = abs(value - mean_val) / std_dev
        threshold = 3.0 * (1.0 - sensitivity)  # Adjust threshold based on sensitivity

        is_anomaly = z_score > threshold
        self.anomaly_scores[metric_name] = z_score

        return is_anomaly

    def _check_dependencies(
        self, dependency_rules: builtins.list[str], current_time: datetime
    ) -> bool:
        """Check if dependency rules are satisfied."""
        if not dependency_rules:
            return True

        # Check if any dependent alert is active
        for dep_rule in dependency_rules:
            if any(alert.name == dep_rule for alert in self.active_alerts.values()):
                return False

        return True

    def _update_baselines(self, metrics: ObservabilityMetrics):
        """Update metric baselines for anomaly detection."""
        metric_values = {
            "request_rate": metrics.request_rate,
            "error_rate": metrics.error_rate,
            "response_time_p95": metrics.response_time_p95,
            "cpu_usage": metrics.cpu_usage,
            "memory_usage": metrics.memory_usage,
        }

        for metric_name, value in metric_values.items():
            if value is not None:
                self.metric_baselines[metric_name].append(value)

    async def _fire_alert(
        self, rule: AlertRule, metrics: ObservabilityMetrics, current_time: datetime
    ):
        """Fire an alert."""
        alert_id = str(uuid4())

        # Check suppression
        if self._is_suppressed(rule.name, current_time):
            return

        alert = Alert(
            id=alert_id,
            name=rule.name,
            severity=rule.severity,
            message=f"Alert {rule.name}: {rule.description}",
            timestamp=current_time,
            labels=rule.labels,
        )

        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        self.last_alert_times[rule.name] = current_time

        # Send notifications
        await self._send_notifications(alert, metrics)

    async def _resolve_alert(self, rule_name: str, current_time: datetime):
        """Resolve alerts for a rule."""
        alerts_to_resolve = [
            alert_id
            for alert_id, alert in self.active_alerts.items()
            if alert.name == rule_name and not alert.resolved
        ]

        for alert_id in alerts_to_resolve:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            del self.active_alerts[alert_id]

            # Send resolution notification
            await self._send_resolution_notification(alert)

    def _is_suppressed(self, rule_name: str, current_time: datetime) -> bool:
        """Check if alert is suppressed."""
        if rule_name not in self.suppression_rules:
            return False

        last_alert_time = self.last_alert_times.get(rule_name)
        if not last_alert_time:
            return False

        suppression_duration = self.suppression_rules[rule_name]
        return current_time - last_alert_time < suppression_duration

    async def _send_notifications(self, alert: Alert, metrics: ObservabilityMetrics):
        """Send alert notifications."""
        for channel in self.notification_channels:
            try:
                if channel["type"] == "webhook":
                    await self._send_webhook_notification(channel["config"], alert, metrics)
                elif channel["type"] == "slack":
                    await self._send_slack_notification(channel["config"], alert, metrics)
                # Add more notification types as needed

            except Exception as e:
                print(f"Error sending notification: {e}")

    async def _send_webhook_notification(
        self,
        config: builtins.dict[str, Any],
        alert: Alert,
        metrics: ObservabilityMetrics,
    ):
        """Send webhook notification."""
        webhook_url = config["url"]

        payload = {
            "alert": {
                "id": alert.id,
                "name": alert.name,
                "severity": alert.severity.value,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "labels": alert.labels,
            },
            "service": self.service_name,
            "metrics": {
                "request_rate": metrics.request_rate,
                "error_rate": metrics.error_rate,
                "response_time_p95": metrics.response_time_p95,
                "cpu_usage": metrics.cpu_usage,
                "memory_usage": metrics.memory_usage,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status != 200:
                    raise Exception(f"Webhook notification failed with status {response.status}")

    async def _send_slack_notification(
        self,
        config: builtins.dict[str, Any],
        alert: Alert,
        metrics: ObservabilityMetrics,
    ):
        """Send Slack notification."""
        # Placeholder for Slack integration

    async def _send_resolution_notification(self, alert: Alert):
        """Send alert resolution notification."""
        # Create resolution payload and send through all channels


class LogAggregator:
    """Advanced log aggregation and analysis."""

    def __init__(
        self,
        service_name: str,
        aggregation_level: LogAggregationLevel = LogAggregationLevel.SERVICE,
    ):
        """Initialize log aggregator."""
        self.service_name = service_name
        self.aggregation_level = aggregation_level

        # Configure structured logging
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        self.logger = structlog.get_logger()

        # Log storage and analysis
        self.log_buffer: deque = deque(maxlen=10000)
        self.log_patterns: builtins.dict[str, int] = defaultdict(int)
        self.error_patterns: builtins.dict[str, int] = defaultdict(int)

        # Performance tracking
        self.log_rates: deque = deque(maxlen=60)  # 1 minute of data
        self.last_log_count = 0

    def log_with_trace(self, level: str, message: str, **kwargs):
        """Log with trace correlation."""
        # Get current trace context
        trace_context = self._get_trace_context()

        # Add trace information to log
        log_data = {
            "message": message,
            "service": self.service_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }

        if trace_context:
            log_data.update(trace_context)

        # Log based on level
        getattr(self.logger, level.lower())(message, **log_data)

        # Store for analysis
        self.log_buffer.append(log_data)
        self._analyze_log_patterns(log_data)

    def _get_trace_context(self) -> builtins.dict[str, str] | None:
        """Get current trace context."""
        try:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                span_context = current_span.get_span_context()
                return {
                    "trace_id": format(span_context.trace_id, "032x"),
                    "span_id": format(span_context.span_id, "016x"),
                }
        except Exception:
            pass
        return None

    def _analyze_log_patterns(self, log_data: builtins.dict[str, Any]):
        """Analyze log patterns for insights."""
        message = log_data.get("message", "")
        level = log_data.get("level", "")

        # Pattern extraction (simple keyword-based)
        words = message.lower().split()
        for word in words:
            if len(word) > 3:  # Ignore short words
                self.log_patterns[word] += 1

        # Error pattern tracking
        if level.upper() in ["ERROR", "CRITICAL"]:
            self.error_patterns[message] += 1

    def get_log_analytics(self) -> builtins.dict[str, Any]:
        """Get log analytics."""
        current_log_count = len(self.log_buffer)
        log_rate = current_log_count - self.last_log_count
        self.log_rates.append(log_rate)
        self.last_log_count = current_log_count

        return {
            "total_logs": len(self.log_buffer),
            "log_rate_per_minute": sum(self.log_rates),
            "avg_log_rate": statistics.mean(self.log_rates) if self.log_rates else 0,
            "top_patterns": dict(
                sorted(self.log_patterns.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "error_patterns": dict(self.error_patterns),
            "log_levels": self._get_log_level_distribution(),
        }

    def _get_log_level_distribution(self) -> builtins.dict[str, int]:
        """Get distribution of log levels."""
        levels = defaultdict(int)
        for log_entry in self.log_buffer:
            level = log_entry.get("level", "unknown")
            levels[level] += 1
        return dict(levels)


class AdvancedObservabilityManager:
    """Advanced observability manager with full-stack monitoring."""

    def __init__(self, service_name: str, config: builtins.dict[str, Any]):
        """Initialize advanced observability manager."""
        self.service_name = service_name
        self.config = config

        # Core components
        self.metrics_collector = MetricsCollector()
        self.health_checker = HealthChecker()

        # Advanced components
        self.tracer = DistributedTracer(
            service_name, config.get("jaeger_endpoint", "http://localhost:14268")
        )
        self.alerting = IntelligentAlerting(service_name)
        self.log_aggregator = LogAggregator(service_name)

        # Observability metrics
        self.last_metrics = ObservabilityMetrics(service_name, datetime.now(timezone.utc))

        # Configure default alert rules
        self._configure_advanced_alerts()

        # Monitoring loop
        self._monitoring_active = False

    def _configure_advanced_alerts(self):
        """Configure advanced alert rules."""
        # High error rate with anomaly detection
        self.alerting.add_alert_rule(
            AlertRule(
                name="high_error_rate_anomaly",
                description="Error rate is unusually high",
                severity=AlertSeverity.WARNING,
                metric_query="error_rate",
                condition="greater_than",
                threshold=0.05,
                duration=timedelta(minutes=5),
                anomaly_detection=True,
                sensitivity=0.8,
            )
        )

        # Response time degradation
        self.alerting.add_alert_rule(
            AlertRule(
                name="response_time_degradation",
                description="Response time P95 is degraded",
                severity=AlertSeverity.WARNING,
                metric_query="response_time_p95",
                condition="greater_than",
                threshold=2000,  # 2 seconds
                duration=timedelta(minutes=3),
            )
        )

        # Memory usage critical
        self.alerting.add_alert_rule(
            AlertRule(
                name="memory_usage_critical",
                description="Memory usage is critically high",
                severity=AlertSeverity.CRITICAL,
                metric_query="memory_usage",
                condition="greater_than",
                threshold=0.9,  # 90%
                duration=timedelta(minutes=2),
            )
        )

    async def start_advanced_monitoring(self):
        """Start advanced monitoring."""
        self._monitoring_active = True

        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())

        self.log_aggregator.log_with_trace(
            "info",
            "Advanced observability monitoring started",
            service=self.service_name,
        )

    async def stop_advanced_monitoring(self):
        """Stop advanced monitoring."""
        self._monitoring_active = False

        self.log_aggregator.log_with_trace(
            "info",
            "Advanced observability monitoring stopped",
            service=self.service_name,
        )

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                # Collect current metrics
                current_metrics = await self._collect_observability_metrics()
                self.last_metrics = current_metrics

                # Evaluate alerts
                await self.alerting.evaluate_alerts(current_metrics)

                # Update system metrics
                self._update_system_metrics()

                # Wait for next iteration
                await asyncio.sleep(30)  # Monitor every 30 seconds

            except Exception as e:
                self.log_aggregator.log_with_trace(
                    "error", "Error in monitoring loop", error=str(e)
                )
                await asyncio.sleep(60)  # Wait longer on error

    async def _collect_observability_metrics(self) -> ObservabilityMetrics:
        """Collect comprehensive observability metrics."""
        current_time = datetime.now(timezone.utc)

        # Get trace analytics
        trace_analytics = self.tracer.get_trace_analytics()

        # Get log analytics
        self.log_aggregator.get_log_analytics()

        # Get basic metrics
        basic_metrics = self.metrics_collector.get_metrics()

        # Calculate derived metrics
        metrics = ObservabilityMetrics(
            service_name=self.service_name,
            timestamp=current_time,
            request_rate=self._calculate_request_rate(trace_analytics),
            error_rate=self._calculate_error_rate(trace_analytics),
            response_time_p95=self._get_percentile_latency(trace_analytics, 0.95),
            response_time_p99=self._get_percentile_latency(trace_analytics, 0.99),
            cpu_usage=self._get_system_metric("cpu_usage", basic_metrics),
            memory_usage=self._get_system_metric("memory_usage", basic_metrics),
        )

        return metrics

    def _calculate_request_rate(self, trace_analytics: builtins.dict[str, Any]) -> float:
        """Calculate request rate from trace analytics."""
        operation_stats = trace_analytics.get("operation_stats", {})
        total_requests = sum(stats["count"] for stats in operation_stats.values())
        return total_requests / 60.0  # Requests per second (assuming 1-minute window)

    def _calculate_error_rate(self, trace_analytics: builtins.dict[str, Any]) -> float:
        """Calculate error rate from trace analytics."""
        error_patterns = trace_analytics.get("error_patterns", {})
        total_errors = sum(error_patterns.values())
        total_spans = trace_analytics.get("total_spans", 1)
        return total_errors / max(total_spans, 1)

    def _get_percentile_latency(
        self, trace_analytics: builtins.dict[str, Any], percentile: float
    ) -> float:
        """Get percentile latency from trace analytics."""
        operation_stats = trace_analytics.get("operation_stats", {})
        percentile_key = f"p{int(percentile * 100)}_duration_ms"

        latencies = [stats.get(percentile_key, 0) for stats in operation_stats.values()]
        return max(latencies) if latencies else 0.0

    def _get_system_metric(self, metric_name: str, basic_metrics: builtins.list) -> float:
        """Get system metric value."""
        for metric in basic_metrics:
            if metric_name in metric.name:
                return metric.value
        return 0.0

    def _update_system_metrics(self):
        """Update system metrics."""
        # This would integrate with the existing SystemMetrics class

    def get_comprehensive_status(self) -> builtins.dict[str, Any]:
        """Get comprehensive observability status."""
        return {
            "service": self.service_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health": self.health_checker.get_overall_status().value,
            "metrics": {
                "request_rate": self.last_metrics.request_rate,
                "error_rate": self.last_metrics.error_rate,
                "response_time_p95": self.last_metrics.response_time_p95,
                "cpu_usage": self.last_metrics.cpu_usage,
                "memory_usage": self.last_metrics.memory_usage,
            },
            "tracing": self.tracer.get_trace_analytics(),
            "alerting": {
                "active_alerts": len(self.alerting.active_alerts),
                "alert_rules": len(self.alerting.alert_rules),
                "anomaly_scores": self.alerting.anomaly_scores,
            },
            "logging": self.log_aggregator.get_log_analytics(),
        }


def create_advanced_observability_manager(
    service_name: str, **config
) -> AdvancedObservabilityManager:
    """Create advanced observability manager with configuration."""
    return AdvancedObservabilityManager(service_name, config)
