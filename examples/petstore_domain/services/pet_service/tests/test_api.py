"""API adapter tests for Pet Service.

Tests the FastAPI HTTP endpoints using TestClient.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from examples.petstore_domain.services.pet_service.application.use_cases.create_pet import (
    CreatePetResult,
)
from examples.petstore_domain.services.pet_service.application.use_cases.delete_pet import (
    DeletePetResult,
)
from examples.petstore_domain.services.pet_service.application.use_cases.get_pet import (
    GetPetResult,
)
from examples.petstore_domain.services.pet_service.application.use_cases.list_pets import (
    ListPetsResult,
    PetSummary,
)
from examples.petstore_domain.services.pet_service.domain.exceptions import (
    PetNotFoundError,
)
from examples.petstore_domain.services.pet_service.infrastructure.adapters.input.api import (
    create_pet_router,
)


@pytest.fixture
def mock_use_cases():
    """Create mock use cases for testing."""
    return {
        "create_pet": AsyncMock(),
        "get_pet": MagicMock(),
        "list_pets": MagicMock(),
        "delete_pet": MagicMock(),
    }


@pytest.fixture
def client(mock_use_cases):
    """Create a test client with mocked use cases."""
    app = FastAPI()
    router = create_pet_router(
        create_pet_use_case=mock_use_cases["create_pet"],
        get_pet_use_case=mock_use_cases["get_pet"],
        list_pets_use_case=mock_use_cases["list_pets"],
        delete_pet_use_case=mock_use_cases["delete_pet"],
    )
    app.include_router(router)
    return TestClient(app)


class TestCreatePetEndpoint:
    """Tests for POST /pets endpoint."""

    def test_create_pet_success(self, client, mock_use_cases):
        """Test successful pet creation."""
        mock_use_cases["create_pet"].execute.return_value = CreatePetResult(
            pet_id="pet-123",
            name="Buddy",
            species="dog",
            age=3,
            owner_id=None,
        )

        response = client.post(
            "/pets",
            json={
                "name": "Buddy",
                "species": "dog",
                "age": 3,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "pet-123"
        assert data["name"] == "Buddy"
        assert data["species"] == "dog"
        assert data["age"] == 3

    def test_create_pet_with_owner(self, client, mock_use_cases):
        """Test pet creation with owner ID."""
        mock_use_cases["create_pet"].execute.return_value = CreatePetResult(
            pet_id="pet-456",
            name="Max",
            species="cat",
            age=2,
            owner_id="owner-789",
        )

        response = client.post(
            "/pets",
            json={
                "name": "Max",
                "species": "cat",
                "age": 2,
                "owner_id": "owner-789",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["owner_id"] == "owner-789"

    def test_create_pet_validation_error(self, client, mock_use_cases):
        """Test pet creation with invalid data."""
        # Empty name should fail validation
        response = client.post(
            "/pets",
            json={
                "name": "",
                "species": "dog",
                "age": 3,
            },
        )

        assert response.status_code == 422  # Validation error

    def test_create_pet_negative_age(self, client, mock_use_cases):
        """Test pet creation with negative age."""
        response = client.post(
            "/pets",
            json={
                "name": "Buddy",
                "species": "dog",
                "age": -1,
            },
        )

        assert response.status_code == 422  # Validation error


class TestGetPetEndpoint:
    """Tests for GET /pets/{pet_id} endpoint."""

    def test_get_pet_success(self, client, mock_use_cases):
        """Test successful pet retrieval."""
        mock_use_cases["get_pet"].execute.return_value = GetPetResult(
            pet_id="pet-123",
            name="Buddy",
            species="dog",
            age=3,
            owner_id=None,
        )

        response = client.get("/pets/pet-123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "pet-123"
        assert data["name"] == "Buddy"

    def test_get_pet_not_found(self, client, mock_use_cases):
        """Test getting a non-existent pet."""
        mock_use_cases["get_pet"].execute.side_effect = PetNotFoundError("nonexistent")

        response = client.get("/pets/nonexistent")

        assert response.status_code == 404


class TestListPetsEndpoint:
    """Tests for GET /pets endpoint."""

    def test_list_pets_success(self, client, mock_use_cases):
        """Test listing all pets."""
        mock_use_cases["list_pets"].execute.return_value = ListPetsResult(
            pets=[
                PetSummary(pet_id="pet-1", name="Buddy", species="dog", age=3, owner_id=None),
                PetSummary(pet_id="pet-2", name="Max", species="cat", age=2, owner_id="owner-1"),
            ],
            total_count=2,
        )

        response = client.get("/pets")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["pets"]) == 2
        assert data["pets"][0]["name"] == "Buddy"
        assert data["pets"][1]["name"] == "Max"

    def test_list_pets_empty(self, client, mock_use_cases):
        """Test listing when no pets exist."""
        mock_use_cases["list_pets"].execute.return_value = ListPetsResult(
            pets=[],
            total_count=0,
        )

        response = client.get("/pets")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["pets"] == []


class TestDeletePetEndpoint:
    """Tests for DELETE /pets/{pet_id} endpoint."""

    def test_delete_pet_success(self, client, mock_use_cases):
        """Test successful pet deletion."""
        mock_use_cases["delete_pet"].execute.return_value = DeletePetResult(
            pet_id="pet-123",
            success=True,
        )

        response = client.delete("/pets/pet-123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "pet-123" in data["message"]

    def test_delete_pet_not_found(self, client, mock_use_cases):
        """Test deleting a non-existent pet."""
        mock_use_cases["delete_pet"].execute.side_effect = PetNotFoundError("nonexistent")

        response = client.delete("/pets/nonexistent")

        assert response.status_code == 404
