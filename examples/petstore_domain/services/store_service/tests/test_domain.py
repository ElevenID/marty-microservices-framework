from decimal import Decimal

import pytest

from examples.petstore_domain.services.store_service.domain.entities import Order
from examples.petstore_domain.services.store_service.domain.value_objects import (
    Money,
    OrderId,
    OrderStatus,
)


def test_order_creation():
    order_id = OrderId.generate()
    order = Order(
        id=order_id,
        pet_id="pet-123",
        quantity=1,
        customer_name="John Doe",
        status=OrderStatus.PENDING,
        total_price=Money.from_float(100.0),
        delivery_requested=True,
        delivery_address="123 Main St"
    )

    assert order.id == order_id
    assert order.pet_id == "pet-123"
    assert order.quantity == 1
    assert order.status == OrderStatus.PENDING
    assert order.total_price.amount == Decimal("100.0")

def test_order_validation():
    order_id = OrderId.generate()
    with pytest.raises(ValueError):
        Order(
            id=order_id,
            pet_id="", # Invalid
            quantity=1,
            customer_name="John Doe",
            status=OrderStatus.PENDING,
            total_price=Money.from_float(100.0),
            delivery_requested=False
        )

    with pytest.raises(ValueError):
        Order(
            id=order_id,
            pet_id="pet-123",
            quantity=0, # Invalid
            customer_name="John Doe",
            status=OrderStatus.PENDING,
            total_price=Money.from_float(100.0),
            delivery_requested=False
        )
