"""
Graceful degradation patterns for resilience.

Ported from Marty's resilience framework to provide graceful degradation
capabilities for microservices.
"""

import logging
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DegradationLevel(str, Enum):
    """Levels of service degradation."""

    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class FallbackProvider:
    """Base class for fallback providers."""

    def get_fallback_value(self, context: dict[str, Any]) -> Any:
        """Get fallback value for given context."""
        return None


class DefaultValueProvider(FallbackProvider):
    """Provides default values as fallback."""

    def __init__(self, default_value: Any):
        self.default_value = default_value

    def get_fallback_value(self, context: dict[str, Any]) -> Any:  # noqa: ARG002
        """Return the default value."""
        return self.default_value


class CachedValueProvider(FallbackProvider):
    """Provides cached values as fallback."""

    def __init__(self):
        self.cache: dict[str, Any] = {}

    def cache_value(self, key: str, value: Any) -> None:
        """Cache a value for fallback use."""
        self.cache[key] = value

    def get_fallback_value(self, context: dict[str, Any]) -> Any:
        """Return cached value based on context."""
        key = context.get("cache_key", "default")
        return self.cache.get(key)


class ServiceFallbackProvider(FallbackProvider):
    """Provides service-level fallback behavior."""

    def __init__(self, service_name: str, fallback_func: Callable[..., Any]):
        self.service_name = service_name
        self.fallback_func = fallback_func

    def get_fallback_value(self, context: dict[str, Any]) -> Any:
        """Execute fallback function."""
        return self.fallback_func(context)


class FeatureToggle:
    """Feature toggle for graceful degradation."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled

    def is_enabled(self) -> bool:
        """Check if feature is enabled."""
        return self.enabled

    def enable(self) -> None:
        """Enable the feature."""
        self.enabled = True

    def disable(self) -> None:
        """Disable the feature."""
        self.enabled = False


class GracefulDegradationManager:
    """Manager for graceful degradation strategies."""

    def __init__(self):
        self.degradation_level = DegradationLevel.NONE
        self.fallback_providers: dict[str, FallbackProvider] = {}
        self.feature_toggles: dict[str, FeatureToggle] = {}

    def set_degradation_level(self, level: DegradationLevel) -> None:
        """Set current degradation level."""
        logger.info("Degradation level changed to %s", level.value)
        self.degradation_level = level

    def add_fallback_provider(self, name: str, provider: FallbackProvider) -> None:
        """Add a fallback provider."""
        self.fallback_providers[name] = provider

    def get_fallback_value(self, provider_name: str, context: dict[str, Any]) -> Any:
        """Get fallback value from specified provider."""
        provider = self.fallback_providers.get(provider_name)
        if provider:
            return provider.get_fallback_value(context)
        return None

    def add_feature_toggle(self, name: str, toggle: FeatureToggle) -> None:
        """Add a feature toggle."""
        self.feature_toggles[name] = toggle

    def is_feature_enabled(self, name: str) -> bool:
        """Check if a feature is enabled."""
        toggle = self.feature_toggles.get(name)
        return toggle.is_enabled() if toggle else True


class HealthBasedDegradationMonitor:
    """Monitor system health and adjust degradation accordingly."""

    def __init__(self, manager: GracefulDegradationManager):
        self.manager = manager
        self.health_thresholds = {
            DegradationLevel.MINOR: 0.8,
            DegradationLevel.MODERATE: 0.6,
            DegradationLevel.SEVERE: 0.4,
            DegradationLevel.CRITICAL: 0.2,
        }

    def update_health_status(self, health_score: float) -> None:
        """Update degradation level based on health score."""
        if health_score >= 0.8:
            self.manager.set_degradation_level(DegradationLevel.NONE)
        elif health_score >= 0.6:
            self.manager.set_degradation_level(DegradationLevel.MINOR)
        elif health_score >= 0.4:
            self.manager.set_degradation_level(DegradationLevel.MODERATE)
        elif health_score >= 0.2:
            self.manager.set_degradation_level(DegradationLevel.SEVERE)
        else:
            self.manager.set_degradation_level(DegradationLevel.CRITICAL)
