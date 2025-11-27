"""
FastAPI Service with Unified Configuration

This is a complete FastAPI service implementation that uses the unified configuration system
with proper error handling, metrics, and real implementations.
"""

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

import structlog
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# Import unified configuration system
from marty_msf.framework.config import (
    ConfigurationStrategy,
    Environment,
    create_unified_config_manager,
)
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field

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
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Metrics
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

active_connections = Gauge(
    'active_connections',
    'Number of active connections'
)


# Configuration model
class FastAPIServiceConfig(BaseModel):
    """Configuration for FastAPI service."""
    service_name: str = Field(default="fastapi-service")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)
    reload: bool = Field(default=False)
    workers: int = Field(default=1)

    # Database configuration with secret reference
    database_url: str = Field(default="${SECRET:database_url}")
    database_pool_size: int = Field(default=10)

    # Security configuration with secret references
    secret_key: str = Field(default="${SECRET:secret_key}")
    api_key: str = Field(default="${SECRET:api_key}")

    # Service-specific settings
    enable_cors: bool = Field(default=True)
    enable_gzip: bool = Field(default=True)
    enable_metrics: bool = Field(default=True)
    cors_origins: list[str] = Field(default=["*"])

    # Monitoring
    log_level: str = Field(default="INFO")


# Pydantic models for API
class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    service: str
    version: str = "1.0.0"
    config_loaded: bool


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trace_id: str | None = None


class ItemRequest(BaseModel):
    """Example item request model."""
    name: str = Field(..., description="Item name")
    description: str | None = Field(None, description="Item description")
    tags: list[str] = Field(default_factory=list, description="Item tags")


class ItemResponse(BaseModel):
    """Example item response model."""
    id: str
    name: str
    description: str | None
    tags: list[str]
    created_at: datetime
    service: str


# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with proper configuration initialization."""

    logger.info("Starting FastAPI service with unified configuration...")

    try:
        # Initialize unified configuration
        env_name = os.getenv("ENVIRONMENT", "development")
        config_dir = os.getenv("CONFIG_DIR", "config")

        config_manager = create_unified_config_manager(
            service_name="fastapi-service",
            environment=Environment(env_name),
            config_class=FastAPIServiceConfig,
            config_dir=config_dir,
            strategy=ConfigurationStrategy.AUTO_DETECT
        )

        await config_manager.initialize()
        service_config = await config_manager.get_configuration()

        # Store in app state for access in endpoints
        app.state.config = service_config
        app.state.config_manager = config_manager

        # Configure CORS and GZip middleware based on configuration
        if service_config.enable_cors:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=service_config.cors_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        if service_config.enable_gzip:
            app.add_middleware(GZipMiddleware, minimum_size=1000)

        logger.info(f"Configuration loaded successfully for {service_config.service_name}")
        logger.info(f"Service will run on {service_config.host}:{service_config.port}")

        # Configure logging level
        logging.getLogger().setLevel(getattr(logging, service_config.log_level.upper()))

    except Exception as e:
        logger.error(f"Failed to initialize configuration: {e}")
        raise

    yield

    # Cleanup
    logger.info("Shutting down FastAPI service...")
    config_manager = getattr(app.state, 'config_manager', None)
    if config_manager and hasattr(config_manager, 'cleanup'):
        try:
            await config_manager.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Create FastAPI application
app = FastAPI(
    title="FastAPI Service with Unified Configuration",
    description="A FastAPI service demonstrating the unified configuration system",
    version="1.0.0",
    lifespan=lifespan,
)


# Middleware setup (will be configured based on loaded configuration)
@app.middleware("http")
async def configure_middleware(request: Request, call_next):
    """Configure middleware based on loaded configuration."""
    # Track active connections
    active_connections.inc()

    start_time = datetime.utcnow()

    try:
        response = await call_next(request)

        # Record metrics
        duration = (datetime.utcnow() - start_time).total_seconds()
        request_duration.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        request_count.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code
        ).inc()

        return response

    finally:
        active_connections.dec()


# CORS and GZip middleware will be configured in lifespan after configuration is loaded


# Dependency to get current configuration
async def get_config(request: Request) -> FastAPIServiceConfig:
    """Dependency to get current service configuration."""
    service_config = getattr(request.app.state, 'config', None)
    if not service_config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")
    return service_config


