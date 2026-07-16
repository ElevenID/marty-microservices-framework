"""Domain exceptions for Delivery Board Service.

These exceptions represent domain-specific error conditions.
They have no external dependencies.
"""


class DeliveryDomainError(Exception):
    """Base exception for all Delivery domain errors."""

    pass


class DeliveryNotFoundError(DeliveryDomainError):
    """Raised when a delivery cannot be found."""

    def __init__(self, delivery_id: str) -> None:
        self.delivery_id = delivery_id
        super().__init__(f"Delivery with id '{delivery_id}' not found")


class TruckNotFoundError(DeliveryDomainError):
    """Raised when a truck cannot be found."""

    def __init__(self, truck_id: str) -> None:
        self.truck_id = truck_id
        super().__init__(f"Truck with id '{truck_id}' not found")


class NoAvailableTruckError(DeliveryDomainError):
    """Raised when no truck is available for delivery."""

    def __init__(self) -> None:
        super().__init__("No truck available for delivery")


class InvalidDeliveryStateError(DeliveryDomainError):
    """Raised when a delivery state transition is invalid."""

    def __init__(self, delivery_id: str, current_status: str, target_status: str) -> None:
        self.delivery_id = delivery_id
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Cannot transition delivery '{delivery_id}' from {current_status} to {target_status}"
        )
