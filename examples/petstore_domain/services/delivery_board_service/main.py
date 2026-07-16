"""Delivery Board Service Main Application (Hexagonal Architecture version).

This is the entry point for running the Delivery Board Service as a standalone
application using the clean Hexagonal Architecture pattern with BaseDIContainer.

For the original version, see main.py.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from examples.petstore_domain.services.delivery_board_service.di_config import (
    DeliveryBoardDIContainer,
)
from examples.petstore_domain.services.delivery_board_service.infrastructure.adapters.input.api import (
    create_delivery_router,
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
    container = DeliveryBoardDIContainer()
    container.initialize()
    app.state.container = container

    # Create and include the router with injected dependencies
    router = create_delivery_router(
        create_delivery_use_case=container.create_delivery_use_case,
        get_delivery_use_case=container.get_delivery_use_case,
        list_deliveries_use_case=container.list_deliveries_use_case,
        complete_delivery_use_case=container.complete_delivery_use_case,
        cancel_delivery_use_case=container.cancel_delivery_use_case,
        list_trucks_use_case=container.list_trucks_use_case,
        update_truck_use_case=container.update_truck_use_case,
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
        title="Delivery Board Service",
        description="Delivery dispatch service demonstrating Hexagonal Architecture with bounded context isolation",
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
        if hasattr(request.app.state, "container"):
            trucks = request.app.state.container.list_trucks_use_case.execute()
            return {
                "status": "ok",
                "trucks": trucks.total_count,
                "active_load": trucks.total_load,
            }
        return {"status": "ok"}

    return app


# Application instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
