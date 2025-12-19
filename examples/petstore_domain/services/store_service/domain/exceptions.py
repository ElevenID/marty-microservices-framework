"""Domain exceptions for Store Service.

These exceptions represent domain-specific error conditions.
They have no external dependencies.
"""


class StoreDomainError(Exception):
    """Base exception for all Store domain errors."""

    pass


class OrderNotFoundError(StoreDomainError):
    """Raised when an order cannot be found."""

    def __init__(self, order_id: str) -> None:
        self.order_id = order_id
        super().__init__(f"Order with id '{order_id}' not found")


class CatalogItemNotFoundError(StoreDomainError):
    """Raised when a catalog item cannot be found."""

    def __init__(self, pet_id: str) -> None:
        self.pet_id = pet_id
        super().__init__(f"Catalog item with pet_id '{pet_id}' not found")


class InsufficientStockError(StoreDomainError):
    """Raised when there's not enough stock for an order."""

    def __init__(self, pet_id: str, requested: int, available: int) -> None:
        self.pet_id = pet_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for '{pet_id}': requested {requested}, available {available}"
        )


class InvalidOrderStateError(StoreDomainError):
    """Raised when an order state transition is invalid."""

    def __init__(self, order_id: str, current_status: str, target_status: str) -> None:
        self.order_id = order_id
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Cannot transition order '{order_id}' from {current_status} to {target_status}"
        )
