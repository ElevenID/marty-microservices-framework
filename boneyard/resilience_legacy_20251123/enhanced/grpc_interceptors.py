"""
Enhanced gRPC interceptors with resilience patterns.

Ported from Marty's resilience framework to provide comprehensive
gRPC interceptor capabilities for microservices.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import grpc

logger = logging.getLogger(__name__)


class ResilienceClientInterceptor(grpc.UnaryUnaryClientInterceptor):
    """Basic resilience client interceptor for gRPC calls."""

    def __init__(self, timeout: float = 30.0, retry_attempts: int = 3):
        self.timeout = timeout
        self.retry_attempts = retry_attempts

    def intercept_unary_unary(
        self,
        continuation: Callable[[grpc.ClientCallDetails, Any], grpc.Call],
        client_call_details: grpc.ClientCallDetails,
        request: Any,
    ) -> grpc.Call:
        """Intercept unary-unary gRPC calls."""
        # Log the call
        logger.debug("gRPC call to %s", client_call_details.method)

        return continuation(client_call_details, request)


class AsyncResilienceClientInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    """Async resilience client interceptor for gRPC calls."""

    def __init__(self, timeout: float = 30.0, retry_attempts: int = 3):
        self.timeout = timeout
        self.retry_attempts = retry_attempts

    async def intercept_unary_unary(
        self,
        continuation: Callable[
            [grpc.aio.ClientCallDetails, Any], Awaitable[grpc.aio.UnaryUnaryCall]
        ],
        client_call_details: grpc.aio.ClientCallDetails,
        request: Any,
    ) -> grpc.aio.UnaryUnaryCall:
        """Intercept async unary-unary gRPC calls."""
        # Log the call
        logger.debug("Async gRPC call to %s", client_call_details.method)

        return await continuation(client_call_details, request)


class EnhancedResilienceServerInterceptor(grpc.aio.ServerInterceptor):
    """Enhanced resilience server interceptor for gRPC services."""

    def __init__(self, collect_metrics: bool = True):
        self.collect_metrics = collect_metrics
        self.call_count = 0
        self.error_count = 0

    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        """Intercept gRPC service calls."""
        start_time = time.time()
        self.call_count += 1

        logger.debug("Handling gRPC call to %s", handler_call_details.method)

        try:
            handler = await continuation(handler_call_details)
            return handler
        except Exception as e:
            self.error_count += 1
            logger.error("Error in gRPC call to %s: %s", handler_call_details.method, e)
            raise
        finally:
            if self.collect_metrics:
                duration = time.time() - start_time
                logger.debug(
                    "gRPC call to %s completed in %.3fs", handler_call_details.method, duration
                )


class CompositeResilienceInterceptor:
    """Composite interceptor that combines multiple resilience patterns."""

    def __init__(self):
        self.interceptors = []

    def add_interceptor(self, interceptor: Any) -> None:
        """Add an interceptor to the composite."""
        self.interceptors.append(interceptor)

    def get_client_interceptors(self) -> list[grpc.UnaryUnaryClientInterceptor]:
        """Get all client interceptors."""
        return [i for i in self.interceptors if isinstance(i, grpc.UnaryUnaryClientInterceptor)]

    def get_server_interceptors(self) -> list[grpc.aio.ServerInterceptor]:
        """Get all server interceptors."""
        return [i for i in self.interceptors if isinstance(i, grpc.aio.ServerInterceptor)]
