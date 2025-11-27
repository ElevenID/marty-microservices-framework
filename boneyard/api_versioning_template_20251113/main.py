"""
API Versioning and Contract Testing Framework

This module implements a comprehensive API versioning strategy with backward compatibility
mechanisms and automated contract testing to ensure API stability across versions.

Key Features:
- Multiple versioning strategies (URL path, header, query parameter)
- Automatic API contract generation and validation
- Backward compatibility checking
- Contract testing with consumer-driven contracts
- API deprecation management
- Schema evolution tracking
- Breaking change detection
- Contract registry and documentation
- Version-specific routing and middleware
- Consumer contract validation

Author: Marty Framework Team
Version: 1.0.0
"""

import builtins
import hashlib
import json
import re
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from os import getenv
from typing import Any, dict, list

import httpx
import semver
import structlog
import uvicorn
from deepdiff import DeepDiff
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate
from marty_msf.framework.config import (
    ConfigurationStrategy,
    Environment,
    create_unified_config_manager,
)
from opentelemetry import trace
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel, Field

from .config import APIVersioningSettings, get_settings

__version__ = "1.0.0"



# Import unified configuration system


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Metrics
api_requests_total = Counter(
    "api_requests_total",
    "Total API requests",
    ["version", "endpoint", "method", "status"],
)
api_version_usage = Counter(
    "api_version_usage_total", "API version usage", ["version", "consumer"]
)
contract_validations_total = Counter(
    "contract_validations_total", "Contract validations", ["version", "status"]
)
breaking_changes_detected = Counter(
    "breaking_changes_detected_total", "Breaking changes detected", ["version"]
)
deprecated_api_usage = Counter(
    "deprecated_api_usage_total", "Deprecated API usage", ["version", "endpoint"]
)
contract_tests_total = Counter(
    "contract_tests_total", "Contract tests executed", ["version", "consumer", "status"]
)


class VersioningStrategy(Enum):
    """API versioning strategies."""

    URL_PATH = "url_path"  # /v1/users, /v2/users
    HEADER = "header"  # Accept: application/vnd.api+json;version=1
    QUERY_PARAMETER = "query"  # /users?version=1
    MEDIA_TYPE = "media_type"  # Accept: application/vnd.api.v1+json
    CUSTOM_HEADER = "custom_header"  # X-API-Version: 1


class ChangeType(Enum):
    """Types of API changes."""

    COMPATIBLE = "compatible"  # Non-breaking changes
    BREAKING = "breaking"  # Breaking changes
    DEPRECATED = "deprecated"  # Deprecated features
    REMOVED = "removed"  # Removed features


