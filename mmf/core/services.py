"""
Core service definitions.

This module provides base classes for core framework services.
"""

from abc import ABC, abstractmethod
from typing import Any


class ObservabilityService(ABC):
    """
    Base class for observability services.
    """

    def __init__(self) -> None:
        self._initialized = False

    @abstractmethod
    def initialize(self, service_name: str, config: dict[str, Any] | None = None) -> None:
        """Initialize the observability service."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup resources."""
        pass

    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._initialized

    def _mark_initialized(self) -> None:
        """Mark service as initialized."""
        self._initialized = True


class ConfigService(ABC):
    """
    Base class for configuration services.
    """

    def __init__(self) -> None:
        self._loaded = False

    @abstractmethod
    def load(self) -> None:
        """Load configuration."""
        pass

    def is_loaded(self) -> bool:
        """Check if configuration is loaded."""
        return self._loaded

    def _mark_loaded(self) -> None:
        """Mark configuration as loaded."""
        self._loaded = True


class SecurityService(ABC):
    """
    Base class for security services.
    """

    @abstractmethod
    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize security service."""
        pass


class MessagingService(ABC):
    """
    Base class for messaging services.
    """

    @abstractmethod
    def connect(self) -> None:
        """Connect to messaging infrastructure."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from messaging infrastructure."""
        pass


class ManagerService(ABC):
    """
    Base class for manager services.
    """

    def __init__(self) -> None:
        self._initialized = False

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the manager."""
        pass

    def is_initialized(self) -> bool:
        """Check if the manager is initialized."""
        return self._initialized

    def _mark_initialized(self) -> None:
        """Mark manager as initialized."""
        self._initialized = True
