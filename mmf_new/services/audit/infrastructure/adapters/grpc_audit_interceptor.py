"""
gRPC Audit Interceptor - Infrastructure Adapter

This module provides automatic auditing for gRPC services using interceptors.
It captures incoming gRPC requests and responses for audit logging.
"""

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any, Optional, Union

import grpc
from grpc import aio
from grpc.aio import ServerInterceptor

from mmf_new.core.domain.audit_types import AuditEventType, AuditSeverity
from mmf_new.services.audit.application.commands import LogRequestCommand
from mmf_new.services.audit.domain.contracts import IAuditService, IMiddlewareAuditor


class GrpcAuditConfig:
    """Configuration for gRPC audit interceptor."""

    def __init__(
        self,
        enabled: bool = True,
        excluded_methods: list[str] | None = None,
        max_request_size: int = 64 * 1024,  # 64KB
        max_response_size: int = 64 * 1024,  # 64KB
        capture_metadata: bool = True,
        capture_peer: bool = True,
        security_sensitive_methods: list[str] | None = None,
        anomaly_detection: bool = True,
        max_execution_time_threshold: float = 30.0,  # seconds
    ):
        self.enabled = enabled
        self.excluded_methods = excluded_methods or []
        self.max_request_size = max_request_size
        self.max_response_size = max_response_size
        self.capture_metadata = capture_metadata
        self.capture_peer = capture_peer
        self.security_sensitive_methods = security_sensitive_methods or [
            "/auth.AuthService/Login",
            "/auth.AuthService/RefreshToken",
            "/user.UserService/CreateUser",
            "/user.UserService/UpdatePassword",
        ]
        self.anomaly_detection = anomaly_detection
        self.max_execution_time_threshold = max_execution_time_threshold


