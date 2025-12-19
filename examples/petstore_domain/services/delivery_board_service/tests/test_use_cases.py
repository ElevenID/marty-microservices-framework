"""Use case tests for Delivery Board Service."""

from unittest.mock import AsyncMock, Mock

import pytest

from examples.petstore_domain.services.delivery_board_service.application.ports.delivery_repository import (
    DeliveryRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.application.ports.truck_repository import (
    TruckRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.create_delivery import (
    CreateDeliveryCommand,
    CreateDeliveryUseCase,
    DeliveryItemCommand,
)
from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Truck,
)
from examples.petstore_domain.services.delivery_board_service.domain.events import (
    DeliveryScheduledEvent,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    TruckId,
)
from mmf.framework.events.enhanced_event_bus import EnhancedEventBus


@pytest.fixture
def mock_delivery_repo():
    return Mock(spec=DeliveryRepositoryPort)


@pytest.fixture
def mock_truck_repo():
    return Mock(spec=TruckRepositoryPort)


@pytest.fixture
def mock_event_bus():
    return AsyncMock(spec=EnhancedEventBus)


@pytest.mark.asyncio
async def test_create_delivery_use_case(
    mock_delivery_repo, mock_truck_repo, mock_event_bus
):
    """Test creating a delivery successfully."""
    # Setup available truck
    truck = Truck(
        id=TruckId.generate(),
        name="Test Truck",
        capacity=5,
        current_load=0
    )
    mock_truck_repo.find_available.return_value = [truck]

    use_case = CreateDeliveryUseCase(
        delivery_repository=mock_delivery_repo,
        truck_repository=mock_truck_repo,
        event_bus=mock_event_bus
    )

    command = CreateDeliveryCommand(
        order_id="order-123",
        address="123 Main St",
        items=[DeliveryItemCommand("Pet Food", 2)],
        priority="high"
    )

    result = await use_case.execute(command)

    # Verify result
    assert result.order_id == "order-123"
    assert result.truck_id == str(truck.id)
    assert result.status == "queued"

    # Verify truck updated
    mock_truck_repo.update.assert_called_once()
    updated_truck = mock_truck_repo.update.call_args[0][0]
    assert updated_truck.current_load == 1

    # Verify delivery saved
    mock_delivery_repo.save.assert_called_once()

    # Verify event published
    mock_event_bus.publish.assert_called_once()
    event = mock_event_bus.publish.call_args[0][0]
    assert isinstance(event, DeliveryScheduledEvent)
    assert event.data["order_id"] == "order-123"
    assert event.data["truck_id"] == str(truck.id)
