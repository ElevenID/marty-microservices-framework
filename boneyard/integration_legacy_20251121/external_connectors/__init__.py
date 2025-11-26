"""
External System Connectors Package

Modular external system integration components including enums, configuration,
base classes, specific connectors, transformation engine, and management.
"""

from .base import ExternalSystemConnector
from .config import (
    DataTransformation,
    ExternalSystemConfig,
    IntegrationRequest,
    IntegrationResponse,
)
from .connectors import (
    DatabaseConnector,
    ExternalSystemManager,
    FileSystemConnector,
    RESTAPIConnector,
    create_external_integration_platform,
)

# Import core components for easy access
from .enums import ConnectorType, DataFormat, IntegrationPattern, TransformationType
from .transformation import DataTransformationEngine

__all__ = [
    # Enums
    "ConnectorType",
    "DataFormat",
    "IntegrationPattern",
    "TransformationType",
    # Config
    "ExternalSystemConfig",
    "IntegrationRequest",
    "IntegrationResponse",
    "DataTransformation",
    # Base
    "ExternalSystemConnector",
    # Connectors
    "DatabaseConnector",
    "FileSystemConnector",
    "ExternalSystemManager",
    "RESTAPIConnector",
    "create_external_integration_platform",
    # Transformation
    "DataTransformationEngine",
]