class ContractTestStatus(Enum):
    """Contract test execution status."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class APIVersion:
    """API version definition."""

    version: str
    major: int
    minor: int
    patch: int
    status: str = "stable"  # draft, stable, deprecated, retired
    release_date: datetime = field(default_factory=datetime.utcnow)
    deprecation_date: datetime | None = None
    retirement_date: datetime | None = None
    changelog: builtins.list[str] = field(default_factory=list)
    breaking_changes: builtins.list[str] = field(default_factory=list)
    compatible_with: builtins.list[str] = field(default_factory=list)

    def __post_init__(self):
        """Parse semantic version."""
        try:
            parsed = semver.VersionInfo.parse(self.version)
            self.major = parsed.major
            self.minor = parsed.minor
            self.patch = parsed.patch
        except ValueError:
            # Fallback for non-semver versions
            parts = self.version.replace("v", "").split(".")
            self.major = int(parts[0]) if parts else 1
            self.minor = int(parts[1]) if len(parts) > 1 else 0
            self.patch = int(parts[2]) if len(parts) > 2 else 0

    def is_compatible_with(self, other_version: str) -> bool:
        """Check if this version is compatible with another version."""
        return other_version in self.compatible_with

    def is_deprecated(self) -> bool:
        """Check if this version is deprecated."""
        return self.status == "deprecated" or (
            self.deprecation_date and datetime.utcnow() >= self.deprecation_date
        )

    def is_retired(self) -> bool:
        """Check if this version is retired."""
        return self.status == "retired" or (
            self.retirement_date and datetime.utcnow() >= self.retirement_date
        )

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["release_date"] = self.release_date.isoformat()
        if self.deprecation_date:
            data["deprecation_date"] = self.deprecation_date.isoformat()
        if self.retirement_date:
            data["retirement_date"] = self.retirement_date.isoformat()
        return data


@dataclass
class APIContract:
    """API contract definition."""

    service_name: str
    version: str
    contract_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    openapi_spec: builtins.dict[str, Any] = field(default_factory=dict)
    schema_definitions: builtins.dict[str, Any] = field(default_factory=dict)
    endpoints: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    consumers: builtins.list[str] = field(default_factory=list)
    provider: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    checksum: str | None = None

    def __post_init__(self):
        """Calculate contract checksum."""
        self.checksum = self.calculate_checksum()

    def calculate_checksum(self) -> str:
        """Calculate contract checksum for change detection."""
        contract_data = {
            "openapi_spec": self.openapi_spec,
            "schema_definitions": self.schema_definitions,
            "endpoints": self.endpoints,
        }
        content = json.dumps(contract_data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()

    def get_endpoint_signature(
        self, path: str, method: str
    ) -> builtins.dict[str, Any] | None:
        """Get endpoint signature for comparison."""
        for endpoint in self.endpoints:
            if (
                endpoint.get("path") == path
                and endpoint.get("method").upper() == method.upper()
            ):
                return endpoint
        return None

    def compare_with(self, other: "APIContract") -> builtins.dict[str, Any]:
        """Compare this contract with another and detect changes."""
        diff = DeepDiff(
            self.to_dict(),
            other.to_dict(),
            exclude_paths=[
                "root['created_at']",
                "root['updated_at']",
                "root['checksum']",
            ],
        )

        changes = {
            "breaking_changes": [],
            "compatible_changes": [],
            "removed_endpoints": [],
            "added_endpoints": [],
            "modified_endpoints": [],
        }

        # Analyze differences
        if "dictionary_item_removed" in diff:
            for removed_item in diff["dictionary_item_removed"]:
                if "endpoints" in removed_item:
                    changes["breaking_changes"].append(
                        f"Endpoint removed: {removed_item}"
                    )
                    changes["removed_endpoints"].append(removed_item)

        if "dictionary_item_added" in diff:
            for added_item in diff["dictionary_item_added"]:
                if "endpoints" in added_item:
                    changes["compatible_changes"].append(
                        f"Endpoint added: {added_item}"
                    )
                    changes["added_endpoints"].append(added_item)

        if "values_changed" in diff:
            for changed_item in diff["values_changed"]:
                if (
                    "required" in changed_item
                    and diff["values_changed"][changed_item]["new_value"]
                ):
                    changes["breaking_changes"].append(
                        f"Required field added: {changed_item}"
                    )
                elif "type" in changed_item:
                    changes["breaking_changes"].append(f"Type changed: {changed_item}")
                else:
                    changes["compatible_changes"].append(
                        f"Value changed: {changed_item}"
                    )

        return changes

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data


@dataclass
class ConsumerContract:
    """Consumer-driven contract definition."""

    consumer_name: str
    provider_service: str
    provider_version: str
    contract_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    expectations: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    test_cases: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_validated: datetime | None = None
    validation_status: ContractTestStatus = ContractTestStatus.SKIPPED
    validation_errors: builtins.list[str] = field(default_factory=list)

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        if self.last_validated:
            data["last_validated"] = self.last_validated.isoformat()
        data["validation_status"] = self.validation_status.value
        return data


class ContractRegistry(ABC):
    """Abstract contract registry for storing API contracts."""

    @abstractmethod
    async def save_contract(self, contract: APIContract) -> bool:
        """Save API contract."""
        pass

    @abstractmethod
    async def get_contract(
        self, service_name: str, version: str
    ) -> APIContract | None:
        """Get API contract by service and version."""
        pass

    @abstractmethod
    async def list_contracts(
        self, service_name: str | None = None
    ) -> builtins.list[APIContract]:
        """List API contracts."""
        pass

    @abstractmethod
    async def save_consumer_contract(self, contract: ConsumerContract) -> bool:
        """Save consumer contract."""
        pass

    @abstractmethod
    async def get_consumer_contracts(
        self, provider_service: str, provider_version: str
    ) -> builtins.list[ConsumerContract]:
        """Get consumer contracts for a provider."""
        pass

    @abstractmethod
    async def save_version(self, version: APIVersion) -> bool:
        """Save API version information."""
        pass

    @abstractmethod
    async def get_versions(self, service_name: str) -> builtins.list[APIVersion]:
        """Get all versions for a service."""
        pass


class MemoryContractRegistry(ContractRegistry):
    """In-memory contract registry for development and testing."""

    def __init__(self):
        self._contracts: builtins.dict[
            str, builtins.dict[str, APIContract]
        ] = {}  # service -> version -> contract
        self._consumer_contracts: builtins.dict[
            str, builtins.list[ConsumerContract]
        ] = {}  # provider:version -> contracts
        self._versions: builtins.dict[str, builtins.list[APIVersion]] = {}  # service -> versions

    async def save_contract(self, contract: APIContract) -> bool:
        """Save API contract."""
        if contract.service_name not in self._contracts:
            self._contracts[contract.service_name] = {}

        self._contracts[contract.service_name][contract.version] = contract
        return True

    async def get_contract(
        self, service_name: str, version: str
    ) -> APIContract | None:
        """Get API contract by service and version."""
        return self._contracts.get(service_name, {}).get(version)

    async def list_contracts(
        self, service_name: str | None = None
    ) -> builtins.list[APIContract]:
        """List API contracts."""
        contracts = []

        if service_name:
            if service_name in self._contracts:
                contracts.extend(self._contracts[service_name].values())
        else:
            for service_contracts in self._contracts.values():
                contracts.extend(service_contracts.values())

        return contracts

    async def save_consumer_contract(self, contract: ConsumerContract) -> bool:
        """Save consumer contract."""
        key = f"{contract.provider_service}:{contract.provider_version}"

        if key not in self._consumer_contracts:
            self._consumer_contracts[key] = []

        # Update existing or add new
        for i, existing in enumerate(self._consumer_contracts[key]):
            if existing.consumer_name == contract.consumer_name:
                self._consumer_contracts[key][i] = contract
                return True

        self._consumer_contracts[key].append(contract)
        return True

    async def get_consumer_contracts(
        self, provider_service: str, provider_version: str
    ) -> builtins.list[ConsumerContract]:
        """Get consumer contracts for a provider."""
        key = f"{provider_service}:{provider_version}"
        return self._consumer_contracts.get(key, [])

    async def save_version(self, version: APIVersion) -> bool:
        """Save API version information."""
        # Extract service name from version context (simplified)
        service_name = getattr(version, "service_name", "default_service")

        if service_name not in self._versions:
            self._versions[service_name] = []

        # Update existing or add new
        for i, existing in enumerate(self._versions[service_name]):
            if existing.version == version.version:
                self._versions[service_name][i] = version
                return True

        self._versions[service_name].append(version)
        return True

    async def get_versions(self, service_name: str) -> builtins.list[APIVersion]:
        """Get all versions for a service."""
        return self._versions.get(service_name, [])


class VersionExtractor:
    """Extract API version from requests based on strategy."""

    def __init__(self, strategy: VersioningStrategy, default_version: str = "v1"):
        self.strategy = strategy
        self.default_version = default_version

    def extract_version(self, request: Request) -> str:
        """Extract version from request."""
        if self.strategy == VersioningStrategy.URL_PATH:
            # Extract from URL path: /v1/users -> v1
            path_parts = request.url.path.strip("/").split("/")
            for part in path_parts:
                if re.match(r"^v\d+(\.\d+)*$", part):
                    return part

        elif self.strategy == VersioningStrategy.HEADER:
            # Extract from Accept header: application/vnd.api+json;version=1
            accept_header = request.headers.get("accept", "")
            version_match = re.search(r"version=(\w+)", accept_header)
            if version_match:
                return f"v{version_match.group(1)}"

        elif self.strategy == VersioningStrategy.QUERY_PARAMETER:
            # Extract from query parameter: ?version=1
            version = request.query_params.get("version")
            if version:
                return f"v{version}" if not version.startswith("v") else version

        elif self.strategy == VersioningStrategy.MEDIA_TYPE:
            # Extract from media type: application/vnd.api.v1+json
            accept_header = request.headers.get("accept", "")
            version_match = re.search(r"\.v(\d+)", accept_header)
            if version_match:
                return f"v{version_match.group(1)}"

        elif self.strategy == VersioningStrategy.CUSTOM_HEADER:
            # Extract from custom header: X-API-Version: 1
            version_header = request.headers.get("x-api-version")
            if version_header:
                return (
                    f"v{version_header}"
                    if not version_header.startswith("v")
                    else version_header
                )

        return self.default_version


class VersioningMiddleware:
    """Middleware for API versioning and contract validation."""

    def __init__(
        self,
        app: FastAPI,
        version_extractor: VersionExtractor,
        contract_registry: ContractRegistry,
    ):
        self.app = app
        self.version_extractor = version_extractor
        self.contract_registry = contract_registry
        self.tracer = trace.get_tracer(__name__)

    async def __call__(self, request: Request, call_next: Callable):
        """Process request with versioning."""
        with self.tracer.start_as_current_span("api_versioning") as span:
            # Extract version
            version = self.version_extractor.extract_version(request)
            span.set_attribute("api.version", version)

            # Add version to request state
            request.state.api_version = version

            # Track version usage
            consumer = request.headers.get("user-agent", "unknown")
            api_version_usage.labels(version=version, consumer=consumer).inc()

            # Process request
            response = await call_next(request)

            # Add version to response headers
            response.headers["X-API-Version"] = version

            # Track API usage
            endpoint = request.url.path
            method = request.method
            status = str(response.status_code)

            api_requests_total.labels(
                version=version, endpoint=endpoint, method=method, status=status
            ).inc()

            return response


class ContractValidator:
    """Validate API requests and responses against contracts."""

    def __init__(self, contract_registry: ContractRegistry):
        self.contract_registry = contract_registry

    async def validate_request(
        self, request: Request, version: str, service_name: str
    ) -> builtins.list[str]:
        """Validate request against contract."""
        errors = []

        try:
            contract = await self.contract_registry.get_contract(service_name, version)
            if not contract:
                return [f"No contract found for {service_name} version {version}"]

            # Find matching endpoint
            endpoint_signature = contract.get_endpoint_signature(
                request.url.path, request.method
            )

            if not endpoint_signature:
                errors.append(
                    f"Endpoint {request.method} {request.url.path} not found in contract"
                )
                return errors

            # Validate request body if present
            if hasattr(request, "_body") and request._body:
                try:
                    request_data = json.loads(request._body)
                    request_schema = endpoint_signature.get("request_schema")

                    if request_schema:
                        validate(instance=request_data, schema=request_schema)

                except json.JSONDecodeError:
                    errors.append("Invalid JSON in request body")
                except JsonSchemaValidationError as e:
                    errors.append(f"Request validation error: {e.message}")

            # Validate query parameters
            query_schema = endpoint_signature.get("query_schema")
            if query_schema:
                try:
                    query_params = dict(request.query_params)
                    validate(instance=query_params, schema=query_schema)
                except JsonSchemaValidationError as e:
                    errors.append(f"Query parameter validation error: {e.message}")

        except Exception as e:
            errors.append(f"Contract validation error: {str(e)}")

        return errors

    async def validate_response(
        self, response: Response, request: Request, version: str, service_name: str
    ) -> builtins.list[str]:
        """Validate response against contract."""
        errors = []

        try:
            contract = await self.contract_registry.get_contract(service_name, version)
            if not contract:
                return []  # Skip validation if no contract

            endpoint_signature = contract.get_endpoint_signature(
                request.url.path, request.method
            )

            if not endpoint_signature:
                return []  # Skip validation if endpoint not in contract

            # Get expected response schema
            response_schemas = endpoint_signature.get("response_schemas", {})
            status_code = str(response.status_code)
            response_schema = response_schemas.get(status_code)

            if response_schema and hasattr(response, "body"):
                try:
                    if response.body:
                        response_data = json.loads(response.body)
                        validate(instance=response_data, schema=response_schema)
                except json.JSONDecodeError:
                    errors.append("Invalid JSON in response body")
                except JsonSchemaValidationError as e:
                    errors.append(f"Response validation error: {e.message}")

        except Exception as e:
            errors.append(f"Response contract validation error: {str(e)}")

        return errors


class ContractTester:
    """Execute contract tests against API providers."""

    def __init__(
        self, contract_registry: ContractRegistry, http_client: httpx.AsyncClient
    ):
        self.contract_registry = contract_registry
        self.http_client = http_client

    async def test_provider_contract(
        self, service_name: str, version: str, base_url: str
    ) -> builtins.dict[str, Any]:
        """Test provider contract."""
        results = {
            "service": service_name,
            "version": version,
            "base_url": base_url,
            "status": ContractTestStatus.PASSED.value,
            "tests": [],
            "errors": [],
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
        }

        try:
            contract = await self.contract_registry.get_contract(service_name, version)
            if not contract:
                results["status"] = ContractTestStatus.SKIPPED.value
                results["errors"].append(
                    f"No contract found for {service_name} version {version}"
                )
                return results

            # Test each endpoint
            for endpoint in contract.endpoints:
                test_result = await self._test_endpoint(endpoint, base_url)
                results["tests"].append(test_result)
                results["total_tests"] += 1

                if test_result["status"] == ContractTestStatus.PASSED.value:
                    results["passed_tests"] += 1
                else:
                    results["failed_tests"] += 1
                    results["errors"].extend(test_result.get("errors", []))

            if results["failed_tests"] > 0:
                results["status"] = ContractTestStatus.FAILED.value

        except Exception as e:
            results["status"] = ContractTestStatus.ERROR.value
            results["errors"].append(f"Contract test error: {str(e)}")

        # Record metrics
        contract_tests_total.labels(
            version=version, consumer="system", status=results["status"]
        ).inc()

        return results

    async def test_consumer_contracts(
        self, provider_service: str, provider_version: str, base_url: str
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Test all consumer contracts for a provider."""
        consumer_contracts = await self.contract_registry.get_consumer_contracts(
            provider_service, provider_version
        )

        results = []

        for consumer_contract in consumer_contracts:
            result = await self._test_consumer_contract(consumer_contract, base_url)
            results.append(result)

            # Update contract validation status
            consumer_contract.last_validated = datetime.utcnow()
            consumer_contract.validation_status = ContractTestStatus(result["status"])
            consumer_contract.validation_errors = result.get("errors", [])

            await self.contract_registry.save_consumer_contract(consumer_contract)

        return results

    async def _test_endpoint(
        self, endpoint: builtins.dict[str, Any], base_url: str
    ) -> builtins.dict[str, Any]:
        """Test individual endpoint."""
        result = {
            "endpoint": f"{endpoint['method']} {endpoint['path']}",
            "status": ContractTestStatus.PASSED.value,
            "errors": [],
            "response_time": 0,
            "status_code": None,
        }

        try:
            url = f"{base_url.rstrip('/')}{endpoint['path']}"
            method = endpoint["method"].upper()

            # Prepare test request
            request_data = endpoint.get("test_request", {})
            headers = request_data.get("headers", {})
            json_data = request_data.get("json")
            params = request_data.get("params", {})

            # Execute request
            start_time = datetime.utcnow()

            response = await self.http_client.request(
                method=method,
                url=url,
                json=json_data,
                headers=headers,
                params=params,
                timeout=30.0,
            )

            end_time = datetime.utcnow()
            result["response_time"] = (end_time - start_time).total_seconds()
            result["status_code"] = response.status_code

            # Validate response
            expected_status = endpoint.get("expected_status", 200)
            if response.status_code != expected_status:
                result["status"] = ContractTestStatus.FAILED.value
                result["errors"].append(
                    f"Expected status {expected_status}, got {response.status_code}"
                )

            # Validate response schema
            response_schema = endpoint.get("response_schema")
            if response_schema and response.content:
                try:
                    response_data = response.json()
                    validate(instance=response_data, schema=response_schema)
                except json.JSONDecodeError:
                    result["errors"].append("Invalid JSON in response")
                    result["status"] = ContractTestStatus.FAILED.value
                except JsonSchemaValidationError as e:
                    result["errors"].append(
                        f"Response schema validation error: {e.message}"
                    )
                    result["status"] = ContractTestStatus.FAILED.value

        except httpx.RequestError as e:
            result["status"] = ContractTestStatus.ERROR.value
            result["errors"].append(f"Request error: {str(e)}")
        except Exception as e:
            result["status"] = ContractTestStatus.ERROR.value
            result["errors"].append(f"Test error: {str(e)}")

        return result

    async def _test_consumer_contract(
        self, consumer_contract: ConsumerContract, base_url: str
    ) -> builtins.dict[str, Any]:
        """Test consumer contract."""
        result = {
            "consumer": consumer_contract.consumer_name,
            "provider": consumer_contract.provider_service,
            "version": consumer_contract.provider_version,
            "status": ContractTestStatus.PASSED.value,
            "tests": [],
            "errors": [],
        }

        try:
            for test_case in consumer_contract.test_cases:
                test_result = await self._execute_consumer_test(test_case, base_url)
                result["tests"].append(test_result)

                if test_result["status"] != ContractTestStatus.PASSED.value:
                    result["status"] = ContractTestStatus.FAILED.value
                    result["errors"].extend(test_result.get("errors", []))

        except Exception as e:
            result["status"] = ContractTestStatus.ERROR.value
            result["errors"].append(f"Consumer contract test error: {str(e)}")

        # Record metrics
        contract_tests_total.labels(
            version=consumer_contract.provider_version,
            consumer=consumer_contract.consumer_name,
            status=result["status"],
        ).inc()

        return result

    async def _execute_consumer_test(
        self, test_case: builtins.dict[str, Any], base_url: str
    ) -> builtins.dict[str, Any]:
        """Execute individual consumer test case."""
        result = {
            "name": test_case.get("name", "Unnamed test"),
            "status": ContractTestStatus.PASSED.value,
            "errors": [],
        }

        try:
            # Similar to _test_endpoint but focused on consumer expectations
            url = f"{base_url.rstrip('/')}{test_case['path']}"
            method = test_case["method"].upper()

            response = await self.http_client.request(
                method=method,
                url=url,
                json=test_case.get("request_body"),
                headers=test_case.get("headers", {}),
                params=test_case.get("query_params", {}),
                timeout=30.0,
            )

            # Validate consumer expectations
            expectations = test_case.get("expectations", {})

            if "status_code" in expectations:
                expected_status = expectations["status_code"]
                if response.status_code != expected_status:
                    result["status"] = ContractTestStatus.FAILED.value
                    result["errors"].append(
                        f"Expected status {expected_status}, got {response.status_code}"
                    )

            if "response_schema" in expectations and response.content:
                try:
                    response_data = response.json()
                    validate(
                        instance=response_data, schema=expectations["response_schema"]
                    )
                except JsonSchemaValidationError as e:
                    result["status"] = ContractTestStatus.FAILED.value
                    result["errors"].append(
                        f"Response schema validation error: {e.message}"
                    )

        except Exception as e:
            result["status"] = ContractTestStatus.ERROR.value
            result["errors"].append(f"Test execution error: {str(e)}")

        return result


