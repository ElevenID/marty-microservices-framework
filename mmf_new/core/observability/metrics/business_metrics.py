"""
Enhanced Business Metrics Collection for Marty Microservices Framework

Provides comprehensive business metrics collection, including:
- Revenue tracking and conversion metrics
- User engagement and retention metrics
- Performance KPIs and business health indicators
- Custom business event tracking
"""

import builtins
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, list

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)


class BusinessEventType(Enum):
    """Types of business events to track"""

    USER_SIGNUP = "user_signup"
    USER_LOGIN = "user_login"
    PURCHASE = "purchase"
    SUBSCRIPTION = "subscription"
    CONVERSION = "conversion"
    ENGAGEMENT = "engagement"
    RETENTION = "retention"
    CHURN = "churn"
    REVENUE = "revenue"
    COST = "cost"
    PERFORMANCE = "performance"
    SUPPORT = "support"
    MARKETING = "marketing"


@dataclass
class BusinessMetricsConfig:
    """Configuration for business metrics collection"""

    service_name: str
    service_version: str = "1.0.0"
    namespace: str = "business"
    enable_revenue_tracking: bool = True
    enable_user_metrics: bool = True
    enable_performance_kpis: bool = True
    enable_cost_tracking: bool = True
    default_currency: str = "USD"
    custom_labels: builtins.dict[str, str] | None = None
    retention_periods: builtins.list[int] = field(default_factory=lambda: [1, 7, 30, 90])
    cohort_analysis_enabled: bool = True


@dataclass
class BusinessEvent:
    """Business event for tracking"""

    event_type: BusinessEventType
    user_id: str | None = None
    session_id: str | None = None
    amount: float | None = None
    currency: str = "USD"
    properties: builtins.dict[str, Any] | None = None
    timestamp: datetime | None = None
    labels: builtins.dict[str, str] | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.properties is None:
            self.properties = {}
        if self.labels is None:
            self.labels = {}


