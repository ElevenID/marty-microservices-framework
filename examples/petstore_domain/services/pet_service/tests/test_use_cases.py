"""Use case tests for Pet Service."""

from unittest.mock import AsyncMock, Mock

import pytest

from examples.petstore_domain.services.pet_service.application.ports.pet_repository import (
    PetRepositoryPort,
)
from examples.petstore_domain.services.pet_service.application.use_cases.create_pet import (
    CreatePetCommand,
    CreatePetUseCase,
)
from examples.petstore_domain.services.pet_service.domain.events import PetCreatedEvent
from mmf.framework.events.enhanced_event_bus import EnhancedEventBus


@pytest.fixture
def mock_repository():
    return Mock(spec=PetRepositoryPort)


@pytest.fixture
def mock_event_bus():
    return AsyncMock(spec=EnhancedEventBus)


@pytest.mark.asyncio
async def test_create_pet_use_case(mock_repository, mock_event_bus):
    """Test creating a pet successfully."""
    use_case = CreatePetUseCase(
        pet_repository=mock_repository,
        event_bus=mock_event_bus
    )

    command = CreatePetCommand(
        name="Buddy",
        species="dog",
        age=2,
        owner_id="owner-1"
    )

    result = await use_case.execute(command)

    # Verify result
    assert result.name == "Buddy"
    assert result.species == "dog"
    assert result.age == 2
    assert result.pet_id is not None

    # Verify repository interaction
    mock_repository.save.assert_called_once()
    saved_pet = mock_repository.save.call_args[0][0]
    assert saved_pet.name == "Buddy"

    # Verify event published
    mock_event_bus.publish.assert_called_once()
    event = mock_event_bus.publish.call_args[0][0]
    assert isinstance(event, PetCreatedEvent)
    assert event.data["name"] == "Buddy"
    assert event.data["pet_id"] == result.pet_id
