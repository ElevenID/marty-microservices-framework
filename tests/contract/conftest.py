"""
Contract Test Configuration

This module provides pytest configuration and fixtures for contract testing.
Contract tests validate API specifications, data schemas, and service contracts.
"""

import json
from pathlib import Path
from typing import Any, Dict

import pytest
import requests

# Test configuration
CONTRACT_TEST_TIMEOUT = 30
API_BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def api_client():
    """Provides an HTTP client for API contract testing."""
    session = requests.Session()
    session.timeout = CONTRACT_TEST_TIMEOUT
    yield session
    session.close()


@pytest.fixture(scope="session")
def openapi_spec():
    """Loads the OpenAPI specification for contract validation."""
    spec_path = Path(__file__).parent.parent.parent / "docs" / "openapi.json"
    if spec_path.exists():
        with open(spec_path) as f:
            return json.load(f)
    return None


@pytest.fixture
def identity_service_contract():
    """Defines the expected contract for the identity service."""
    return {
        "endpoints": {
            "/health": {
                "methods": ["GET"],
                "response_schema": {
                    "type": "object",
                    "required": ["status", "service"],
                    "properties": {
                        "status": {"type": "string"},
                        "service": {"type": "string"}
                    }
                }
            },
            "/authenticate": {
                "methods": ["POST"],
                "request_schema": {
                    "type": "object",
                    "required": ["username", "password"],
                    "properties": {
                        "username": {"type": "string"},
                        "password": {"type": "string"}
                    }
                },
                "response_schema": {
                    "type": "object",
                    "required": ["success"],
                    "properties": {
                        "success": {"type": "boolean"},
                        "user_id": {"type": ["string", "null"]},
                        "username": {"type": ["string", "null"]},
                        "authenticated_at": {"type": ["string", "null"]},
                        "expires_at": {"type": ["string", "null"]},
                        "error_message": {"type": ["string", "null"]}
                    }
                }
            }
        }
    }


@pytest.fixture
def schema_validator():
    """Provides JSON schema validation functionality."""
    from jsonschema import Draft7Validator

    def validate_schema(data: Dict[Any, Any], schema: Dict[str, Any]) -> bool:
        validator = Draft7Validator(schema)
        return validator.is_valid(data)

    return validate_schema


# Contract test markers
pytest.mark.contract = pytest.mark.contract
pytest.mark.api_contract = pytest.mark.api_contract
pytest.mark.schema_validation = pytest.mark.schema_validation
pytest.mark.backward_compatibility = pytest.mark.backward_compatibility
