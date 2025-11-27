"""
Main entry point for the Morty service.

This demonstrates how to create a microservice using the modern
Marty Microservices Framework.
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from marty_msf.framework.config_factory import create_service_config
from marty_msf.framework.logging import UnifiedServiceLogger
from marty_msf.framework.monitoring import setup_fastapi_monitoring
from observability import init_observability

# Initialize logger
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    try:
        # Load configuration using the new framework
        create_service_config(service_name="morty_service", environment="development")

        # Initialize observability (metrics, tracing, logging)
        init_observability("morty_service")

        # Set up service logger
        service_logger = UnifiedServiceLogger(service_name="morty_service")
        service_logger.log_service_startup(
            {
                "event_topic_prefix": "morty",
                "from_email": "morty@company.com",
            }
        )

        logger.info("Morty service started successfully")
        yield

    except Exception as e:
        logger.error(f"Failed to start Morty service: {e}")
        raise
    finally:
        logger.info("Morty service stopped")


# Create the FastAPI application
app = FastAPI(
    title="Morty Service",
    description="Microservice using modern Marty framework",
    version="1.0.0",
    lifespan=lifespan,
)

# Set up monitoring middleware
setup_fastapi_monitoring(app)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "morty_service"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Morty service running on modern framework"}


if __name__ == "__main__":

    # Load configuration
    config = create_service_config(service_name="morty_service", environment="development")

    # Run the service
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
