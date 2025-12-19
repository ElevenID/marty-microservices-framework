"""Store Service Main Application (Hexagonal Architecture version).

This is the entry point for running the Store Service as a standalone application
using the clean Hexagonal Architecture pattern with BaseDIContainer.

For the original version with SQLModel, Dishka, and Taskiq integration,
see main_legacy.py.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from examples.petstore_domain.services.store_service.di_config import (
    StoreServiceDIContainer,
)
from examples.petstore_domain.services.store_service.infrastructure.adapters.input.api import (
    create_store_router,
)
from mmf.framework.observability import add_correlation_id_middleware
from mmf.services.identity.integration import (
    JWTAuthenticationMiddleware,
    create_development_config,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle.

    Initializes the DI container on startup and cleans up on shutdown.
    Container is stored in app.state for proper dependency injection.
    """
    # Startup: Initialize DI container and store in app.state
    container = StoreServiceDIContainer()
    container.initialize()
    app.state.container = container

    # Create and include the router with injected dependencies
    router = create_store_router(
        create_order_use_case=container.create_order_use_case,
        get_order_use_case=container.get_order_use_case,
        list_orders_use_case=container.list_orders_use_case,
        get_catalog_use_case=container.get_catalog_use_case,
    )
    app.include_router(router)

    yield

    # Shutdown: Cleanup DI container
    if hasattr(app.state, "container"):
        app.state.container.cleanup()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Store Service",
        description="Pet store service demonstrating Hexagonal Architecture with bounded context isolation",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure JWT Authentication (Development Mode)
    jwt_auth_config = create_development_config()
    jwt_config = jwt_auth_config.to_jwt_config()
    app.add_middleware(
        JWTAuthenticationMiddleware,
        jwt_config=jwt_config,
        excluded_paths=jwt_auth_config.excluded_paths,
        optional_paths=jwt_auth_config.optional_paths,
    )

    # Add correlation ID middleware for distributed tracing
    add_correlation_id_middleware(app)

    FastAPIInstrumentor.instrument_app(app)

    @app.get("/health")
    async def health(request: Request) -> dict:
        """Health check endpoint."""
        return {"status": "ok"}

    return app


# Application instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
