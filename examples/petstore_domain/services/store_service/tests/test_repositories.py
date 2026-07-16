"""Repository adapter tests for Store Service.

Tests the in-memory repository implementations to ensure proper
storage, retrieval, and domain entity mapping.
"""

from decimal import Decimal

import pytest

from examples.petstore_domain.services.store_service.domain.entities import (
    CatalogItem,
    Order,
)
from examples.petstore_domain.services.store_service.domain.value_objects import (
    Money,
    OrderId,
    OrderStatus,
)
from examples.petstore_domain.services.store_service.infrastructure.adapters.output.in_memory_catalog_repository import (
    InMemoryCatalogRepository,
)
from examples.petstore_domain.services.store_service.infrastructure.adapters.output.in_memory_order_repository import (
    InMemoryOrderRepository,
)


class TestInMemoryOrderRepository:
    """Tests for InMemoryOrderRepository."""

    def _create_order(
        self,
        order_id: OrderId | None = None,
        pet_id: str = "pet-123",
        quantity: int = 1,
        status: OrderStatus = OrderStatus.PENDING
    ) -> Order:
        """Helper to create a test order."""
        return Order(
            id=order_id or OrderId.generate(),
            pet_id=pet_id,
            quantity=quantity,
            customer_name="John Doe",
            status=status,
            total_price=Money.from_float(99.99),
            delivery_requested=True,
            delivery_address="123 Main St"
        )

    def test_save_and_find_by_id(self):
        """Test saving an order and retrieving it by ID."""
        repo = InMemoryOrderRepository()
        order_id = OrderId.generate()
        order = self._create_order(order_id, pet_id="pet-456", quantity=2)

        repo.save(order)
        found = repo.find_by_id(order_id)

        assert found is not None
        assert found.id == order_id
        assert found.pet_id == "pet-456"
        assert found.quantity == 2
        assert found.customer_name == "John Doe"
        assert found.status == OrderStatus.PENDING

    def test_find_by_id_not_found(self):
        """Test finding a non-existent order returns None."""
        repo = InMemoryOrderRepository()
        order_id = OrderId.generate()

        found = repo.find_by_id(order_id)

        assert found is None

    def test_find_all(self):
        """Test retrieving all orders."""
        repo = InMemoryOrderRepository()
        order1 = self._create_order(pet_id="pet-1")
        order2 = self._create_order(pet_id="pet-2")
        order3 = self._create_order(pet_id="pet-3")

        repo.save(order1)
        repo.save(order2)
        repo.save(order3)
        all_orders = repo.find_all()

        assert len(all_orders) == 3
        pet_ids = {o.pet_id for o in all_orders}
        assert pet_ids == {"pet-1", "pet-2", "pet-3"}

    def test_find_all_empty(self):
        """Test find_all returns empty list when no orders exist."""
        repo = InMemoryOrderRepository()

        all_orders = repo.find_all()

        assert all_orders == []

    def test_update(self):
        """Test updating an existing order."""
        repo = InMemoryOrderRepository()
        order_id = OrderId.generate()
        order = self._create_order(order_id, status=OrderStatus.PENDING)
        repo.save(order)

        # Update the order status (simulating confirm)
        order.status = OrderStatus.CONFIRMED
        repo.update(order)

        found = repo.find_by_id(order_id)
        assert found is not None
        assert found.status == OrderStatus.CONFIRMED

    def test_clear(self):
        """Test clearing all orders from memory."""
        repo = InMemoryOrderRepository()
        repo.save(self._create_order())
        repo.save(self._create_order())

        repo.clear()

        assert len(repo.find_all()) == 0

    def test_order_status_transitions(self):
        """Test order status can be transitioned correctly."""
        repo = InMemoryOrderRepository()
        order_id = OrderId.generate()
        order = self._create_order(order_id, status=OrderStatus.PENDING)
        repo.save(order)

        # Transition through valid states
        order.status = OrderStatus.CONFIRMED
        repo.update(order)

        found = repo.find_by_id(order_id)
        assert found is not None
        assert found.status == OrderStatus.CONFIRMED

        order.status = OrderStatus.PROCESSING
        repo.update(order)

        found = repo.find_by_id(order_id)
        assert found is not None
        assert found.status == OrderStatus.PROCESSING

    def test_money_value_object_persisted(self):
        """Test that Money value object is properly persisted."""
        repo = InMemoryOrderRepository()
        order_id = OrderId.generate()
        price = Money(amount=Decimal("149.99"), currency="USD")
        order = Order(
            id=order_id,
            pet_id="pet-123",
            quantity=1,
            customer_name="Jane Doe",
            status=OrderStatus.PENDING,
            total_price=price,
        )

        repo.save(order)
        found = repo.find_by_id(order_id)

        assert found is not None
        assert found.total_price.amount == Decimal("149.99")
        assert found.total_price.currency == "USD"


class TestInMemoryCatalogRepository:
    """Tests for InMemoryCatalogRepository."""

    def _create_catalog_item(
        self,
        pet_id: str = "pet-123",
        name: str = "Golden Retriever",
        quantity: int = 5
    ) -> CatalogItem:
        """Helper to create a test catalog item."""
        return CatalogItem(
            pet_id=pet_id,
            name=name,
            species="dog",
            price=Money.from_float(299.99),
            quantity=quantity,
            delivery_lead_days=2
        )

    def test_save_and_find_by_id(self):
        """Test saving a catalog item and retrieving it by ID."""
        repo = InMemoryCatalogRepository()
        item = self._create_catalog_item(pet_id="pet-456", name="Persian Cat")

        repo.save(item)
        found = repo.find_by_pet_id("pet-456")

        assert found is not None
        assert found.pet_id == "pet-456"
        assert found.name == "Persian Cat"
        assert found.species == "dog"

    def test_find_by_id_not_found(self):
        """Test finding a non-existent catalog item returns None."""
        repo = InMemoryCatalogRepository()

        found = repo.find_by_pet_id("nonexistent")

        assert found is None

    def test_find_all(self):
        """Test retrieving all catalog items."""
        repo = InMemoryCatalogRepository()
        repo.save(self._create_catalog_item(pet_id="pet-1", name="Item 1"))
        repo.save(self._create_catalog_item(pet_id="pet-2", name="Item 2"))

        all_items = repo.find_all()

        assert len(all_items) == 2

    def test_stock_operations(self):
        """Test stock reduction and addition."""
        repo = InMemoryCatalogRepository()
        item = self._create_catalog_item(pet_id="pet-123", quantity=10)
        repo.save(item)

        # Reduce stock
        found = repo.find_by_pet_id("pet-123")
        assert found is not None
        assert found.is_in_stock()

        found.reduce_stock(3)
        assert found.quantity == 7

        found.add_stock(5)
        assert found.quantity == 12

    def test_reduce_stock_insufficient(self):
        """Test reducing stock beyond available raises error."""
        item = self._create_catalog_item(quantity=2)

        with pytest.raises(ValueError, match="Insufficient stock"):
            item.reduce_stock(5)

    def test_is_in_stock(self):
        """Test is_in_stock method."""
        item_with_stock = self._create_catalog_item(quantity=5)
        item_no_stock = self._create_catalog_item(pet_id="pet-empty", quantity=0)

        assert item_with_stock.is_in_stock() is True
        assert item_no_stock.is_in_stock() is False
