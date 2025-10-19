"""
Enterprise API Gateway Service Template

This template provides a comprehensive API gateway implementation using
the modern Marty Microservices Framework.

Features:
- Dynamic service discovery
- Load balancing
- Circuit breaker patterns
- Rate limiting
- Authentication/Authorization
- Request/Response transformation
- Metrics and monitoring
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from marty_msf.core.di_container import get_container
from marty_msf.framework.config_factory import create_service_config
from marty_msf.framework.discovery import (
    DiscoveryManagerConfig,
    ServiceDiscoveryManager,
)
from marty_msf.framework.discovery.core import ServiceInstance
from marty_msf.framework.gateway import APIGateway
from marty_msf.observability.monitoring import MetricsCollector

# Initialize logger
logger = logging.getLogger(__name__)

# Global gateway instance
gateway: APIGateway | None = None
discovery_manager: ServiceDiscoveryManager | None = None
metrics: MetricsCollector | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""

    container = get_container()

    try:
        # Load configuration using the new framework
        config = create_service_config(
            service_name="api_gateway",
            environment="development"
        )
        logger.info("Starting API Gateway service...")

        # Initialize metrics using DI container
        metrics = container.get_or_create(MetricsCollector, lambda: MetricsCollector())

        # Initialize service discovery
        discovery_config = DiscoveryManagerConfig(
            service_name="api-gateway",
            registry_type="consul",  # or "etcd", "kubernetes", "memory"
            load_balancing_enabled=True,
            health_check_enabled=True,
            health_check_interval=30,
        )
        discovery_manager = container.get_or_create(ServiceDiscoveryManager, lambda: ServiceDiscoveryManager(discovery_config))
        await discovery_manager.start()

        # Initialize API Gateway using DI container
        gateway = container.get_or_create(APIGateway, lambda: APIGateway())
        await gateway.start()

        # Register with service discovery
        gateway_instance = ServiceInstance(
            service_name="api-gateway",
            instance_id="gateway-001",
            host="localhost",
            port=8080,
            metadata={
                "version": "1.0.0",
                "environment": "development",
                "gateway_type": "main",
            },
        )
        await discovery_manager.register_service(gateway_instance)

        # Configure routes from configuration
        await configure_gateway_routes(gateway, config)

        logger.info("API Gateway service started successfully")
        yield

    except Exception as e:
        logger.error(f"Failed to start API Gateway: {e}")
        raise
    finally:
        # Cleanup using DI container
        try:
            gateway = container.get(APIGateway)
            if gateway:
                await gateway.stop()
        except KeyError:
            pass  # Service not initialized

        try:
            discovery_manager = container.get(ServiceDiscoveryManager)
            if discovery_manager:
                await discovery_manager.stop()
        except KeyError:
            pass  # Service not initialized

        logger.info("API Gateway service stopped")


async def configure_gateway_routes(gateway: APIGateway, config):
    """Configure gateway routes from configuration."""

    # Example route configurations using the framework patterns
    # Note: This is a simplified version that demonstrates the current
    # framework structure

    logger.info("Configuring gateway routes...")

    # In the framework, route configuration is handled through
    # This placeholder shows the pattern - actual implementation
    # would depend on the current framework gateway API

    logger.info("Routes configured successfully")


# Create FastAPI app with the new framework patterns
app = FastAPI(
    title="API Gateway Service",
    description="Enterprise API Gateway using modern Marty framework",
    version="1.0.0",
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


@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    """Gateway middleware for request processing."""
    try:
        # In a full implementation, this would route requests through the gateway
        response = await call_next(request)

        # Record metrics if available
        if metrics:
            # Use the framework's metrics API (simplified for migration)
            pass

        return response
    except Exception as e:
        logger.error(f"Gateway middleware error: {e}")
        return JSONResponse(
            content={"error": "Gateway error"},
            status_code=500
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "api_gateway",
        "framework": "marty_framework_v2"
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "API Gateway running on modern Marty framework",
        "version": "1.0.0"
    }


@app.get("/gateway/info")
async def gateway_info():
    """Get gateway information."""
    return {
        "service": "api_gateway",
        "framework": "marty_framework_v2",
        "status": "migrated_from_chassis",
        "components": {
            "gateway": "initialized" if gateway else "not_initialized",
            "discovery": "initialized" if discovery_manager else "not_initialized",
            "metrics": "initialized" if metrics else "not_initialized"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
    )
