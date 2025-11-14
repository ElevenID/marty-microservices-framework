"""
Log Analysis and Processing Examples for Marty Microservices Framework

Demonstrates advanced log analysis patterns including:
- Real-time log analysis and alerting
- Log aggregation and metrics extraction
- Security event detection
- Performance analysis
- Business intelligence from logs
"""

import asyncio
import builtins
import importlib.util
import json
import re
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional, dict, list

# External dependencies - fail if not available
import aioredis
import redis.asyncio as redis_client
from prometheus_client import Counter, Gauge, Histogram, start_http_server


@dataclass
class LogEvent:
    """Structured log event for processing"""

    timestamp: datetime
    level: str
    service_name: str
    message: str
    category: str
    context: builtins.dict[str, Any] = field(default_factory=dict)
    fields: builtins.dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, log_line: str) -> Optional["LogEvent"]:
        """Create LogEvent from JSON log line"""
        try:
            data = json.loads(log_line)
            return cls(
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
                level=data.get("level", "INFO"),
                service_name=data.get("service_name", "unknown"),
                message=data.get("message", ""),
                category=data.get("category", "application"),
                context=data.get("context", {}),
                fields=data.get("fields", {}),
            )
        except (json.JSONDecodeError, ValueError, KeyError):
            return None


@dataclass
class AlertRule:
    """Alert rule configuration"""

    name: str
    pattern: str
    severity: str
    threshold: int
    window_minutes: int
    cooldown_minutes: int = 5
    last_triggered: datetime | None = None


