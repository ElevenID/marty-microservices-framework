"""
Contract testing framework for Marty Microservices Framework.

This module provides comprehensive contract testing capabilities including
Pact-style consumer-driven contracts, API contract validation, and service
contract verification for microservices architectures.
"""

import builtins
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import aiohttp
import jsonschema

from .core import TestCase, TestMetrics, TestResult, TestSeverity, TestStatus, TestType

logger = logging.getLogger(__name__)


class ContractType(Enum):
    """Types of contracts supported."""

    HTTP_API = "http_api"
    MESSAGE_QUEUE = "message_queue"
    GRPC = "grpc"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    DATABASE = "database"


class VerificationLevel(Enum):
    """Contract verification levels."""

    STRICT = "strict"
    PERMISSIVE = "permissive"
    SCHEMA_ONLY = "schema_only"


@dataclass
class ContractRequest:
    """HTTP request specification for contract."""

    method: str
    path: str
    headers: builtins.dict[str, str] = field(default_factory=dict)
    query_params: builtins.dict[str, Any] = field(default_factory=dict)
    body: Any | None = None
    content_type: str = "application/json"


@dataclass
class ContractResponse:
    """HTTP response specification for contract."""

    status_code: int
    headers: builtins.dict[str, str] = field(default_factory=dict)
    body: Any | None = None
    schema: builtins.dict[str, Any] | None = None
    content_type: str = "application/json"


