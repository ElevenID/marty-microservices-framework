"""
Ports for API documentation generators.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from mmf_new.framework.documentation.domain.models import (
    APIService,
    DocumentationConfig,
)


class APIDocumentationGenerator(ABC):
    """Abstract base class for API documentation generators."""

    def __init__(self, config: DocumentationConfig):
        self.config = config
        self.template_env = self._setup_templates()

    def _setup_templates(self) -> Environment:
        """Setup Jinja2 template environment."""
        template_dir = self.config.template_dir or Path(__file__).parent.parent / "templates"
        return Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)

    @abstractmethod
    async def generate_documentation(self, service: APIService) -> dict[str, Path]:
        """Generate documentation for the service."""
        pass

    @abstractmethod
    async def discover_apis(self, source_path: Path) -> list[APIService]:
        """Discover APIs from source code."""
        pass