class APIVersionManager:
    """Manage API versions and backward compatibility."""

    def __init__(self, contract_registry: ContractRegistry):
        self.contract_registry = contract_registry
        self.contract_validator = ContractValidator(contract_registry)
        self.contract_tester = ContractTester(contract_registry, httpx.AsyncClient())

    async def register_api_version(
        self, version: APIVersion, contract: APIContract
    ) -> bool:
        """Register new API version with contract."""
        try:
            # Save version information
            await self.contract_registry.save_version(version)

            # Save contract
            contract.version = version.version
            await self.contract_registry.save_contract(contract)

            # Check for breaking changes
            await self._check_breaking_changes(contract)

            logger.info(
                "API version registered",
                version=version.version,
                service=contract.service_name,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to register API version", version=version.version, error=str(e)
            )
            return False

    async def check_compatibility(
        self, service_name: str, current_version: str, target_version: str
    ) -> builtins.dict[str, Any]:
        """Check compatibility between API versions."""
        current_contract = await self.contract_registry.get_contract(
            service_name, current_version
        )
        target_contract = await self.contract_registry.get_contract(
            service_name, target_version
        )

        if not current_contract or not target_contract:
            return {
                "compatible": False,
                "error": "One or both contracts not found",
                "changes": {},
            }

        changes = current_contract.compare_with(target_contract)

        # Determine compatibility
        compatible = len(changes["breaking_changes"]) == 0

        if changes["breaking_changes"]:
            breaking_changes_detected.labels(version=target_version).inc()

        return {
            "compatible": compatible,
            "changes": changes,
            "breaking_changes_count": len(changes["breaking_changes"]),
            "compatible_changes_count": len(changes["compatible_changes"]),
        }

    async def get_supported_versions(self, service_name: str) -> builtins.list[APIVersion]:
        """Get all supported versions for a service."""
        versions = await self.contract_registry.get_versions(service_name)

        # Filter out retired versions
        supported_versions = [v for v in versions if not v.is_retired()]

        # Sort by version
        supported_versions.sort(key=lambda x: (x.major, x.minor, x.patch), reverse=True)

        return supported_versions

    async def deprecate_version(
        self,
        service_name: str,
        version: str,
        deprecation_date: datetime,
        retirement_date: datetime,
    ) -> bool:
        """Deprecate an API version."""
        versions = await self.contract_registry.get_versions(service_name)

        for v in versions:
            if v.version == version:
                v.status = "deprecated"
                v.deprecation_date = deprecation_date
                v.retirement_date = retirement_date

                await self.contract_registry.save_version(v)

                logger.info(
                    "API version deprecated",
                    service=service_name,
                    version=version,
                    retirement_date=retirement_date.isoformat(),
                )
                return True

        return False

    async def _check_breaking_changes(self, contract: APIContract):
        """Check for breaking changes against previous versions."""
        contracts = await self.contract_registry.list_contracts(contract.service_name)

        # Find previous version
        previous_contract = None
        for c in contracts:
            if c.version != contract.version:
                if not previous_contract or self._is_newer_version(
                    c.version, previous_contract.version
                ):
                    previous_contract = c

        if previous_contract:
            changes = previous_contract.compare_with(contract)

            if changes["breaking_changes"]:
                logger.warning(
                    "Breaking changes detected",
                    service=contract.service_name,
                    version=contract.version,
                    breaking_changes=changes["breaking_changes"],
                )

                breaking_changes_detected.labels(version=contract.version).inc()

    def _is_newer_version(self, version1: str, version2: str) -> bool:
        """Check if version1 is newer than version2."""
        try:
            v1 = semver.VersionInfo.parse(version1.replace("v", ""))
            v2 = semver.VersionInfo.parse(version2.replace("v", ""))
            return v1 > v2
        except ValueError:
            # Fallback for non-semver versions
            return version1 > version2


