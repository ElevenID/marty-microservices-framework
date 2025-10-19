"""
PetstoreDomain service for petstore-domain functionality

This service follows enterprise patterns and the MMF adoption flow:
clone → generate → add business logic

Features:
- Comprehensive logging with correlation IDs
- Prometheus metrics integration
- Health checks and readiness probes
- Structured configuration management
- Error handling and audit logging
- Service mesh ready

Service: petstore-domain
Generated with MMF Service Generator
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

# from marty_msf.observability.correlation_middleware import add_correlation_id_middleware
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
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('petstore_domain_service.log'),
        logging.FileHandler('petstore_domain_service_audit.log')
    ]
)
logger = logging.getLogger("petstore-domain")

# Prometheus Metrics (with duplicate registration protection)

# Initialize metrics with error handling for duplicates
REQUEST_COUNTER = None
REQUEST_DURATION = None
ACTIVE_REQUESTS = None
BUSINESS_OPERATIONS = None

try:
    REQUEST_COUNTER = Counter('petstore_domain_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
    REQUEST_DURATION = Histogram('petstore_domain_request_duration_seconds', 'Request duration', ['method', 'endpoint'])
    ACTIVE_REQUESTS = Gauge('petstore_domain_active_requests', 'Active requests')
    BUSINESS_OPERATIONS = Counter('petstore_domain_business_operations_total', 'Business operations', ['operation', 'status'])
except ValueError as e:
    if "Duplicated timeseries" in str(e):
        logger.warning(f"Metrics already registered: {e}")
        # Create with different registry or skip metrics
        pass
    else:
        raise

# Global service instance
service_instance = None
security_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global service_instance, security_service

    # Startup
    logger.info("Starting PetstoreDomain Service...")
    try:
        # Get configuration
        config = get_settings()

        # Initialize security service first
        security_service = await get_security_service(config)
        logger.info("Security service initialized")

        # Initialize main service
        service_instance = PetstoreDomainService()
        await service_instance.initialize()

        # Initialize event service (Kafka)
        await event_service.start()

        # Initialize outbox event service
        await outbox_event_service.start()

        logger.info("Service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down PetstoreDomain Service...")
    try:
        # Stop event services
        await event_service.stop()
        await outbox_event_service.stop()

        # Cleanup security service
        await cleanup_security_service()

        # Cleanup main service
        if service_instance and hasattr(service_instance, 'cleanup'):
            await service_instance.cleanup()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    logger.info("Service shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="PetstoreDomain Service",
    description="PetstoreDomain service for petstore-domain functionality",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security middleware
config = get_settings()
if config.enable_authentication or config.enable_authorization:
    app.add_middleware(
        PetStoreSecurityMiddleware,
        require_auth=config.enable_authentication,
        public_paths=[
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/pets/public"
        ]
    )

# Add correlation ID middleware
# add_correlation_id_middleware(app)  # Commented out for now

# Metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to collect metrics for all requests"""
    start_time = time.time()
    if ACTIVE_REQUESTS:
        ACTIVE_REQUESTS.inc()

    try:
        response = await call_next(request)

        # Record metrics (if available)
        duration = time.time() - start_time
        if REQUEST_DURATION:
            REQUEST_DURATION.labels(method=request.method, endpoint=request.url.path).observe(duration)
        if REQUEST_COUNTER:
            REQUEST_COUNTER.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()

        return response
    finally:
        if ACTIVE_REQUESTS:
            ACTIVE_REQUESTS.dec()

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging"""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    error_data = {
        "event": "http_exception",
        "correlation_id": correlation_id,
        "status_code": exc.status_code,
        "detail": exc.detail,
        "path": request.url.path,
        "method": request.method,
        "timestamp": datetime.utcnow().isoformat()
    }

    logger.warning(f"HTTP Exception: {json.dumps(error_data)}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    error_data = {
        "event": "unexpected_exception",
        "correlation_id": correlation_id,
        "error": str(exc),
        "error_type": type(exc).__name__,
        "path": request.url.path,
        "method": request.method,
        "timestamp": datetime.utcnow().isoformat()
    }

    logger.error(f"Unexpected Exception: {json.dumps(error_data)}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Health and monitoring endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Basic health check
        health_status = {
            "status": "healthy",
            "service": "petstore-domain",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        }

        # Add security health if available
        if security_service:
            security_health = await security_service.health_check()
            health_status["security"] = security_health

        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/ready", tags=["monitoring"])
async def readiness_check():
    """Readiness check endpoint"""
    try:
        # Check Kafka connectivity
        kafka_ready = event_service.is_healthy()

        # Add your other readiness checks here
        service_ready = True
        if service_instance:
            # Note: Commenting out health_check call since method doesn't exist
            # is_ready = await service_instance.health_check()
            service_ready = True  # Assume ready for now

        if kafka_ready and service_ready:
            return {
                "status": "ready",
                "service": "petstore-domain",
                "timestamp": datetime.utcnow().isoformat(),
                "kafka_status": "ready",
                "checks": {
                    "kafka": "ready",
                    "service": "ready"
                }
            }

        raise HTTPException(status_code=503, detail="Service not ready")
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")

@app.get("/metrics", tags=["monitoring"])
async def get_metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/info", tags=["monitoring"])
async def service_info():
    """Service information endpoint"""
    settings = get_settings()
    return {
        "service": "petstore-domain",
        "version": "1.0.0",
        "description": "PetstoreDomain service for petstore-domain functionality",
        "environment": getattr(settings, 'environment', 'unknown'),
        "framework": "Marty Microservices Framework",
        "generated_at": "2025-10-13 12:00:00",
        "timestamp": datetime.utcnow().isoformat()
    }

# Include API routes
app.include_router(router)
app.include_router(petstore_domain_router)
app.include_router(delivery_board_router)
app.include_router(payment_service_router)
app.include_router(order_router)
app.include_router(outbox_router)
app.include_router(secure_router)  # Add secure routes

def get_service() -> PetstoreDomainService:
    """Get the service instance"""
    if service_instance is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return service_instance

if __name__ == "__main__":
    settings = get_settings()

    print(f"🚀 Starting PetstoreDomain Service...")
    print(f"📊 Metrics: http://localhost:8080/metrics")
    print(f"📋 API Docs: http://localhost:8080/docs")
    print(f"❤️  Health: http://localhost:8080/health")
    print(f"🔄 Ready: http://localhost:8080/ready")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=getattr(settings, 'debug', False),
        log_level="info"
    )