class LogAnalyzer:
    """
    Real-time log analyzer with pattern detection and alerting

    Features:
    - Real-time pattern matching
    - Threshold-based alerting
    - Performance metrics extraction
    - Security event detection
    - Business intelligence gathering
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        elasticsearch_host: str = "localhost",
        elasticsearch_port: int = 9200,
        enable_metrics: bool = True,
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.elasticsearch_host = elasticsearch_host
        self.elasticsearch_port = elasticsearch_port

        # Event storage for analysis
        self.event_buffer: deque = deque(maxlen=10000)
        self.pattern_counts: defaultdict = defaultdict(int)
        self.service_metrics: defaultdict = defaultdict(lambda: defaultdict(list))

        # Alert rules
        self.alert_rules: builtins.list[AlertRule] = self._create_default_alert_rules()

        # Metrics
        if enable_metrics:
            self._setup_metrics()

        # Initialize redis connection
        self.redis = None
        # Redis will be connected async when needed
        self._redis_host = redis_host
        self._redis_port = redis_port

        # Pattern cache
        self._compiled_patterns: builtins.dict[str, re.Pattern] = {}

        print("Log analyzer initialized")

    def _create_default_alert_rules(self) -> builtins.list[AlertRule]:
        """Create default alert rules"""
        return [
            AlertRule(
                name="high_error_rate",
                pattern=r'"level":\s*"ERROR"',
                severity="warning",
                threshold=10,
                window_minutes=5,
            ),
            AlertRule(
                name="critical_errors",
                pattern=r'"level":\s*"CRITICAL"',
                severity="critical",
                threshold=1,
                window_minutes=1,
            ),
            AlertRule(
                name="authentication_failures",
                pattern=r'"security_event":\s*"authentication_failure"',
                severity="warning",
                threshold=5,
                window_minutes=5,
            ),
            AlertRule(
                name="high_response_time",
                pattern=r'"duration_ms":\s*([5-9][0-9]{3,}|[1-9][0-9]{4,})',
                severity="warning",
                threshold=3,
                window_minutes=5,
            ),
            AlertRule(
                name="service_unavailable",
                pattern=r'"http_status":\s*50[0-9]',
                severity="critical",
                threshold=5,
                window_minutes=2,
            ),
        ]

    def _setup_metrics(self):
        """Setup Prometheus metrics"""
        self.metrics = {
            "log_events_total": Counter(
                "marty_log_events_total",
                "Total log events processed",
                ["service", "level", "category"],
            ),
            "error_events_total": Counter(
                "marty_error_events_total",
                "Total error events",
                ["service", "error_type"],
            ),
            "response_time_histogram": Histogram(
                "marty_response_time_seconds",
                "Response time distribution",
                ["service", "endpoint"],
            ),
            "business_events_total": Counter(
                "marty_business_events_total",
                "Business events",
                ["service", "event_type"],
            ),
            "security_events_total": Counter(
                "marty_security_events_total",
                "Security events",
                ["service", "event_type"],
            ),
            "active_services": Gauge("marty_active_services", "Number of active services"),
        }

    async def _ensure_redis_connection(self):
        """Ensure redis connection is established"""
        if self.redis is None:
            try:
                self.redis = await aioredis.from_url(
                    f"redis://{self._redis_host}:{self._redis_port}"
                )
            except Exception as e:
                print(f"Failed to connect to Redis: {e}")
                self.redis = None

    def _get_compiled_pattern(self, pattern: str) -> re.Pattern:
        """Get or compile regex pattern"""
        if pattern not in self._compiled_patterns:
            self._compiled_patterns[pattern] = re.compile(pattern)
        return self._compiled_patterns[pattern]

    async def process_log_event(self, log_line: str) -> LogEvent | None:
        """Process a single log event"""
        event = LogEvent.from_json(log_line)
        if not event:
            return None

        # Add to buffer
        self.event_buffer.append(event)

        # Update metrics
        if hasattr(self, "metrics"):
            self.metrics["log_events_total"].labels(
                service=event.service_name, level=event.level, category=event.category
            ).inc()

        # Analyze event
        await self._analyze_event(event, log_line)

        return event

    async def _analyze_event(self, event: LogEvent, raw_log: str):
        """Analyze log event for patterns and alerts"""
        # Check alert rules
        await self._check_alert_rules(raw_log)

        # Extract performance metrics
        await self._extract_performance_metrics(event)

        # Detect security events
        await self._detect_security_events(event)

        # Process business events
        await self._process_business_events(event)

        # Update service health
        await self._update_service_health(event)

    async def _check_alert_rules(self, log_line: str):
        """Check log against alert rules"""
        current_time = datetime.now()

        for rule in self.alert_rules:
            pattern = self._get_compiled_pattern(rule.pattern)

            if pattern.search(log_line):
                # Count recent matches
                window_start = current_time - timedelta(minutes=rule.window_minutes)
                recent_matches = sum(
                    1
                    for event in self.event_buffer
                    if event.timestamp >= window_start
                    and pattern.search(json.dumps(event.__dict__))
                )

                # Check threshold
                if recent_matches >= rule.threshold:
                    # Check cooldown
                    if (
                        rule.last_triggered is None
                        or current_time - rule.last_triggered
                        >= timedelta(minutes=rule.cooldown_minutes)
                    ):
                        await self._trigger_alert(rule, recent_matches)
                        rule.last_triggered = current_time

    async def _trigger_alert(self, rule: AlertRule, count: int):
        """Trigger an alert"""
        alert_data = {
            "rule_name": rule.name,
            "severity": rule.severity,
            "count": count,
            "window_minutes": rule.window_minutes,
            "timestamp": datetime.now().isoformat(),
            "message": f"Alert: {rule.name} - {count} occurrences in {rule.window_minutes} minutes",
        }

        print(f"🚨 ALERT: {alert_data['message']}")

        # Send to Redis for real-time processing
        try:
            await self._ensure_redis_connection()
            if self.redis is not None:
                await self.redis.lpush("alerts", json.dumps(alert_data))
        except Exception as e:
            print(f"Failed to send alert to Redis: {e}")

    async def _extract_performance_metrics(self, event: LogEvent):
        """Extract performance metrics from event"""
        duration_ms = event.fields.get("duration_ms")
        if duration_ms is not None:
            try:
                duration_seconds = float(duration_ms) / 1000

                # Update metrics
                if hasattr(self, "metrics"):
                    endpoint = event.fields.get("http_path", "unknown")
                    self.metrics["response_time_histogram"].labels(
                        service=event.service_name, endpoint=endpoint
                    ).observe(duration_seconds)

                # Store for analysis
                self.service_metrics[event.service_name]["response_times"].append(duration_ms)

                # Keep only recent data (last 1000 entries)
                if len(self.service_metrics[event.service_name]["response_times"]) > 1000:
                    self.service_metrics[event.service_name]["response_times"] = (
                        self.service_metrics[event.service_name]["response_times"][-1000:]
                    )

            except (ValueError, TypeError):
                pass

    async def _detect_security_events(self, event: LogEvent):
        """Detect and process security events"""
        if event.category == "security":
            security_event = event.fields.get("security_event", "unknown")

            # Update metrics
            if hasattr(self, "metrics"):
                self.metrics["security_events_total"].labels(
                    service=event.service_name, event_type=security_event
                ).inc()

            # Special handling for critical security events
            if security_event in [
                "authentication_failure",
                "unauthorized_access",
                "suspicious_activity",
            ]:
                await self._handle_critical_security_event(event, security_event)

    async def _handle_critical_security_event(self, event: LogEvent, event_type: str):
        """Handle critical security events"""
        security_data = {
            "event_type": event_type,
            "service": event.service_name,
            "timestamp": event.timestamp.isoformat(),
            "user_id": event.context.get("user_id"),
            "source_ip": event.fields.get("source_ip"),
            "message": event.message,
            "severity": "high",
        }

        print(f"🔒 SECURITY EVENT: {event_type} in {event.service_name}")

        # Send to security queue
        try:
            await self._ensure_redis_connection()
            if self.redis is not None:
                await self.redis.lpush("security_events", json.dumps(security_data))
        except Exception as e:
            print(f"Failed to send security event to Redis: {e}")

    async def _process_business_events(self, event: LogEvent):
        """Process business events for intelligence"""
        if event.category == "business":
            business_data = event.fields.get("business", {})
            event_type = business_data.get("event_type", "unknown")

            # Update metrics
            if hasattr(self, "metrics"):
                self.metrics["business_events_total"].labels(
                    service=event.service_name, event_type=event_type
                ).inc()

            # Process revenue events
            if event_type == "transaction" and business_data.get("amount"):
                await self._process_revenue_event(event, business_data)

    async def _process_revenue_event(self, event: LogEvent, business_data: builtins.dict[str, Any]):
        """Process revenue-generating events"""
        revenue_data = {
            "service": event.service_name,
            "amount": business_data.get("amount"),
            "currency": business_data.get("currency", "USD"),
            "timestamp": event.timestamp.isoformat(),
            "user_id": event.context.get("user_id"),
            "transaction_id": business_data.get("entity_id"),
        }

        print(
            f"💰 REVENUE EVENT: {revenue_data['amount']} {revenue_data['currency']} from {event.service_name}"
        )

        # Send to business intelligence queue
        try:
            await self._ensure_redis_connection()
            if self.redis is not None:
                await self.redis.lpush("revenue_events", json.dumps(revenue_data))
        except Exception as e:
            print(f"Failed to send revenue event to Redis: {e}")

    async def _update_service_health(self, event: LogEvent):
        """Update service health metrics"""
        # Track active services
        current_services = {event.service_name for event in self.event_buffer}

        if hasattr(self, "metrics"):
            self.metrics["active_services"].set(len(current_services))

    def get_service_performance_summary(self, service_name: str) -> builtins.dict[str, Any]:
        """Get performance summary for a service"""
        response_times = self.service_metrics[service_name]["response_times"]

        if not response_times:
            return {"service": service_name, "no_data": True}

        return {
            "service": service_name,
            "response_time_avg": statistics.mean(response_times),
            "response_time_median": statistics.median(response_times),
            "response_time_95th": statistics.quantiles(response_times, n=20)[18]
            if len(response_times) >= 20
            else max(response_times),
            "response_time_max": max(response_times),
            "response_time_min": min(response_times),
            "sample_count": len(response_times),
        }

    def get_recent_events(
        self,
        service_name: str | None = None,
        level: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> builtins.list[LogEvent]:
        """Get recent events with optional filtering"""
        events = list(self.event_buffer)

        # Apply filters
        if service_name:
            events = [e for e in events if e.service_name == service_name]
        if level:
            events = [e for e in events if e.level == level]
        if category:
            events = [e for e in events if e.category == category]

        # Sort by timestamp (most recent first) and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    async def analyze_log_stream(self, log_stream):
        """Analyze a stream of log lines"""
        async for log_line in log_stream:
            await self.process_log_event(log_line.strip())


class LogStreamProcessor:
    """
    Stream processor for real-time log analysis

    Integrates with various log sources:
    - File tailing
    - Redis streams
    - Kafka topics
    - HTTP webhooks
    """

    def __init__(self, analyzer: LogAnalyzer):
        self.analyzer = analyzer
        self.running = False

    async def start_file_processing(self, file_path: str):
        """Process logs from a file (tail -f style)"""
        self.running = True

        try:
            with open(file_path) as file:
                # Seek to end of file
                file.seek(0, 2)

                while self.running:
                    line = file.readline()
                    if line:
                        await self.analyzer.process_log_event(line.strip())
                    else:
                        await asyncio.sleep(0.1)
        except FileNotFoundError:
            print(f"Log file not found: {file_path}")
        except Exception as e:
            print(f"Error processing log file: {e}")

    async def start_redis_processing(self, stream_name: str = "logs"):
        """Process logs from Redis stream"""
        # Process logs from Redis stream

        self.running = True
        redis = redis_client.from_url(
            f"redis://{self.analyzer.redis_host}:{self.analyzer.redis_port}"
        )

        try:
            while self.running:
                # Read from Redis stream
                messages = await redis.xread({stream_name: "$"}, count=100, block=1000)

                for _stream, msgs in messages:
                    for _msg_id, fields in msgs:
                        log_line = fields.get(b"log", b"").decode("utf-8")
                        if log_line:
                            await self.analyzer.process_log_event(log_line)
        except Exception as e:
            print(f"Error processing Redis stream: {e}")
        finally:
            await redis.close()

    def stop_processing(self):
        """Stop log processing"""
        self.running = False


# Example usage and testing
async def main():
    """Example usage of log analysis framework"""
    # Create analyzer
    analyzer = LogAnalyzer()

    # Start metrics server
    start_http_server(8090)
    print("Metrics server started on :8090")

    # Example log events
    sample_logs = [
        '{"timestamp":"2023-12-01T12:34:56.789Z","level":"INFO","service_name":"user-service","message":"User login successful","category":"access","context":{"user_id":"user123","correlation_id":"abc123"},"fields":{"http_method":"POST","http_path":"/login","http_status":200,"duration_ms":150}}',
        '{"timestamp":"2023-12-01T12:35:01.234Z","level":"ERROR","service_name":"payment-service","message":"Payment processing failed","category":"error","context":{"user_id":"user456","correlation_id":"def456"},"fields":{"error_type":"ValidationError","transaction_id":"txn789"}}',
        '{"timestamp":"2023-12-01T12:35:05.567Z","level":"WARNING","service_name":"auth-service","message":"Multiple failed login attempts","category":"security","context":{"user_id":"user789","correlation_id":"ghi789"},"fields":{"security_event":"authentication_failure","source_ip":"192.168.1.100","attempts":3}}',
        '{"timestamp":"2023-12-01T12:35:10.890Z","level":"INFO","service_name":"order-service","message":"Order completed","category":"business","context":{"user_id":"user123","correlation_id":"jkl012"},"fields":{"business":{"event_type":"transaction","amount":99.99,"currency":"USD","entity_id":"order123"}}}',
        '{"timestamp":"2023-12-01T12:35:15.123Z","level":"INFO","service_name":"api-gateway","message":"Request processed","category":"access","context":{"correlation_id":"mno345"},"fields":{"http_method":"GET","http_path":"/api/products","http_status":200,"duration_ms":5500}}',
    ]

    # Process sample logs
    print("Processing sample log events...")
    for log_line in sample_logs:
        await analyzer.process_log_event(log_line)
        await asyncio.sleep(0.1)  # Small delay to simulate real-time processing

    # Show analysis results
    print("\n=== ANALYSIS RESULTS ===")

    # Service performance
    for service in ["user-service", "payment-service", "api-gateway"]:
        summary = analyzer.get_service_performance_summary(service)
        if not summary.get("no_data"):
            print(f"\n{service} Performance:")
            print(f"  Average Response Time: {summary['response_time_avg']:.2f}ms")
            print(f"  95th Percentile: {summary['response_time_95th']:.2f}ms")
            print(f"  Sample Count: {summary['sample_count']}")

    # Recent errors
    error_events = analyzer.get_recent_events(level="ERROR", limit=5)
    print(f"\nRecent Errors ({len(error_events)}):")
    for event in error_events:
        print(f"  {event.timestamp} - {event.service_name}: {event.message}")

    # Security events
    security_events = analyzer.get_recent_events(category="security", limit=5)
    print(f"\nSecurity Events ({len(security_events)}):")
    for event in security_events:
        print(f"  {event.timestamp} - {event.service_name}: {event.message}")


if __name__ == "__main__":
    asyncio.run(main())
