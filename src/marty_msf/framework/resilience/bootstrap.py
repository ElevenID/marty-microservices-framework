"""
Resilience Framework Bootstrap

Composition root and dependency injection setup for the resilience framework.
Following the level contract architecture pattern.
"""

from __future__ import annotations

import logging
from typing import Any

from .api import IResilienceManager, IResilienceService, ResilienceConfig
from .consolidated_manager import (
    ConsolidatedResilienceConfig,
    ConsolidatedResilienceManager,
)

logger = logging.getLogger(__name__)


class ResilienceBootstrap:
    """
    Bootstrap class for configuring and creating resilience components.

    This follows the same pattern as SecurityBootstrap - it's responsible for
    wiring together the resilience components based on configuration.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the resilience bootstrap."""
        self.config = config or {}

        # Cached components
        self._resilience_manager: IResilienceManager | None = None
        self._resilience_service: IResilienceService | None = None

    def get_resilience_manager(self) -> IResilienceManager:
        """Get or create the resilience manager."""
        if self._resilience_manager is None:
            self._resilience_manager = self._create_resilience_manager()
        return self._resilience_manager

    # Service creation removed to prevent circular dependencies
    # The service layer should directly create managers and not use bootstrap

    def initialize_resilience_system(self) -> IResilienceManager:
        """
        Initialize the resilience system and return manager.

        Returns:
            The resilience manager instance
        """
        manager = self.get_resilience_manager()
        return manager

    def _create_resilience_manager(self) -> IResilienceManager:
        """Create and configure the resilience manager."""
        manager_config = self.config.get("resilience_manager", {})
        manager_type = manager_config.get("type", "consolidated")

        if manager_type == "consolidated":
            return self._create_consolidated_manager(manager_config)
        else:
            logger.warning("Unknown resilience manager type %s, using consolidated", manager_type)
            return self._create_consolidated_manager(manager_config)

    def _create_consolidated_manager(self, config: dict[str, Any]) -> IResilienceManager:
        """Create the consolidated resilience manager."""
        # Lazy import to avoid circular dependencies

        # Create resilience configuration
        resilience_config = self._create_resilience_config(config)

        # Convert to consolidated config
        consolidated_config = ConsolidatedResilienceConfig(
            circuit_breaker_enabled=resilience_config.circuit_breaker_enabled,
            circuit_breaker_failure_threshold=resilience_config.circuit_breaker_failure_threshold,
            circuit_breaker_recovery_timeout=resilience_config.circuit_breaker_recovery_timeout,
            retry_enabled=resilience_config.retry_enabled,
            retry_max_attempts=resilience_config.retry_max_attempts,
            retry_base_delay=resilience_config.retry_delay,
            retry_exponential_base=resilience_config.retry_backoff_multiplier,
            timeout_enabled=resilience_config.timeout_enabled,
            timeout_seconds=resilience_config.timeout_duration,
            bulkhead_enabled=resilience_config.bulkhead_enabled,
            bulkhead_max_concurrent=resilience_config.bulkhead_max_concurrent,
        )

        return ConsolidatedResilienceManager(consolidated_config)

    # Service creation methods commented out to prevent circular dependencies
    # The service layer should create its own manager directly
    # def _create_resilience_service(self) -> IResilienceService:
    #     """Create and configure the resilience service."""
    #     service_config = self.config.get("resilience_service", {})
    #     service_type = service_config.get("type", "manager_service")
    #
    #     if service_type == "manager_service":
    #         return self._create_manager_service(service_config)
    #     else:
    #         logger.warning("Unknown resilience service type %s, using manager_service", service_type)
    #         return self._create_manager_service(service_config)
    #
    # def _create_manager_service(self, config: dict[str, Any]) -> IResilienceService:
    #     """Create the resilience manager service."""
    #     # Lazy import to avoid circular dependencies
    #     from .resilience_manager_service import ResilienceManagerService
    #
    #     return ResilienceManagerService(config)

    def _create_resilience_config(self, config: dict[str, Any]) -> ResilienceConfig:
        """Create resilience configuration from dict."""
        return ResilienceConfig(
            # Circuit breaker settings
            circuit_breaker_enabled=config.get("circuit_breaker_enabled", True),
            circuit_breaker_failure_threshold=config.get("circuit_breaker_failure_threshold", 5),
            circuit_breaker_recovery_timeout=config.get("circuit_breaker_recovery_timeout", 60.0),

            # Retry settings
            retry_enabled=config.get("retry_enabled", True),
            retry_max_attempts=config.get("retry_max_attempts", 3),
            retry_delay=config.get("retry_delay", 1.0),
            retry_backoff_multiplier=config.get("retry_backoff_multiplier", 2.0),
            retry_max_delay=config.get("retry_max_delay", 60.0),
            retry_jitter=config.get("retry_jitter", True),

            # Timeout settings
            timeout_enabled=config.get("timeout_enabled", True),
            timeout_duration=config.get("timeout_duration", 30.0),

            # Bulkhead settings
            bulkhead_enabled=config.get("bulkhead_enabled", False),
            bulkhead_max_concurrent=config.get("bulkhead_max_concurrent", 10),

            # Strategy
            strategy=config.get("strategy", "internal_service"),

            # Custom settings
            custom_settings=config.get("custom_settings", {})
        )


