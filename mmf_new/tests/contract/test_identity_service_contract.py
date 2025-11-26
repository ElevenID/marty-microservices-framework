"""
Contract Tests for Identity Service API

These tests validate API contracts, ensuring backward compatibility
and correct schema validation for the identity service.
"""

import pytest
import requests
from jsonschema import ValidationError, validate


@pytest.mark.contract
@pytest.mark.api_contract
class TestIdentityServiceContract:
    """Test suite for identity service API contracts."""

    def test_health_endpoint_contract(
        self, api_client, api_base_url, identity_service_contract, schema_validator
    ):
        """Test health endpoint contract compliance."""
        # Get expected schema
        health_schema = identity_service_contract["endpoints"]["/health"]["response_schema"]

        # Make request
        response = api_client.get(f"{api_base_url}/health")

        # Validate contract
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/json"

        # Validate response schema
        response_data = response.json()
        assert schema_validator(response_data, health_schema)

        # Validate required fields
        assert "status" in response_data
        assert "service" in response_data
        assert response_data["status"] == "healthy"
        assert response_data["service"] == "identity"

    def test_authenticate_endpoint_request_contract(
        self, api_client, identity_service_contract, schema_validator
    ):
        """Test authenticate endpoint request contract."""
        auth_contract = identity_service_contract["endpoints"]["/authenticate"]
        request_schema = auth_contract["request_schema"]

        # Test valid request
        valid_request = {"username": "admin", "password": "admin123"}

        assert schema_validator(valid_request, request_schema)

        # Test invalid requests should fail schema validation
        invalid_requests = [
            {},  # Missing required fields
            {"username": "admin"},  # Missing password
            {"password": "admin123"},  # Missing username
            {"username": 123, "password": "admin123"},  # Wrong type
            {"username": "admin", "password": 123},  # Wrong type
        ]

        for invalid_request in invalid_requests:
            assert not schema_validator(invalid_request, request_schema)

    def test_authenticate_endpoint_response_contract(
        self, api_client, api_base_url, identity_service_contract, schema_validator
    ):
        """Test authenticate endpoint response contract."""
        auth_contract = identity_service_contract["endpoints"]["/authenticate"]
        response_schema = auth_contract["response_schema"]

        # Test successful authentication response
        response = api_client.post(
            f"{api_base_url}/authenticate", json={"username": "admin", "password": "admin123"}
        )

        assert response.status_code == 200
        response_data = response.json()

        # Validate response schema
        assert schema_validator(response_data, response_schema)

        # Validate successful response structure
        assert response_data["success"] is True
        assert isinstance(response_data["user_id"], str)
        assert isinstance(response_data["username"], str)
        assert isinstance(response_data["authenticated_at"], str)
        assert isinstance(response_data["expires_at"], str)
        assert response_data["error_message"] is None

    def test_authenticate_failure_response_contract(
        self, api_client, api_base_url, identity_service_contract, schema_validator
    ):
        """Test authenticate endpoint failure response contract."""
        auth_contract = identity_service_contract["endpoints"]["/authenticate"]
        response_schema = auth_contract["response_schema"]

        # Test failed authentication response
        response = api_client.post(
            f"{api_base_url}/authenticate", json={"username": "admin", "password": "wrong_password"}
        )

        assert response.status_code == 200
        response_data = response.json()

        # Validate response schema
        assert schema_validator(response_data, response_schema)

        # Validate failure response structure
        assert response_data["success"] is False
        assert response_data["user_id"] is None
        assert response_data["username"] is None
        assert response_data["authenticated_at"] is None
        assert response_data["expires_at"] is None
        assert isinstance(response_data["error_message"], str)


