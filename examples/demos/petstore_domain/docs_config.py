"""
API Documentation Configuration for Petstore Domain Plugin

This module demonstrates how to use the Marty Framework's unified API documentation
and contract testing capabilities with a real-world petstore service.

Features demonstrated:
- OpenAPI documentation generation with custom metadata
- API versioning and deprecation management
- Consumer-driven contract testing setup
- Interactive documentation with examples
- Multiple output formats (HTML, Markdown, Postman)

Author: Marty Framework Team
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from marty_msf.framework.documentation.api_docs import (
    APIDocumentationManager,
    APIEndpoint,
    APIService,
    APIVersionManager,
    DocumentationConfig,
)

logger = logging.getLogger(__name__)


class PetstoreDocumentationConfig:
    """Petstore-specific documentation configuration."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.output_dir = base_path / "docs" / "api"

        # Create comprehensive documentation config
        self.config = DocumentationConfig(
            output_dir=self.output_dir,
            include_examples=True,
            generate_postman=True,
            generate_grpc_docs=False,  # Petstore is REST-only
            generate_unified_docs=False,  # Single service
            theme="redoc",
            service_metadata={
                "title": "Petstore Domain API",
                "version": "2.0.0",
                "description": """
# Petstore Domain Microservice

A comprehensive petstore domain service demonstrating enterprise-grade microservice patterns
with the Marty Microservices Framework.

## Features

- **Event-Driven Architecture**: Saga orchestration for order workflows
- **Observability**: Comprehensive metrics, tracing, and logging
- **Resilience Patterns**: Circuit breakers, retries, and timeouts
- **Security**: JWT/OIDC authentication and rate limiting
- **Data Integration**: Redis caching and PostgreSQL persistence

## API Versioning

This service supports multiple API versions:
- **v1.0**: Legacy endpoints (deprecated)
- **v2.0**: Current stable version
- **v2.1**: Beta features (experimental)

## Authentication

All endpoints require JWT token authentication:
```bash
Authorization: Bearer <jwt_token>
```

## Rate Limiting

API requests are rate-limited:
- **Standard**: 100 requests/minute
- **Premium**: 1000 requests/minute
""",
                "contact": {
                    "name": "Petstore API Team",
                    "email": "api-support@petstore.example.com",
                    "url": "https://docs.petstore.example.com"
                },
                "license": {
                    "name": "MIT",
                    "url": "https://opensource.org/licenses/MIT"
                },
                "servers": [
                    {
                        "url": "https://api.petstore.example.com",
                        "description": "Production server"
                    },
                    {
                        "url": "https://staging-api.petstore.example.com",
                        "description": "Staging server"
                    },
                    {
                        "url": "http://localhost:8000",
                        "description": "Development server"
                    }
                ]
            }
        )

    async def generate_documentation(self) -> dict[str, dict[str, Path]]:
        """Generate comprehensive API documentation for the petstore service."""
        logger.info("Generating Petstore API documentation...")

        manager = APIDocumentationManager(self.base_path, self.config)

        # Scan the app directory for FastAPI applications
        source_paths = [self.base_path / "app"]
        results = await manager.generate_all_documentation(source_paths)

        logger.info(f"Documentation generated successfully in {self.output_dir}")
        return results

    async def register_api_versions(self) -> None:
        """Register API versions for tracking and deprecation management."""

        logger.info("Registering Petstore API versions...")

        version_manager = APIVersionManager(self.base_path)

        # Register current stable version
        await version_manager.register_version(
            service_name="petstore-domain",
            version="2.0.0",
            deprecation_date=None,
            migration_guide="https://docs.petstore.example.com/migration/v2.0"
        )

        # Register deprecated v1.0
        await version_manager.deprecate_version(
            service_name="petstore-domain",
            version="1.0.0",
            deprecation_date="2024-12-31",
            migration_guide="https://docs.petstore.example.com/migration/v1-to-v2"
        )

        # Register beta version
        await version_manager.register_version(
            service_name="petstore-domain",
            version="2.1.0-beta",
            deprecation_date=None,
            migration_guide="https://docs.petstore.example.com/migration/v2.1-beta"
        )

        logger.info("API versions registered successfully")


async def setup_petstore_documentation():
    """Setup and generate petstore documentation."""
    base_path = Path(__file__).parent
    doc_config = PetstoreDocumentationConfig(base_path)

    # Generate documentation
    results = await doc_config.generate_documentation()

    # Register API versions
    await doc_config.register_api_versions()

    return results


if __name__ == "__main__":
    # CLI entry point for documentation generation
    logging.basicConfig(level=logging.INFO)
    asyncio.run(setup_petstore_documentation())
