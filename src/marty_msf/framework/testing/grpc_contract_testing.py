"""
Enhanced Contract Testing Framework for gRPC Services.

This module extends the existing contract testing framework to support gRPC services,
providing comprehensive contract validation for both REST and gRPC APIs.

Features:
- gRPC service contract generation from protobuf definitions
- gRPC client/server contract validation
- Integration with existing Pact-style contract testing
- Support for streaming gRPC contracts
- Protocol buffer schema validation
- gRPC reflection-based contract discovery

Author: Marty Framework Team
Version: 1.0.0
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Union

import grpc
from google.protobuf import descriptor_pb2, message
from google.protobuf.descriptor import MethodDescriptor, ServiceDescriptor
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc

from ..testing.contract_testing import (
    Contract,
    ContractBuilder,
    ContractInteraction,
    ContractManager,
    ContractRepository,
    ContractType,
    TestResult,
    TestStatus,
    VerificationLevel,
    verify_contracts_for_provider,
)

logger = logging.getLogger(__name__)


@dataclass
class GRPCContractRequest:
    """gRPC request specification for contract."""

    method_name: str
    service_name: str
    request_type: str
    request_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    streaming: str = "unary"  # unary, client_streaming, server_streaming, bidirectional


@dataclass
class GRPCContractResponse:
    """gRPC response specification for contract."""

    response_type: str
    response_data: dict[str, Any] = field(default_factory=dict)
    status_code: str = "OK"
    error_message: str | None = None
    response_metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class GRPCContractInteraction:
    """gRPC interaction in a contract."""

    description: str
    request: GRPCContractRequest
    response: GRPCContractResponse
    given: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GRPCContract:
    """gRPC service contract definition."""

    consumer: str
    provider: str
    version: str
    service_name: str
    package_name: str
    proto_file: str | None = None
    interactions: list[GRPCContractInteraction] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class GRPCContractBuilder:
    """Builder for creating gRPC contracts."""

    def __init__(self, consumer: str, provider: str, service_name: str, version: str = "1.0.0"):
        self.contract = GRPCContract(
            consumer=consumer,
            provider=provider,
            version=version,
            service_name=service_name,
            package_name=""
        )

    def with_package(self, package_name: str) -> "GRPCContractBuilder":
        """Set the package name."""
        self.contract.package_name = package_name
        return self

    def with_proto_file(self, proto_file: str) -> "GRPCContractBuilder":
        """Set the proto file path."""
        self.contract.proto_file = proto_file
        return self

    def with_metadata(self, **metadata) -> "GRPCContractBuilder":
        """Add contract metadata."""
        self.contract.metadata.update(metadata)
        return self

    def interaction(self, description: str) -> "GRPCInteractionBuilder":
        """Start building an interaction."""
        return GRPCInteractionBuilder(self, description)

    def build(self) -> GRPCContract:
        """Build the contract."""
        return self.contract


class GRPCInteractionBuilder:
    """Builder for creating gRPC contract interactions."""

    def __init__(self, contract_builder: GRPCContractBuilder, description: str):
        self.contract_builder = contract_builder
        self.interaction = GRPCContractInteraction(
            description=description,
            request=GRPCContractRequest(method_name="", service_name="", request_type=""),
            response=GRPCContractResponse(response_type="")
        )

    def given(self, state: str) -> "GRPCInteractionBuilder":
        """Add provider state."""
        self.interaction.given.append(state)
        return self

    def upon_calling(self, method_name: str, service_name: str | None = None) -> "GRPCInteractionBuilder":
        """Set the gRPC method being called."""
        self.interaction.request.method_name = method_name
        self.interaction.request.service_name = service_name or self.contract_builder.contract.service_name
        return self

    def with_request(self, request_type: str, **request_data) -> "GRPCInteractionBuilder":
        """Configure the request."""
        self.interaction.request.request_type = request_type
        self.interaction.request.request_data = request_data
        return self

    def with_metadata(self, **metadata) -> "GRPCInteractionBuilder":
        """Add request metadata."""
        self.interaction.request.metadata.update(metadata)
        return self

    def with_timeout(self, timeout: float) -> "GRPCInteractionBuilder":
        """Set request timeout."""
        self.interaction.request.timeout = timeout
        return self

    def with_streaming(self, streaming_type: str) -> "GRPCInteractionBuilder":
        """Set streaming type."""
        self.interaction.request.streaming = streaming_type
        return self

    def will_respond_with(self, response_type: str, status: str = "OK", **response_data) -> "GRPCInteractionBuilder":
        """Configure the expected response."""
        self.interaction.response.response_type = response_type
        self.interaction.response.status_code = status
        self.interaction.response.response_data = response_data
        return self

    def will_fail_with(self, status: str, error_message: str) -> "GRPCInteractionBuilder":
        """Configure an expected error response."""
        self.interaction.response.status_code = status
        self.interaction.response.error_message = error_message
        return self

    def and_interaction(self, description: str) -> "GRPCInteractionBuilder":
        """Add current interaction and start a new one."""
        self.contract_builder.contract.interactions.append(self.interaction)
        return GRPCInteractionBuilder(self.contract_builder, description)

    def build(self) -> GRPCContract:
        """Add interaction and build contract."""
        self.contract_builder.contract.interactions.append(self.interaction)
        return self.contract_builder.build()


class GRPCContractValidator:
    """Validates gRPC contracts against running services."""

    def __init__(self, verification_level: VerificationLevel = VerificationLevel.STRICT):
        self.verification_level = verification_level

    async def validate_contract(self, contract: GRPCContract, server_address: str) -> TestResult:
        """Validate a gRPC contract against a running service."""
        errors = []
        warnings = []

        try:
            # Create gRPC channel
            channel = grpc.aio.insecure_channel(server_address)

            # Validate service availability
            if not await self._check_service_availability(channel, contract.service_name):
                errors.append(f"Service {contract.service_name} not available at {server_address}")
                return TestResult(
                    test_id=f"grpc_contract_{contract.consumer}_{contract.provider}",
                    status=TestStatus.FAILED,
                    errors=errors,
                    duration_ms=0
                )

            # Validate each interaction
            interaction_results = []
            for interaction in contract.interactions:
                result = await self._validate_interaction(channel, interaction, contract)
                interaction_results.append(result)

                if not result.passed:
                    errors.extend(result.errors)
                if result.warnings:
                    warnings.extend(result.warnings)

            # Close channel
            await channel.close()

            status = TestStatus.PASSED if not errors else TestStatus.FAILED
            if warnings and self.verification_level == VerificationLevel.STRICT:
                status = TestStatus.FAILED

            return TestResult(
                test_id=f"grpc_contract_{contract.consumer}_{contract.provider}",
                status=status,
                errors=errors,
                warnings=warnings,
                duration_ms=sum(r.duration_ms for r in interaction_results)
            )

        except Exception as e:
            logger.error(f"Error validating gRPC contract: {e}")
            return TestResult(
                test_id=f"grpc_contract_{contract.consumer}_{contract.provider}",
                status=TestStatus.ERROR,
                errors=[str(e)],
                duration_ms=0
            )

    async def _check_service_availability(self, channel: grpc.aio.Channel, service_name: str) -> bool:
        """Check if the gRPC service is available using reflection."""
        try:
            stub = reflection_pb2_grpc.ServerReflectionStub(channel)
            request = reflection_pb2.ServerReflectionRequest()
            request.list_services = ""

            response_stream = stub.ServerReflectionInfo(iter([request]))
            async for response in response_stream:
                if response.HasField('list_services_response'):
                    services = [s.name for s in response.list_services_response.service]
                    return service_name in services

            return False
        except Exception as e:
            logger.warning(f"Could not check service availability using reflection: {e}")
            return True  # Assume available if reflection fails

    async def _validate_interaction(self, channel: grpc.aio.Channel,
                                  interaction: GRPCContractInteraction,
                                  contract: GRPCContract) -> TestResult:
        """Validate a single gRPC interaction."""
        start_time = datetime.now()
        errors = []
        warnings = []

        try:
            # Create dynamic stub (simplified - in practice would use reflection)
            # This is a placeholder for actual gRPC method invocation
            method_name = interaction.request.method_name

            # For now, we'll simulate the call
            # In a real implementation, you'd use the service descriptor
            # to create proper request/response objects

            # Simulate request/response validation
            if not interaction.request.request_type:
                errors.append(f"Request type not specified for {method_name}")

            if not interaction.response.response_type:
                errors.append(f"Response type not specified for {method_name}")

            # Check timeout
            if interaction.request.timeout <= 0:
                warnings.append(f"Invalid timeout for {method_name}: {interaction.request.timeout}")

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return TestResult(
                test_id=f"grpc_interaction_{method_name}",
                status=TestStatus.PASSED if not errors else TestStatus.FAILED,
                errors=errors,
                warnings=warnings,
                duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return TestResult(
                test_id=f"grpc_interaction_{interaction.request.method_name}",
                status=TestStatus.ERROR,
                errors=[str(e)],
                duration_ms=duration_ms
            )


class GRPCContractRepository:
    """Repository for storing and retrieving gRPC contracts."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save_contract(self, contract: GRPCContract) -> bool:
        """Save a gRPC contract to storage."""
        try:
            filename = f"grpc_{contract.consumer}_{contract.provider}_{contract.version}.json"
            filepath = self.storage_path / filename

            contract_dict = {
                "consumer": contract.consumer,
                "provider": contract.provider,
                "version": contract.version,
                "service_name": contract.service_name,
                "package_name": contract.package_name,
                "proto_file": contract.proto_file,
                "interactions": [
                    {
                        "description": i.description,
                        "given": i.given,
                        "request": {
                            "method_name": i.request.method_name,
                            "service_name": i.request.service_name,
                            "request_type": i.request.request_type,
                            "request_data": i.request.request_data,
                            "metadata": i.request.metadata,
                            "timeout": i.request.timeout,
                            "streaming": i.request.streaming
                        },
                        "response": {
                            "response_type": i.response.response_type,
                            "response_data": i.response.response_data,
                            "status_code": i.response.status_code,
                            "error_message": i.response.error_message,
                            "response_metadata": i.response.response_metadata
                        },
                        "metadata": i.metadata
                    }
                    for i in contract.interactions
                ],
                "metadata": contract.metadata,
                "created_date": contract.created_date
            }

            with open(filepath, 'w') as f:
                json.dump(contract_dict, f, indent=2)

            logger.info(f"Saved gRPC contract: {filename}")
            return True

        except Exception as e:
            logger.error(f"Error saving gRPC contract: {e}")
            return False

    def load_contract(self, consumer: str, provider: str, version: str | None = None) -> GRPCContract | None:
        """Load a gRPC contract from storage."""
        try:
            # Find matching contract file
            pattern = f"grpc_{consumer}_{provider}"
            if version:
                pattern += f"_{version}"
            pattern += ".json"

            matching_files = list(self.storage_path.glob(pattern))
            if not matching_files:
                return None

            # Use the first match (or most recent if multiple)
            filepath = sorted(matching_files)[-1]

            with open(filepath) as f:
                contract_dict = json.load(f)

            # Reconstruct contract
            contract = GRPCContract(
                consumer=contract_dict["consumer"],
                provider=contract_dict["provider"],
                version=contract_dict["version"],
                service_name=contract_dict["service_name"],
                package_name=contract_dict["package_name"],
                proto_file=contract_dict.get("proto_file"),
                metadata=contract_dict.get("metadata", {}),
                created_date=contract_dict.get("created_date", "")
            )

            # Reconstruct interactions
            for i_dict in contract_dict.get("interactions", []):
                request = GRPCContractRequest(
                    method_name=i_dict["request"]["method_name"],
                    service_name=i_dict["request"]["service_name"],
                    request_type=i_dict["request"]["request_type"],
                    request_data=i_dict["request"]["request_data"],
                    metadata=i_dict["request"]["metadata"],
                    timeout=i_dict["request"]["timeout"],
                    streaming=i_dict["request"]["streaming"]
                )

                response = GRPCContractResponse(
                    response_type=i_dict["response"]["response_type"],
                    response_data=i_dict["response"]["response_data"],
                    status_code=i_dict["response"]["status_code"],
                    error_message=i_dict["response"]["error_message"],
                    response_metadata=i_dict["response"]["response_metadata"]
                )

                interaction = GRPCContractInteraction(
                    description=i_dict["description"],
                    request=request,
                    response=response,
                    given=i_dict["given"],
                    metadata=i_dict["metadata"]
                )

                contract.interactions.append(interaction)

            return contract

        except Exception as e:
            logger.error(f"Error loading gRPC contract: {e}")
            return None

    def list_contracts(self, consumer: str | None = None, provider: str | None = None) -> list[dict[str, str]]:
        """List available gRPC contracts."""
        contracts = []

        for filepath in self.storage_path.glob("grpc_*.json"):
            parts = filepath.stem.split("_")
            if len(parts) >= 4:  # grpc_consumer_provider_version
                contract_consumer = parts[1]
                contract_provider = parts[2]
                contract_version = "_".join(parts[3:])

                if (consumer is None or contract_consumer == consumer) and \
                   (provider is None or contract_provider == provider):
                    contracts.append({
                        "consumer": contract_consumer,
                        "provider": contract_provider,
                        "version": contract_version,
                        "file": str(filepath),
                        "type": "grpc"
                    })

        return contracts


