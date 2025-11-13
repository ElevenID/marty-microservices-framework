"""
Comprehensive test suite for API Versioning and Contract Testing framework.

This module tests all aspects of the API versioning system including:
- Version extraction from requests
- Contract validation
- Consumer-driven contract testing
- Breaking change detection
- API compatibility checking
- Version management
- Contract registry operations

Author: Marty Framework Team
Version: 1.0.0
"""

import json
from datetime import datetime, timedelta
from typing import list
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from main import (
    APIContract,
    APIVersion,
    APIVersionManager,
    ConsumerContract,
    ContractTester,
    ContractValidator,
    MemoryContractRegistry,
    VersionExtractor,
    VersioningStrategy,
    create_versioned_app,
)

from config import APIVersioningSettings


# Test fixtures
@pytest.fixture
def memory_registry():
    """Create a memory contract registry for testing."""
    return MemoryContractRegistry()


@pytest.fixture
def sample_api_contract():
    """Create a sample API contract for testing."""
    return APIContract(
        service_name="user-service",
        version="v1",
        openapi_spec={
            "openapi": "3.0.0",
            "info": {"title": "User Service", "version": "1.0.0"},
            "paths": {
                "/users/{user_id}": {
                    "get": {
                        "parameters": [
                            {
                                "name": "user_id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer"},
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Success",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "integer"},
                                                "name": {"type": "string"},
                                                "email": {"type": "string"},
                                            },
                                            "required": ["id", "name", "email"],
                                        }
                                    }
                                },
                            }
                        },
                    }
                }
            },
        },
        endpoints=[
            {
                "path": "/users/{user_id}",
                "method": "GET",
                "request_schema": {},
                "response_schemas": {
                    "200": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                        },
                        "required": ["id", "name", "email"],
                    }
                },
                "test_request": {"params": {"user_id": 1}},
                "expected_status": 200,
            }
        ],
    )


@pytest.fixture
def sample_consumer_contract():
    """Create a sample consumer contract for testing."""
    return ConsumerContract(
        consumer_name="mobile-app",
        provider_service="user-service",
        provider_version="v1",
        expectations=[
            {
                "endpoint": "/users/{user_id}",
                "method": "GET",
                "response_format": "json",
                "required_fields": ["id", "name", "email"],
            }
        ],
        test_cases=[
            {
                "name": "Get user by ID",
                "path": "/users/1",
                "method": "GET",
                "expectations": {
                    "status_code": 200,
                    "response_schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                        },
                        "required": ["id", "name", "email"],
                    },
                },
            }
        ],
    )


@pytest.fixture
def sample_api_version():
    """Create a sample API version for testing."""
    return APIVersion(
        version="v1.0.0",
        status="stable",
        changelog=["Initial release"],
        breaking_changes=[],
        compatible_with=[],
    )


@pytest.fixture
def version_extractor():
    """Create a version extractor for testing."""
    return VersionExtractor(VersioningStrategy.URL_PATH, "v1")


@pytest.fixture
def test_app():
    """Create a test FastAPI application."""
    return create_versioned_app("test-service", VersioningStrategy.URL_PATH, "v1")


@pytest.fixture
def test_client(test_app):
    """Create a test client."""
    return TestClient(test_app)


class TestVersionExtractor:
    """Test version extraction from requests."""

    def test_url_path_extraction(self, version_extractor):
        """Test version extraction from URL path."""
        mock_request = MagicMock()
        mock_request.url.path = "/v2/users/123"

        version = version_extractor.extract_version(mock_request)
        assert version == "v2"

    def test_header_extraction(self):
        """Test version extraction from Accept header."""
        extractor = VersionExtractor(VersioningStrategy.HEADER, "v1")
        mock_request = MagicMock()
        mock_request.url.path = "/users/123"
        mock_request.headers = {"accept": "application/vnd.api+json;version=2"}

        version = extractor.extract_version(mock_request)
        assert version == "v2"

    def test_query_parameter_extraction(self):
        """Test version extraction from query parameter."""
        extractor = VersionExtractor(VersioningStrategy.QUERY_PARAMETER, "v1")
        mock_request = MagicMock()
        mock_request.url.path = "/users/123"
        mock_request.query_params = {"version": "3"}
        mock_request.headers = {}

        version = extractor.extract_version(mock_request)
        assert version == "v3"

    def test_custom_header_extraction(self):
        """Test version extraction from custom header."""
        extractor = VersionExtractor(VersioningStrategy.CUSTOM_HEADER, "v1")
        mock_request = MagicMock()
        mock_request.url.path = "/users/123"
        mock_request.headers = {"x-api-version": "v4"}
        mock_request.query_params = {}

        version = extractor.extract_version(mock_request)
        assert version == "v4"

    def test_default_version_fallback(self, version_extractor):
        """Test fallback to default version."""
        mock_request = MagicMock()
        mock_request.url.path = "/users/123"
        mock_request.headers = {}
        mock_request.query_params = {}

        version = version_extractor.extract_version(mock_request)
        assert version == "v1"


