"""
Unified API Documentation Generator for Marty Microservices Framework.

This module provides comprehensive API documentation generation for both REST (OpenAPI)
and gRPC (protobuf) services, with grpc-gateway integration for unified HTTP exposure.

Features:
- Automatic OpenAPI spec generation from FastAPI services
- Protocol buffer documentation generation from .proto files
- grpc-gateway integration for REST/gRPC unified exposure
- API versioning support across REST and gRPC
- Deprecation warnings and migration guides
- Consumer-driven contract documentation
- Interactive documentation generation

Author: Marty Framework Team
Version: 1.0.0
"""

import argparse
import asyncio
import json
import logging
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Union

import yaml
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


@dataclass
class APIEndpoint:
    """API endpoint documentation."""

    path: str
    method: str
    summary: str
    description: str = ""
    parameters: list[dict[str, Any]] = field(default_factory=list)
    request_schema: dict[str, Any] | None = None
    response_schemas: dict[str, dict[str, Any]] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    deprecation_date: str | None = None
    migration_guide: str | None = None
    version: str = "1.0.0"


@dataclass
class GRPCMethod:
    """gRPC method documentation."""

    name: str
    full_name: str
    input_type: str
    output_type: str
    description: str = ""
    streaming: str = "unary"  # unary, client_streaming, server_streaming, bidirectional
    deprecated: bool = False
    deprecation_date: str | None = None
    migration_guide: str | None = None
    version: str = "1.0.0"


@dataclass
class APIService:
    """API service documentation."""

    name: str
    version: str
    description: str
    base_url: str = ""
    endpoints: list[APIEndpoint] = field(default_factory=list)
    grpc_methods: list[GRPCMethod] = field(default_factory=list)
    schemas: dict[str, dict[str, Any]] = field(default_factory=dict)
    contact: dict[str, str] | None = None
    license: dict[str, str] | None = None
    servers: list[dict[str, str]] = field(default_factory=list)
    deprecated_versions: list[str] = field(default_factory=list)


@dataclass
class DocumentationConfig:
    """Configuration for documentation generation."""

    output_dir: Path
    template_dir: Path | None = None
    include_examples: bool = True
    include_schemas: bool = True
    generate_postman: bool = True
    generate_openapi: bool = True
    generate_grpc_docs: bool = True
    generate_unified_docs: bool = True
    theme: str = "redoc"  # redoc, swagger-ui, stoplight
    custom_css: Path | None = None
    custom_js: Path | None = None


class APIDocumentationGenerator(ABC):
    """Abstract base class for API documentation generators."""

    def __init__(self, config: DocumentationConfig):
        self.config = config
        self.template_env = self._setup_templates()

    def _setup_templates(self) -> Environment:
        """Setup Jinja2 template environment."""
        template_dir = self.config.template_dir or Path(__file__).parent / "templates"
        return Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )

    @abstractmethod
    async def generate_documentation(self, service: APIService) -> dict[str, Path]:
        """Generate documentation for the service."""
        pass

    @abstractmethod
    async def discover_apis(self, source_path: Path) -> list[APIService]:
        """Discover APIs from source code."""
        pass


