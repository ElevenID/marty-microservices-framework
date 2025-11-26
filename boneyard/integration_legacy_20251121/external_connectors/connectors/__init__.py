"""
Specific Connector Implementations

Individual connector classes for different external system types.
"""

from .database import DatabaseConnector
from .filesystem import FileSystemConnector
from .manager import ExternalSystemManager, create_external_integration_platform
from .rest_api import RESTAPIConnector

__all__ = [
    "DatabaseConnector",
    "FileSystemConnector",
    "ExternalSystemManager",
    "RESTAPIConnector",
    "create_external_integration_platform",
]
