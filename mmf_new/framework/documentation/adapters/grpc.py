"""
gRPC documentation generator adapter.
"""

import logging
import re
from datetime import datetime
from pathlib import Path

from mmf_new.framework.documentation.domain.models import APIService, GRPCMethod
from mmf_new.framework.documentation.ports.generator import APIDocumentationGenerator

logger = logging.getLogger(__name__)


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
        with open(proto_file, "w") as f:
            f.write(proto_docs)
        output_files["grpc_docs"] = proto_file

        # Generate gRPC-web client code documentation
        if self.config.include_examples:
            client_docs = await self._generate_client_examples(service)
            client_file = self.config.output_dir / f"{service.name}-grpc-clients.md"
            with open(client_file, "w") as f:
                f.write(client_docs)
            output_files["client_examples"] = client_file

        return output_files

    async def _generate_proto_docs(self, service: APIService) -> str:
        """Generate HTML documentation for protobuf services."""
        template = self.template_env.get_template("grpc_docs.html")

        return template.render(service=service, timestamp=datetime.utcnow().isoformat())

    async def _generate_client_examples(self, service: APIService) -> str:
        """Generate client code examples for different languages."""
        template = self.template_env.get_template("grpc_client_examples.md")

        return template.render(service=service, timestamp=datetime.utcnow().isoformat())

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
            package_match = re.search(r"package\s+([^;]+);", content)
            package_name = package_match.group(1) if package_match else "unknown"

            # Extract service definitions
            service_pattern = r"service\s+(\w+)\s*\{([^}]+)\}"
            services = re.findall(service_pattern, content, re.DOTALL)

            if not services:
                return None

            # For now, take the first service
            service_name, service_body = services[0]

            # Extract methods
            method_pattern = r"rpc\s+(\w+)\s*\(([^)]+)\)\s*returns\s*\(([^)]+)\)"
            methods = re.findall(method_pattern, service_body)

            grpc_methods = []
            for method_name, input_type, output_type in methods:
                grpc_methods.append(
                    GRPCMethod(
                        name=method_name,
                        full_name=f"{package_name}.{service_name}.{method_name}",
                        input_type=input_type.strip(),
                        output_type=output_type.strip(),
                        description=f"gRPC method {method_name}",
                    )
                )

            return APIService(
                name=service_name,
                version="1.0.0",
                description=f"gRPC service {service_name}",
                grpc_methods=grpc_methods,
            )

        except Exception as e:
            logger.error(f"Error parsing proto file {proto_file}: {e}")
            return None
