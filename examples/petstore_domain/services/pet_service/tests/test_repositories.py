"""Repository adapter tests for Pet Service.

Tests the in-memory repository implementations to ensure proper
storage, retrieval, and domain entity mapping.
"""

import pytest

from examples.petstore_domain.services.pet_service.domain.entities import Pet
from examples.petstore_domain.services.pet_service.domain.exceptions import (
    DuplicatePetError,
)
from examples.petstore_domain.services.pet_service.domain.value_objects import (
    PetId,
    Species,
)
from examples.petstore_domain.services.pet_service.infrastructure.adapters.output.in_memory_repository import (
    InMemoryPetRepository,
)


class TestInMemoryPetRepository:
    """Tests for InMemoryPetRepository."""

    def _create_pet(
        self,
        pet_id: PetId | None = None,
        name: str = "Buddy",
        species: Species = Species.DOG,
        age: int = 3
    ) -> Pet:
        """Helper to create a test pet."""
        return Pet(
            id=pet_id or PetId.generate(),
            name=name,
            species=species,
            age=age
        )

    def test_save_and_find_by_id(self):
        """Test saving a pet and retrieving it by ID."""
        repo = InMemoryPetRepository()
        pet_id = PetId.generate()
        pet = self._create_pet(pet_id, name="Max", species=Species.CAT, age=5)

        repo.save(pet)
        found = repo.find_by_id(pet_id)

        assert found is not None
        assert found.id == pet_id
        assert found.name == "Max"
        assert found.species == Species.CAT
        assert found.age == 5

    def test_save_duplicate_raises_error(self):
        """Test saving a pet with duplicate ID raises DuplicatePetError."""
        repo = InMemoryPetRepository()
        pet_id = PetId.generate()
        pet = self._create_pet(pet_id)

        repo.save(pet)

        with pytest.raises(DuplicatePetError) as exc_info:
            repo.save(pet)

        assert exc_info.value.pet_id == str(pet_id)

    def test_find_by_id_not_found(self):
        """Test finding a non-existent pet returns None."""
        repo = InMemoryPetRepository()
        pet_id = PetId.generate()

        found = repo.find_by_id(pet_id)

        assert found is None

    def test_find_all(self):
        """Test retrieving all pets."""
        repo = InMemoryPetRepository()
        pet1 = self._create_pet(name="Pet 1")
        pet2 = self._create_pet(name="Pet 2")
        pet3 = self._create_pet(name="Pet 3")

        repo.save(pet1)
        repo.save(pet2)
        repo.save(pet3)
        all_pets = repo.find_all()

        assert len(all_pets) == 3
        names = {p.name for p in all_pets}
        assert names == {"Pet 1", "Pet 2", "Pet 3"}

    def test_find_all_empty(self):
        """Test find_all returns empty list when no pets exist."""
        repo = InMemoryPetRepository()

        all_pets = repo.find_all()

        assert all_pets == []

    def test_delete_existing_pet(self):
        """Test deleting an existing pet returns True."""
        repo = InMemoryPetRepository()
        pet_id = PetId.generate()
        pet = self._create_pet(pet_id)
        repo.save(pet)

        result = repo.delete(pet_id)

        assert result is True
        assert repo.find_by_id(pet_id) is None

    def test_delete_non_existent_pet(self):
        """Test deleting a non-existent pet returns False."""
        repo = InMemoryPetRepository()
        pet_id = PetId.generate()

        result = repo.delete(pet_id)

        assert result is False

    def test_exists(self):
        """Test checking if a pet exists."""
        repo = InMemoryPetRepository()
        pet_id = PetId.generate()
        pet = self._create_pet(pet_id)

        assert repo.exists(pet_id) is False

        repo.save(pet)

        assert repo.exists(pet_id) is True

    def test_clear(self):
        """Test clearing all pets from memory."""
        repo = InMemoryPetRepository()
        repo.save(self._create_pet(name="Pet 1"))
        repo.save(self._create_pet(name="Pet 2"))

        repo.clear()

        assert len(repo.find_all()) == 0
        assert repo.count() == 0

    def test_count(self):
        """Test counting pets in the repository."""
        repo = InMemoryPetRepository()

        assert repo.count() == 0

        repo.save(self._create_pet(name="Pet 1"))
        assert repo.count() == 1

        repo.save(self._create_pet(name="Pet 2"))
        assert repo.count() == 2

    def test_pet_entity_updates_are_reflected(self):
        """Test that entity updates are reflected in the repository."""
        repo = InMemoryPetRepository()
        pet_id = PetId.generate()
        pet = self._create_pet(pet_id, name="Original", age=2)
        repo.save(pet)

        # Modify the entity (note: in-memory stores references)
        found = repo.find_by_id(pet_id)
        assert found is not None
        found.update_name("Updated")
        found.celebrate_birthday()

        # Changes should be visible since it's the same object
        found_again = repo.find_by_id(pet_id)
        assert found_again is not None
        assert found_again.name == "Updated"
        assert found_again.age == 3

    def test_assign_and_remove_owner(self):
        """Test owner assignment and removal are persisted."""
        repo = InMemoryPetRepository()
        pet_id = PetId.generate()
        pet = self._create_pet(pet_id)
        repo.save(pet)

        found = repo.find_by_id(pet_id)
        assert found is not None
        assert found.owner_id is None

        found.assign_owner("owner-123")

        found_again = repo.find_by_id(pet_id)
        assert found_again is not None
        assert found_again.owner_id == "owner-123"

        found_again.remove_owner()

        found_final = repo.find_by_id(pet_id)
        assert found_final is not None
        assert found_final.owner_id is None
