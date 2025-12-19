"""Get Catalog Use Case.

This use case handles retrieving catalog items.
"""

from dataclasses import dataclass

from examples.petstore_domain.services.store_service.application.ports.catalog_repository import (
    CatalogRepositoryPort,
)


@dataclass
class CatalogItemSummary:
    """Summary information for a catalog item."""

    pet_id: str
    name: str
    species: str
    price: float
    quantity: int
    delivery_lead_days: int
    in_stock: bool


@dataclass
class GetCatalogResult:
    """Result of listing catalog items."""

    items: list[CatalogItemSummary]
    total_count: int


class GetCatalogUseCase:
    """Use case for retrieving catalog items.

    This use case:
    1. Retrieves all catalog items from the repository
    2. Maps them to summary objects
    3. Returns the list with count
    """

    def __init__(self, catalog_repository: CatalogRepositoryPort) -> None:
        """Initialize the use case with required dependencies.

        Args:
            catalog_repository: Port for catalog persistence operations
        """
        self._catalog_repository = catalog_repository

    def execute(self) -> GetCatalogResult:
        """Execute the get catalog use case.

        Returns:
            Result containing list of catalog item summaries
        """
        items = self._catalog_repository.find_all()

        summaries = [
            CatalogItemSummary(
                pet_id=item.pet_id,
                name=item.name,
                species=item.species,
                price=item.price.to_float(),
                quantity=item.quantity,
                delivery_lead_days=item.delivery_lead_days,
                in_stock=item.is_in_stock(),
            )
            for item in items
        ]

        return GetCatalogResult(
            items=summaries,
            total_count=len(summaries),
        )
