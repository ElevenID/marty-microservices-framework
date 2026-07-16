"""FastAPI HTTP Adapter for Pet Service.

This is a driving (input) adapter that handles HTTP requests and
translates them into application use case calls.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from examples.petstore_domain.services.pet_service.application.use_cases.create_pet import (
    CreatePetCommand,
    CreatePetUseCase,
)
from examples.petstore_domain.services.pet_service.application.use_cases.delete_pet import (
    DeletePetCommand,
    DeletePetUseCase,
)
from examples.petstore_domain.services.pet_service.application.use_cases.get_pet import (
    GetPetQuery,
    GetPetUseCase,
)
from examples.petstore_domain.services.pet_service.application.use_cases.list_pets import (
    ListPetsUseCase,
    PaginationQuery,
)
from examples.petstore_domain.services.pet_service.domain.exceptions import (
    PetNotFoundError,
)

# =============================================================================
# Request/Response DTOs (Data Transfer Objects)
# =============================================================================


class CreatePetRequest(BaseModel):
    """HTTP request body for creating a pet."""

    name: str = Field(..., min_length=1, description="Pet's name")
    species: str = Field(..., description="Type of animal (dog, cat, bird, fish, reptile, other)")
    age: int = Field(..., ge=0, description="Pet's age in years")
    owner_id: Optional[str] = Field(None, description="Optional owner reference")


class PetResponse(BaseModel):
    """HTTP response body for a pet."""

    id: str
    name: str
    species: str
    age: int
    owner_id: Optional[str]


class PetListResponse(BaseModel):
    """HTTP response body for listing pets."""

    pets: list[PetResponse]
    total_count: int
    limit: int
    offset: int
    has_more: bool


class DeleteResponse(BaseModel):
    """HTTP response body for delete operations."""

    success: bool
    message: str


# =============================================================================
# Router Factory
# =============================================================================


def create_pet_router(
    create_pet_use_case: CreatePetUseCase,
    get_pet_use_case: GetPetUseCase,
    list_pets_use_case: ListPetsUseCase,
    delete_pet_use_case: DeletePetUseCase,
) -> APIRouter:
    """Create a FastAPI router with all pet endpoints.

    This factory function receives use cases via dependency injection,
    keeping the infrastructure layer decoupled from concrete implementations.

    Args:
        create_pet_use_case: Use case for creating pets
        get_pet_use_case: Use case for retrieving a pet
        list_pets_use_case: Use case for listing pets
        delete_pet_use_case: Use case for deleting pets

    Returns:
        Configured APIRouter with all pet endpoints
    """
    router = APIRouter(prefix="/pets", tags=["pets"])

    @router.post(
        "",
        response_model=PetResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a new pet",
    )
    async def create_pet(request: CreatePetRequest) -> PetResponse:
        """Create a new pet in the system."""
        command = CreatePetCommand(
            name=request.name,
            species=request.species,
            age=request.age,
            owner_id=request.owner_id,
        )

        try:
            result = await create_pet_use_case.execute(command)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        return PetResponse(
            id=result.pet_id,
            name=result.name,
            species=result.species,
            age=result.age,
            owner_id=result.owner_id,
        )

    @router.get(
        "/{pet_id}",
        response_model=PetResponse,
        summary="Get a pet by ID",
    )
    async def get_pet(pet_id: str) -> PetResponse:
        """Retrieve a pet by its unique identifier."""
        query = GetPetQuery(pet_id=pet_id)

        try:
            result = get_pet_use_case.execute(query)
        except PetNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        return PetResponse(
            id=result.pet_id,
            name=result.name,
            species=result.species,
            age=result.age,
            owner_id=result.owner_id,
        )

    @router.get(
        "",
        response_model=PetListResponse,
        summary="List all pets",
    )
    async def list_pets(
        limit: int = Query(20, ge=1, le=100, description="Maximum number of pets to return"),
        offset: int = Query(0, ge=0, description="Number of pets to skip"),
    ) -> PetListResponse:
        """Retrieve all pets in the system with pagination."""
        pagination = PaginationQuery(limit=limit, offset=offset)
        result = list_pets_use_case.execute(pagination)

        return PetListResponse(
            pets=[
                PetResponse(
                    id=pet.pet_id,
                    name=pet.name,
                    species=pet.species,
                    age=pet.age,
                    owner_id=pet.owner_id,
                )
                for pet in result.pets
            ],
            total_count=result.total_count,
            limit=result.limit,
            offset=result.offset,
            has_more=result.has_more,
        )

    @router.delete(
        "/{pet_id}",
        response_model=DeleteResponse,
        summary="Delete a pet",
    )
    async def delete_pet(pet_id: str) -> DeleteResponse:
        """Delete a pet by its unique identifier."""
        command = DeletePetCommand(pet_id=pet_id)

        try:
            result = delete_pet_use_case.execute(command)
        except PetNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        return DeleteResponse(
            success=result.success,
            message=f"Pet {pet_id} deleted successfully",
        )

    return router
