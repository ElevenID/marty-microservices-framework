"""
Application logic for API documentation management.
"""

import argparse
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from mmf_new.framework.documentation.adapters.unified import (
    UnifiedAPIDocumentationGenerator,
)
from mmf_new.framework.documentation.domain.models import (
    APIService,
    DocumentationConfig,
)

logger = logging.getLogger(__name__)


class APIVersionManager:
    """Manages API versions and deprecation policies."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.versions_file = base_path / "api_versions.yaml"

    async def register_version(
        self,
        service_name: str,
        version: str,
        deprecation_date: str | None = None,
        migration_guide: str | None = None,
    ) -> bool:
        """Register a new API version."""
        versions = await self._load_versions()

        if service_name not in versions:
            versions[service_name] = {}

        versions[service_name][version] = {
            "created_date": datetime.utcnow().isoformat(),
            "deprecation_date": deprecation_date,
            "migration_guide": migration_guide,
            "status": "active",
        }

        return await self._save_versions(versions)

    async def deprecate_version(
        self, service_name: str, version: str, deprecation_date: str, migration_guide: str
    ) -> bool:
        """Mark a version as deprecated."""
        versions = await self._load_versions()

        if service_name in versions and version in versions[service_name]:
            versions[service_name][version].update(
                {
                    "status": "deprecated",
                    "deprecation_date": deprecation_date,
                    "migration_guide": migration_guide,
                }
            )
            return await self._save_versions(versions)

        return False

    async def get_active_versions(self, service_name: str) -> list[str]:
        """Get all active versions for a service."""
        versions = await self._load_versions()

        if service_name not in versions:
            return []

        return [
            version
            for version, info in versions[service_name].items()
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
                deprecated.append(
                    {
                        "version": version,
                        "deprecation_date": info.get("deprecation_date"),
                        "migration_guide": info.get("migration_guide"),
                    }
                )

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
            with open(self.versions_file, "w") as f:
                yaml.dump(versions, f, default_flow_style=False)
            return True
        except Exception as e:
            logger.error(f"Error saving versions file: {e}")
            return False


class APIDocumentationManager:
    """Main manager for API documentation generation and management."""

    def __init__(self, base_path: Path, config: DocumentationConfig | None = None):
        self.base_path = base_path
        self.config = config or DocumentationConfig(output_dir=base_path / "docs" / "api")
        self.generator = UnifiedAPIDocumentationGenerator(self.config)
        self.version_manager = APIVersionManager(base_path)

    async def generate_all_documentation(
        self, source_paths: list[Path]
    ) -> dict[str, dict[str, Path]]:
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

        html_content = template.render(services=services, timestamp=datetime.utcnow().isoformat())

        index_file = self.config.output_dir / "index.html"
        with open(index_file, "w") as f:
            f.write(html_content)


async def generate_api_docs(
    source_paths: list[str], output_dir: str, config_file: str | None = None
) -> None:
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
