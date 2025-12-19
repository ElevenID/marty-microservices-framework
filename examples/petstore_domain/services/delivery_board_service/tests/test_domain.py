"""Domain tests for Delivery Board Service."""

import pytest

from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Delivery,
    DeliveryItem,
    Truck,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    DeliveryId,
    DeliveryStatus,
    TruckId,
)


def test_truck_creation():
    """Test creating a valid truck entity."""
    truck_id = TruckId.generate()
    truck = Truck(
        id=truck_id,
        name="Truck 1",
        capacity=10,
        current_load=0
    )

    assert truck.id == truck_id
    assert truck.name == "Truck 1"
    assert truck.capacity == 10
    assert truck.current_load == 0
    assert truck.is_available()


def test_truck_assignment():
    """Test assigning delivery to truck."""
    truck = Truck(
        id=TruckId.generate(),
        name="Truck 1",
        capacity=2,
        current_load=0
    )

    truck.assign_delivery()
    assert truck.current_load == 1
    assert truck.is_available()  # Still has capacity

    truck.assign_delivery()
    assert truck.current_load == 2
    assert not truck.is_available()  # Full


def test_truck_overload():
    """Test assigning delivery to full truck raises error."""
    truck = Truck(
        id=TruckId.generate(),
        name="Truck 1",
        capacity=1,
        current_load=1
    )

    with pytest.raises(ValueError, match="Truck Truck 1 is at capacity"):
        truck.assign_delivery()


def test_delivery_creation():
    """Test creating a valid delivery entity."""
    delivery_id = DeliveryId.generate()
    truck_id = TruckId.generate()

    delivery = Delivery(
        id=delivery_id,
        order_id="order-123",
        address="123 Main St",
        items=[DeliveryItem("Item 1", 1)],
        status=DeliveryStatus.QUEUED,
        truck_id=truck_id,
        eta_minutes=60,
        priority="standard"
    )

    assert delivery.id == delivery_id
    assert delivery.order_id == "order-123"
    assert delivery.status == DeliveryStatus.QUEUED
