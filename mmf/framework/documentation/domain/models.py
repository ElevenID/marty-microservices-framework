"""
Domain models for API documentation.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
