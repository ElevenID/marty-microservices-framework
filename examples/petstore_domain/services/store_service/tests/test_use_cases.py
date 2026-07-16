"""Use case tests for Store Service."""

from unittest.mock import AsyncMock, Mock

import pytest

from examples.petstore_domain.services.store_service.application.ports.catalog_repository import (
    CatalogRepositoryPort,
)
from examples.petstore_domain.services.store_service.application.ports.order_repository import (
    OrderRepositoryPort,
)
from examples.petstore_domain.services.store_service.application.sagas.order_fulfillment import (
    OrderFulfillmentSaga,
)
from examples.petstore_domain.services.store_service.application.use_cases.create_order import (
    CreateOrderCommand,
    CreateOrderUseCase,
)
from examples.petstore_domain.services.store_service.domain.entities import CatalogItem
from examples.petstore_domain.services.store_service.domain.events import (
    OrderPlacedEvent,
)
from examples.petstore_domain.services.store_service.domain.value_objects import Money
from mmf.framework.events.enhanced_event_bus import EnhancedEventBus
from mmf.framework.patterns.saga.orchestrator import SagaOrchestrator


@pytest.fixture
def mock_catalog_repo():
    return Mock(spec=CatalogRepositoryPort)


@pytest.fixture
def mock_order_repo():
    return Mock(spec=OrderRepositoryPort)


@pytest.fixture
def mock_event_bus():
    return AsyncMock(spec=EnhancedEventBus)


@pytest.fixture
def mock_saga():
    return AsyncMock(spec=OrderFulfillmentSaga)


@pytest.mark.asyncio
async def test_create_order_use_case(
    mock_catalog_repo, mock_order_repo, mock_event_bus
):
    """Test creating an order successfully."""
    # Setup catalog item
    item = CatalogItem(
        pet_id="corgi",
        name="Corgi",
        species="dog",
        price=Money.from_float(1000.0),
        quantity=5,
        delivery_lead_days=1
    )
    mock_catalog_repo.find_by_pet_id.return_value = item

    use_case = CreateOrderUseCase(
        catalog_repository=mock_catalog_repo,
        order_repository=mock_order_repo,
        event_bus=mock_event_bus,
    )

    command = CreateOrderCommand(
        pet_id="corgi",
        quantity=1,
        customer_name="Alice",
        delivery_address="123 Wonderland",
        delivery_requested=True
    )

    result = await use_case.execute(command)

    # Verify result
    assert result.pet_id == "corgi"
    assert result.total_price == 1000.0
    assert result.status == "pending"

    # Verify stock reduced
    mock_catalog_repo.update.assert_called_once()
    updated_item = mock_catalog_repo.update.call_args[0][0]
    assert updated_item.quantity == 4

    # Verify order saved
    mock_order_repo.save.assert_called_once()

    # Verify event published
    mock_event_bus.publish.assert_called_once()
    event = mock_event_bus.publish.call_args[0][0]
    assert isinstance(event, OrderPlacedEvent)
    assert event.data["total_amount"] == 1000.0
