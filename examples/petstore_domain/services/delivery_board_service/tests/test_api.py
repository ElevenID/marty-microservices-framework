"""API adapter tests for Delivery Board Service.

Tests the FastAPI HTTP endpoints using TestClient.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from examples.petstore_domain.services.delivery_board_service.application.use_cases.create_delivery import (
    CreateDeliveryResult,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.get_delivery import (
    DeliveryItemResult,
    GetDeliveryResult,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.list_trucks import (
    ListTrucksResult,
    TruckSummary,
)
from examples.petstore_domain.services.delivery_board_service.domain.exceptions import (
    DeliveryNotFoundError,
    NoAvailableTruckError,
)
from examples.petstore_domain.services.delivery_board_service.infrastructure.adapters.input.api import (
    create_delivery_router,
)


@pytest.fixture
def mock_use_cases():
    """Create mock use cases for testing."""
    return {
        "create_delivery": AsyncMock(),
        "get_delivery": MagicMock(),
        "list_deliveries": MagicMock(),
        "complete_delivery": AsyncMock(),
        "list_trucks": MagicMock(),
        "cancel_delivery": AsyncMock(),
        "update_truck": MagicMock(),
    }


@pytest.fixture
def client(mock_use_cases):
    """Create a test client with mocked use cases."""
    app = FastAPI()
    router = create_delivery_router(
        create_delivery_use_case=mock_use_cases["create_delivery"],
        get_delivery_use_case=mock_use_cases["get_delivery"],
        list_deliveries_use_case=mock_use_cases["list_deliveries"],
        complete_delivery_use_case=mock_use_cases["complete_delivery"],
        cancel_delivery_use_case=mock_use_cases["cancel_delivery"],
        list_trucks_use_case=mock_use_cases["list_trucks"],
        update_truck_use_case=mock_use_cases["update_truck"],
    )
    app.include_router(router)
    return TestClient(app)


class TestListTrucksEndpoint:
    """Tests for GET /trucks endpoint."""

    def test_list_trucks_success(self, client, mock_use_cases):
        """Test listing all trucks."""
        mock_use_cases["list_trucks"].execute.return_value = ListTrucksResult(
            trucks=[
                TruckSummary(
                    truck_id="truck-1",
                    name="Truck Alpha",
                    capacity=10,
                    current_load=3,
                    region="North",
                    auto_scaled=False,
                    available=True,
                ),
                TruckSummary(
                    truck_id="truck-2",
                    name="Truck Beta",
                    capacity=8,
                    current_load=8,
                    region="South",
                    auto_scaled=True,
                    available=False,
                ),
            ],
            total_count=2,
            total_capacity=18,
            total_load=11,
        )

        response = client.get("/trucks")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert data["total_capacity"] == 18
        assert data["total_load"] == 11
        assert len(data["trucks"]) == 2
        assert data["trucks"][0]["name"] == "Truck Alpha"
        assert data["trucks"][0]["available"] is True
        assert data["trucks"][1]["available"] is False

    def test_list_trucks_empty(self, client, mock_use_cases):
        """Test listing when no trucks exist."""
        mock_use_cases["list_trucks"].execute.return_value = ListTrucksResult(
            trucks=[],
            total_count=0,
            total_capacity=0,
            total_load=0,
        )

        response = client.get("/trucks")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["trucks"] == []


class TestCreateDeliveryEndpoint:
    """Tests for POST /deliveries endpoint."""

    def test_create_delivery_success(self, client, mock_use_cases):
        """Test successful delivery creation."""
        mock_use_cases["create_delivery"].execute.return_value = CreateDeliveryResult(
            delivery_id="delivery-123",
            order_id="order-456",
            truck_id="truck-1",
            status="queued",
            eta_minutes=30,
            priority="standard",
        )

        response = client.post(
            "/deliveries",
            json={
                "order_id": "order-456",
                "address": "123 Main St",
                "items": [
                    {"description": "Pet Food", "quantity": 2},
                    {"description": "Pet Toy", "quantity": 1},
                ],
                "priority": "standard",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "delivery-123"
        assert data["order_id"] == "order-456"
        assert data["truck_id"] == "truck-1"
        assert data["eta_minutes"] == 30

    def test_create_delivery_express_priority(self, client, mock_use_cases):
        """Test delivery creation with express priority."""
        mock_use_cases["create_delivery"].execute.return_value = CreateDeliveryResult(
            delivery_id="delivery-789",
            order_id="order-999",
            truck_id="truck-2",
            status="queued",
            eta_minutes=15,
            priority="express",
        )

        response = client.post(
            "/deliveries",
            json={
                "order_id": "order-999",
                "address": "456 Oak Ave",
                "items": [{"description": "Urgent Pet Medicine", "quantity": 1}],
                "priority": "express",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["priority"] == "express"
        assert data["eta_minutes"] == 15

    def test_create_delivery_validation_error(self, client, mock_use_cases):
        """Test delivery creation with invalid data."""
        # Empty order_id should fail validation
        response = client.post(
            "/deliveries",
            json={
                "order_id": "",
                "address": "123 Main St",
                "items": [{"description": "Item", "quantity": 1}],
            },
        )

        assert response.status_code == 422  # Validation error

    def test_create_delivery_empty_items(self, client, mock_use_cases):
        """Test delivery creation with no items."""
        response = client.post(
            "/deliveries",
            json={
                "order_id": "order-123",
                "address": "123 Main St",
                "items": [],
            },
        )

        # FastAPI may validate this or the use case may reject it
        # Depending on implementation, this could be 422 or 400
        assert response.status_code in [400, 422]


class TestGetDeliveryEndpoint:
    """Tests for GET /deliveries/{delivery_id} endpoint."""

    def test_get_delivery_success(self, client, mock_use_cases):
        """Test successful delivery retrieval."""
        mock_use_cases["get_delivery"].execute.return_value = GetDeliveryResult(
            delivery_id="delivery-123",
            order_id="order-456",
            address="123 Main St",
            items=[
                DeliveryItemResult(description="Pet Food", quantity=2),
            ],
            status="in_transit",
            truck_id="truck-1",
            eta_minutes=15,
            priority="standard",
            created_at=datetime(2025, 1, 1, 10, 0, 0),
            updated_at=datetime(2025, 1, 1, 10, 30, 0),
        )

        response = client.get("/deliveries/delivery-123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "delivery-123"
        assert data["status"] == "in_transit"
        assert len(data["items"]) == 1

    def test_get_delivery_not_found(self, client, mock_use_cases):
        """Test getting a non-existent delivery."""
        mock_use_cases["get_delivery"].execute.side_effect = DeliveryNotFoundError("nonexistent")

        response = client.get("/deliveries/nonexistent")

        assert response.status_code == 404


class TestCompleteDeliveryEndpoint:
    """Tests for POST /deliveries/{delivery_id}/complete endpoint."""

    def test_complete_delivery_success(self, client, mock_use_cases):
        """Test successful delivery completion."""
        from examples.petstore_domain.services.delivery_board_service.application.use_cases.complete_delivery import (
            CompleteDeliveryResult,
        )
        from examples.petstore_domain.services.delivery_board_service.domain.entities import (
            Delivery,
            DeliveryItem,
        )
        from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
            DeliveryId,
            DeliveryStatus,
            TruckId,
        )

        # Create a mock delivery for the result
        mock_delivery = Delivery(
            id=DeliveryId("delivery-123"),
            order_id="order-456",
            address="123 Main St",
            items=[DeliveryItem("Pet Food", 1)],
            status=DeliveryStatus.DELIVERED,
            truck_id=TruckId("truck-1"),
            eta_minutes=0,
        )

        mock_use_cases["complete_delivery"].execute.return_value = CompleteDeliveryResult(
            delivery=mock_delivery,
            success=True,
        )

        response = client.post("/deliveries/delivery-123/complete")

        assert response.status_code == 200
