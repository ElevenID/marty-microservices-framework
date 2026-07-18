"""
gRPC Client Library

Provides managed channel lifecycle, stub factory, and client-side interceptors
for inter-service gRPC communication.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import grpc
from grpc import aio
from grpc_health.v1 import health_pb2, health_pb2_grpc

logger = logging.getLogger(__name__)


class GrpcChannelManager:
    """Manages a pool of gRPC channels with health monitoring.

    Channels are created lazily on first access and shared across stubs
    targeting the same address. Unhealthy channels are transparently
    re-created.

    Usage::

        manager = GrpcChannelManager()
        channel = await manager.get_channel("document-signer:8082")
        stub = DocumentSignerStub(channel)
        # ...
        await manager.close_all()
    """

    def __init__(
        self,
        *,
        tls_enabled: bool = False,
        root_cert_path: str | None = None,
        client_cert_path: str | None = None,
        client_key_path: str | None = None,
        keepalive_time_ms: int = 30_000,
        keepalive_timeout_ms: int = 5_000,
    ):
        self._tls_enabled = tls_enabled
        self._root_cert_path = root_cert_path
        self._client_cert_path = client_cert_path
        self._client_key_path = client_key_path
        self._keepalive_time_ms = keepalive_time_ms
        self._keepalive_timeout_ms = keepalive_timeout_ms

        self._channels: dict[str, aio.Channel] = {}
        self._lock = asyncio.Lock()

    async def get_channel(
        self,
        target: str,
        *,
        interceptors: list[grpc.aio.ClientInterceptor] | None = None,
    ) -> aio.Channel:
        """Return a (possibly cached) async channel to *target*.

        Args:
            target: gRPC target address (e.g. ``"service:50051"``).
            interceptors: Optional client-side interceptors applied to
                the channel.
        """
        async with self._lock:
            existing = self._channels.get(target)
            if existing is not None:
                state = existing.get_state(try_to_connect=False)
                if state != grpc.ChannelConnectivity.SHUTDOWN:
                    return existing
                # Channel was shut down — recreate
                logger.warning("Channel to %s was shut down, recreating", target)

            channel = self._create_channel(target, interceptors)
            self._channels[target] = channel
            return channel

    async def close(self, target: str) -> None:
        """Close and remove the channel for *target*."""
        async with self._lock:
            channel = self._channels.pop(target, None)
            if channel is not None:
                await channel.close()
                logger.info("Closed gRPC channel to %s", target)

    async def close_all(self) -> None:
        """Close all managed channels."""
        async with self._lock:
            for target, channel in self._channels.items():
                await channel.close()
                logger.info("Closed gRPC channel to %s", target)
            self._channels.clear()

    def _create_channel(
        self,
        target: str,
        interceptors: list[grpc.aio.ClientInterceptor] | None,
    ) -> aio.Channel:
        options = [
            ("grpc.keepalive_time_ms", self._keepalive_time_ms),
            ("grpc.keepalive_timeout_ms", self._keepalive_timeout_ms),
            ("grpc.keepalive_permit_without_calls", True),
            ("grpc.http2.max_pings_without_data", 0),
        ]

        if self._tls_enabled:
            root_cert = _read_optional(self._root_cert_path)
            client_cert = _read_optional(self._client_cert_path)
            client_key = _read_optional(self._client_key_path)
            credentials = grpc.ssl_channel_credentials(
                root_certificates=root_cert,
                private_key=client_key,
                certificate_chain=client_cert,
            )
            channel = aio.secure_channel(
                target, credentials, options=options, interceptors=interceptors
            )
        else:
            channel = aio.insecure_channel(target, options=options, interceptors=interceptors)

        logger.info("Created gRPC channel to %s (tls=%s)", target, self._tls_enabled)
        return channel


class GrpcStubFactory:
    """Factory for creating typed gRPC stubs from a :class:`GrpcChannelManager`.

    Usage::

        manager = GrpcChannelManager()
        factory = GrpcStubFactory(manager)

        factory.register("document-signer", "document-signer:8082", DocumentSignerStub)

        stub = await factory.get_stub("document-signer")
        response = await stub.SignDocument(request)
    """

    def __init__(self, channel_manager: GrpcChannelManager):
        self._manager = channel_manager
        self._registry: dict[str, _StubRegistration] = {}

    def register(self, name: str, target: str, stub_class: type) -> None:
        """Register a service stub for lazy creation.

        Args:
            name: Logical service name.
            target: gRPC address (e.g. ``"service:50051"``).
            stub_class: The generated ``*Stub`` class.
        """
        self._registry[name] = _StubRegistration(
            target=target, stub_class=stub_class, instance=None
        )

    async def get_stub(self, name: str) -> Any:
        """Get or create a stub instance by service name."""
        reg = self._registry.get(name)
        if reg is None:
            raise KeyError(f"Service '{name}' not registered. Known: {list(self._registry)}")

        if reg.instance is not None:
            return reg.instance

        channel = await self._manager.get_channel(reg.target)
        reg.instance = reg.stub_class(channel)
        return reg.instance

    def invalidate(self, name: str) -> None:
        """Drop the cached stub so it is re-created on next access."""
        reg = self._registry.get(name)
        if reg is not None:
            reg.instance = None

    async def health_check(self, name: str) -> bool:
        """Check the gRPC health of a registered service."""
        reg = self._registry.get(name)
        if reg is None:
            return False

        try:
            channel = await self._manager.get_channel(reg.target)
            stub = health_pb2_grpc.HealthStub(channel)
            resp = await stub.Check(
                health_pb2.HealthCheckRequest(service=""),
                timeout=5,
            )
            return resp.status == health_pb2.HealthCheckResponse.SERVING
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Client-side interceptors
# ---------------------------------------------------------------------------


class MetricsClientInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    """Records Prometheus-style metrics for outbound gRPC calls.

    Collects counters (by method + status) and latency histograms. The
    collected data is exposed via ``get_metrics()`` for reporting.
    """

    def __init__(self):
        self._call_count: dict[tuple[str, str], int] = {}
        self._latencies: list[tuple[str, float]] = []

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        method = client_call_details.method
        start = time.time()
        try:
            response = await continuation(client_call_details, request)
            status = "OK"
            return response
        except grpc.aio.AioRpcError as exc:
            status = exc.code().name
            raise
        finally:
            latency = time.time() - start
            key = (method, status)
            self._call_count[key] = self._call_count.get(key, 0) + 1
            self._latencies.append((method, latency))

    def get_metrics(self) -> dict:
        return {
            "call_counts": dict(self._call_count),
            "latencies": list(self._latencies),
        }


class AuthTokenInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    """Injects an authorization token into outbound gRPC metadata.

    The token can be a static string or a callable returning a token
    (supporting async callables for token refresh).
    """

    def __init__(self, token_provider: str | Any):
        self._token_provider = token_provider

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        if callable(self._token_provider):
            token = self._token_provider()
            if asyncio.iscoroutine(token):
                token = await token
        else:
            token = self._token_provider

        metadata = list(client_call_details.metadata or [])
        metadata.append(("authorization", f"Bearer {token}"))

        new_details = grpc.aio.ClientCallDetails(
            method=client_call_details.method,
            timeout=client_call_details.timeout,
            metadata=metadata,
            credentials=client_call_details.credentials,
            wait_for_ready=client_call_details.wait_for_ready,
        )
        return await continuation(new_details, request)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _StubRegistration:
    __slots__ = ("target", "stub_class", "instance")

    def __init__(self, target: str, stub_class: type, instance: Any):
        self.target = target
        self.stub_class = stub_class
        self.instance = instance


def _read_optional(path: str | None) -> bytes | None:
    if not path:
        return None
    with open(path, "rb") as f:
        return f.read()
