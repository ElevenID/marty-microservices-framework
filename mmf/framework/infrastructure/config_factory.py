"""
Configuration Factory for MMF New.

This module provides a factory for creating configuration managers,
bridging the gap between the old framework and the new hexagonal architecture.
"""

from pathlib import Path
from typing import TypeVar

from pydantic_settings import BaseSettings

from .config_manager import Environment
from .unified_config import UnifiedConfigurationManager, create_unified_config_manager

T = TypeVar("T", bound=BaseSettings)


def create_service_config(
    service_name: str,
    environment: str | Environment = Environment.DEVELOPMENT,
    config_path: Path | str | None = None,
    config_class: type[T] = BaseSettings,
) -> UnifiedConfigurationManager[T]:
    """
    Create a UnifiedConfigurationManager for a service.

    Args:
        service_name: Name of the service
        environment: Environment name or Environment enum
        config_path: Path to configuration directory
        config_class: Configuration class (Pydantic BaseSettings)

    Returns:
        UnifiedConfigurationManager instance
    """
    if config_path is None:
        config_path = Path("config")
    else:
        config_path = Path(config_path)

    # Convert string environment to Environment enum
    if isinstance(environment, str):
        try:
            environment = Environment(environment)
        except ValueError:
            # Default to development if invalid environment string provided
            environment = Environment.DEVELOPMENT

    return create_unified_config_manager(
        service_name=service_name,
        environment=environment,
        config_dir=str(config_path),
        config_class=config_class,
    )
