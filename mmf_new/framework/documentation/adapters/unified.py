"""
Unified documentation generator adapter.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from mmf_new.framework.documentation.adapters.grpc import GRPCDocumentationGenerator
from mmf_new.framework.documentation.adapters.openapi import OpenAPIGenerator
from mmf_new.framework.documentation.domain.models import APIService, DocumentationConfig
from mmf_new.framework.documentation.ports.generator import APIDocumentationGenerator


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
            with open(unified_file, "w") as f:
                f.write(unified_docs)
            output_files["unified_docs"] = unified_file

        # Generate grpc-gateway configuration if needed
        if service.endpoints and service.grpc_methods:
            gateway_config = await self._generate_grpc_gateway_config(service)
            gateway_file = self.config.output_dir / f"{service.name}-gateway.yaml"
            with open(gateway_file, "w") as f:
                yaml.dump(gateway_config, f, default_flow_style=False)
            output_files["grpc_gateway_config"] = gateway_file

        return output_files

    async def _generate_unified_docs(self, service: APIService) -> str:
        """Generate unified documentation showing both REST and gRPC APIs."""
        template = self.template_env.get_template("unified_docs.html")

        return template.render(
            service=service,
            has_rest=bool(service.endpoints),
            has_grpc=bool(service.grpc_methods),
            timestamp=datetime.utcnow().isoformat(),
        )

    async def _generate_grpc_gateway_config(self, service: APIService) -> dict[str, Any]:
        """Generate grpc-gateway configuration for REST-to-gRPC proxying."""
        config = {
            "type": "google.api.Service",
            "config_version": 3,
            "name": f"{service.name}.api",
            "title": f"{service.name} API",
            "description": service.description,
            "apis": [{"name": f"{service.name}", "version": service.version}],
            "http": {"rules": []},
        }

        # Map gRPC methods to HTTP endpoints
        for method in service.grpc_methods:
            rule = {
                "selector": method.full_name,
                "post": f"/api/v1/{method.name.lower()}",
                "body": "*",
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
