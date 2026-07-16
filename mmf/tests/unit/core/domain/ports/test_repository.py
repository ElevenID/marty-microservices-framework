from typing import Optional

import pytest

from mmf.core.domain.entity import Entity
from mmf.core.domain.ports.repository import Repository


class TestEntity(Entity):
    """Test entity for repository testing."""

    def __init__(self, id: str, name: str):
        super().__init__(id)
        self.name = name


class ConcreteRepository(Repository[TestEntity]):
    """Concrete implementation of Repository for testing."""

    async def save(self, entity: TestEntity) -> TestEntity:
        return entity

    async def find_by_id(self, id: str) -> TestEntity | None:
        return TestEntity(id, "test")

    async def find_all(self, skip: int = 0, limit: int = 100) -> list[TestEntity]:
        return []

    async def update(self, id: str, updates: dict) -> TestEntity | None:
        return TestEntity(id, "updated")

    async def delete(self, id: str) -> bool:
        return True

    async def exists(self, id: str) -> bool:
        return True

    async def count(self) -> int:
        return 0


class TestRepository:
    def test_cannot_instantiate_abstract_repository(self):
        """Test that the abstract Repository class cannot be instantiated."""
        with pytest.raises(TypeError):
            Repository()

    @pytest.mark.asyncio
    async def test_concrete_repository_implementation(self):
        """Test that a concrete implementation works as expected."""
        repo = ConcreteRepository()
        entity = TestEntity("123", "test")

        saved = await repo.save(entity)
        assert saved == entity

        found = await repo.find_by_id("123")
        assert found.id == "123"
        assert found.name == "test"

        all_items = await repo.find_all()
        assert isinstance(all_items, list)

        updated = await repo.update("123", {"name": "updated"})
        assert updated.name == "updated"

        deleted = await repo.delete("123")
        assert deleted is True

        exists = await repo.exists("123")
        assert exists is True

        count = await repo.count()
        assert count == 0
