"""Domain tests for Pet Service."""

import pytest

from examples.petstore_domain.services.pet_service.domain.entities import Pet
from examples.petstore_domain.services.pet_service.domain.value_objects import (
    PetId,
    Species,
)


def test_pet_creation():
    """Test creating a valid pet entity."""
    pet_id = PetId.generate()
    pet = Pet(
        id=pet_id,
        name="Fluffy",
        species=Species.DOG,
        age=3,
        owner_id="owner-123"
    )

    assert pet.id == pet_id
    assert pet.name == "Fluffy"
    assert pet.species == Species.DOG
    assert pet.age == 3
    assert pet.owner_id == "owner-123"


def test_pet_validation_empty_name():
    """Test validation for empty name."""
    with pytest.raises(ValueError, match="Pet name cannot be empty"):
        Pet(
            id=PetId.generate(),
            name="",
            species=Species.CAT,
            age=1
        )


def test_pet_validation_negative_age():
    """Test validation for negative age."""
    with pytest.raises(ValueError, match="Pet age cannot be negative"):
        Pet(
            id=PetId.generate(),
            name="Whiskers",
            species=Species.CAT,
            age=-1
        )


def test_pet_update_name():
    """Test updating pet name."""
    pet = Pet(
        id=PetId.generate(),
        name="Old Name",
        species=Species.BIRD,
        age=2
    )

    pet.update_name("New Name")
    assert pet.name == "New Name"


def test_pet_celebrate_birthday():
    """Test birthday celebration increments age."""
    pet = Pet(
        id=PetId.generate(),
        name="Birthday Boy",
        species=Species.DOG,
        age=5
    )

    pet.celebrate_birthday()
    assert pet.age == 6
