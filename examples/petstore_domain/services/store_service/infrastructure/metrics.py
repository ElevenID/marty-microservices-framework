"""Business Metrics for Store Service.

This module defines custom business metrics for the store service
using the MMF FrameworkMetrics helper.
"""

from mmf.framework.observability.framework_metrics import FrameworkMetrics


class StoreMetrics(FrameworkMetrics):
    """Business metrics for the Store Service.

    Provides custom metrics for tracking orders, inventory, and
    store performance.
    """

    def __init__(self) -> None:
        """Initialize store service metrics."""
        super().__init__("store_service")

        # Business metrics for orders
        self.orders_placed = self.create_counter(
            "orders_placed_total",
            "Total number of orders placed",
            ["delivery_requested"],
        )

        self.order_total_amount = self.create_counter(
            "order_total_amount",
            "Total monetary value of orders",
            ["currency"],
        )

        # Inventory metrics
        self.catalog_items = self.create_gauge(
            "catalog_items_total",
            "Total number of distinct items in catalog",
        )

        self.item_stock_level = self.create_gauge(
            "item_stock_level",
            "Current stock level for catalog items",
            ["pet_id", "pet_name"],
        )

        self.out_of_stock_items = self.create_gauge(
            "out_of_stock_items",
            "Number of catalog items currently out of stock",
        )

        # Performance metrics
        self.order_processing_duration = self.create_histogram(
            "order_processing_duration_seconds",
            "Time to process an order from creation to confirmation",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        )

        self.catalog_list_duration = self.create_histogram(
            "catalog_list_duration_seconds",
            "Time to retrieve the catalog",
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0],
        )

    def record_order_placed(self, delivery_requested: bool = True) -> None:
        """Record a new order placement."""
        if self.orders_placed:
            self.orders_placed.labels(
                delivery_requested=str(delivery_requested), service=self.service_name
            ).inc()

    def record_order_amount(self, amount: float, currency: str = "USD") -> None:
        """Record the total value of an order."""
        if self.order_total_amount:
            self.order_total_amount.labels(
                currency=currency, service=self.service_name
            ).inc(amount)

    def update_catalog_item_count(self, count: int) -> None:
        """Update the total number of catalog items."""
        if self.catalog_items:
            self.catalog_items.labels(service=self.service_name).set(count)

    def update_item_stock(self, pet_id: str, pet_name: str, stock_level: int) -> None:
        """Update stock level for a catalog item."""
        if self.item_stock_level:
            self.item_stock_level.labels(
                pet_id=pet_id, pet_name=pet_name, service=self.service_name
            ).set(stock_level)

    def update_out_of_stock_count(self, count: int) -> None:
        """Update the count of out-of-stock items."""
        if self.out_of_stock_items:
            self.out_of_stock_items.labels(service=self.service_name).set(count)

    def record_order_processing_duration(self, duration_seconds: float) -> None:
        """Record the time taken to process an order."""
        if self.order_processing_duration:
            self.order_processing_duration.labels(service=self.service_name).observe(
                duration_seconds
            )

    def record_catalog_list_duration(self, duration_seconds: float) -> None:
        """Record the time taken to retrieve the catalog."""
        if self.catalog_list_duration:
            self.catalog_list_duration.labels(service=self.service_name).observe(
                duration_seconds
            )


# Singleton instance for the service
_metrics: StoreMetrics | None = None


def get_store_metrics() -> StoreMetrics:
    """Get or create the store metrics singleton.

    Returns:
        StoreMetrics instance
    """
    global _metrics
    if _metrics is None:
        _metrics = StoreMetrics()
    return _metrics
