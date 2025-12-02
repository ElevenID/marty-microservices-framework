"""
OpenAPI documentation generator adapter.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from mmf.framework.documentation.domain.models import APIService, DocumentationConfig
from mmf.framework.documentation.ports.generator import APIDocumentationGenerator

logger = logging.getLogger(__name__)


class OpenAPIGenerator(APIDocumentationGenerator):
    """OpenAPI/Swagger documentation generator for REST APIs."""

    async def generate_documentation(self, service: APIService) -> dict[str, Path]:
        """Generate OpenAPI documentation."""
        output_files = {}

        # Generate OpenAPI spec
        openapi_spec = self._generate_openapi_spec(service)

        # Write OpenAPI JSON
        openapi_file = self.config.output_dir / f"{service.name}-openapi.json"
        with open(openapi_file, "w") as f:
            json.dump(openapi_spec, f, indent=2)
        output_files["openapi_spec"] = openapi_file

        # Generate HTML documentation
        if self.config.generate_openapi:
            html_file = await self._generate_html_docs(service, openapi_spec)
            output_files["html_docs"] = html_file

        # Generate Postman collection
        if self.config.generate_postman:
            postman_file = await self._generate_postman_collection(service, openapi_spec)
            output_files["postman_collection"] = postman_file

        return output_files

    def _generate_openapi_spec(self, service: APIService) -> dict[str, Any]:
        """Generate OpenAPI 3.0 specification."""
        spec = {
            "openapi": "3.0.3",
            "info": {
                "title": service.name,
                "version": service.version,
                "description": service.description,
            },
            "servers": service.servers or [{"url": service.base_url}],
            "paths": {},
            "components": {"schemas": service.schemas},
        }

        # Add contact and license if available
        if service.contact:
            spec["info"]["contact"] = service.contact
        if service.license:
            spec["info"]["license"] = service.license

        # Add endpoints
        for endpoint in service.endpoints:
            path = endpoint.path
            if path not in spec["paths"]:
                spec["paths"][path] = {}

            operation = {
                "summary": endpoint.summary,
                "description": endpoint.description,
                "tags": endpoint.tags,
                "parameters": endpoint.parameters,
                "responses": endpoint.response_schemas,
            }

            if endpoint.request_schema:
                operation["requestBody"] = {
                    "content": {"application/json": {"schema": endpoint.request_schema}}
                }

            if endpoint.deprecated:
                operation["deprecated"] = True
                if endpoint.deprecation_date:
                    operation["x-deprecation-date"] = endpoint.deprecation_date
                if endpoint.migration_guide:
                    operation["x-migration-guide"] = endpoint.migration_guide

            spec["paths"][path][endpoint.method.lower()] = operation

        return spec

    async def _generate_html_docs(self, service: APIService, openapi_spec: dict[str, Any]) -> Path:
        """Generate HTML documentation."""
        template = self.template_env.get_template("openapi_docs.html")

        html_content = template.render(
            service=service,
            openapi_spec=json.dumps(openapi_spec, indent=2),
            theme=self.config.theme,
            timestamp=datetime.utcnow().isoformat(),
        )

        html_file = self.config.output_dir / f"{service.name}-docs.html"
        with open(html_file, "w") as f:
            f.write(html_content)

        return html_file

    async def _generate_postman_collection(
        self, service: APIService, openapi_spec: dict[str, Any]
    ) -> Path:
        """Generate Postman collection from OpenAPI spec."""
        collection = {
            "info": {
                "name": service.name,
                "description": service.description,
                "version": service.version,
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "item": [],
        }

        # Convert endpoints to Postman requests
        for endpoint in service.endpoints:
            request_item = {
                "name": endpoint.summary,
                "request": {
                    "method": endpoint.method.upper(),
                    "header": [{"key": "Content-Type", "value": "application/json"}],
                    "url": {
                        "raw": f"{service.base_url}{endpoint.path}",
                        "host": [service.base_url.replace("https://", "").replace("http://", "")],
                        "path": endpoint.path.strip("/").split("/"),
                    },
                },
            }

            if endpoint.request_schema:
                request_item["request"]["body"] = {
                    "mode": "raw",
                    "raw": json.dumps({"example": "Add your request data here"}, indent=2),
                }

            collection["item"].append(request_item)

        postman_file = self.config.output_dir / f"{service.name}-postman.json"
        with open(postman_file, "w") as f:
            json.dump(collection, f, indent=2)

        return postman_file

    async def discover_apis(self, source_path: Path) -> list[APIService]:
        """Discover FastAPI applications and extract API information."""
        services = []

        # Look for FastAPI applications
        for py_file in source_path.rglob("*.py"):
            if await self._is_fastapi_app(py_file):
                service = await self._extract_fastapi_service(py_file)
                if service:
                    services.append(service)

        return services

    async def _is_fastapi_app(self, file_path: Path) -> bool:
        """Check if file contains a FastAPI application."""
        try:
            content = file_path.read_text()
            return "FastAPI" in content and "app = FastAPI" in content
        except Exception:
            return False

    async def _extract_fastapi_service(self, file_path: Path) -> APIService | None:
        """Extract API service information from FastAPI application."""
        # This is a simplified implementation
        # In practice, you'd use AST parsing or import the module
        try:
            content = file_path.read_text()

            # Extract basic info (simplified)
            service_name = file_path.parent.name
            version = "1.0.0"
            description = "FastAPI Service"

            # Extract title from FastAPI constructor
            title_match = re.search(r'title="([^"]+)"', content)
            if title_match:
                service_name = title_match.group(1)

            # Extract version
            version_match = re.search(r'version="([^"]+)"', content)
            if version_match:
                version = version_match.group(1)

            # Extract description
            desc_match = re.search(r'description="([^"]+)"', content)
            if desc_match:
                description = desc_match.group(1)

            return APIService(
                name=service_name,
                version=version,
                description=description,
                base_url="http://localhost:8000",
            )

        except Exception as e:
            logger.error(f"Error extracting FastAPI service from {file_path}: {e}")
            return None
