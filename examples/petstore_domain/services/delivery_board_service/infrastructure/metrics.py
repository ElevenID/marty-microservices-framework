"""Business Metrics for Delivery Board Service.

This module defines custom business metrics for the delivery board service
using the MMF FrameworkMetrics helper.
"""

from mmf.framework.observability.framework_metrics import FrameworkMetrics


class DeliveryMetrics(FrameworkMetrics):
    """Business metrics for the Delivery Board Service.

    Provides custom metrics for tracking delivery operations, truck
    utilization, and service performance.
    """

    def __init__(self) -> None:
        """Initialize delivery board metrics."""
        super().__init__("delivery_board_service")

        # Business metrics for deliveries
        self.deliveries_created = self.create_counter(
            "deliveries_created_total",
            "Total number of deliveries created",
            ["priority"],
        )

        self.deliveries_completed = self.create_counter(
            "deliveries_completed_total",
            "Total number of deliveries completed successfully",
            ["priority"],
        )

        self.deliveries_cancelled = self.create_counter(
            "deliveries_cancelled_total",
            "Total number of deliveries cancelled",
            ["reason"],
        )

        self.delivery_duration = self.create_histogram(
            "delivery_duration_seconds",
            "Time from delivery creation to completion",
            ["priority"],
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 28800],  # 1min to 8hrs
        )

        # Truck metrics
        self.trucks_active = self.create_gauge(
            "trucks_active",
            "Number of trucks currently with assigned deliveries",
        )

        self.truck_utilization = self.create_gauge(
            "truck_utilization_percent",
            "Truck capacity utilization percentage",
            ["truck_id", "truck_name"],
        )

        self.truck_assignments = self.create_counter(
            "truck_assignments_total",
            "Total number of truck assignments",
            ["truck_id"],
        )

        # Operational metrics
        self.no_truck_available = self.create_counter(
            "no_truck_available_total",
            "Number of times no truck was available for delivery",
        )

        self.pending_deliveries = self.create_gauge(
            "pending_deliveries",
            "Number of deliveries waiting to be dispatched",
        )

    def record_delivery_created(self, priority: str = "standard") -> None:
        """Record a new delivery creation."""
        if self.deliveries_created:
            self.deliveries_created.labels(
                priority=priority, service=self.service_name
            ).inc()

    def record_delivery_completed(self, priority: str = "standard") -> None:
        """Record a delivery completion."""
        if self.deliveries_completed:
            self.deliveries_completed.labels(
                priority=priority, service=self.service_name
            ).inc()

    def record_delivery_cancelled(self, reason: str = "user_request") -> None:
        """Record a delivery cancellation."""
        if self.deliveries_cancelled:
            self.deliveries_cancelled.labels(
                reason=reason, service=self.service_name
            ).inc()

    def record_delivery_duration(
        self, duration_seconds: float, priority: str = "standard"
    ) -> None:
        """Record delivery completion duration."""
        if self.delivery_duration:
            self.delivery_duration.labels(
                priority=priority, service=self.service_name
            ).observe(duration_seconds)

    def record_truck_assignment(self, truck_id: str) -> None:
        """Record a truck being assigned to a delivery."""
        if self.truck_assignments:
            self.truck_assignments.labels(
                truck_id=truck_id, service=self.service_name
            ).inc()

    def record_no_truck_available(self) -> None:
        """Record that no truck was available."""
        if self.no_truck_available:
            self.no_truck_available.labels(service=self.service_name).inc()

    def update_truck_utilization(
        self, truck_id: str, truck_name: str, utilization_percent: float
    ) -> None:
        """Update truck utilization gauge."""
        if self.truck_utilization:
            self.truck_utilization.labels(
                truck_id=truck_id,
                truck_name=truck_name,
                service=self.service_name,
            ).set(utilization_percent)

    def update_pending_deliveries(self, count: int) -> None:
        """Update pending deliveries gauge."""
        if self.pending_deliveries:
            self.pending_deliveries.labels(service=self.service_name).set(count)

    def update_active_trucks(self, count: int) -> None:
        """Update active trucks gauge."""
        if self.trucks_active:
            self.trucks_active.labels(service=self.service_name).set(count)


# Singleton instance for the service
_metrics: DeliveryMetrics | None = None


def get_delivery_metrics() -> DeliveryMetrics:
    """Get or create the delivery metrics singleton.

    Returns:
        DeliveryMetrics instance
    """
    global _metrics
    if _metrics is None:
        _metrics = DeliveryMetrics()
    return _metrics