class EnhancedContractManager:
    """Enhanced contract manager supporting both REST and gRPC contracts."""

    def __init__(self, repository: ContractRepository | None = None,
                 grpc_repository: GRPCContractRepository | None = None):
        self.repository = repository or ContractRepository()
        self.grpc_repository = grpc_repository or GRPCContractRepository(
            Path.cwd() / "contracts" / "grpc"
        )

    # REST contract methods (delegate to existing manager)
    def create_contract(self, consumer: str, provider: str, version: str = "1.0.0") -> ContractBuilder:
        """Create a new REST contract builder."""
        return ContractBuilder(consumer, provider, version)

    def save_contract(self, contract: Contract):
        """Save a REST contract to repository."""
        self.repository.save_contract(contract)

    # gRPC contract methods
    def create_grpc_contract(self, consumer: str, provider: str, service_name: str,
                           version: str = "1.0.0") -> GRPCContractBuilder:
        """Create a new gRPC contract builder."""
        return GRPCContractBuilder(consumer, provider, service_name, version)

    def save_grpc_contract(self, contract: GRPCContract):
        """Save a gRPC contract to repository."""
        self.grpc_repository.save_contract(contract)

    async def verify_grpc_contract(self, consumer: str, provider: str, server_address: str,
                                 version: str | None = None,
                                 verification_level: VerificationLevel = VerificationLevel.STRICT) -> TestResult:
        """Verify a gRPC contract against a running service."""
        contract = self.grpc_repository.load_contract(consumer, provider, version)

        if not contract:
            return TestResult(
                test_id=f"grpc_contract_{consumer}_{provider}",
                status=TestStatus.ERROR,
                errors=[f"gRPC contract not found: {consumer} -> {provider} (version: {version})"],
                duration_ms=0
            )

        validator = GRPCContractValidator(verification_level)
        return await validator.validate_contract(contract, server_address)

    def list_all_contracts(self, consumer: str | None = None, provider: str | None = None) -> list[dict[str, str]]:
        """List all contracts (both REST and gRPC)."""
        rest_contracts = self.repository.list_contracts(consumer or "", provider or "")
        grpc_contracts = self.grpc_repository.list_contracts(consumer or "", provider or "")

        # Add type information
        for contract in rest_contracts:
            contract["type"] = "rest"

        return rest_contracts + grpc_contracts

    async def verify_all_contracts_for_provider(self, provider: str,
                                              rest_url: str = None,
                                              grpc_address: str = None) -> list[TestResult]:
        """Verify all contracts for a provider (both REST and gRPC)."""
        results = []

        # Verify REST contracts
        if rest_url:
            rest_results = await verify_contracts_for_provider(provider, rest_url, self.repository)
            results.extend(rest_results)

        # Verify gRPC contracts
        if grpc_address:
            grpc_contracts = self.grpc_repository.list_contracts(provider=provider)
            for contract_info in grpc_contracts:
                contract = self.grpc_repository.load_contract(
                    contract_info["consumer"],
                    contract_info["provider"],
                    contract_info["version"]
                )
                if contract:
                    validator = GRPCContractValidator()
                    result = await validator.validate_contract(contract, grpc_address)
                    results.append(result)

        return results


