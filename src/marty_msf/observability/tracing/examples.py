"""
Tracing Examples and Integration Helpers for Marty Microservices Framework

Provides practical examples for integrating distributed tracing into
FastAPI and gRPC services with best practices and common patterns.
"""

import asyncio
import builtins
import logging
import time
from typing import Any, dict

import grpc
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from pydantic import BaseModel

from . import DistributedTracing, setup_distributed_tracing

# FastAPI imports
try:

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# gRPC imports
try:

    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False


# OpenTelemetry imports

# Import our tracing module

logger = logging.getLogger(__name__)


# Example models
class UserModel(BaseModel):
    id: str
    name: str
    email: str


class OrderModel(BaseModel):
    id: str
    user_id: str
    amount: float
    currency: str = "USD"


class PaymentModel(BaseModel):
    order_id: str
    amount: float
    payment_method: str


class TracedFastAPIService:
    """
    Example FastAPI service with comprehensive tracing integration

    Demonstrates:
    - Service initialization with tracing
    - Request/response tracing
    - Database operation tracing
    - External service call tracing
    - Background task tracing
    - Error handling with traces
    """

    def __init__(self, service_name: str = "example-fastapi-service"):
        self.app = FastAPI(title=service_name)
        self.tracing = setup_distributed_tracing(
            service_name=service_name,
            environment="production",
            enable_auto_instrumentation=True,
        )

        # Instrument FastAPI app
        self.tracing.instrument_fastapi(self.app)

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self._setup_routes()
        logger.info(f"Traced FastAPI service {service_name} initialized")

    def _setup_routes(self):
        """Setup API routes with tracing examples"""

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint - typically excluded from tracing"""
            return {"status": "healthy", "service": "example-fastapi-service"}

        @self.app.get("/users/{user_id}")
        @self.tracing.trace_function("get_user", {"operation": "read"})
        async def get_user(user_id: str):
            """Get user by ID with tracing"""
            # Add custom span attributes
            self.tracing.set_span_attribute("user.id", user_id)
            self.tracing.add_span_event("user.lookup.started")

            try:
                # Simulate database lookup
                user = await self._get_user_from_db(user_id)

                if not user:
                    self.tracing.add_span_event("user.not_found", {"user_id": user_id})
                    raise HTTPException(status_code=404, detail="User not found")

                self.tracing.add_span_event("user.found", {"user_id": user_id})
                return user

            except HTTPException:
                raise
            except Exception as e:
                self.tracing.add_span_event("user.lookup.error", {"error": str(e)})
                raise HTTPException(status_code=500, detail="Internal server error")

        @self.app.post("/orders")
        async def create_order(order: OrderModel, background_tasks: BackgroundTasks):
            """Create order with distributed tracing across services"""
            async with self.tracing.trace_async_operation(
                "create_order", {"user_id": order.user_id, "amount": order.amount}
            ) as span:
                try:
                    # Step 1: Validate user
                    await self._validate_user(order.user_id)

                    # Step 2: Create order in database
                    order_id = await self._create_order_in_db(order)
                    span.set_attribute("order.id", order_id)

                    # Step 3: Process payment (external service call)
                    payment_result = await self._process_payment(order_id, order.amount)
                    span.set_attribute("payment.status", payment_result["status"])

                    # Step 4: Send confirmation email (background task)
                    background_tasks.add_task(
                        self._send_confirmation_email, order.user_id, order_id
                    )

                    return {
                        "order_id": order_id,
                        "status": "created",
                        "payment_status": payment_result["status"],
                    }

                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/orders/{order_id}/trace-info")
        async def get_trace_info(order_id: str):
            """Get current trace information"""
            trace_id = self.tracing.get_trace_id()
            span_id = self.tracing.get_span_id()

            return {
                "order_id": order_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "jaeger_url": f"http://jaeger:16686/trace/{trace_id}" if trace_id else None,
            }

    async def _get_user_from_db(self, user_id: str) -> UserModel | None:
        """Simulate database user lookup with tracing"""
        async with self.tracing.trace_async_operation(
            "db.user.select", {"db.operation": "SELECT", "user.id": user_id}
        ):
            # Simulate database delay
            await asyncio.sleep(0.1)

            if user_id == "404":
                return None

            return UserModel(id=user_id, name=f"User {user_id}", email=f"user{user_id}@example.com")

    async def _validate_user(self, user_id: str):
        """Validate user exists"""
        user = await self._get_user_from_db(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

    async def _create_order_in_db(self, order: OrderModel) -> str:
        """Simulate order creation in database"""
        async with self.tracing.trace_async_operation(
            "db.order.insert", {"db.operation": "INSERT", "order.amount": order.amount}
        ):
            # Simulate database operation
            await asyncio.sleep(0.2)
            order_id = f"order_{int(time.time())}"

            self.tracing.add_span_event("order.created", {"order_id": order_id})
            return order_id

    async def _process_payment(self, order_id: str, amount: float) -> builtins.dict[str, Any]:
        """Simulate external payment service call"""
        async with self.tracing.trace_async_operation(
            "external.payment_service.process",
            {
                "external.service": "payment-service",
                "payment.amount": amount,
                "order.id": order_id,
            },
        ) as span:
            # Simulate external API call
            await asyncio.sleep(0.5)

            # Simulate payment processing
            if amount > 10000:  # Simulate payment failure for large amounts
                span.set_status(Status(StatusCode.ERROR, "Payment amount too large"))
                raise ValueError("Payment amount exceeds limit")

            payment_id = f"pay_{int(time.time())}"
            span.set_attribute("payment.id", payment_id)

            return {
                "payment_id": payment_id,
                "status": "completed",
                "order_id": order_id,
            }

    async def _send_confirmation_email(self, user_id: str, order_id: str):
        """Background task with tracing"""
        async with self.tracing.trace_async_operation(
            "background.send_email",
            {
                "background.task": "send_confirmation_email",
                "user.id": user_id,
                "order.id": order_id,
            },
        ):
            # Simulate email sending
            await asyncio.sleep(1.0)
            self.tracing.add_span_event(
                "email.sent", {"email.type": "order_confirmation", "recipient": user_id}
            )


class TracedGRPCService:
    """
    Example gRPC service with distributed tracing

    Demonstrates:
    - gRPC server instrumentation
    - Inter-service communication tracing
    - Context propagation
    - Error handling
    """

    def __init__(self, service_name: str = "example-grpc-service"):
        self.service_name = service_name
        self.tracing = setup_distributed_tracing(
            service_name=service_name, environment="production"
        )
        logger.info(f"Traced gRPC service {service_name} initialized")

    async def ProcessPayment(self, request, context):
        """gRPC method with tracing"""
        # Extract trace context from gRPC metadata
        metadata = dict(context.invocation_metadata())
        self.tracing.extract_context(metadata)

        async with self.tracing.trace_async_operation(
            "grpc.ProcessPayment",
            {
                "grpc.service": "PaymentService",
                "grpc.method": "ProcessPayment",
                "payment.amount": getattr(request, "amount", 0),
                "payment.currency": getattr(request, "currency", "USD"),
            },
        ) as span:
            try:
                # Simulate payment processing logic
                await self._validate_payment_request(request)

                payment_result = await self._process_payment_internal(request)

                # Create response
                response = self._create_payment_response(payment_result)

                span.set_attribute("payment.status", payment_result["status"])
                span.set_attribute("payment.id", payment_result["payment_id"])

                return response

            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
                raise

    async def _validate_payment_request(self, request):
        """Validate payment request"""
        async with self.tracing.trace_async_operation("payment.validation"):
            # Simulate validation logic
            await asyncio.sleep(0.1)

            if not hasattr(request, "amount") or request.amount <= 0:
                raise ValueError("Invalid payment amount")

    async def _process_payment_internal(self, request) -> builtins.dict[str, Any]:
        """Internal payment processing"""
        async with self.tracing.trace_async_operation(
            "payment.processing",
            {"payment.method": getattr(request, "payment_method", "unknown")},
        ):
            # Simulate payment gateway communication
            await asyncio.sleep(0.3)

            return {
                "payment_id": f"pay_{int(time.time())}",
                "status": "completed",
                "amount": getattr(request, "amount", 0),
            }

    def _create_payment_response(self, payment_result):
        """Create gRPC response (implementation depends on your proto definitions)"""
        # This would return your actual gRPC response object
        return payment_result


class TracingIntegrationHelper:
    """
    Helper class for common tracing integration patterns
    """

    @staticmethod
    def propagate_trace_context(source_headers: builtins.dict[str, str]) -> builtins.dict[str, str]:
        """Extract trace context from headers and prepare for propagation"""
        propagator = TraceContextTextMapPropagator()

        # Extract context from source headers
        context = propagator.extract(source_headers)

        # Prepare headers for outgoing request
        carrier = {}
        propagator.inject(carrier, context)

        return carrier

    @staticmethod
    def create_http_client_headers(
        additional_headers: builtins.dict[str, str] | None = None,
    ) -> builtins.dict[str, str]:
        """Create HTTP headers with trace context for outgoing requests"""
        headers = {}

        # Inject current trace context
        propagator = TraceContextTextMapPropagator()
        propagator.inject(headers)

        # Add additional headers
        if additional_headers:
            headers.update(additional_headers)

        return headers

    @staticmethod
    def add_user_context_to_trace(user_id: str, user_role: str = None, user_email: str = None):
        """Add user context to current trace"""
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute("user.id", user_id)
            if user_role:
                current_span.set_attribute("user.role", user_role)
            if user_email:
                current_span.set_attribute("user.email", user_email)

    @staticmethod
    def add_business_context_to_trace(operation_type: str, entity_id: str, entity_type: str):
        """Add business context to current trace"""
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute("business.operation", operation_type)
            current_span.set_attribute("business.entity.id", entity_id)
            current_span.set_attribute("business.entity.type", entity_type)

    @staticmethod
    def trace_external_http_call(url: str, method: str = "GET"):
        """Context manager for tracing external HTTP calls"""

        def decorator(func):
            async def wrapper(*args, **kwargs):
                async with trace.get_tracer(__name__).start_as_current_span(
                    f"http.{method.lower()}", kind=trace.SpanKind.CLIENT
                ) as span:
                    span.set_attribute("http.method", method)
                    span.set_attribute("http.url", url)
                    span.set_attribute("span.kind", "client")

                    try:
                        result = await func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        raise

            return wrapper

        return decorator


# Example usage and setup functions
def setup_fastapi_with_tracing(service_name: str) -> FastAPI:
    """Setup FastAPI application with comprehensive tracing"""
    traced_service = TracedFastAPIService(service_name)
    return traced_service.app


def setup_grpc_server_with_tracing(service_name: str):
    """Setup gRPC server with tracing (implementation depends on your gRPC setup)"""
    traced_service = TracedGRPCService(service_name)
    # Return configured gRPC server
    return traced_service


# Example middleware for manual instrumentation
class ManualTracingMiddleware:
    """
    Manual tracing middleware for cases where auto-instrumentation is not sufficient
    """

    def __init__(self, app, tracing: DistributedTracing):
        self.app = app
        self.tracing = tracing

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract trace context from headers
            headers = dict(scope.get("headers", []))
            context = self.tracing.extract_context(
                {k.decode(): v.decode() for k, v in headers.items()}
            )

            # Create span for request
            with self.tracing.tracer.start_as_current_span(
                f"{scope['method']} {scope['path']}",
                context=context,
                kind=trace.SpanKind.SERVER,
            ) as span:
                # Add request attributes
                span.set_attribute("http.method", scope["method"])
                span.set_attribute("http.scheme", scope["scheme"])
                span.set_attribute("http.path", scope["path"])

                await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)