class OpenAPIGenerator(APIDocumentationGenerator):
    """OpenAPI/Swagger documentation generator for REST APIs."""

    async def generate_documentation(self, service: APIService) -> dict[str, Path]:
        """Generate OpenAPI documentation."""
        output_files = {}

        # Generate OpenAPI spec
        openapi_spec = self._generate_openapi_spec(service)

        # Write OpenAPI JSON
        openapi_file = self.config.output_dir / f"{service.name}-openapi.json"
        with open(openapi_file, 'w') as f:
            json.dump(openapi_spec, f, indent=2)
        output_files['openapi_spec'] = openapi_file

        # Generate HTML documentation
        if self.config.generate_openapi:
            html_file = await self._generate_html_docs(service, openapi_spec)
            output_files['html_docs'] = html_file

        # Generate Postman collection
        if self.config.generate_postman:
            postman_file = await self._generate_postman_collection(service, openapi_spec)
            output_files['postman_collection'] = postman_file

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
            "components": {
                "schemas": service.schemas
            }
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
                "responses": endpoint.response_schemas
            }

            if endpoint.request_schema:
                operation["requestBody"] = {
                    "content": {
                        "application/json": {
                            "schema": endpoint.request_schema
                        }
                    }
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
            timestamp=datetime.utcnow().isoformat()
        )

        html_file = self.config.output_dir / f"{service.name}-docs.html"
        with open(html_file, 'w') as f:
            f.write(html_content)

        return html_file

    async def _generate_postman_collection(self, service: APIService, openapi_spec: dict[str, Any]) -> Path:
        """Generate Postman collection from OpenAPI spec."""
        collection = {
            "info": {
                "name": service.name,
                "description": service.description,
                "version": service.version,
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": []
        }

        # Convert endpoints to Postman requests
        for endpoint in service.endpoints:
            request_item = {
                "name": endpoint.summary,
                "request": {
                    "method": endpoint.method.upper(),
                    "header": [
                        {
                            "key": "Content-Type",
                            "value": "application/json"
                        }
                    ],
                    "url": {
                        "raw": f"{service.base_url}{endpoint.path}",
                        "host": [service.base_url.replace("https://", "").replace("http://", "")],
                        "path": endpoint.path.strip("/").split("/")
                    }
                }
            }

            if endpoint.request_schema:
                request_item["request"]["body"] = {
                    "mode": "raw",
                    "raw": json.dumps({
                        "example": "Add your request data here"
                    }, indent=2)
                }

            collection["item"].append(request_item)

        postman_file = self.config.output_dir / f"{service.name}-postman.json"
        with open(postman_file, 'w') as f:
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
                base_url="http://localhost:8000"
            )

        except Exception as e:
            logger.error(f"Error extracting FastAPI service from {file_path}: {e}")
            return None


class GRPCDocumentationGenerator(APIDocumentationGenerator):
    """gRPC documentation generator from protocol buffer files."""

    async def generate_documentation(self, service: APIService) -> dict[str, Path]:
        """Generate gRPC documentation."""
        output_files = {}

        if not service.grpc_methods:
            return output_files

        # Generate protobuf documentation
        proto_docs = await self._generate_proto_docs(service)
        proto_file = self.config.output_dir / f"{service.name}-grpc-docs.html"
        with open(proto_file, 'w') as f:
            f.write(proto_docs)
        output_files['grpc_docs'] = proto_file

        # Generate gRPC-web client code documentation
        if self.config.include_examples:
            client_docs = await self._generate_client_examples(service)
            client_file = self.config.output_dir / f"{service.name}-grpc-clients.md"
            with open(client_file, 'w') as f:
                f.write(client_docs)
            output_files['client_examples'] = client_file

        return output_files

    async def _generate_proto_docs(self, service: APIService) -> str:
        """Generate HTML documentation for protobuf services."""
        template = self.template_env.get_template("grpc_docs.html")

        return template.render(
            service=service,
            timestamp=datetime.utcnow().isoformat()
        )

    async def _generate_client_examples(self, service: APIService) -> str:
        """Generate client code examples for different languages."""
        template = self.template_env.get_template("grpc_client_examples.md")

        return template.render(
            service=service,
            timestamp=datetime.utcnow().isoformat()
        )

    async def discover_apis(self, source_path: Path) -> list[APIService]:
        """Discover gRPC services from .proto files."""
        services = []

        for proto_file in source_path.rglob("*.proto"):
            service = await self._parse_proto_file(proto_file)
            if service:
                services.append(service)

        return services

    async def _parse_proto_file(self, proto_file: Path) -> APIService | None:
        """Parse protobuf file and extract service information."""
        try:
            content = proto_file.read_text()

            # Extract package name
            package_match = re.search(r'package\s+([^;]+);', content)
            package_name = package_match.group(1) if package_match else "unknown"

            # Extract service definitions
            service_pattern = r'service\s+(\w+)\s*\{([^}]+)\}'
            services = re.findall(service_pattern, content, re.DOTALL)

            if not services:
                return None

            # For now, take the first service
            service_name, service_body = services[0]

            # Extract methods
            method_pattern = r'rpc\s+(\w+)\s*\(([^)]+)\)\s*returns\s*\(([^)]+)\)'
            methods = re.findall(method_pattern, service_body)

            grpc_methods = []
            for method_name, input_type, output_type in methods:
                grpc_methods.append(GRPCMethod(
                    name=method_name,
                    full_name=f"{package_name}.{service_name}.{method_name}",
                    input_type=input_type.strip(),
                    output_type=output_type.strip(),
                    description=f"gRPC method {method_name}"
                ))

            return APIService(
                name=service_name,
                version="1.0.0",
                description=f"gRPC service {service_name}",
                grpc_methods=grpc_methods
            )

        except Exception as e:
            logger.error(f"Error parsing proto file {proto_file}: {e}")
            return None


