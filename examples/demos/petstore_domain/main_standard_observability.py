"""
PetstoreDomain service with MMF Standard Observability

This service demonstrates the MMF standard observability implementation:
- Zero-configuration OpenTelemetry instrumentation
- Automatic correlation ID tracking across all requests
- Standard Prometheus metrics with consistent naming
- Plugin developer debugging support
- Integrated Grafana dashboards

Service: petstore-domain
Generated with MMF Service Generator v2.0 (Standard Observability)
"""
import asyncio
import json
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

import uvicorn
from app.api.delivery_board_routes import router as delivery_board_router
from app.api.order_routes import router as order_router
from app.api.outbox_routes import router as outbox_router
from app.api.payment_service_routes import router as payment_service_router
from app.api.petstore_domain_routes import router as petstore_domain_router
from app.api.routes import router
from app.api.secure_routes import secure_router

# Import service components
from app.core.config import get_settings
from app.middleware.security import PetStoreSecurityMiddleware
from app.services.event_service import event_service
from app.services.outbox_event_service import outbox_event_service
from app.services.petstore_domain_service import PetstoreDomainService

# Import security components
from app.services.security_service import cleanup_security_service, get_security_service
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

# MMF Standard Observability - Zero Configuration Required
from marty_msf.observability.standard import (
    create_standard_observability,
    get_observability,
    set_global_observability,
)
from marty_msf.observability.standard_correlation import (
    CorrelationContext,
    StandardCorrelationMiddleware,
    async_correlation_context,
    inject_correlation_to_span,
)

# Configure structured logging with correlation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - correlation_id=%(correlation_id)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('petstore_domain_service.log'),
        logging.FileHandler('petstore_domain_service_audit.log')
    ]
)
logger = logging.getLogger("petstore-domain")