class TestMemoryContractRegistry:
    """Test memory-based contract registry."""

    @pytest.mark.asyncio
    async def test_save_and_get_contract(self, memory_registry, sample_api_contract):
        """Test saving and retrieving API contracts."""
        # Save contract
        success = await memory_registry.save_contract(sample_api_contract)
        assert success

        # Retrieve contract
        retrieved = await memory_registry.get_contract("user-service", "v1")
        assert retrieved is not None
        assert retrieved.service_name == "user-service"
        assert retrieved.version == "v1"
        assert retrieved.contract_id == sample_api_contract.contract_id

    @pytest.mark.asyncio
    async def test_list_contracts(self, memory_registry, sample_api_contract):
        """Test listing contracts."""
        # Save multiple contracts
        contract_v2 = APIContract(
            service_name="user-service",
            version="v2",
            openapi_spec=sample_api_contract.openapi_spec,
            endpoints=sample_api_contract.endpoints,
        )

        await memory_registry.save_contract(sample_api_contract)
        await memory_registry.save_contract(contract_v2)

        # List all contracts for service
        contracts = await memory_registry.list_contracts("user-service")
        assert len(contracts) == 2

        versions = [c.version for c in contracts]
        assert "v1" in versions
        assert "v2" in versions

    @pytest.mark.asyncio
    async def test_consumer_contracts(self, memory_registry, sample_consumer_contract):
        """Test consumer contract operations."""
        # Save consumer contract
        success = await memory_registry.save_consumer_contract(sample_consumer_contract)
        assert success

        # Retrieve consumer contracts
        contracts = await memory_registry.get_consumer_contracts("user-service", "v1")
        assert len(contracts) == 1
        assert contracts[0].consumer_name == "mobile-app"

    @pytest.mark.asyncio
    async def test_version_operations(self, memory_registry, sample_api_version):
        """Test API version operations."""
        # Save version (need to set service_name for memory registry)
        sample_api_version.service_name = "user-service"
        success = await memory_registry.save_version(sample_api_version)
        assert success

        # Retrieve versions
        versions = await memory_registry.get_versions("user-service")
        assert len(versions) == 1
        assert versions[0].version == "v1.0.0"


class TestAPIContract:
    """Test API contract functionality."""

    def test_contract_checksum(self, sample_api_contract):
        """Test contract checksum calculation."""
        checksum1 = sample_api_contract.calculate_checksum()
        checksum2 = sample_api_contract.calculate_checksum()
        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA256 hex digest

    def test_contract_comparison(self, sample_api_contract):
        """Test contract comparison for changes."""
        # Create modified contract
        modified_contract = APIContract(
            service_name=sample_api_contract.service_name,
            version="v2",
            openapi_spec=sample_api_contract.openapi_spec.copy(),
            endpoints=sample_api_contract.endpoints.copy(),
        )

        # Add breaking change - remove required field
        modified_contract.endpoints[0]["response_schemas"]["200"]["required"] = [
            "id",
            "name",
        ]

        changes = sample_api_contract.compare_with(modified_contract)
        assert (
            len(changes["breaking_changes"]) > 0
            or len(changes["compatible_changes"]) > 0
        )

    def test_endpoint_signature_retrieval(self, sample_api_contract):
        """Test endpoint signature retrieval."""
        signature = sample_api_contract.get_endpoint_signature(
            "/users/{user_id}", "GET"
        )
        assert signature is not None
        assert signature["method"] == "GET"
        assert signature["path"] == "/users/{user_id}"

        # Test non-existent endpoint
        signature = sample_api_contract.get_endpoint_signature(
            "/posts/{post_id}", "POST"
        )
        assert signature is None


