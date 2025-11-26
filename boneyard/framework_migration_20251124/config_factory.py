"""
Modern Configuration Factory for Marty Microservices Framework.

This module provides a simplified configuration factory that creates
properly structured ServiceConfig instances for modern Marty services.
"""

from pathlib import Path
from typing import Any

from .config import BaseServiceConfig, Environment


def create_service_config(
    service_name: str,
    environment: str | Environment = Environment.DEVELOPMENT,
    config_path: Path | str | None = None,
) -> BaseServiceConfig:
    """
    Create a modern BaseServiceConfig instance.

    Args:
        service_name: Name of the service
        environment: Environment name or Environment enum
        config_path: Path to configuration directory

    Returns:
        BaseServiceConfig instance
    """
    if config_path is None:
        config_path = Path("config")
    else:
        config_path = Path(config_path)

    # Convert string environment to Environment enum
    if isinstance(environment, str):
        environment = Environment(environment)

    return BaseServiceConfig(
        service_name=service_name,
        environment=environment,
        config_path=config_path,
    )


def validate_config_structure(config_path: Path) -> dict[str, Any]:
    """
    Validate that configuration files have the expected modern structure.

    Returns:
        Dictionary with validation results
    """
    results = {"valid": True, "errors": [], "warnings": [], "files_found": []}

    # Check for expected config files
    expected_files = ["base.yaml", "development.yaml", "testing.yaml", "production.yaml"]

    for filename in expected_files:
        file_path = config_path / filename
        if file_path.exists():
            results["files_found"].append(filename)
        elif filename == "base.yaml":
            results["errors"].append(f"Missing required base configuration: {filename}")
            results["valid"] = False

    return results
