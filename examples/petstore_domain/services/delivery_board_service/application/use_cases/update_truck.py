"""Update Truck Use Case.

This use case handles updating an existing truck's properties.
"""

from dataclasses import dataclass
from typing import Optional

from examples.petstore_domain.services.delivery_board_service.application.ports.truck_repository import (
    TruckRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Truck,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    TruckId,
)


@dataclass
class UpdateTruckCommand:
    """Command object for updating a truck."""

    truck_id: str
    name: Optional[str] = None
    capacity: Optional[int] = None
    region: Optional[str] = None


@dataclass
class UpdateTruckResult:
    """Result of updating a truck."""

    truck_id: str
    name: str
    capacity: int
    region: Optional[str]
    current_load: int
    success: bool
    error_message: Optional[str] = None


class UpdateTruckUseCase:
    """Use case for updating an existing truck.

    This use case:
    1. Finds the truck by ID
    2. Validates the update is valid
    3. Updates the truck properties
    4. Persists the changes
    """

    def __init__(
        self,
        truck_repository: TruckRepositoryPort,
    ) -> None:
        """Initialize the use case.

        Args:
            truck_repository: Repository for accessing trucks
        """
        self._truck_repository = truck_repository

    def execute(self, command: UpdateTruckCommand) -> UpdateTruckResult:
        """Execute the use case.

        Args:
            command: Command containing truck ID and fields to update

        Returns:
            Result containing the updated truck details or error
        """
        # Find truck
        truck_id = TruckId(command.truck_id)
        truck = self._truck_repository.find_by_id(truck_id)

        if truck is None:
            return UpdateTruckResult(
                truck_id=command.truck_id,
                name="",
                capacity=0,
                region=None,
                current_load=0,
                success=False,
                error_message=f"Truck {command.truck_id} not found",
            )

        # Apply updates
        if command.name is not None:
            if not command.name:
                return UpdateTruckResult(
                    truck_id=command.truck_id,
                    name=truck.name,
                    capacity=truck.capacity,
                    region=truck.region,
                    current_load=truck.current_load,
                    success=False,
                    error_message="Truck name cannot be empty",
                )
            truck.name = command.name

        if command.capacity is not None:
            if command.capacity <= 0:
                return UpdateTruckResult(
                    truck_id=command.truck_id,
                    name=truck.name,
                    capacity=truck.capacity,
                    region=truck.region,
                    current_load=truck.current_load,
                    success=False,
                    error_message="Truck capacity must be positive",
                )
            if command.capacity < truck.current_load:
                return UpdateTruckResult(
                    truck_id=command.truck_id,
                    name=truck.name,
                    capacity=truck.capacity,
                    region=truck.region,
                    current_load=truck.current_load,
                    success=False,
                    error_message=f"Cannot reduce capacity below current load ({truck.current_load})",
                )
            truck.capacity = command.capacity

        if command.region is not None:
            truck.region = command.region

        # Persist changes
        self._truck_repository.update(truck)

        return UpdateTruckResult(
            truck_id=str(truck.id),
            name=truck.name,
            capacity=truck.capacity,
            region=truck.region,
            current_load=truck.current_load,
            success=True,
        )