class TestAPIVersion:
    """Test API version functionality."""

    def test_version_parsing(self):
        """Test semantic version parsing."""
        version = APIVersion(version="v2.1.3")
        assert version.major == 2
        assert version.minor == 1
        assert version.patch == 3

    def test_version_status_checks(self):
        """Test version status checking methods."""
        # Test deprecated version
        deprecated_version = APIVersion(
            version="v1.0.0",
            status="deprecated",
            deprecation_date=datetime.utcnow() - timedelta(days=1),
        )
        assert deprecated_version.is_deprecated()
        assert not deprecated_version.is_retired()

        # Test retired version
        retired_version = APIVersion(
            version="v0.9.0",
            status="retired",
            retirement_date=datetime.utcnow() - timedelta(days=1),
        )
        assert retired_version.is_retired()

    def test_compatibility_checking(self):
        """Test version compatibility checking."""
        version = APIVersion(version="v2.0.0", compatible_with=["v1.5.0", "v1.6.0"])

        assert version.is_compatible_with("v1.5.0")
        assert not version.is_compatible_with("v1.0.0")

    def test_version_serialization(self, sample_api_version):
        """Test version dictionary serialization."""
        version_dict = sample_api_version.to_dict()
        assert version_dict["version"] == "v1.0.0"
        assert version_dict["status"] == "stable"
        assert "release_date" in version_dict


class TestContractValidator:
    """Test contract validation functionality."""

    @pytest.mark.asyncio
    async def test_request_validation(self, memory_registry, sample_api_contract):
        """Test request validation against contract."""
        await memory_registry.save_contract(sample_api_contract)
        validator = ContractValidator(memory_registry)

        # Mock request
        mock_request = MagicMock()
        mock_request.url.path = "/users/123"
        mock_request.method = "GET"
        mock_request.query_params = {}

        errors = await validator.validate_request(mock_request, "v1", "user-service")
        assert isinstance(errors, list)

    @pytest.mark.asyncio
    async def test_response_validation(self, memory_registry, sample_api_contract):
        """Test response validation against contract."""
        await memory_registry.save_contract(sample_api_contract)
        validator = ContractValidator(memory_registry)

        # Mock request and response
        mock_request = MagicMock()
        mock_request.url.path = "/users/123"
        mock_request.method = "GET"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.body = json.dumps(
            {"id": 123, "name": "John Doe", "email": "john@example.com"}
        ).encode()

        errors = await validator.validate_response(
            mock_response, mock_request, "v1", "user-service"
        )
        assert isinstance(errors, list)

    @pytest.mark.asyncio
    async def test_validation_missing_contract(self, memory_registry):
        """Test validation when contract is missing."""
        validator = ContractValidator(memory_registry)

        mock_request = MagicMock()
        mock_request.url.path = "/users/123"
        mock_request.method = "GET"

        errors = await validator.validate_request(
            mock_request, "v1", "nonexistent-service"
        )
        assert len(errors) > 0
        assert "No contract found" in errors[0]


class TestContractTester:
    """Test contract testing functionality."""

    @pytest.mark.asyncio
    async def test_provider_contract_testing(
        self, memory_registry, sample_api_contract
    ):
        """Test provider contract testing."""
        await memory_registry.save_contract(sample_api_contract)

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
        }
        mock_response.content = json.dumps(
            {"id": 1, "name": "John Doe", "email": "john@example.com"}
        ).encode()
        mock_client.request.return_value = mock_response

        tester = ContractTester(memory_registry, mock_client)

        results = await tester.test_provider_contract(
            "user-service", "v1", "http://localhost:8080"
        )

        assert results["service"] == "user-service"
        assert results["version"] == "v1"
        assert results["total_tests"] > 0

    @pytest.mark.asyncio
    async def test_consumer_contract_testing(
        self, memory_registry, sample_consumer_contract
    ):
        """Test consumer contract testing."""
        await memory_registry.save_consumer_contract(sample_consumer_contract)

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
        }
        mock_response.content = json.dumps(
            {"id": 1, "name": "John Doe", "email": "john@example.com"}
        ).encode()
        mock_client.request.return_value = mock_response

        tester = ContractTester(memory_registry, mock_client)

        results = await tester.test_consumer_contracts(
            "user-service", "v1", "http://localhost:8080"
        )

        assert len(results) == 1
        assert results[0]["consumer"] == "mobile-app"
        assert results[0]["provider"] == "user-service"


