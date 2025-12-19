"""
Consumer-Driven Contract Tests: Gateway ↔ Identity Service

This module implements Pact-based contract tests for the interaction between
the Gateway (consumer) and the Identity Service (provider).

The Gateway depends on the Identity Service for:
1. Token validation (POST /auth/validate)
2. User info retrieval (GET /auth/me)
3. Health checks (GET /health)

These tests ensure that:
- The Gateway can correctly consume Identity Service responses
- Breaking changes in Identity Service are detected early
- API contracts are documented and enforced
"""

import httpx
import pytest
from pact import Pact


@pytest.mark.contract
@pytest.mark.pact
class TestGatewayIdentityContract:
    """
    Consumer-driven contract tests for Gateway consuming Identity Service.

    These tests run from the Gateway's perspective (consumer), defining
    what the Gateway expects from the Identity Service (provider).
    """

    @pytest.fixture
    def pact(self):
        """Create Pact instance for Gateway (consumer) and Identity Service (provider)."""
        return Pact("Gateway", "IdentityService")

    def test_validate_token_success(self, pact: Pact):
        """
        Contract: Gateway validates a bearer token with Identity Service.

        Given: A valid user token exists
        When: Gateway sends POST /auth/validate with Bearer token
        Then: Identity Service returns valid=True with user_id
        """
        expected_response = {"valid": True, "user_id": "user_admin"}

        (
            pact.upon_receiving("a request to validate a valid token")
            .given("a valid user token exists for user_admin")
            .with_request("POST", "/auth/validate")
            .with_header("Authorization", "Bearer user_admin")
            .will_respond_with(200)
            .with_header("Content-Type", "application/json")
            .with_body(expected_response)
        )

        with pact.serve() as srv:
            response = httpx.post(
                f"{srv.url}/auth/validate",
                headers={"Authorization": "Bearer user_admin"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert data["user_id"] == "user_admin"

    def test_validate_token_invalid(self, pact: Pact):
        """
        Contract: Gateway handles invalid token response.

        Given: No matching token exists
        When: Gateway sends POST /auth/validate with invalid token
        Then: Identity Service returns valid=False
        """
        expected_response = {"valid": False, "user_id": None}

        (
            pact.upon_receiving("a request to validate an invalid token")
            .given("no valid token exists for the provided value")
            .with_request("POST", "/auth/validate")
            .with_header("Authorization", "Bearer invalid_token_xyz")
            .will_respond_with(200)
            .with_header("Content-Type", "application/json")
            .with_body(expected_response)
        )

        with pact.serve() as srv:
            response = httpx.post(
                f"{srv.url}/auth/validate",
                headers={"Authorization": "Bearer invalid_token_xyz"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is False
            assert data["user_id"] is None

    def test_validate_token_missing_header(self, pact: Pact):
        """
        Contract: Gateway handles missing Authorization header.

        Given: Any state
        When: Gateway sends POST /auth/validate without Authorization header
        Then: Identity Service returns valid=False
        """
        expected_response = {"valid": False}

        (
            pact.upon_receiving("a token validation request without authorization header")
            .given("any state")
            .with_request("POST", "/auth/validate")
            .will_respond_with(200)
            .with_header("Content-Type", "application/json")
            .with_body(expected_response)
        )

        with pact.serve() as srv:
            response = httpx.post(f"{srv.url}/auth/validate")

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is False

    def test_get_current_user_success(self, pact: Pact):
        """
        Contract: Gateway retrieves user details from Identity Service.

        Given: A valid authenticated user exists
        When: Gateway sends GET /auth/me with valid token
        Then: Identity Service returns full user details
        """
        expected_response = {
            "user_id": "user_admin",
            "username": "admin",
            "email": "admin@example.com",
            "roles": ["admin", "user"],
            "permissions": ["read", "write", "admin"],
            "auth_method": "basic",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": None,
        }

        (
            pact.upon_receiving("a request to get current user details")
            .given("user_admin is authenticated with valid token")
            .with_request("GET", "/auth/me")
            .with_header("Authorization", "Bearer user_admin")
            .will_respond_with(200)
            .with_header("Content-Type", "application/json")
            .with_body(expected_response)
        )

        with pact.serve() as srv:
            response = httpx.get(
                f"{srv.url}/auth/me",
                headers={"Authorization": "Bearer user_admin"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "user_admin"
            assert data["username"] == "admin"
            assert "roles" in data
            assert "permissions" in data
            assert isinstance(data["roles"], list)
            assert isinstance(data["permissions"], list)

    def test_get_current_user_unauthorized(self, pact: Pact):
        """
        Contract: Gateway handles unauthorized user request.

        Given: No valid token provided
        When: Gateway sends GET /auth/me with invalid/missing token
        Then: Identity Service returns 401 Unauthorized
        """
        (
            pact.upon_receiving("a request for user details with invalid token")
            .given("no valid authentication exists")
            .with_request("GET", "/auth/me")
            .with_header("Authorization", "Bearer invalid_token")
            .will_respond_with(401)
            .with_header("Content-Type", "application/json")
            .with_body({"detail": "User not found or invalid token"})
        )

        with pact.serve() as srv:
            response = httpx.get(
                f"{srv.url}/auth/me",
                headers={"Authorization": "Bearer invalid_token"},
            )

            assert response.status_code == 401
            data = response.json()
            assert "detail" in data

    def test_health_check(self, pact: Pact):
        """
        Contract: Gateway checks Identity Service health.

        Given: Identity Service is running
        When: Gateway sends GET /health
        Then: Identity Service returns healthy status
        """
        expected_response = {"status": "healthy", "service": "identity"}

        (
            pact.upon_receiving("a health check request")
            .given("the identity service is running")
            .with_request("GET", "/health")
            .will_respond_with(200)
            .with_header("Content-Type", "application/json")
            .with_body(expected_response)
        )

        with pact.serve() as srv:
            response = httpx.get(f"{srv.url}/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "identity"

    def test_authenticate_user_success(self, pact: Pact):
        """
        Contract: Gateway authenticates user via Identity Service.

        Given: Valid user credentials exist
        When: Gateway sends POST /authenticate with credentials
        Then: Identity Service returns success with user info
        """
        request_body = {"username": "admin", "password": "admin123"}  # pragma: allowlist secret
        expected_response = {
            "success": True,
            "user_id": "user_admin",
            "username": "admin",
            "authenticated_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
            "error_message": None,
        }

        (
            pact.upon_receiving("a request to authenticate a valid user")
            .given("user admin exists with password admin123")
            .with_request("POST", "/authenticate")
            .with_header("Content-Type", "application/json")
            .with_body(request_body)
            .will_respond_with(200)
            .with_header("Content-Type", "application/json")
            .with_body(expected_response)
        )

        with pact.serve() as srv:
            response = httpx.post(
                f"{srv.url}/authenticate",
                json=request_body,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["user_id"] is not None
            assert data["username"] is not None
            assert data["error_message"] is None

    def test_authenticate_user_invalid_credentials(self, pact: Pact):
        """
        Contract: Gateway handles failed authentication.

        Given: Invalid credentials provided
        When: Gateway sends POST /authenticate with wrong password
        Then: Identity Service returns failure with error message
        """
        request_body = {
            "username": "admin",
            "password": "wrong_password",
        }  # pragma: allowlist secret
        expected_response = {
            "success": False,
            "user_id": None,
            "username": None,
            "authenticated_at": None,
            "expires_at": None,
            "error_message": "Invalid credentials",
        }

        (
            pact.upon_receiving("a request to authenticate with invalid credentials")
            .given("user admin exists but wrong password provided")
            .with_request("POST", "/authenticate")
            .with_header("Content-Type", "application/json")
            .with_body(request_body)
            .will_respond_with(200)
            .with_header("Content-Type", "application/json")
            .with_body(expected_response)
        )

        with pact.serve() as srv:
            response = httpx.post(
                f"{srv.url}/authenticate",
                json=request_body,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["user_id"] is None
            assert data["error_message"] is not None


@pytest.mark.contract
@pytest.mark.pact
class TestGatewayIdentityContractEdgeCases:
    """Edge case contract tests for Gateway ↔ Identity Service interaction."""

    @pytest.fixture
    def pact(self):
        """Create Pact instance for edge case testing."""
        return Pact("Gateway", "IdentityService")

    def test_authenticate_user_not_found(self, pact: Pact):
        """
        Contract: Gateway handles non-existent user authentication.

        Given: User does not exist
        When: Gateway sends POST /authenticate
        Then: Identity Service returns failure with appropriate error
        """
        request_body = {
            "username": "nonexistent",
            "password": "anypassword",
        }  # pragma: allowlist secret
        expected_response = {
            "success": False,
            "user_id": None,
            "username": None,
            "authenticated_at": None,
            "expires_at": None,
            "error_message": "User not found",
        }

        (
            pact.upon_receiving("a request to authenticate a non-existent user")
            .given("user nonexistent does not exist")
            .with_request("POST", "/authenticate")
            .with_header("Content-Type", "application/json")
            .with_body(request_body)
            .will_respond_with(200)
            .with_header("Content-Type", "application/json")
            .with_body(expected_response)
        )

        with pact.serve() as srv:
            response = httpx.post(
                f"{srv.url}/authenticate",
                json=request_body,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_get_user_with_minimal_permissions(self, pact: Pact):
        """
        Contract: Gateway handles user with minimal permissions.

        Given: User exists with minimal/empty permissions
        When: Gateway requests user details
        Then: Identity Service returns user with empty role/permission arrays
        """
        expected_response = {
            "user_id": "user_guest",
            "username": "guest",
            "email": None,
            "roles": [],
            "permissions": [],
            "auth_method": "basic",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": None,
        }

        (
            pact.upon_receiving("a request for a user with minimal permissions")
            .given("guest user exists with no roles or permissions")
            .with_request("GET", "/auth/me")
            .with_header("Authorization", "Bearer user_guest")
            .will_respond_with(200)
            .with_header("Content-Type", "application/json")
            .with_body(expected_response)
        )

        with pact.serve() as srv:
            response = httpx.get(
                f"{srv.url}/auth/me",
                headers={"Authorization": "Bearer user_guest"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "user_guest"
            assert data["roles"] == []
            assert data["permissions"] == []

    def test_validate_malformed_authorization_header(self, pact: Pact):
        """
        Contract: Gateway handles malformed Authorization header.

        Given: Any state
        When: Gateway sends request with malformed Authorization header
        Then: Identity Service returns valid=False
        """
        expected_response = {"valid": False}

        (
            pact.upon_receiving("a token validation with malformed authorization header")
            .given("any state")
            .with_request("POST", "/auth/validate")
            .with_header("Authorization", "NotBearer some_token")
            .will_respond_with(200)
            .with_header("Content-Type", "application/json")
            .with_body(expected_response)
        )

        with pact.serve() as srv:
            response = httpx.post(
                f"{srv.url}/auth/validate",
                headers={"Authorization": "NotBearer some_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is False
