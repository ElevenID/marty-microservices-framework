"""Platform plugin API."""

from abc import ABC, abstractmethod


class PlatformPlugin(ABC):
    """Base class for platform plugins."""

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Unique plugin identifier."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""

    @abstractmethod
    def initialize(self, config: dict[str, any]) -> None:
        """Initialize the plugin with configuration."""

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the plugin."""
