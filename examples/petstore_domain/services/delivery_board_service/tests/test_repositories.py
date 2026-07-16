"""Repository adapter tests for Delivery Board Service.

Tests the in-memory repository implementations to ensure proper
storage, retrieval, and domain entity mapping.
"""

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
from examples.petstore_domain.services.delivery_board_service.infrastructure.adapters.output.in_memory_delivery_repository import (
    InMemoryDeliveryRepository,
)
from examples.petstore_domain.services.delivery_board_service.infrastructure.adapters.output.in_memory_truck_repository import (
    InMemoryTruckRepository,
)


class TestInMemoryTruckRepository:
    """Tests for InMemoryTruckRepository."""

    def test_save_and_find_by_id(self):
        """Test saving a truck and retrieving it by ID."""
        repo = InMemoryTruckRepository()
        truck_id = TruckId.generate()
        truck = Truck(
            id=truck_id,
            name="Test Truck",
            capacity=10,
            region="North"
        )

        repo.save(truck)
        found = repo.find_by_id(truck_id)

        assert found is not None
        assert found.id == truck_id
        assert found.name == "Test Truck"
        assert found.capacity == 10
        assert found.region == "North"

    def test_find_by_id_not_found(self):
        """Test finding a non-existent truck returns None."""
        repo = InMemoryTruckRepository()
        truck_id = TruckId.generate()

        found = repo.find_by_id(truck_id)

        assert found is None

    def test_find_all(self):
        """Test retrieving all trucks."""
        repo = InMemoryTruckRepository()
        truck1 = Truck(id=TruckId.generate(), name="Truck 1", capacity=5)
        truck2 = Truck(id=TruckId.generate(), name="Truck 2", capacity=10)

        repo.save(truck1)
        repo.save(truck2)
        all_trucks = repo.find_all()

        assert len(all_trucks) == 2
        names = {t.name for t in all_trucks}
        assert names == {"Truck 1", "Truck 2"}

    def test_find_available(self):
        """Test finding trucks with available capacity."""
        repo = InMemoryTruckRepository()
        available_truck = Truck(id=TruckId.generate(), name="Available", capacity=5, current_load=2)
        full_truck = Truck(id=TruckId.generate(), name="Full", capacity=3, current_load=3)

        repo.save(available_truck)
        repo.save(full_truck)
        available = repo.find_available()

        assert len(available) == 1
        assert available[0].name == "Available"

    def test_update(self):
        """Test updating an existing truck."""
        repo = InMemoryTruckRepository()
        truck_id = TruckId.generate()
        truck = Truck(id=truck_id, name="Original", capacity=5)
        repo.save(truck)

        # Modify and update
        truck.assign_delivery()
        repo.update(truck)

        found = repo.find_by_id(truck_id)
        assert found is not None
        assert found.current_load == 1

    def test_clear(self):
        """Test clearing all trucks from memory."""
        repo = InMemoryTruckRepository()
        repo.save(Truck(id=TruckId.generate(), name="Truck 1", capacity=5))
        repo.save(Truck(id=TruckId.generate(), name="Truck 2", capacity=5))

        repo.clear()

        assert len(repo.find_all()) == 0


class TestInMemoryDeliveryRepository:
    """Tests for InMemoryDeliveryRepository."""

    def _create_delivery(
        self,
        delivery_id: DeliveryId | None = None,
        status: DeliveryStatus = DeliveryStatus.QUEUED
    ) -> Delivery:
        """Helper to create a test delivery."""
        return Delivery(
            id=delivery_id or DeliveryId.generate(),
            order_id="order-123",
            address="123 Test St",
            items=[DeliveryItem("Test Item", 1)],
            status=status,
            truck_id=TruckId.generate(),
            eta_minutes=30,
            priority="standard"
        )

    def test_save_and_find_by_id(self):
        """Test saving a delivery and retrieving it by ID."""
        repo = InMemoryDeliveryRepository()
        delivery_id = DeliveryId.generate()
        delivery = self._create_delivery(delivery_id)

        repo.save(delivery)
        found = repo.find_by_id(delivery_id)

        assert found is not None
        assert found.id == delivery_id
        assert found.order_id == "order-123"
        assert found.address == "123 Test St"
        assert len(found.items) == 1

    def test_find_by_id_not_found(self):
        """Test finding a non-existent delivery returns None."""
        repo = InMemoryDeliveryRepository()
        delivery_id = DeliveryId.generate()

        found = repo.find_by_id(delivery_id)

        assert found is None

    def test_find_all(self):
        """Test retrieving all deliveries."""
        repo = InMemoryDeliveryRepository()
        delivery1 = self._create_delivery()
        delivery2 = self._create_delivery()

        repo.save(delivery1)
        repo.save(delivery2)
        all_deliveries = repo.find_all()

        assert len(all_deliveries) == 2

    def test_update(self):
        """Test updating an existing delivery."""
        repo = InMemoryDeliveryRepository()
        delivery_id = DeliveryId.generate()
        delivery = self._create_delivery(delivery_id, DeliveryStatus.ASSIGNED)
        repo.save(delivery)

        # Update status
        delivery.start_transit()
        repo.update(delivery)

        found = repo.find_by_id(delivery_id)
        assert found is not None
        assert found.status == DeliveryStatus.IN_TRANSIT

    def test_clear(self):
        """Test clearing all deliveries from memory."""
        repo = InMemoryDeliveryRepository()
        repo.save(self._create_delivery())
        repo.save(self._create_delivery())

        repo.clear()

        assert len(repo.find_all()) == 0

    def test_delivery_status_transitions(self):
        """Test that status transitions are persisted correctly."""
        repo = InMemoryDeliveryRepository()
        delivery_id = DeliveryId.generate()
        delivery = self._create_delivery(delivery_id, DeliveryStatus.ASSIGNED)
        repo.save(delivery)

        # Progress through states
        delivery.start_transit()
        repo.update(delivery)

        found = repo.find_by_id(delivery_id)
        assert found is not None
        assert found.status == DeliveryStatus.IN_TRANSIT

        delivery.complete()
        repo.update(delivery)

        found = repo.find_by_id(delivery_id)
        assert found is not None
        assert found.status == DeliveryStatus.DELIVERED