class UnifiedAPIDocumentationGenerator(APIDocumentationGenerator):
    """Unified documentation generator for REST and gRPC APIs."""

    def __init__(self, config: DocumentationConfig):
        super().__init__(config)
        self.openapi_generator = OpenAPIGenerator(config)
        self.grpc_generator = GRPCDocumentationGenerator(config)

    async def generate_documentation(self, service: APIService) -> dict[str, Path]:
        """Generate unified documentation for both REST and gRPC."""
        output_files = {}

        # Generate REST documentation if endpoints exist
        if service.endpoints:
            rest_files = await self.openapi_generator.generate_documentation(service)
            output_files.update(rest_files)

        # Generate gRPC documentation if methods exist
        if service.grpc_methods:
            grpc_files = await self.grpc_generator.generate_documentation(service)
            output_files.update(grpc_files)

        # Generate unified documentation
        if self.config.generate_unified_docs:
            unified_docs = await self._generate_unified_docs(service)
            unified_file = self.config.output_dir / f"{service.name}-unified-docs.html"
            with open(unified_file, 'w') as f:
                f.write(unified_docs)
            output_files['unified_docs'] = unified_file

        # Generate grpc-gateway configuration if needed
        if service.endpoints and service.grpc_methods:
            gateway_config = await self._generate_grpc_gateway_config(service)
            gateway_file = self.config.output_dir / f"{service.name}-gateway.yaml"
            with open(gateway_file, 'w') as f:
                yaml.dump(gateway_config, f, default_flow_style=False)
            output_files['grpc_gateway_config'] = gateway_file

        return output_files

    async def _generate_unified_docs(self, service: APIService) -> str:
        """Generate unified documentation showing both REST and gRPC APIs."""
        template = self.template_env.get_template("unified_docs.html")

        return template.render(
            service=service,
            has_rest=bool(service.endpoints),
            has_grpc=bool(service.grpc_methods),
            timestamp=datetime.utcnow().isoformat()
        )

    async def _generate_grpc_gateway_config(self, service: APIService) -> dict[str, Any]:
        """Generate grpc-gateway configuration for REST-to-gRPC proxying."""
        config = {
            "type": "google.api.Service",
            "config_version": 3,
            "name": f"{service.name}.api",
            "title": f"{service.name} API",
            "description": service.description,
            "apis": [
                {
                    "name": f"{service.name}",
                    "version": service.version
                }
            ],
            "http": {
                "rules": []
            }
        }

        # Map gRPC methods to HTTP endpoints
        for method in service.grpc_methods:
            rule = {
                "selector": method.full_name,
                "post": f"/api/v1/{method.name.lower()}",
                "body": "*"
            }
            config["http"]["rules"].append(rule)

        return config

    async def discover_apis(self, source_path: Path) -> list[APIService]:
        """Discover both REST and gRPC APIs."""
        rest_services = await self.openapi_generator.discover_apis(source_path)
        grpc_services = await self.grpc_generator.discover_apis(source_path)

        # Merge services by name
        merged_services = {}

        for service in rest_services:
            merged_services[service.name] = service

        for service in grpc_services:
            if service.name in merged_services:
                # Merge gRPC methods into existing service
                merged_services[service.name].grpc_methods.extend(service.grpc_methods)
            else:
                merged_services[service.name] = service

        return list(merged_services.values())


