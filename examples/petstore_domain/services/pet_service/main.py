"""Pet Service Main Application.

This is the entry point for running the Pet Service as a standalone application.
It demonstrates proper initialization using the DI container.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from examples.petstore_domain.services.pet_service.di_config import (
    PetServiceDIContainer,
)
from examples.petstore_domain.services.pet_service.infrastructure.adapters.input.api import (
    create_pet_router,
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
    container = PetServiceDIContainer()
    container.initialize()
    app.state.container = container

    # Create and include the router with injected dependencies
    router = create_pet_router(
        create_pet_use_case=container.create_pet_use_case,
        get_pet_use_case=container.get_pet_use_case,
        list_pets_use_case=container.list_pets_use_case,
        delete_pet_use_case=container.delete_pet_use_case,
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
        title="Pet Service",
        description="A pet management service demonstrating Hexagonal Architecture",
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

    uvicorn.run(app, host="0.0.0.0", port=8000)
