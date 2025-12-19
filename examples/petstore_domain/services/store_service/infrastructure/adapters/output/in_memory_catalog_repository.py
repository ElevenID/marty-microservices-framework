"""In-Memory Catalog Repository Adapter.

This is a driven (output) adapter that implements the CatalogRepositoryPort
interface using an in-memory dictionary.
"""

from typing import Optional

from examples.petstore_domain.services.store_service.application.ports.catalog_repository import (
    CatalogRepositoryPort,
)
from examples.petstore_domain.services.store_service.domain.entities import CatalogItem


class InMemoryCatalogRepository(CatalogRepositoryPort):
    """In-memory implementation of the catalog repository.

    This adapter stores catalog items in a dictionary.
    """

    def __init__(self) -> None:
        """Initialize the in-memory storage."""
        self._storage: dict[str, CatalogItem] = {}

    def find_by_pet_id(self, pet_id: str) -> Optional[CatalogItem]:
        """Find a catalog item by pet ID.

        Args:
            pet_id: The catalog item's unique identifier

        Returns:
            The catalog item if found, None otherwise
        """
        return self._storage.get(pet_id)

    def find_all(self) -> list[CatalogItem]:
        """Retrieve all catalog items.

        Returns:
            List of all catalog items
        """
        return list(self._storage.values())

    def save(self, item: CatalogItem) -> None:
        """Persist a catalog item.

        Args:
            item: The catalog item to save
        """
        self._storage[item.pet_id] = item

    def update(self, item: CatalogItem) -> None:
        """Update an existing catalog item.

        Args:
            item: The catalog item to update
        """
        self._storage[item.pet_id] = item

    def clear(self) -> None:
        """Clear all catalog items from memory."""
        self._storage.clear()