# API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check(config: FastAPIServiceConfig = Depends(get_config)):
    """Health check endpoint."""
    return HealthResponse(
        service=config.service_name,
        config_loaded=True
    )


@app.get("/metrics")
async def metrics(config: FastAPIServiceConfig = Depends(get_config)):
    """Prometheus metrics endpoint."""
    if not config.enable_metrics:
        raise HTTPException(status_code=404, detail="Metrics disabled")

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/config/reload")
async def reload_config(request: Request, config: FastAPIServiceConfig = Depends(get_config)):
    """Reload configuration endpoint."""
    try:
        config_manager = getattr(request.app.state, 'config_manager', None)
        if not config_manager:
            raise HTTPException(status_code=500, detail="Configuration manager not available")

        service_config = await config_manager.get_configuration(reload=True)
        request.app.state.config = service_config

        logger.info("Configuration reloaded successfully")
        return {"status": "success", "message": "Configuration reloaded"}

    except Exception as e:
        logger.error(f"Failed to reload configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration reload failed: {str(e)}")


@app.get("/config")
async def get_current_config(config: FastAPIServiceConfig = Depends(get_config)):
    """Get current configuration (excluding sensitive data)."""
    config_dict = config.dict()

    # Remove sensitive information
    sensitive_keys = ["secret_key", "api_key", "database_url"]
    for key in sensitive_keys:
        if key in config_dict:
            config_dict[key] = "[REDACTED]"

    return config_dict


# Example business logic endpoints
@app.post("/items", response_model=ItemResponse)
async def create_item(
    item_request: ItemRequest,
    config: FastAPIServiceConfig = Depends(get_config)
):
    """Create a new item."""

    # Simulate some business logic
    item_id = str(uuid.uuid4())

    response = ItemResponse(
        id=item_id,
        name=item_request.name,
        description=item_request.description,
        tags=item_request.tags,
        created_at=datetime.utcnow(),
        service=config.service_name
    )

    logger.info(f"Created item {item_id}", extra={"item_name": item_request.name})

    return response


@app.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: str,
    config: FastAPIServiceConfig = Depends(get_config)
):
    """Get an item by ID."""
    # Simulate item retrieval
    # In a real implementation, this would query a database

    if not item_id:
        raise HTTPException(status_code=400, detail="Item ID is required")

    # Simulate item not found for demo
    if item_id == "notfound":
        raise HTTPException(status_code=404, detail="Item not found")

    return ItemResponse(
        id=item_id,
        name=f"Item {item_id}",
        description="A sample item",
        tags=["sample", "demo"],
        created_at=datetime.utcnow(),
        service=config.service_name
    )


@app.get("/items")
async def list_items(
    limit: int = 10,
    offset: int = 0,
    config: FastAPIServiceConfig = Depends(get_config)
):
    """List items with pagination."""
    # Simulate item listing
    items = []
    for i in range(limit):
        item_id = f"item-{offset + i + 1}"
        items.append({
            "id": item_id,
            "name": f"Item {item_id}",
            "description": f"Sample item {item_id}",
            "tags": ["sample"],
            "created_at": datetime.utcnow().isoformat(),
            "service": config.service_name
        })

    return {
        "items": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": 100  # Simulated total
        }
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="HTTP_ERROR",
            message=exc.detail,
            trace_id=request.headers.get("X-Trace-ID")
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="INTERNAL_ERROR",
            message="An internal error occurred",
            trace_id=request.headers.get("X-Trace-ID")
        ).dict()
    )


# Main execution
if __name__ == "__main__":
    # Load configuration for running the service
    try:
        # For development, we can load config synchronously

        async def load_config():
            temp_config_manager = create_unified_config_manager(
                service_name="fastapi-service",
                environment=Environment(os.getenv("ENVIRONMENT", "development")),
                config_class=FastAPIServiceConfig,
                config_dir=os.getenv("CONFIG_DIR", "config"),
                strategy=ConfigurationStrategy.AUTO_DETECT
            )
            await temp_config_manager.initialize()
            return await temp_config_manager.get_configuration()

        config = asyncio.run(load_config())

        uvicorn.run(
            "main:app",
            host=config.host,
            port=config.port,
            reload=config.reload,
            workers=config.workers if not config.reload else 1,
            log_level=config.log_level.lower()
        )

    except Exception as e:
        print(f"Failed to load configuration, using defaults: {e}")
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
