"""List Trucks Use Case.

This use case handles retrieving all trucks in the fleet.
"""

from dataclasses import dataclass
from typing import Optional

from examples.petstore_domain.services.delivery_board_service.application.ports.truck_repository import (
    TruckRepositoryPort,
)


@dataclass
class TruckSummary:
    """Summary information for a truck."""

    truck_id: str
    name: str
    capacity: int
    current_load: int
    region: Optional[str]
    auto_scaled: bool
    available: bool


@dataclass
class ListTrucksResult:
    """Result of listing trucks."""

    trucks: list[TruckSummary]
    total_count: int
    total_capacity: int
    total_load: int


class ListTrucksUseCase:
    """Use case for listing all trucks."""

    def __init__(self, truck_repository: TruckRepositoryPort) -> None:
        """Initialize the use case with required dependencies."""
        self._truck_repository = truck_repository

    def execute(self) -> ListTrucksResult:
        """Execute the list trucks use case.

        Returns:
            Result containing list of truck summaries and fleet stats
        """
        trucks = self._truck_repository.find_all()

        summaries = [
            TruckSummary(
                truck_id=str(truck.id),
                name=truck.name,
                capacity=truck.capacity,
                current_load=truck.current_load,
                region=truck.region,
                auto_scaled=truck.auto_scaled,
                available=truck.is_available(),
            )
            for truck in trucks
        ]

        return ListTrucksResult(
            trucks=summaries,
            total_count=len(summaries),
            total_capacity=sum(t.capacity for t in trucks),
            total_load=sum(t.current_load for t in trucks),
        )