# FastAPI application factory
def create_versioned_app(
    service_name: str = "api-service",
    versioning_strategy: VersioningStrategy = VersioningStrategy.URL_PATH,
    default_version: str = "v1",
) -> FastAPI:
    """Create FastAPI application with versioning support."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan management."""
        logger.info("Starting API Versioning Service")

        # Initialize unified configuration
        try:
            env_name = getenv("ENVIRONMENT", "development")
            config_manager = create_unified_config_manager(
                service_name="api-versioning-service",
                environment=Environment(env_name),
                config_class=APIVersioningSettings,
                strategy=ConfigurationStrategy.AUTO_DETECT
            )

            await config_manager.initialize()
            app.state.config = await config_manager.get_configuration()
            app.state.config_manager = config_manager

            logger.info(f"Unified configuration loaded for {app.state.config.service_name}")
        except Exception as e:
            logger.warning(f"Failed to load unified configuration, using fallback: {e}")
            app.state.config = get_settings()  # Fallback to existing config

        yield
        logger.info("Shutting down API Versioning Service")

    app = FastAPI(
        title=f"{service_name} - Versioned API",
        description="API with versioning and contract testing support",
        version=__version__,
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Initialize components
    contract_registry = MemoryContractRegistry()
    version_extractor = VersionExtractor(versioning_strategy, default_version)
    versioning_middleware = VersioningMiddleware(
        app, version_extractor, contract_registry
    )
    version_manager = APIVersionManager(contract_registry)

    # Add versioning middleware
    app.middleware("http")(versioning_middleware)

    # Store components in app state
    app.state.contract_registry = contract_registry
    app.state.version_manager = version_manager
    app.state.service_name = service_name

    return app


# Example usage and API routes
# Create app with unified configuration support
app = create_versioned_app("api-versioning-service")


# Pydantic models
class UserV1(BaseModel):
    id: int
    name: str
    email: str


class UserV2(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractRequest(BaseModel):
    service_name: str
    version: str
    openapi_spec: builtins.dict[str, Any]
    endpoints: builtins.list[builtins.dict[str, Any]]


class ConsumerContractRequest(BaseModel):
    consumer_name: str
    provider_service: str
    provider_version: str
    expectations: builtins.list[builtins.dict[str, Any]]
    test_cases: builtins.list[builtins.dict[str, Any]]


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": __version__,
    }


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Version management endpoints
@app.post("/api/contracts", status_code=201)
async def register_contract(contract_request: ContractRequest):
    """Register API contract."""
    contract = APIContract(
        service_name=contract_request.service_name,
        version=contract_request.version,
        openapi_spec=contract_request.openapi_spec,
        endpoints=contract_request.endpoints,
    )

    success = await app.state.contract_registry.save_contract(contract)

    if success:
        return {
            "message": "Contract registered successfully",
            "contract_id": contract.contract_id,
            "checksum": contract.checksum,
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to register contract")


@app.post("/api/consumer-contracts", status_code=201)
async def register_consumer_contract(contract_request: ConsumerContractRequest):
    """Register consumer contract."""
    contract = ConsumerContract(
        consumer_name=contract_request.consumer_name,
        provider_service=contract_request.provider_service,
        provider_version=contract_request.provider_version,
        expectations=contract_request.expectations,
        test_cases=contract_request.test_cases,
    )

    success = await app.state.contract_registry.save_consumer_contract(contract)

    if success:
        return {
            "message": "Consumer contract registered successfully",
            "contract_id": contract.contract_id,
        }
    else:
        raise HTTPException(
            status_code=500, detail="Failed to register consumer contract"
        )


@app.get("/api/contracts/{service_name}")
async def list_service_contracts(service_name: str):
    """List contracts for a service."""
    contracts = await app.state.contract_registry.list_contracts(service_name)
    return {
        "service_name": service_name,
        "contracts": [contract.to_dict() for contract in contracts],
    }


@app.get("/api/compatibility/{service_name}/{current_version}/{target_version}")
async def check_compatibility(
    service_name: str, current_version: str, target_version: str
):
    """Check compatibility between API versions."""
    compatibility = await app.state.version_manager.check_compatibility(
        service_name, current_version, target_version
    )
    return compatibility


@app.post("/api/test-contracts/{service_name}/{version}")
async def test_contract(service_name: str, version: str, base_url: str):
    """Test API contract."""
    results = await app.state.version_manager.contract_tester.test_provider_contract(
        service_name, version, base_url
    )
    return results


# Example versioned endpoints
@app.get("/v1/users/{user_id}", response_model=UserV1)
async def get_user_v1(user_id: int, request: Request):
    """Get user - Version 1."""
    # Track deprecated API usage
    deprecated_api_usage.labels(version="v1", endpoint="/users/{user_id}").inc()

    return UserV1(id=user_id, name="John Doe", email="john@example.com")


@app.get("/v2/users/{user_id}", response_model=UserV2)
async def get_user_v2(user_id: int, request: Request):
    """Get user - Version 2."""
    return UserV2(
        id=user_id, first_name="John", last_name="Doe", email="john@example.com"
    )


if __name__ == "__main__":
    # Load configuration for running the service
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level="debug" if settings.debug else "info"
    )