@pytest.mark.contract
@pytest.mark.schema_validation
class TestDataSchemaValidation:
    """Test suite for data schema validation."""

    def test_user_id_schema(self, schema_validator):
        """Test UserId value object schema."""
        user_id_schema = {
            "type": "string",
            "pattern": "^user_[0-9]+$",
            "minLength": 6,
            "maxLength": 20,
        }

        # Valid user IDs
        valid_user_ids = ["user_1", "user_123", "user_999999"]
        for user_id in valid_user_ids:
            assert schema_validator(user_id, user_id_schema)

        # Invalid user IDs
        invalid_user_ids = [
            "user",  # Too short
            "123",  # Wrong format
            "user_",  # Missing number
            "user_abc",  # Non-numeric
            "x" * 25,  # Too long
        ]
        for user_id in invalid_user_ids:
            assert not schema_validator(user_id, user_id_schema)

    def test_credentials_schema(self, schema_validator):
        """Test Credentials value object schema."""
        credentials_schema = {
            "type": "object",
            "required": ["username", "password"],
            "properties": {
                "username": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 50,
                    "pattern": "^[a-zA-Z0-9_]+$",
                },
                "password": {"type": "string", "minLength": 1, "maxLength": 100},
            },
            "additionalProperties": False,
        }

        # Valid credentials
        valid_credentials = [
            {"username": "admin", "password": "admin123"},
            {"username": "user_123", "password": "p@ssw0rd!"},
            {"username": "a", "password": "x"},
        ]
        for creds in valid_credentials:
            assert schema_validator(creds, credentials_schema)

        # Invalid credentials
        invalid_credentials = [
            {},  # Missing required fields
            {"username": "admin"},  # Missing password
            {"password": "admin123"},  # Missing username
            {"username": "", "password": "admin123"},  # Empty username
            {"username": "admin", "password": ""},  # Empty password
            {"username": "admin@domain.com", "password": "admin123"},  # Invalid username format
            {"username": "x" * 51, "password": "admin123"},  # Username too long
            {"username": "admin", "password": "x" * 101},  # Password too long
        ]
        for creds in invalid_credentials:
            assert not schema_validator(creds, credentials_schema)


@pytest.mark.contract
@pytest.mark.backward_compatibility
class TestBackwardCompatibility:
    """Test suite for backward compatibility validation."""

    def test_api_version_compatibility(self, api_client, api_base_url):
        """Test API version backward compatibility."""
        # Test that older API versions still work
        headers = {"API-Version": "1.0"}
        response = api_client.get(f"{api_base_url}/health", headers=headers)

        assert response.status_code == 200
        assert "status" in response.json()

    def test_response_field_presence(self, api_client, api_base_url):
        """Test that all expected response fields are present."""
        # Test authentication response has all expected fields
        response = api_client.post(
            f"{api_base_url}/authenticate", json={"username": "admin", "password": "admin123"}
        )

        response_data = response.json()
        expected_fields = {
            "success",
            "user_id",
            "username",
            "authenticated_at",
            "expires_at",
            "error_message",
        }

        assert expected_fields <= set(response_data.keys())

    def test_field_type_consistency(self, api_client, api_base_url):
        """Test that field types remain consistent."""
        response = api_client.post(
            f"{api_base_url}/authenticate", json={"username": "admin", "password": "admin123"}
        )

        response_data = response.json()

        # Type consistency checks
        assert isinstance(response_data["success"], bool)
        if response_data["user_id"] is not None:
            assert isinstance(response_data["user_id"], str)
        if response_data["username"] is not None:
            assert isinstance(response_data["username"], str)
        if response_data["authenticated_at"] is not None:
            assert isinstance(response_data["authenticated_at"], str)
        if response_data["expires_at"] is not None:
            assert isinstance(response_data["expires_at"], str)
        if response_data["error_message"] is not None:
            assert isinstance(response_data["error_message"], str)

    def test_error_response_format_consistency(self, api_client, api_base_url):
        """Test that error responses maintain consistent format."""
        # Test various error scenarios
        error_scenarios = [
            {"username": "nonexistent", "password": "password"},
            {"username": "admin", "password": "wrong"},
            {"username": "", "password": ""},
        ]

        for scenario in error_scenarios:
            response = api_client.post(f"{api_base_url}/authenticate", json=scenario)
            response_data = response.json()

            # All error responses should have consistent structure
            assert "success" in response_data
            assert "error_message" in response_data
            assert response_data["success"] is False
            assert isinstance(response_data["error_message"], str)