class APIVersionManager:
    """Manages API versions and deprecation policies."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.versions_file = base_path / "api_versions.yaml"

    async def register_version(self, service_name: str, version: str,
                              deprecation_date: str | None = None,
                              migration_guide: str | None = None) -> bool:
        """Register a new API version."""
        versions = await self._load_versions()

        if service_name not in versions:
            versions[service_name] = {}

        versions[service_name][version] = {
            "created_date": datetime.utcnow().isoformat(),
            "deprecation_date": deprecation_date,
            "migration_guide": migration_guide,
            "status": "active"
        }

        return await self._save_versions(versions)

    async def deprecate_version(self, service_name: str, version: str,
                               deprecation_date: str, migration_guide: str) -> bool:
        """Mark a version as deprecated."""
        versions = await self._load_versions()

        if service_name in versions and version in versions[service_name]:
            versions[service_name][version].update({
                "status": "deprecated",
                "deprecation_date": deprecation_date,
                "migration_guide": migration_guide
            })
            return await self._save_versions(versions)

        return False

    async def get_active_versions(self, service_name: str) -> list[str]:
        """Get all active versions for a service."""
        versions = await self._load_versions()

        if service_name not in versions:
            return []

        return [
            version for version, info in versions[service_name].items()
            if info.get("status") == "active"
        ]

    async def get_deprecated_versions(self, service_name: str) -> list[dict[str, Any]]:
        """Get all deprecated versions with deprecation info."""
        versions = await self._load_versions()

        if service_name not in versions:
            return []

        deprecated = []
        for version, info in versions[service_name].items():
            if info.get("status") == "deprecated":
                deprecated.append({
                    "version": version,
                    "deprecation_date": info.get("deprecation_date"),
                    "migration_guide": info.get("migration_guide")
                })

        return deprecated

    async def _load_versions(self) -> dict[str, Any]:
        """Load version information from file."""
        if not self.versions_file.exists():
            return {}

        try:
            with open(self.versions_file) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error loading versions file: {e}")
            return {}

    async def _save_versions(self, versions: dict[str, Any]) -> bool:
        """Save version information to file."""
        try:
            self.versions_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.versions_file, 'w') as f:
                yaml.dump(versions, f, default_flow_style=False)
            return True
        except Exception as e:
            logger.error(f"Error saving versions file: {e}")
            return False


# Main API Documentation Manager
class APIDocumentationManager:
    """Main manager for API documentation generation and management."""

    def __init__(self, base_path: Path, config: DocumentationConfig | None = None):
        self.base_path = base_path
        self.config = config or DocumentationConfig(
            output_dir=base_path / "docs" / "api"
        )
        self.generator = UnifiedAPIDocumentationGenerator(self.config)
        self.version_manager = APIVersionManager(base_path)

    async def generate_all_documentation(self, source_paths: list[Path]) -> dict[str, dict[str, Path]]:
        """Generate documentation for all services in the given paths."""
        all_services = []

        for source_path in source_paths:
            services = await self.generator.discover_apis(source_path)
            all_services.extend(services)

        results = {}
        for service in all_services:
            output_files = await self.generator.generate_documentation(service)
            results[service.name] = output_files

            # Register version if not already registered
            active_versions = await self.version_manager.get_active_versions(service.name)
            if service.version not in active_versions:
                await self.version_manager.register_version(service.name, service.version)

        # Generate index page
        await self._generate_index_page(all_services)

        return results

    async def _generate_index_page(self, services: list[APIService]) -> None:
        """Generate an index page listing all services."""
        template = self.generator.template_env.get_template("index.html")

        html_content = template.render(
            services=services,
            timestamp=datetime.utcnow().isoformat()
        )

        index_file = self.config.output_dir / "index.html"
        with open(index_file, 'w') as f:
            f.write(html_content)


# Command-line interface functions
async def generate_api_docs(source_paths: list[str], output_dir: str,
                           config_file: str | None = None) -> None:
    """Generate API documentation from source paths."""
    # Load configuration
    config = DocumentationConfig(output_dir=Path(output_dir))

    if config_file and Path(config_file).exists():
        with open(config_file) as f:
            config_data = yaml.safe_load(f)
            # Update config with loaded data
            for key, value in config_data.items():
                if hasattr(config, key):
                    setattr(config, key, value)

    # Create documentation manager
    manager = APIDocumentationManager(Path.cwd(), config)

    # Generate documentation
    source_paths_list = [Path(p) for p in source_paths]
    results = await manager.generate_all_documentation(source_paths_list)

    print(f"Generated documentation for {len(results)} services:")
    for service_name, files in results.items():
        print(f"  {service_name}:")
        for file_type, file_path in files.items():
            print(f"    {file_type}: {file_path}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Generate API documentation")
    parser.add_argument("source_paths", nargs="+", help="Source code paths to scan")
    parser.add_argument("--output-dir", default="./docs/api", help="Output directory")
    parser.add_argument("--config", help="Configuration file")

    args = parser.parse_args()

    asyncio.run(generate_api_docs(args.source_paths, args.output_dir, args.config))