class BusinessMetricsCollector:
    """
    Enhanced business metrics collector with comprehensive KPI tracking

    Features:
    - Revenue and financial metrics
    - User engagement and retention
    - Conversion funnel tracking
    - Performance KPIs
    - Cost analysis
    - Custom business events
    """

    def __init__(self, config: BusinessMetricsConfig):
        self.config = config
        self.registry = CollectorRegistry()
        self._setup_metrics()
        self._active_sessions = {}
        self._user_cohorts = {}

        logger.info(f"Business metrics collector initialized for {config.service_name}")

    def _setup_metrics(self):
        """Initialize all business metrics"""
        labels = ["service_name", "environment"]

        # Revenue Metrics
        self.revenue_total = Counter(
            "business_revenue_total",
            "Total revenue generated",
            labelnames=labels + ["currency", "source", "product"],
            registry=self.registry,
        )

        self.revenue_per_user = Histogram(
            "business_revenue_per_user",
            "Revenue per user distribution",
            labelnames=labels + ["currency", "user_segment"],
            buckets=[0, 10, 50, 100, 500, 1000, 5000, float("inf")],
            registry=self.registry,
        )

        self.monthly_recurring_revenue = Gauge(
            "business_mrr_current",
            "Current Monthly Recurring Revenue",
            labelnames=labels + ["currency"],
            registry=self.registry,
        )

        self.annual_recurring_revenue = Gauge(
            "business_arr_current",
            "Current Annual Recurring Revenue",
            labelnames=labels + ["currency"],
            registry=self.registry,
        )

        # User Metrics
        self.user_signups_total = Counter(
            "business_user_signups_total",
            "Total user signups",
            labelnames=labels + ["source", "plan"],
            registry=self.registry,
        )

        self.active_users = Gauge(
            "business_active_users",
            "Currently active users",
            labelnames=labels + ["period"],
            registry=self.registry,
        )

        self.user_sessions_total = Counter(
            "business_user_sessions_total",
            "Total user sessions",
            labelnames=labels + ["device_type", "location"],
            registry=self.registry,
        )

        self.user_session_duration = Histogram(
            "business_user_session_duration_seconds",
            "User session duration in seconds",
            labelnames=labels + ["user_segment"],
            buckets=[30, 120, 300, 600, 1800, 3600, 7200, float("inf")],
            registry=self.registry,
        )

        # Conversion Metrics
        self.conversion_events = Counter(
            "business_conversion_events_total",
            "Conversion events",
            labelnames=labels + ["funnel_step", "source"],
            registry=self.registry,
        )

        self.conversion_rate = Gauge(
            "business_conversion_rate",
            "Current conversion rate",
            labelnames=labels + ["funnel", "period"],
            registry=self.registry,
        )

        self.cart_abandonment_rate = Gauge(
            "business_cart_abandonment_rate",
            "Cart abandonment rate",
            labelnames=labels + ["period"],
            registry=self.registry,
        )

        # Transaction Metrics
        self.transactions_total = Counter(
            "business_transactions_total",
            "Total transactions",
            labelnames=labels + ["status", "payment_method", "product"],
            registry=self.registry,
        )

        self.transaction_value = Histogram(
            "business_transaction_value",
            "Transaction value distribution",
            labelnames=labels + ["currency", "product"],
            buckets=[0, 5, 10, 25, 50, 100, 250, 500, 1000, float("inf")],
            registry=self.registry,
        )

        self.refunds_total = Counter(
            "business_refunds_total",
            "Total refunds",
            labelnames=labels + ["reason", "product"],
            registry=self.registry,
        )

        # Engagement Metrics
        self.page_views_total = Counter(
            "business_page_views_total",
            "Total page views",
            labelnames=labels + ["page", "user_segment"],
            registry=self.registry,
        )

        self.feature_usage = Counter(
            "business_feature_usage_total",
            "Feature usage count",
            labelnames=labels + ["feature", "user_segment"],
            registry=self.registry,
        )

        self.user_retention_rate = Gauge(
            "business_user_retention_rate",
            "User retention rate",
            labelnames=labels + ["period_days", "cohort"],
            registry=self.registry,
        )

        # Support and Satisfaction Metrics
        self.support_tickets_total = Counter(
            "business_support_tickets_total",
            "Total support tickets",
            labelnames=labels + ["priority", "category", "channel"],
            registry=self.registry,
        )

        self.nps_score = Gauge(
            "business_nps_score",
            "Net Promoter Score",
            labelnames=labels + ["period"],
            registry=self.registry,
        )

        self.customer_satisfaction = Gauge(
            "business_customer_satisfaction_score",
            "Customer satisfaction score",
            labelnames=labels + ["survey_type", "period"],
            registry=self.registry,
        )

        # Cost Metrics
        self.acquisition_cost = Histogram(
            "business_customer_acquisition_cost",
            "Customer acquisition cost",
            labelnames=labels + ["channel", "currency"],
            buckets=[0, 10, 25, 50, 100, 250, 500, 1000, float("inf")],
            registry=self.registry,
        )

        self.operational_costs = Gauge(
            "business_operational_costs",
            "Operational costs",
            labelnames=labels + ["category", "currency"],
            registry=self.registry,
        )

        # Performance KPIs
        self.ltv_cac_ratio = Gauge(
            "business_ltv_cac_ratio",
            "Lifetime Value to Customer Acquisition Cost ratio",
            labelnames=labels + ["period"],
            registry=self.registry,
        )

        self.churn_rate = Gauge(
            "business_churn_rate",
            "Customer churn rate",
            labelnames=labels + ["period", "segment"],
            registry=self.registry,
        )

        self.gross_margin = Gauge(
            "business_gross_margin_percentage",
            "Gross margin percentage",
            labelnames=labels + ["product", "period"],
            registry=self.registry,
        )

        # Real-time Business Health
        self.business_health_score = Gauge(
            "business_health_score",
            "Overall business health score (0-100)",
            labelnames=labels,
            registry=self.registry,
        )

    async def track_event(self, event: BusinessEvent):
        """Track a business event"""
        try:
            labels = [self.config.service_name, "production"]
            (labels + list(event.labels.values()) if event.labels else labels)

            if event.event_type == BusinessEventType.USER_SIGNUP:
                await self._track_user_signup(event)
            elif event.event_type == BusinessEventType.USER_LOGIN:
                await self._track_user_login(event)
            elif event.event_type == BusinessEventType.PURCHASE:
                await self._track_purchase(event)
            elif event.event_type == BusinessEventType.CONVERSION:
                await self._track_conversion(event)
            elif event.event_type == BusinessEventType.REVENUE:
                await self._track_revenue(event)
            elif event.event_type == BusinessEventType.ENGAGEMENT:
                await self._track_engagement(event)

            logger.debug(f"Tracked business event: {event.event_type.value}")

        except Exception as e:
            logger.error(f"Error tracking business event: {e}")

    async def _track_user_signup(self, event: BusinessEvent):
        """Track user signup event"""
        source = event.properties.get("source", "unknown")
        plan = event.properties.get("plan", "free")

        self.user_signups_total.labels(
            service_name=self.config.service_name,
            environment="production",
            source=source,
            plan=plan,
        ).inc()

        # Add to cohort tracking
        if event.user_id and self.config.cohort_analysis_enabled:
            cohort_key = event.timestamp.strftime("%Y-%m")
            if cohort_key not in self._user_cohorts:
                self._user_cohorts[cohort_key] = set()
            self._user_cohorts[cohort_key].add(event.user_id)

    async def _track_user_login(self, event: BusinessEvent):
        """Track user login event"""
        device_type = event.properties.get("device_type", "unknown")
        location = event.properties.get("location", "unknown")

        self.user_sessions_total.labels(
            service_name=self.config.service_name,
            environment="production",
            device_type=device_type,
            location=location,
        ).inc()

        # Track active session
        if event.session_id:
            self._active_sessions[event.session_id] = {
                "user_id": event.user_id,
                "start_time": event.timestamp,
                "last_activity": event.timestamp,
            }

    async def _track_purchase(self, event: BusinessEvent):
        """Track purchase event"""
        payment_method = event.properties.get("payment_method", "unknown")
        product = event.properties.get("product", "unknown")

        self.transactions_total.labels(
            service_name=self.config.service_name,
            environment="production",
            status="success",
            payment_method=payment_method,
            product=product,
        ).inc()

        if event.amount:
            self.transaction_value.labels(
                service_name=self.config.service_name,
                environment="production",
                currency=event.currency,
                product=product,
            ).observe(event.amount)

            # Track revenue
            await self._track_revenue(event)

    async def _track_revenue(self, event: BusinessEvent):
        """Track revenue event"""
        if event.amount:
            source = event.properties.get("source", "direct")
            product = event.properties.get("product", "unknown")

            self.revenue_total.labels(
                service_name=self.config.service_name,
                environment="production",
                currency=event.currency,
                source=source,
                product=product,
            ).inc(event.amount)

    async def _track_conversion(self, event: BusinessEvent):
        """Track conversion event"""
        funnel_step = event.properties.get("funnel_step", "unknown")
        source = event.properties.get("source", "unknown")

        self.conversion_events.labels(
            service_name=self.config.service_name,
            environment="production",
            funnel_step=funnel_step,
            source=source,
        ).inc()

    async def _track_engagement(self, event: BusinessEvent):
        """Track engagement event"""
        if event.properties.get("page"):
            user_segment = event.properties.get("user_segment", "unknown")
            self.page_views_total.labels(
                service_name=self.config.service_name,
                environment="production",
                page=event.properties["page"],
                user_segment=user_segment,
            ).inc()

        if event.properties.get("feature"):
            user_segment = event.properties.get("user_segment", "unknown")
            self.feature_usage.labels(
                service_name=self.config.service_name,
                environment="production",
                feature=event.properties["feature"],
                user_segment=user_segment,
            ).inc()

    async def calculate_kpis(self):
        """Calculate and update business KPIs"""
        try:
            # This would typically fetch data from your business database
            # For demo purposes, we'll calculate some example KPIs

            # Calculate business health score
            health_score = await self._calculate_business_health_score()
            self.business_health_score.labels(
                service_name=self.config.service_name, environment="production"
            ).set(health_score)

            # Update retention rates
            await self._update_retention_rates()

            # Update churn rates
            await self._update_churn_rates()

            logger.info("Business KPIs updated successfully")

        except Exception as e:
            logger.error(f"Error calculating business KPIs: {e}")

    async def _calculate_business_health_score(self) -> float:
        """Calculate overall business health score (0-100)"""
        # This is a simplified example - in reality, you'd use complex business logic
        # combining multiple factors like revenue growth, user satisfaction, churn, etc.

        # Factors that contribute to business health
        factors = {
            "revenue_growth": 85,  # 85% weight for revenue growth
            "user_satisfaction": 78,  # User satisfaction score
            "churn_rate": 92,  # Inverse of churn rate
            "conversion_rate": 65,  # Conversion performance
            "operational_efficiency": 80,  # Operational metrics
        }

        # Weighted average
        weights = {
            "revenue_growth": 0.3,
            "user_satisfaction": 0.25,
            "churn_rate": 0.2,
            "conversion_rate": 0.15,
            "operational_efficiency": 0.1,
        }

        health_score = sum(factors[k] * weights[k] for k in factors)
        return min(100, max(0, health_score))

    async def _update_retention_rates(self):
        """Update user retention rates for different periods"""
        for period in self.config.retention_periods:
            # Calculate retention rate for each cohort
            for cohort, users in self._user_cohorts.items():
                if users:
                    # This would typically query your user database
                    # For demo, we'll use a simulated retention rate
                    retention_rate = max(0, 100 - (period * 2))  # Simplified calculation

                    self.user_retention_rate.labels(
                        service_name=self.config.service_name,
                        environment="production",
                        period_days=str(period),
                        cohort=cohort,
                    ).set(retention_rate)

    async def _update_churn_rates(self):
        """Update churn rates"""
        # This would typically be calculated from user data
        # For demo purposes, we'll set example values

        periods = ["daily", "weekly", "monthly"]
        segments = ["free", "premium", "enterprise"]

        for period in periods:
            for segment in segments:
                # Simulate churn rate calculation
                base_churn = {"daily": 0.5, "weekly": 2.0, "monthly": 5.0}
                segment_modifier = {"free": 1.5, "premium": 0.8, "enterprise": 0.3}

                churn_rate = base_churn[period] * segment_modifier[segment]

                self.churn_rate.labels(
                    service_name=self.config.service_name,
                    environment="production",
                    period=period,
                    segment=segment,
                ).set(churn_rate)

    def track_user_session_end(self, session_id: str, user_segment: str = "unknown"):
        """Track when a user session ends"""
        if session_id in self._active_sessions:
            session = self._active_sessions[session_id]
            duration = (datetime.utcnow() - session["start_time"]).total_seconds()

            self.user_session_duration.labels(
                service_name=self.config.service_name,
                environment="production",
                user_segment=user_segment,
            ).observe(duration)

            del self._active_sessions[session_id]

    def track_support_ticket(self, priority: str, category: str, channel: str = "web"):
        """Track support ticket creation"""
        self.support_tickets_total.labels(
            service_name=self.config.service_name,
            environment="production",
            priority=priority,
            category=category,
            channel=channel,
        ).inc()

    def update_nps_score(self, score: float, period: str = "monthly"):
        """Update Net Promoter Score"""
        self.nps_score.labels(
            service_name=self.config.service_name,
            environment="production",
            period=period,
        ).set(score)

    def get_metrics(self) -> str:
        """Get all business metrics in Prometheus format"""
        return generate_latest(self.registry).decode("utf-8")

    @asynccontextmanager
    async def user_session(self, user_id: str, session_id: str, user_segment: str = "unknown"):
        """Context manager for tracking user sessions"""
        # Track session start
        await self.track_event(
            BusinessEvent(
                event_type=BusinessEventType.USER_LOGIN,
                user_id=user_id,
                session_id=session_id,
                properties={"user_segment": user_segment},
            )
        )

        try:
            yield session_id
        finally:
            # Track session end
            self.track_user_session_end(session_id, user_segment)


# Factory function for easy setup
def create_business_metrics_collector(
    service_name: str, **config_kwargs
) -> BusinessMetricsCollector:
    """Create a configured business metrics collector"""
    config = BusinessMetricsConfig(service_name=service_name, **config_kwargs)
    return BusinessMetricsCollector(config)