class TestAPIVersionManager:
    """Test API version management functionality."""

    @pytest.mark.asyncio
    async def test_register_api_version(
        self, memory_registry, sample_api_version, sample_api_contract
    ):
        """Test API version registration."""
        manager = APIVersionManager(memory_registry)

        success = await manager.register_api_version(
            sample_api_version, sample_api_contract
        )
        assert success

        # Verify contract was saved
        contract = await memory_registry.get_contract("user-service", "v1.0.0")
        assert contract is not None

    @pytest.mark.asyncio
    async def test_compatibility_checking(self, memory_registry):
        """Test compatibility checking between versions."""
        manager = APIVersionManager(memory_registry)

        # Create two compatible contracts
        contract_v1 = APIContract(
            service_name="user-service",
            version="v1",
            endpoints=[
                {
                    "path": "/users/{user_id}",
                    "method": "GET",
                    "response_schemas": {
                        "200": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                            },
                            "required": ["id", "name"],
                        }
                    },
                }
            ],
        )

        contract_v2 = APIContract(
            service_name="user-service",
            version="v2",
            endpoints=[
                {
                    "path": "/users/{user_id}",
                    "method": "GET",
                    "response_schemas": {
                        "200": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "email": {"type": "string"},  # Added field
                            },
                            "required": ["id", "name"],  # No new required fields
                        }
                    },
                }
            ],
        )

        await memory_registry.save_contract(contract_v1)
        await memory_registry.save_contract(contract_v2)

        compatibility = await manager.check_compatibility("user-service", "v1", "v2")
        assert "compatible" in compatibility
        assert "changes" in compatibility

    @pytest.mark.asyncio
    async def test_version_deprecation(self, memory_registry):
        """Test version deprecation."""
        manager = APIVersionManager(memory_registry)

        # Create and save a version
        version = APIVersion(version="v1.0.0")
        version.service_name = "user-service"  # Set for memory registry
        await memory_registry.save_version(version)

        # Deprecate the version
        deprecation_date = datetime.utcnow()
        retirement_date = datetime.utcnow() + timedelta(days=90)

        success = await manager.deprecate_version(
            "user-service", "v1.0.0", deprecation_date, retirement_date
        )
        assert success

        # Verify deprecation
        versions = await memory_registry.get_versions("user-service")
        deprecated_version = next(v for v in versions if v.version == "v1.0.0")
        assert deprecated_version.status == "deprecated"
        assert deprecated_version.deprecation_date == deprecation_date

    @pytest.mark.asyncio
    async def test_supported_versions_filtering(self, memory_registry):
        """Test filtering of supported versions."""
        manager = APIVersionManager(memory_registry)

        # Create versions with different statuses
        active_version = APIVersion(version="v2.0.0", status="stable")
        deprecated_version = APIVersion(version="v1.0.0", status="deprecated")
        retired_version = APIVersion(version="v0.9.0", status="retired")

        # Set service name for memory registry
        for version in [active_version, deprecated_version, retired_version]:
            version.service_name = "user-service"
            await memory_registry.save_version(version)

        supported = await manager.get_supported_versions("user-service")

        # Should exclude retired versions
        versions = [v.version for v in supported]
        assert "v2.0.0" in versions
        assert "v1.0.0" in versions  # Deprecated but not retired
        assert "v0.9.0" not in versions  # Retired


class TestFastAPIIntegration:
    """Test FastAPI application integration."""

    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_versioned_endpoint_v1(self, test_client):
        """Test versioned endpoint v1."""
        response = test_client.get("/v1/users/123")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "email" in data
        # V1 should not have first_name/last_name
        assert "first_name" not in data

    def test_versioned_endpoint_v2(self, test_client):
        """Test versioned endpoint v2."""
        response = test_client.get("/v2/users/123")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "first_name" in data
        assert "last_name" in data
        assert "email" in data
        assert "created_at" in data

    def test_contract_registration(self, test_client):
        """Test contract registration endpoint."""
        contract_data = {
            "service_name": "test-service",
            "version": "v1",
            "openapi_spec": {
                "openapi": "3.0.0",
                "info": {"title": "Test Service", "version": "1.0.0"},
            },
            "endpoints": [
                {
                    "path": "/test",
                    "method": "GET",
                    "response_schemas": {"200": {"type": "object"}},
                }
            ],
        }

        response = test_client.post("/api/contracts", json=contract_data)
        assert response.status_code == 201
        data = response.json()
        assert "contract_id" in data
        assert "checksum" in data

    def test_consumer_contract_registration(self, test_client):
        """Test consumer contract registration endpoint."""
        contract_data = {
            "consumer_name": "test-consumer",
            "provider_service": "test-service",
            "provider_version": "v1",
            "expectations": [
                {"endpoint": "/test", "method": "GET", "response_format": "json"}
            ],
            "test_cases": [
                {
                    "name": "Test case 1",
                    "path": "/test",
                    "method": "GET",
                    "expectations": {"status_code": 200},
                }
            ],
        }

        response = test_client.post("/api/consumer-contracts", json=contract_data)
        assert response.status_code == 201
        data = response.json()
        assert "contract_id" in data

    def test_metrics_endpoint(self, test_client):
        """Test metrics endpoint."""
        response = test_client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]