class GrpcAuditInterceptor(ServerInterceptor):
    """gRPC server interceptor for automatic audit logging."""

    def __init__(self, auditor: IMiddlewareAuditor, config: GrpcAuditConfig | None = None):
        self.auditor = auditor
        self.config = config or GrpcAuditConfig()

    async def intercept_service(
        self, continuation: Callable, handler_call_details: grpc.HandlerCallDetails
    ) -> grpc.RpcMethodHandler:
        """Intercept gRPC service calls."""
        if not self.config.enabled:
            return await continuation(handler_call_details)

        method = handler_call_details.method
        if method in self.config.excluded_methods:
            return await continuation(handler_call_details)

        # Get the original handler
        handler = await continuation(handler_call_details)
        if handler is None:
            return None

        # Wrap the handler based on its type
        if handler.unary_unary:
            return self._wrap_unary_unary(handler, method)
        elif handler.unary_stream:
            return self._wrap_unary_stream(handler, method)
        elif handler.stream_unary:
            return self._wrap_stream_unary(handler, method)
        elif handler.stream_stream:
            return self._wrap_stream_stream(handler, method)

        return handler

    def _wrap_unary_unary(
        self, handler: grpc.RpcMethodHandler, method: str
    ) -> grpc.RpcMethodHandler:
        """Wrap unary-unary RPC handler."""
        original_handler = handler.unary_unary

        async def audited_handler(request, context: grpc.aio.ServicerContext):
            start_time = time.time()

            try:
                # Extract request information
                request_data = await self._extract_request_data(request, context, method)

                # Call original handler
                response = await original_handler(request, context)

                # Calculate execution time
                execution_time = time.time() - start_time

                # Extract response information
                response_data = await self._extract_response_data(response, context, method)

                # Log successful request
                await self._log_grpc_request(
                    method=method,
                    request_data=request_data,
                    response_data=response_data,
                    context=context,
                    execution_time=execution_time,
                    success=True,
                )

                return response

            except Exception as e:
                execution_time = time.time() - start_time

                # Log failed request
                await self._log_grpc_request(
                    method=method,
                    request_data=await self._extract_request_data(request, context, method),
                    response_data={"error": str(e), "error_type": type(e).__name__},
                    context=context,
                    execution_time=execution_time,
                    success=False,
                    error=e,
                )

                raise

        return grpc.unary_unary_rpc_method_handler(audited_handler)

    def _wrap_unary_stream(
        self, handler: grpc.RpcMethodHandler, method: str
    ) -> grpc.RpcMethodHandler:
        """Wrap unary-stream RPC handler."""
        original_handler = handler.unary_stream

        async def audited_handler(request, context: grpc.aio.ServicerContext):
            start_time = time.time()

            try:
                # Extract request information
                request_data = await self._extract_request_data(request, context, method)

                # Call original handler and collect responses
                responses = []
                async for response in original_handler(request, context):
                    responses.append(response)
                    yield response

                # Calculate execution time
                execution_time = time.time() - start_time

                # Log successful streaming request
                await self._log_grpc_request(
                    method=method,
                    request_data=request_data,
                    response_data={"stream_responses": len(responses), "type": "stream"},
                    context=context,
                    execution_time=execution_time,
                    success=True,
                )

            except Exception as e:
                execution_time = time.time() - start_time

                # Log failed streaming request
                await self._log_grpc_request(
                    method=method,
                    request_data=await self._extract_request_data(request, context, method),
                    response_data={"error": str(e), "error_type": type(e).__name__},
                    context=context,
                    execution_time=execution_time,
                    success=False,
                    error=e,
                )

                raise

        return grpc.unary_stream_rpc_method_handler(audited_handler)

    def _wrap_stream_unary(
        self, handler: grpc.RpcMethodHandler, method: str
    ) -> grpc.RpcMethodHandler:
        """Wrap stream-unary RPC handler."""
        original_handler = handler.stream_unary

        async def audited_handler(request_iterator, context: grpc.aio.ServicerContext):
            start_time = time.time()

            try:
                # Collect streaming requests
                requests = []
                async for request in request_iterator:
                    requests.append(request)

                # Call original handler with collected requests
                response = await original_handler(iter(requests), context)

                # Calculate execution time
                execution_time = time.time() - start_time

                # Extract response information
                response_data = await self._extract_response_data(response, context, method)

                # Log successful streaming request
                await self._log_grpc_request(
                    method=method,
                    request_data={"stream_requests": len(requests), "type": "stream"},
                    response_data=response_data,
                    context=context,
                    execution_time=execution_time,
                    success=True,
                )

                return response

            except Exception as e:
                execution_time = time.time() - start_time

                # Log failed streaming request
                await self._log_grpc_request(
                    method=method,
                    request_data={"stream_requests": "unknown", "type": "stream"},
                    response_data={"error": str(e), "error_type": type(e).__name__},
                    context=context,
                    execution_time=execution_time,
                    success=False,
                    error=e,
                )

                raise

        return grpc.stream_unary_rpc_method_handler(audited_handler)

    def _wrap_stream_stream(
        self, handler: grpc.RpcMethodHandler, method: str
    ) -> grpc.RpcMethodHandler:
        """Wrap stream-stream RPC handler."""
        original_handler = handler.stream_stream

        async def audited_handler(request_iterator, context: grpc.aio.ServicerContext):
            start_time = time.time()

            try:
                # Call original handler and track streaming
                request_count = 0
                response_count = 0

                async for response in original_handler(request_iterator, context):
                    response_count += 1
                    yield response

                # Calculate execution time
                execution_time = time.time() - start_time

                # Log successful bidirectional streaming
                await self._log_grpc_request(
                    method=method,
                    request_data={"stream_requests": request_count, "type": "bidirectional_stream"},
                    response_data={
                        "stream_responses": response_count,
                        "type": "bidirectional_stream",
                    },
                    context=context,
                    execution_time=execution_time,
                    success=True,
                )

            except Exception as e:
                execution_time = time.time() - start_time

                # Log failed bidirectional streaming
                await self._log_grpc_request(
                    method=method,
                    request_data={"type": "bidirectional_stream"},
                    response_data={"error": str(e), "error_type": type(e).__name__},
                    context=context,
                    execution_time=execution_time,
                    success=False,
                    error=e,
                )

                raise

        return grpc.stream_stream_rpc_method_handler(audited_handler)

    async def _extract_request_data(
        self, request: Any, context: grpc.aio.ServicerContext, method: str
    ) -> dict[str, Any]:
        """Extract request data for auditing."""
        request_data = {}

        # Add method information
        request_data["grpc_method"] = method

        # Add peer information if enabled
        if self.config.capture_peer:
            request_data["peer"] = context.peer()

        # Add metadata if enabled
        if self.config.capture_metadata:
            metadata = dict(context.invocation_metadata())
            # Filter out sensitive headers
            filtered_metadata = {
                k: v
                for k, v in metadata.items()
                if not k.lower().startswith(("authorization", "authentication", "token"))
            }
            request_data["metadata"] = filtered_metadata

        # Serialize request (with size limit)
        try:
            if hasattr(request, "SerializeToString"):
                serialized = request.SerializeToString()
                if len(serialized) <= self.config.max_request_size:
                    # Convert to dict representation if possible
                    if hasattr(request, "DESCRIPTOR"):
                        request_data["request"] = self._message_to_dict(request)
                    else:
                        request_data["request_size"] = len(serialized)
                else:
                    request_data["request_size"] = len(serialized)
                    request_data["request_truncated"] = True
            else:
                request_data["request"] = str(request)[: self.config.max_request_size]
        except Exception as e:
            request_data["request_error"] = str(e)

        return request_data

    async def _extract_response_data(
        self, response: Any, context: grpc.aio.ServicerContext, method: str
    ) -> dict[str, Any]:
        """Extract response data for auditing."""
        response_data = {}

        # Add status code
        response_data["status_code"] = context.code()

        # Serialize response (with size limit)
        try:
            if hasattr(response, "SerializeToString"):
                serialized = response.SerializeToString()
                if len(serialized) <= self.config.max_response_size:
                    # Convert to dict representation if possible
                    if hasattr(response, "DESCRIPTOR"):
                        response_data["response"] = self._message_to_dict(response)
                    else:
                        response_data["response_size"] = len(serialized)
                else:
                    response_data["response_size"] = len(serialized)
                    response_data["response_truncated"] = True
            else:
                response_data["response"] = str(response)[: self.config.max_response_size]
        except Exception as e:
            response_data["response_error"] = str(e)

        return response_data

    def _message_to_dict(self, message: Any) -> dict[str, Any]:
        """Convert protobuf message to dictionary."""
        try:
            from google.protobuf.json_format import MessageToDict

            return MessageToDict(message)
        except ImportError:
            # Fallback if protobuf not available
            return {"message": str(message)}

    async def _log_grpc_request(
        self,
        method: str,
        request_data: dict[str, Any],
        response_data: dict[str, Any],
        context: grpc.aio.ServicerContext,
        execution_time: float,
        success: bool,
        error: Exception | None = None,
    ):
        """Log gRPC request to audit service."""
        try:
            # Determine event type and severity
            event_type = self._determine_event_type(method, success)
            severity = self._determine_severity(method, success, execution_time, error)

            # Extract user information from metadata
            user_info = self._extract_user_info(context)

            # Detect anomalies
            anomalies = []
            if self.config.anomaly_detection:
                anomalies = self._detect_anomalies(method, execution_time, success, error)

            # Create audit event
            await self.auditor.audit_request(
                event_type=event_type,
                severity=severity,
                method=method,
                user_id=user_info.get("user_id"),
                user_role=user_info.get("user_role"),
                request_data=request_data,
                response_data=response_data,
                execution_time=execution_time,
                anomalies=anomalies,
                protocol="grpc",
            )

        except Exception as audit_error:
            # Don't let audit failures affect the main request
            print(f"Audit logging failed for gRPC method {method}: {audit_error}")

    def _determine_event_type(self, method: str, success: bool) -> AuditEventType:
        """Determine audit event type based on gRPC method."""
        if not success:
            return AuditEventType.API_ERROR

        method_lower = method.lower()

        # Authentication methods
        if any(auth_method in method_lower for auth_method in ["login", "authenticate", "token"]):
            return AuditEventType.USER_LOGIN

        # User management methods
        if any(
            user_method in method_lower
            for user_method in ["createuser", "updateuser", "deleteuser"]
        ):
            return AuditEventType.USER_MANAGEMENT

        # Data access methods
        if any(data_method in method_lower for data_method in ["get", "list", "read", "query"]):
            return AuditEventType.DATA_ACCESS

        # Data modification methods
        if any(
            mod_method in method_lower for mod_method in ["create", "update", "delete", "modify"]
        ):
            return AuditEventType.DATA_MODIFICATION

        # Default to API request
        return AuditEventType.API_REQUEST

    def _determine_severity(
        self, method: str, success: bool, execution_time: float, error: Exception | None
    ) -> AuditSeverity:
        """Determine audit severity based on request characteristics."""
        if not success:
            if isinstance(error, grpc.RpcError):
                status_code = error.code()
                if status_code in [
                    grpc.StatusCode.PERMISSION_DENIED,
                    grpc.StatusCode.UNAUTHENTICATED,
                ]:
                    return AuditSeverity.HIGH
                elif status_code in [grpc.StatusCode.INVALID_ARGUMENT, grpc.StatusCode.NOT_FOUND]:
                    return AuditSeverity.MEDIUM
            return AuditSeverity.HIGH

        # Security-sensitive methods
        if method in self.config.security_sensitive_methods:
            return AuditSeverity.HIGH

        # Slow requests
        if execution_time > self.config.max_execution_time_threshold:
            return AuditSeverity.MEDIUM

        # Default severity
        return AuditSeverity.LOW

    def _extract_user_info(self, context: grpc.aio.ServicerContext) -> dict[str, str | None]:
        """Extract user information from gRPC context metadata."""
        metadata = dict(context.invocation_metadata())

        return {
            "user_id": metadata.get("user-id") or metadata.get("x-user-id"),
            "user_role": metadata.get("user-role") or metadata.get("x-user-role"),
            "session_id": metadata.get("session-id") or metadata.get("x-session-id"),
            "correlation_id": metadata.get("correlation-id") or metadata.get("x-correlation-id"),
        }

    def _detect_anomalies(
        self, method: str, execution_time: float, success: bool, error: Exception | None
    ) -> list[str]:
        """Detect potential anomalies in gRPC requests."""
        anomalies = []

        # Unusually long execution time
        if execution_time > self.config.max_execution_time_threshold:
            anomalies.append(f"Long execution time: {execution_time:.2f}s")

        # Authentication failures
        if not success and isinstance(error, grpc.RpcError):
            if error.code() == grpc.StatusCode.UNAUTHENTICATED:
                anomalies.append("Authentication failure")
            elif error.code() == grpc.StatusCode.PERMISSION_DENIED:
                anomalies.append("Authorization failure")

        # Repeated failed calls (would need state tracking)
        # This is a simplified implementation

        return anomalies


class GrpcMiddlewareAuditor(IMiddlewareAuditor):
    """gRPC-specific implementation of middleware auditor."""

    def __init__(self, audit_service: IAuditService):
        self.audit_service = audit_service

    async def audit_request(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity,
        method: str,
        user_id: str | None = None,
        user_role: str | None = None,
        request_data: dict[str, Any] | None = None,
        response_data: dict[str, Any] | None = None,
        execution_time: float | None = None,
        anomalies: list[str] | None = None,
        protocol: str = "grpc",
    ) -> str:
        """Audit a gRPC request."""
        # Create the audit command
        command = LogRequestCommand(
            event_type=event_type,
            severity=severity,
            service_name="grpc-service",  # Could be configured
            endpoint=method,
            user_id=user_id,
            user_role=user_role,
            request_data=request_data or {},
            response_data=response_data or {},
            execution_time_seconds=execution_time,
            additional_context={
                "protocol": protocol,
                "anomalies": anomalies or [],
            },
        )

        # Log the request
        response = await self.audit_service.log_request(command)
        return str(response.event_id)