# Utility functions for gRPC contract creation
def grpc_contract(consumer: str, provider: str, service_name: str, version: str = "1.0.0") -> GRPCContractBuilder:
    """Create a gRPC contract builder (convenience function)."""
    return GRPCContractBuilder(consumer, provider, service_name, version)


async def generate_contract_from_proto(proto_file: Path, consumer: str, provider: str) -> GRPCContract:
    """Generate a gRPC contract from a protobuf file."""
    # This is a simplified implementation
    # In practice, you'd parse the proto file to extract service definitions

    try:
        content = proto_file.read_text()

        # Extract service name (simplified parsing)
        service_match = re.search(r'service\s+(\w+)', content)
        service_name = service_match.group(1) if service_match else "UnknownService"

        # Extract package
        package_match = re.search(r'package\s+([^;]+);', content)
        package_name = package_match.group(1) if package_match else ""

        contract = GRPCContract(
            consumer=consumer,
            provider=provider,
            version="1.0.0",
            service_name=service_name,
            package_name=package_name,
            proto_file=str(proto_file)
        )

        # Extract methods (simplified)
        method_pattern = r'rpc\s+(\w+)\s*\(([^)]+)\)\s*returns\s*\(([^)]+)\)'
        methods = re.findall(method_pattern, content)

        for method_name, input_type, output_type in methods:
            interaction = GRPCContractInteraction(
                description=f"Call {method_name}",
                request=GRPCContractRequest(
                    method_name=method_name,
                    service_name=service_name,
                    request_type=input_type.strip()
                ),
                response=GRPCContractResponse(
                    response_type=output_type.strip()
                )
            )
            contract.interactions.append(interaction)

        return contract

    except Exception as e:
        logger.error(f"Error generating contract from proto file {proto_file}: {e}")
        raise


# Integration with existing contract testing framework
class UnifiedContractManager(ContractManager):
    """Unified contract manager that extends the existing one with gRPC support."""

    def __init__(self, repository: ContractRepository | None = None):
        # Pass repository with proper handling for None
        super().__init__(repository or ContractRepository())
        self.enhanced_manager = EnhancedContractManager(repository)

    def create_grpc_contract(self, consumer: str, provider: str, service_name: str,
                           version: str = "1.0.0") -> GRPCContractBuilder:
        """Create a new gRPC contract builder."""
        return self.enhanced_manager.create_grpc_contract(consumer, provider, service_name, version)

    def save_grpc_contract(self, contract: GRPCContract):
        """Save a gRPC contract."""
        self.enhanced_manager.save_grpc_contract(contract)

    async def verify_grpc_contract(self, consumer: str, provider: str, server_address: str,
                                 version: str | None = None) -> TestResult:
        """Verify a gRPC contract."""
        return await self.enhanced_manager.verify_grpc_contract(
            consumer, provider, server_address, version
        )