def create_default_resilience_system() -> IResilienceManager:
    """
    Create a default resilience system with standard configuration.

    Returns:
        The resilience manager instance
    """
    bootstrap = ResilienceBootstrap()
    return bootstrap.initialize_resilience_system()


def create_development_resilience_system() -> IResilienceManager:
    """
    Create a resilience system optimized for development.

    Returns:
        Tuple of (resilience_manager, resilience_service)
    """
    config = {
        "resilience_manager": {
            "type": "consolidated",
            "circuit_breaker_failure_threshold": 3,  # Lower threshold for dev
            "retry_max_attempts": 2,  # Fewer retries for faster feedback
            "timeout_duration": 10.0,  # Shorter timeout for dev
        },
        "resilience_service": {
            "type": "manager_service"
        }
    }

    bootstrap = ResilienceBootstrap(config)
    return bootstrap.initialize_resilience_system()


def create_production_resilience_system() -> IResilienceManager:
    """
    Create a resilience system optimized for production.

    Returns:
        The resilience manager instance
    """
    config = {
        "resilience_manager": {
            "type": "consolidated",
            "circuit_breaker_enabled": True,
            "circuit_breaker_failure_threshold": 5,
            "circuit_breaker_recovery_timeout": 60.0,
            "retry_enabled": True,
            "retry_max_attempts": 3,
            "retry_delay": 1.0,
            "retry_backoff_multiplier": 2.0,
            "retry_max_delay": 60.0,
            "retry_jitter": True,
            "timeout_enabled": True,
            "timeout_duration": 30.0,
            "bulkhead_enabled": True,
            "bulkhead_max_concurrent": 100,
        },
        "resilience_service": {
            "type": "manager_service"
        }
    }

    bootstrap = ResilienceBootstrap(config)
    return bootstrap.initialize_resilience_system()


def create_testing_resilience_system() -> IResilienceManager:
    """
    Create a resilience system optimized for testing.

    Returns:
        The resilience manager instance
    """
    config = {
        "resilience_manager": {
            "type": "consolidated",
            "circuit_breaker_enabled": False,  # Disabled for predictable tests
            "retry_enabled": False,  # Disabled for faster tests
            "timeout_enabled": False,  # Disabled to avoid timing issues
            "bulkhead_enabled": False,  # Disabled for simplicity
        },
        "resilience_service": {
            "type": "manager_service"
        }
    }

    bootstrap = ResilienceBootstrap(config)
    return bootstrap.initialize_resilience_system()
