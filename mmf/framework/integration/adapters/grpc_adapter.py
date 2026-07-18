"""
gRPC Adapter

Provides a gRPC client adapter implementing ExternalSystemPort for inter-service
communication. Manages channel lifecycle, stub creation, and health checking.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import grpc
from grpc import aio
from grpc_health.v1 import health_pb2, health_pb2_grpc

from mmf.framework.integration.domain.exceptions import (
    ConnectionFailedError,
)
from mmf.framework.integration.domain.models import (
    ConnectionConfig,
    IntegrationRequest,
    IntegrationResponse,
)
from mmf.framework.integration.ports.connector import ExternalSystemPort

logger = logging.getLogger(__name__)


class GrpcAdapter(ExternalSystemPort):
    """gRPC client adapter for inter-service communication.

    Manages an async gRPC channel with configurable TLS and keepalive settings.
    Operations are dispatched by mapping ``request.operation`` to registered
    stub methods.

    Usage::

        config = ConnectionConfig(
            system_id="document-signer",
            name="Document Signer",
            connector_type=ConnectorType.GRPC,
            endpoint_url="document-signer:8082",
            protocol_settings={
                "tls_enabled": False,
                # Optional TLS fields:
                # "root_cert_path": "/certs/ca.pem",
                # "client_cert_path": "/certs/client.pem",
                # "client_key_path": "/certs/client-key.pem",
            },
        )
        adapter = GrpcAdapter(config)
        adapter.register_stub("DocumentSigner", DocumentSignerStub)
        adapter.register_operation(
            "SignDocument",
            stub_name="DocumentSigner",
            method="SignDocument",
            request_class=SignDocumentRequest,
        )

        await adapter.connect()
        response = await adapter.execute_request(
            IntegrationRequest(
                system_id="document-signer",
                operation="SignDocument",
                data={"document": "..."},
            )
        )
    """

    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.channel: aio.Channel | None = None
        self.connected = False
        self._stubs: dict[str, Any] = {}
        self._stub_classes: dict[str, type] = {}
        self._operations: dict[str, _OperationBinding] = {}

    def register_stub(self, name: str, stub_class: type) -> None:
        """Register a gRPC stub class that will be instantiated on connect.

        Args:
            name: Logical name for this stub (e.g. "DocumentSigner").
            stub_class: The generated ``*Stub`` class (e.g.
                ``document_signer_pb2_grpc.DocumentSignerStub``).
        """
        self._stub_classes[name] = stub_class

    def register_operation(
        self,
        operation: str,
        *,
        stub_name: str,
        method: str,
        request_class: type | None = None,
    ) -> None:
        """Map an operation name to a stub method.

        Args:
            operation: The ``IntegrationRequest.operation`` value.
            stub_name: Name of a previously registered stub.
            method: The RPC method name on the stub.
            request_class: Optional protobuf request message class. When
                provided, ``request.data`` (a dict) will be unpacked into
                ``request_class(**data)`` automatically.
        """
        self._operations[operation] = _OperationBinding(
            stub_name=stub_name,
            method=method,
            request_class=request_class,
        )

    # -- ExternalSystemPort interface -----------------------------------------

    async def connect(self) -> bool:
        """Open a gRPC channel to the target service."""
        if self.connected and self.channel is not None:
            return True

        target = self.config.endpoint_url
        settings = self.config.protocol_settings or {}

        channel_options = [
            ("grpc.keepalive_time_ms", settings.get("keepalive_time_ms", 30_000)),
            ("grpc.keepalive_timeout_ms", settings.get("keepalive_timeout_ms", 5_000)),
            ("grpc.keepalive_permit_without_calls", True),
        ]

        try:
            if settings.get("tls_enabled"):
                root_cert = _read_optional(settings.get("root_cert_path"))
                client_cert = _read_optional(settings.get("client_cert_path"))
                client_key = _read_optional(settings.get("client_key_path"))
                credentials = grpc.ssl_channel_credentials(
                    root_certificates=root_cert,
                    private_key=client_key,
                    certificate_chain=client_cert,
                )
                self.channel = aio.secure_channel(target, credentials, options=channel_options)
            else:
                self.channel = aio.insecure_channel(target, options=channel_options)

            # Instantiate all registered stubs on this channel
            for name, stub_cls in self._stub_classes.items():
                self._stubs[name] = stub_cls(self.channel)

            self.connected = True
            logger.info("gRPC channel opened to %s", target)
            return True
        except Exception as exc:
            logger.exception("Failed to open gRPC channel to %s", target)
            raise ConnectionFailedError(f"Failed to connect to {target}: {exc}") from exc

    async def disconnect(self) -> bool:
        """Close the gRPC channel."""
        try:
            if self.channel is not None:
                await self.channel.close()
                self.channel = None
            self._stubs.clear()
            self.connected = False
            logger.info("gRPC channel closed for %s", self.config.endpoint_url)
            return True
        except Exception:
            logger.exception("Error closing gRPC channel for %s", self.config.endpoint_url)
            return False

    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Dispatch an RPC based on ``request.operation``.

        If the operation was registered via :meth:`register_operation`, the
        adapter resolves the correct stub/method and optionally constructs
        the protobuf request from ``request.data``.

        If the operation is **not** registered, the adapter falls back to
        interpreting ``request.operation`` as ``"StubName.MethodName"`` and
        passes ``request.data`` directly as the protobuf message.
        """
        if not self.connected or self.channel is None:
            await self.connect()

        start_time = time.time()

        try:
            binding = self._operations.get(request.operation)
            if binding is not None:
                stub = self._stubs.get(binding.stub_name)
                if stub is None:
                    raise ValueError(
                        f"Stub '{binding.stub_name}' not found. "
                        f"Registered stubs: {list(self._stubs)}"
                    )
                rpc_method = getattr(stub, binding.method)

                if binding.request_class is not None and isinstance(request.data, dict):
                    proto_request = binding.request_class(**request.data)
                else:
                    proto_request = request.data

                timeout = request.timeout or self.config.timeout
                result = await rpc_method(proto_request, timeout=timeout)
            else:
                # Fallback: operation = "StubName.MethodName"
                result = await self._dynamic_dispatch(request)

            latency = (time.time() - start_time) * 1000
            return IntegrationResponse(
                request_id=request.request_id,
                success=True,
                data=result,
                latency_ms=latency,
            )
        except grpc.aio.AioRpcError as exc:
            latency = (time.time() - start_time) * 1000
            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_code=exc.code().name,
                error_message=exc.details(),
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.time() - start_time) * 1000
            logger.exception("gRPC request failed: %s", exc)
            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(exc),
                latency_ms=latency,
            )

    async def health_check(self) -> bool:
        """Check service health via the gRPC Health protocol."""
        if not self.connected or self.channel is None:
            return False

        try:
            stub = health_pb2_grpc.HealthStub(self.channel)
            settings = self.config.protocol_settings or {}
            service_name = settings.get("health_service_name", "")
            resp = await stub.Check(
                health_pb2.HealthCheckRequest(service=service_name),
                timeout=5,
            )
            return resp.status == health_pb2.HealthCheckResponse.SERVING
        except Exception:
            return False

    # -- Internal helpers -----------------------------------------------------

    async def _dynamic_dispatch(self, request: IntegrationRequest) -> Any:
        """Fallback dispatcher: parse ``StubName.Method`` from operation."""
        parts = request.operation.split(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Unregistered operation '{request.operation}'. "
                f"Expected format 'StubName.MethodName' or register it first."
            )
        stub_name, method_name = parts
        stub = self._stubs.get(stub_name)
        if stub is None:
            raise ValueError(f"Stub '{stub_name}' not found. Registered: {list(self._stubs)}")
        rpc_method = getattr(stub, method_name)
        timeout = request.timeout or self.config.timeout
        return await rpc_method(request.data, timeout=timeout)


class _OperationBinding:
    """Internal mapping from an operation name to a stub method."""

    __slots__ = ("stub_name", "method", "request_class")

    def __init__(self, stub_name: str, method: str, request_class: type | None):
        self.stub_name = stub_name
        self.method = method
        self.request_class = request_class


def _read_optional(path: str | None) -> bytes | None:
    """Read a file if path is provided, otherwise return None."""
    if not path:
        return None
    with open(path, "rb") as f:
        return f.read()
