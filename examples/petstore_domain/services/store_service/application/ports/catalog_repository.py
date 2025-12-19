"""Catalog Repository Port (Interface).

This is an output port defining how the application layer expects to
interact with catalog persistence.
"""

from abc import ABC, abstractmethod
from typing import Optional

from examples.petstore_domain.services.store_service.domain.entities import CatalogItem


class CatalogRepositoryPort(ABC):
    """Abstract interface for catalog persistence operations.

    This port defines the contract that any catalog repository implementation
    must fulfill.
    """

    @abstractmethod
    def find_by_pet_id(self, pet_id: str) -> Optional[CatalogItem]:
        """Find a catalog item by pet ID.

        Args:
            pet_id: The catalog item's unique identifier

        Returns:
            The catalog item if found, None otherwise
        """
        pass

    @abstractmethod
    def find_all(self) -> list[CatalogItem]:
        """Retrieve all catalog items.

        Returns:
            List of all catalog items
        """
        pass

    @abstractmethod
    def save(self, item: CatalogItem) -> None:
        """Persist a catalog item.

        Args:
            item: The catalog item to save
        """
        pass

    @abstractmethod
    def update(self, item: CatalogItem) -> None:
        """Update an existing catalog item.

        Args:
            item: The catalog item to update
        """
        pass
