import os
from collections.abc import AsyncGenerator

import httpx
import pytest

# Default to the URL used in deploy/test.sh
BASE_URL = os.getenv("IDENTITY_SERVICE_URL", "http://identity.local:8080")


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client for testing."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        yield client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_health_check(client: httpx.AsyncClient):
    """Test the health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    # Assert basic health structure if known, otherwise just status is good for now
    assert isinstance(data, dict)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_users(client: httpx.AsyncClient):
    """Test retrieving users."""
    response = await client.get("/users")
    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list) or isinstance(users, dict)
    # Based on bash script: curl -s "$BASE_URL/users" | jq .
    # It seems to return a list or dict of users.


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_authentication_flow(client: httpx.AsyncClient):
    """Test the full authentication flow."""
    # 1. Authenticate successfully
    login_data = {
        "username": "admin",
        "password": "admin123",  # pragma: allowlist secret
    }
    response = await client.post("/authenticate", json=login_data)

    assert response.status_code == 200
    auth_data = response.json()

    # Check for success flag as per bash script
    # if echo "$response" | jq -r '.success' | grep -q true; then
    assert auth_data.get("success") is True, f"Authentication failed: {auth_data}"

    # Assuming there might be a token in the response for further requests
    # token = auth_data.get("token")
    # if token:
    #     # Verify we can use the token (if there's a protected endpoint)
    #     headers = {"Authorization": f"Bearer {token}"}
    #     # Example: response = await client.get("/users/me", headers=headers)
    #     # assert response.status_code == 200


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_authentication_failure(client: httpx.AsyncClient):
    """Test authentication with invalid credentials."""
    login_data = {
        "username": "admin",
        "password": "wrongpassword",  # pragma: allowlist secret
    }
    response = await client.post("/authenticate", json=login_data)

    # Depending on implementation, this might be 401 or 200 with success=False
    # The bash script just checks for success=true for success case.
    # Let's assume it returns 401 or success=False

    if response.status_code == 200:
        auth_data = response.json()
        assert auth_data.get("success") is False
    else:
        assert response.status_code in [401, 403]