@dataclass
class ContractInteraction:
    """Single interaction in a contract."""

    description: str
    request: ContractRequest
    response: ContractResponse
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class Contract:
    """Service contract definition."""

    consumer: str
    provider: str
    version: str
    contract_type: ContractType
    interactions: builtins.list[ContractInteraction] = field(default_factory=list)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert contract to dictionary."""
        return {
            "consumer": self.consumer,
            "provider": self.provider,
            "version": self.version,
            "contract_type": self.contract_type.value,
            "interactions": [
                {
                    "description": interaction.description,
                    "request": {
                        "method": interaction.request.method,
                        "path": interaction.request.path,
                        "headers": interaction.request.headers,
                        "query_params": interaction.request.query_params,
                        "body": interaction.request.body,
                        "content_type": interaction.request.content_type,
                    },
                    "response": {
                        "status_code": interaction.response.status_code,
                        "headers": interaction.response.headers,
                        "body": interaction.response.body,
                        "schema": interaction.response.schema,
                        "content_type": interaction.response.content_type,
                    },
                    "metadata": interaction.metadata,
                }
                for interaction in self.interactions
            ],
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


class ContractBuilder:
    """Builder for creating contracts."""

    def __init__(self, consumer: str, provider: str, version: str = "1.0.0"):
        self.contract = Contract(
            consumer=consumer,
            provider=provider,
            version=version,
            contract_type=ContractType.HTTP_API,
        )

    def with_type(self, contract_type: ContractType) -> "ContractBuilder":
        """Set contract type."""
        self.contract.contract_type = contract_type
        return self

    def with_metadata(self, **metadata) -> "ContractBuilder":
        """Add contract metadata."""
        self.contract.metadata.update(metadata)
        return self

    def interaction(self, description: str) -> "InteractionBuilder":
        """Start building an interaction."""
        return InteractionBuilder(self, description)

    def build(self) -> Contract:
        """Build the contract."""
        return self.contract


class InteractionBuilder:
    """Builder for creating contract interactions."""

    def __init__(self, contract_builder: ContractBuilder, description: str):
        self.contract_builder = contract_builder
        self.interaction = ContractInteraction(
            description=description,
            request=ContractRequest(method="GET", path="/"),
            response=ContractResponse(status_code=200),
        )

    def given(self, state: str) -> "InteractionBuilder":
        """Add provider state."""
        if "given" not in self.interaction.metadata:
            self.interaction.metadata["given"] = []
        self.interaction.metadata["given"].append(state)
        return self

    def upon_receiving(self, description: str) -> "InteractionBuilder":
        """Set interaction description."""
        self.interaction.description = description
        return self

    def with_request(self, method: str, path: str, **kwargs) -> "InteractionBuilder":
        """Configure request."""
        self.interaction.request = ContractRequest(
            method=method.upper(),
            path=path,
            headers=kwargs.get("headers", {}),
            query_params=kwargs.get("query_params", {}),
            body=kwargs.get("body"),
            content_type=kwargs.get("content_type", "application/json"),
        )
        return self

    def will_respond_with(self, status_code: int, **kwargs) -> "InteractionBuilder":
        """Configure response."""
        self.interaction.response = ContractResponse(
            status_code=status_code,
            headers=kwargs.get("headers", {}),
            body=kwargs.get("body"),
            schema=kwargs.get("schema"),
            content_type=kwargs.get("content_type", "application/json"),
        )
        return self

    def and_interaction(self, description: str) -> "InteractionBuilder":
        """Add current interaction and start a new one."""
        self.contract_builder.contract.interactions.append(self.interaction)
        return InteractionBuilder(self.contract_builder, description)

    def build(self) -> Contract:
        """Add interaction and build contract."""
        self.contract_builder.contract.interactions.append(self.interaction)
        return self.contract_builder.build()


class ContractValidator:
    """Validates contracts and responses."""

    def __init__(self, verification_level: VerificationLevel = VerificationLevel.STRICT):
        self.verification_level = verification_level

    def validate_response(
        self, interaction: ContractInteraction, actual_response: dict
    ) -> builtins.tuple[bool, builtins.list[str]]:
        """Validate actual response against contract."""
        errors = []

        # Validate status code
        expected_status = interaction.response.status_code
        actual_status = actual_response.get("status_code")

        if actual_status != expected_status:
            errors.append(f"Status code mismatch: expected {expected_status}, got {actual_status}")

        # Validate headers
        if self.verification_level == VerificationLevel.STRICT:
            for header, value in interaction.response.headers.items():
                actual_value = actual_response.get("headers", {}).get(header)
                if actual_value != value:
                    errors.append(
                        f"Header '{header}' mismatch: expected '{value}', got '{actual_value}'"
                    )

        # Validate body schema
        if interaction.response.schema and actual_response.get("body"):
            try:
                jsonschema.validate(actual_response["body"], interaction.response.schema)
            except jsonschema.ValidationError as e:
                errors.append(f"Response body schema validation failed: {e.message}")

        # Validate exact body match if no schema provided and strict mode
        elif (
            self.verification_level == VerificationLevel.STRICT
            and interaction.response.body is not None
        ):
            if actual_response.get("body") != interaction.response.body:
                errors.append("Response body exact match failed")

        return len(errors) == 0, errors

    def validate_contract_syntax(
        self, contract: Contract
    ) -> builtins.tuple[bool, builtins.list[str]]:
        """Validate contract syntax and structure."""
        errors = []

        if not contract.consumer:
            errors.append("Contract must have a consumer")

        if not contract.provider:
            errors.append("Contract must have a provider")

        if not contract.interactions:
            errors.append("Contract must have at least one interaction")

        for i, interaction in enumerate(contract.interactions):
            if not interaction.description:
                errors.append(f"Interaction {i} must have a description")

            if not interaction.request.method:
                errors.append(f"Interaction {i} request must have a method")

            if not interaction.request.path:
                errors.append(f"Interaction {i} request must have a path")

            if interaction.response.status_code < 100 or interaction.response.status_code > 599:
                errors.append(f"Interaction {i} response status code must be valid HTTP status")

        return len(errors) == 0, errors


class ContractRepository:
    """Manages contract storage and retrieval."""

    def __init__(self, storage_path: str = "./contracts"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

    def save_contract(self, contract: Contract):
        """Save contract to storage."""
        filename = f"{contract.consumer}_{contract.provider}_{contract.version}.json"
        filepath = self.storage_path / filename

        with open(filepath, "w") as f:
            json.dump(contract.to_dict(), f, indent=2)

        logger.info(f"Contract saved: {filepath}")

    def load_contract(self, consumer: str, provider: str, version: str = None) -> Contract | None:
        """Load contract from storage."""
        if version:
            filename = f"{consumer}_{provider}_{version}.json"
            filepath = self.storage_path / filename

            if filepath.exists():
                return self._load_contract_file(filepath)
        else:
            # Find latest version
            pattern = f"{consumer}_{provider}_*.json"
            matching_files = list(self.storage_path.glob(pattern))

            if matching_files:
                # Sort by modification time, get latest
                latest_file = max(matching_files, key=lambda f: f.stat().st_mtime)
                return self._load_contract_file(latest_file)

        return None

    def _load_contract_file(self, filepath: Path) -> Contract:
        """Load contract from file."""
        with open(filepath) as f:
            data = json.load(f)

        contract = Contract(
            consumer=data["consumer"],
            provider=data["provider"],
            version=data["version"],
            contract_type=ContractType(data["contract_type"]),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

        for interaction_data in data["interactions"]:
            request = ContractRequest(
                method=interaction_data["request"]["method"],
                path=interaction_data["request"]["path"],
                headers=interaction_data["request"]["headers"],
                query_params=interaction_data["request"]["query_params"],
                body=interaction_data["request"]["body"],
                content_type=interaction_data["request"]["content_type"],
            )

            response = ContractResponse(
                status_code=interaction_data["response"]["status_code"],
                headers=interaction_data["response"]["headers"],
                body=interaction_data["response"]["body"],
                schema=interaction_data["response"]["schema"],
                content_type=interaction_data["response"]["content_type"],
            )

            interaction = ContractInteraction(
                description=interaction_data["description"],
                request=request,
                response=response,
                metadata=interaction_data["metadata"],
            )

            contract.interactions.append(interaction)

        return contract

    def list_contracts(
        self, consumer: str = None, provider: str = None
    ) -> builtins.list[builtins.dict[str, str]]:
        """List available contracts."""
        contracts = []

        for filepath in self.storage_path.glob("*.json"):
            parts = filepath.stem.split("_")
            if len(parts) >= 3:
                contract_consumer = parts[0]
                contract_provider = parts[1]
                contract_version = "_".join(parts[2:])

                if (consumer is None or contract_consumer == consumer) and (
                    provider is None or contract_provider == provider
                ):
                    contracts.append(
                        {
                            "consumer": contract_consumer,
                            "provider": contract_provider,
                            "version": contract_version,
                            "file": str(filepath),
                        }
                    )

        return contracts


class ContractTestCase(TestCase):
    """Test case for contract verification."""

    def __init__(
        self,
        contract: Contract,
        provider_url: str,
        verification_level: VerificationLevel = VerificationLevel.STRICT,
    ):
        super().__init__(
            name=f"Contract Test: {contract.consumer} -> {contract.provider}",
            test_type=TestType.CONTRACT,
            tags=["contract", contract.consumer, contract.provider],
        )
        self.contract = contract
        self.provider_url = provider_url
        self.validator = ContractValidator(verification_level)
        self.session: aiohttp.ClientSession | None = None

    async def setup(self):
        """Setup contract test."""
        await super().setup()
        self.session = aiohttp.ClientSession()

    async def teardown(self):
        """Teardown contract test."""
        if self.session:
            await self.session.close()
        await super().teardown()

    async def execute(self) -> TestResult:
        """Execute contract verification."""
        start_time = datetime.utcnow()
        errors = []

        try:
            # Validate contract syntax first
            is_valid, syntax_errors = self.validator.validate_contract_syntax(self.contract)
            if not is_valid:
                raise ValueError(f"Contract syntax errors: {', '.join(syntax_errors)}")

            # Execute each interaction
            for i, interaction in enumerate(self.contract.interactions):
                try:
                    actual_response = await self._execute_interaction(interaction)
                    is_valid, validation_errors = self.validator.validate_response(
                        interaction, actual_response
                    )

                    if not is_valid:
                        errors.extend(
                            [f"Interaction {i + 1}: {error}" for error in validation_errors]
                        )

                except Exception as e:
                    errors.append(f"Interaction {i + 1} failed: {e!s}")

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            if errors:
                return TestResult(
                    test_id=self.id,
                    name=self.name,
                    test_type=self.test_type,
                    status=TestStatus.FAILED,
                    execution_time=execution_time,
                    started_at=start_time,
                    completed_at=datetime.utcnow(),
                    error_message=f"Contract verification failed: {'; '.join(errors)}",
                    severity=TestSeverity.HIGH,
                    metrics=TestMetrics(
                        execution_time=execution_time,
                        custom_metrics={
                            "interactions_tested": len(self.contract.interactions),
                            "interactions_failed": len(errors),
                        },
                    ),
                )
            return TestResult(
                test_id=self.id,
                name=self.name,
                test_type=self.test_type,
                status=TestStatus.PASSED,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                metrics=TestMetrics(
                    execution_time=execution_time,
                    custom_metrics={
                        "interactions_tested": len(self.contract.interactions),
                        "interactions_passed": len(self.contract.interactions),
                    },
                ),
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return TestResult(
                test_id=self.id,
                name=self.name,
                test_type=self.test_type,
                status=TestStatus.ERROR,
                execution_time=execution_time,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                error_message=str(e),
                severity=TestSeverity.CRITICAL,
            )

    async def _execute_interaction(
        self, interaction: ContractInteraction
    ) -> builtins.dict[str, Any]:
        """Execute a single contract interaction."""
        url = urljoin(self.provider_url, interaction.request.path)

        # Prepare request parameters
        params = interaction.request.query_params
        headers = interaction.request.headers.copy()

        if interaction.request.content_type:
            headers["Content-Type"] = interaction.request.content_type

        # Prepare request body
        data = None
        json_data = None

        if interaction.request.body is not None:
            if interaction.request.content_type == "application/json":
                json_data = interaction.request.body
            else:
                data = interaction.request.body

        # Execute request
        async with self.session.request(
            method=interaction.request.method,
            url=url,
            params=params,
            headers=headers,
            data=data,
            json=json_data,
        ) as response:
            response_headers = dict(response.headers)

            # Parse response body
            try:
                if response.content_type == "application/json":
                    response_body = await response.json()
                else:
                    response_body = await response.text()
            except Exception as decode_error:
                logger.debug(
                    "Response body parsing failed, falling back to text: %s",
                    decode_error,
                    exc_info=True,
                )
                response_body = await response.text()

            return {
                "status_code": response.status,
                "headers": response_headers,
                "body": response_body,
                "content_type": response.content_type,
            }


class ContractManager:
    """Manages contract testing workflow."""

    def __init__(self, repository: ContractRepository = None):
        self.repository = repository or ContractRepository()

    def create_contract(
        self, consumer: str, provider: str, version: str = "1.0.0"
    ) -> ContractBuilder:
        """Create a new contract builder."""
        return ContractBuilder(consumer, provider, version)

    def save_contract(self, contract: Contract):
        """Save contract to repository."""
        self.repository.save_contract(contract)

    def verify_contract(
        self,
        consumer: str,
        provider: str,
        provider_url: str,
        version: str = None,
        verification_level: VerificationLevel = VerificationLevel.STRICT,
    ) -> ContractTestCase:
        """Create contract verification test case."""
        contract = self.repository.load_contract(consumer, provider, version)

        if not contract:
            raise ValueError(f"Contract not found: {consumer} -> {provider} (version: {version})")

        return ContractTestCase(contract, provider_url, verification_level)

    def generate_contract_from_openapi(
        self, openapi_spec: builtins.dict[str, Any], consumer: str, provider: str
    ) -> Contract:
        """Generate contract from OpenAPI specification."""
        contract = Contract(
            consumer=consumer,
            provider=provider,
            version=openapi_spec.get("info", {}).get("version", "1.0.0"),
            contract_type=ContractType.HTTP_API,
        )

        paths = openapi_spec.get("paths", {})

        for path, methods in paths.items():
            for method, spec in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    # Create interaction from OpenAPI spec
                    description = spec.get("summary", f"{method.upper()} {path}")

                    # Build request
                    request = ContractRequest(method=method.upper(), path=path)

                    # Add query parameters
                    parameters = spec.get("parameters", [])
                    for param in parameters:
                        if param.get("in") == "query":
                            request.query_params[param["name"]] = param.get("example", "test_value")

                    # Build response (use first successful response)
                    responses = spec.get("responses", {})
                    status_code = 200
                    response_spec = None

                    for code, resp in responses.items():
                        if str(code).startswith("2"):
                            status_code = int(code)
                            response_spec = resp
                            break

                    response = ContractResponse(status_code=status_code)

                    if response_spec:
                        content = response_spec.get("content", {})
                        json_content = content.get("application/json", {})
                        schema = json_content.get("schema")

                        if schema:
                            response.schema = schema

                    interaction = ContractInteraction(
                        description=description, request=request, response=response
                    )

                    contract.interactions.append(interaction)

        return contract


# Utility functions
def pact_contract(consumer: str, provider: str, version: str = "1.0.0") -> ContractBuilder:
    """Create a Pact-style contract builder."""
    return ContractBuilder(consumer, provider, version)


async def verify_contracts_for_provider(
    provider: str, provider_url: str, repository: ContractRepository = None
) -> builtins.list[TestResult]:
    """Verify all contracts for a provider."""
    repo = repository or ContractRepository()
    manager = ContractManager(repo)

    contracts = repo.list_contracts(provider=provider)
    results = []

    for contract_info in contracts:
        try:
            test_case = manager.verify_contract(
                consumer=contract_info["consumer"],
                provider=contract_info["provider"],
                provider_url=provider_url,
                version=contract_info["version"],
            )

            result = await test_case.execute()
            results.append(result)

        except Exception as e:
            error_result = TestResult(
                test_id=str(hash(f"{contract_info['consumer']}_{contract_info['provider']}")),
                name=f"Contract verification: {contract_info['consumer']} -> {contract_info['provider']}",
                test_type=TestType.CONTRACT,
                status=TestStatus.ERROR,
                execution_time=0.0,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                error_message=str(e),
                severity=TestSeverity.HIGH,
            )
            results.append(error_result)

    return results