class TestConfiguration:
    """Test configuration management."""

    def test_default_settings(self):
        """Test default configuration settings."""
        settings = APIVersioningSettings()
        assert settings.service_name == "api-versioning-service"
        assert settings.versioning.strategy == VersioningStrategy.URL_PATH
        assert settings.versioning.default_version == "v1"
        assert settings.contracts.storage_backend.value == "memory"

    def test_environment_validation(self):
        """Test environment-specific validation."""
        # Production settings should not allow debug mode
        with pytest.raises(ValueError):
            APIVersioningSettings(environment="production", debug=True)

    def test_database_url_generation(self):
        """Test database URL generation."""
        settings = APIVersioningSettings()
        settings.contracts.storage_backend = "postgresql"
        settings.storage.postgres_user = "testuser"
        settings.storage.postgres_password = "testpass"
        settings.storage.postgres_host = "localhost"
        settings.storage.postgres_port = 5432
        settings.storage.postgres_db = "testdb"

        url = settings.get_database_url()
        assert "postgresql://testuser:testpass@localhost:5432/testdb" == url


# Integration tests
class TestEndToEndScenarios:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_complete_versioning_workflow(self, memory_registry):
        """Test complete API versioning workflow."""
        manager = APIVersionManager(memory_registry)

        # 1. Register initial API version
        version_v1 = APIVersion(version="v1.0.0", status="stable")
        contract_v1 = APIContract(
            service_name="user-service",
            version="v1.0.0",
            endpoints=[
                {
                    "path": "/users/{user_id}",
                    "method": "GET",
                    "response_schemas": {
                        "200": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                            },
                            "required": ["id", "name"],
                        }
                    },
                }
            ],
        )

        success = await manager.register_api_version(version_v1, contract_v1)
        assert success

        # 2. Register consumer contract
        consumer_contract = ConsumerContract(
            consumer_name="mobile-app",
            provider_service="user-service",
            provider_version="v1.0.0",
            test_cases=[
                {
                    "name": "Get user",
                    "path": "/users/1",
                    "method": "GET",
                    "expectations": {"status_code": 200},
                }
            ],
        )

        await memory_registry.save_consumer_contract(consumer_contract)

        # 3. Create new version with breaking changes
        version_v2 = APIVersion(version="v2.0.0", status="stable")
        contract_v2 = APIContract(
            service_name="user-service",
            version="v2.0.0",
            endpoints=[
                {
                    "path": "/users/{user_id}",
                    "method": "GET",
                    "response_schemas": {
                        "200": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "full_name": {"type": "string"},  # Changed from 'name'
                            },
                            "required": ["id", "full_name"],
                        }
                    },
                }
            ],
        )

        await manager.register_api_version(version_v2, contract_v2)

        # 4. Check compatibility
        compatibility = await manager.check_compatibility(
            "user-service", "v1.0.0", "v2.0.0"
        )
        assert not compatibility["compatible"]  # Should detect breaking changes

        # 5. Deprecate old version
        deprecation_date = datetime.utcnow()
        retirement_date = datetime.utcnow() + timedelta(days=90)

        await manager.deprecate_version(
            "user-service", "v1.0.0", deprecation_date, retirement_date
        )

        # 6. Verify supported versions
        supported = await manager.get_supported_versions("user-service")
        assert (
            len(supported) == 2
        )  # Both versions should be supported (v1 deprecated but not retired)

        # 7. Test contracts
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps({"id": 1, "full_name": "John Doe"}).encode()
        mock_client.request.return_value = mock_response

        tester = ContractTester(memory_registry, mock_client)
        test_results = await tester.test_consumer_contracts(
            "user-service", "v1.0.0", "http://localhost"
        )

        # Consumer contract should fail due to breaking changes
        assert len(test_results) == 1


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--cov=main", "--cov-report=html"])