# Global service instances
service_instance = None
security_service = None
observability = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with standard observability"""
    global service_instance, security_service, observability

    logger.info("Starting Petstore Domain service with MMF Standard Observability")

    # Initialize MMF Standard Observability
    observability = create_standard_observability(
        service_name="petstore-domain",
        service_version="2.0.0",
        service_type="fastapi",
        environment="demo"
    )

    await observability.initialize()
    set_global_observability(observability)

    # Instrument the FastAPI app
    observability.instrument_fastapi(app)

    logger.info("MMF Standard Observability initialized successfully")

    # Initialize business services
    service_instance = PetstoreDomainService()
    await service_instance.initialize()

    # Initialize security service
    security_service = await get_security_service()

    # Initialize event services
    await event_service.start()
    await outbox_event_service.start()

    logger.info("Petstore Domain service startup complete")

    yield

    # Shutdown sequence
    logger.info("Shutting down Petstore Domain service")

    if outbox_event_service:
        await outbox_event_service.stop()
    if event_service:
        await event_service.stop()
    if security_service:
        await cleanup_security_service()
    if service_instance:
        # Service instance cleanup (if it has shutdown method)
        if hasattr(service_instance, 'shutdown'):
            await service_instance.shutdown()
    if observability:
        await observability.shutdown()

    logger.info("Petstore Domain service shutdown complete")

# Create FastAPI application with standard observability
app = FastAPI(
    title="Petstore Domain Service",
    description="Petstore domain service with MMF Standard Observability",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add MMF Standard Correlation Middleware
app.add_middleware(StandardCorrelationMiddleware)

# Add security middleware
app.add_middleware(PetStoreSecurityMiddleware)

# Enhanced middleware with standard observability integration
@app.middleware("http")
async def enhanced_request_tracking(request: Request, call_next):
    """Enhanced request tracking with standard observability and correlation."""
    start_time = time.time()

    # Get correlation context (automatically managed by StandardCorrelationMiddleware)
    correlation_id = CorrelationContext.get_correlation_id()

    # Record active request
    if observability:
        observability.active_requests.inc() if observability.active_requests else None

    try:
        # Process request with correlation context
        async with async_correlation_context(operation_id=f"{request.method}:{request.url.path}"):
            response = await call_next(request)

        # Record successful request metrics (automatically handled by standard observability)
        duration = time.time() - start_time

        # Record business metrics with correlation
        if observability:
            observability.record_request(
                method=request.method,
                endpoint=str(request.url.path),
                status_code=response.status_code,
                duration=duration
            )

        logger.info(
            f"Request processed: {request.method} {request.url.path}",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration": duration
            }
        )

        return response

    except Exception as e:
        # Record error metrics
        if observability:
            observability.record_error(
                error_type=type(e).__name__,
                endpoint=str(request.url.path)
            )

        logger.error(
            f"Request failed: {request.method} {request.url.path}",
            extra={
                "correlation_id": correlation_id,
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise
    finally:
        # Decrement active requests
        if observability:
            observability.active_requests.dec() if observability.active_requests else None

# Core application routes
app.include_router(router, prefix="/api/v1")
app.include_router(secure_router, prefix="/api/v1/secure")

# Business domain routes
app.include_router(petstore_domain_router, prefix="/api/v1/petstore")
app.include_router(order_router, prefix="/api/v1/orders")
app.include_router(payment_service_router, prefix="/api/v1/payments")
app.include_router(delivery_board_router, prefix="/api/v1/delivery")
app.include_router(outbox_router, prefix="/api/v1/outbox")

@app.get("/health")
async def health_check():
    """Enhanced health check with observability status."""
    return {
        "service": "petstore-domain",
        "version": "2.0.0",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "observability": {
            "enabled": observability is not None,
            "correlation_tracking": True,
            "metrics_collection": True,
            "distributed_tracing": True
        },
        "correlation_id": CorrelationContext.get_correlation_id()
    }

@app.get("/metrics")
async def metrics():
    """Standard Prometheus metrics endpoint."""
    if observability:
        metrics_data = observability.get_metrics()
        return Response(
            metrics_data,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
    else:
        return {"message": "Metrics not available"}

@app.get("/info")
async def service_info():
    """Service information with observability details."""
    correlation_id = CorrelationContext.get_correlation_id()

    return {
        "service": "petstore-domain",
        "version": "2.0.0",
        "description": "Petstore domain service with MMF Standard Observability",
        "observability_features": [
            "OpenTelemetry distributed tracing",
            "Prometheus metrics collection",
            "Multi-dimensional correlation tracking",
            "Plugin operation debugging",
            "Standard Grafana dashboards",
            "Zero-configuration setup"
        ],
        "correlation": {
            "correlation_id": correlation_id,
            "request_id": CorrelationContext.get_request_id(),
            "user_id": CorrelationContext.get_user_id(),
            "session_id": CorrelationContext.get_session_id()
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# Business logic endpoints with enhanced observability
@app.post("/api/v1/petstore/pets")
async def create_pet(pet_data: Dict[str, Any]):
    """Create a pet with enhanced correlation tracking."""

    async with async_correlation_context(operation_id="create_pet"):
        # Inject correlation into OpenTelemetry span
        inject_correlation_to_span()

        # Record business operation
        if observability:
            observability.record_plugin_operation(
                plugin_id="petstore-core",
                operation="create_pet",
                status="started"
            )

        try:
            # Business logic
            pet_id = str(uuid.uuid4())
            pet = {
                "id": pet_id,
                "name": pet_data.get("name"),
                "species": pet_data.get("species"),
                "created_at": datetime.utcnow().isoformat(),
                "correlation_id": CorrelationContext.get_correlation_id()
            }

            # Record successful operation
            if observability:
                observability.record_plugin_operation(
                    plugin_id="petstore-core",
                    operation="create_pet",
                    status="success"
                )

            logger.info(
                f"Pet created successfully",
                extra={
                    "correlation_id": CorrelationContext.get_correlation_id(),
                    "pet_id": pet_id,
                    "operation": "create_pet"
                }
            )

            return pet

        except Exception as e:
            # Record failed operation
            if observability:
                observability.record_plugin_operation(
                    plugin_id="petstore-core",
                    operation="create_pet",
                    status="error"
                )
                observability.record_error(
                    error_type=type(e).__name__,
                    endpoint="/api/v1/petstore/pets"
                )

            logger.error(
                f"Pet creation failed",
                extra={
                    "correlation_id": CorrelationContext.get_correlation_id(),
                    "error": str(e),
                    "operation": "create_pet"
                },
                exc_info=True
            )
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/petstore/pets/{pet_id}")
async def get_pet(pet_id: str):
    """Get a pet with correlation tracking."""

    async with async_correlation_context(operation_id="get_pet"):
        inject_correlation_to_span()

        logger.info(
            f"Retrieving pet",
            extra={
                "correlation_id": CorrelationContext.get_correlation_id(),
                "pet_id": pet_id,
                "operation": "get_pet"
            }
        )

        # Simulate pet retrieval
        return {
            "id": pet_id,
            "name": "Demo Pet",
            "species": "Dog",
            "correlation_id": CorrelationContext.get_correlation_id(),
            "retrieved_at": datetime.utcnow().isoformat()
        }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info"
    )
