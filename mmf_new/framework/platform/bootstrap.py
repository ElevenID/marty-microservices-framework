"""
Bootstrap Functions for Platform Layer.

This module provides factory functions for creating and initializing
platform services in the correct order with proper dependency injection.
"""

from __future__ import annotations

import logging
from typing import Any

from mmf_new.framework.infrastructure.dependency_injection import (
    DIContainer,
    get_container,
    register_instance,
)

from .implementations import (
    ConfigurationService,
    MessagingService,
    ObservabilityService,
    SecurityService,
    ServiceRegistry,
)
from .utilities import AtomicCounter

logger = logging.getLogger(__name__)


def create_service_registry(
    container: DIContainer | None = None, config: dict[str, Any] | None = None
) -> ServiceRegistry:
    """Create and register a service registry."""
    if container is None:
        container = get_container()

    registry = ServiceRegistry(container, config)
    register_instance(ServiceRegistry, registry)
    logger.info("Created and registered ServiceRegistry")
    return registry


def create_configuration_service(
    container: DIContainer | None = None, config: dict[str, Any] | None = None
) -> ConfigurationService:
    """Create and register a configuration service."""
    if container is None:
        container = get_container()

    service = ConfigurationService(container, config)
    register_instance(ConfigurationService, service)
    logger.info("Created and registered ConfigurationService")
    return service


def create_observability_service(
    container: DIContainer | None = None, config: dict[str, Any] | None = None
) -> ObservabilityService:
    """Create and register an observability service."""
    if container is None:
        container = get_container()

    service = ObservabilityService(container, config)
    register_instance(ObservabilityService, service)
    logger.info("Created and registered ObservabilityService")
    return service


def create_security_service(
    container: DIContainer | None = None, config: dict[str, Any] | None = None
) -> SecurityService:
    """Create and register a security service."""
    if container is None:
        container = get_container()

    service = SecurityService(container, config)
    register_instance(SecurityService, service)
    logger.info("Created and registered SecurityService")
    return service


def create_messaging_service(
    container: DIContainer | None = None, config: dict[str, Any] | None = None
) -> MessagingService:
    """Create and register a messaging service."""
    if container is None:
        container = get_container()

    service = MessagingService(container, config)
    register_instance(MessagingService, service)
    logger.info("Created and registered MessagingService")
    return service


def create_atomic_counter(
    container: DIContainer | None = None,
    initial_value: int = 0,
    config: dict[str, Any] | None = None,
) -> AtomicCounter:
    """Create and register an atomic counter."""
    if container is None:
        container = get_container()

    counter = AtomicCounter(container, initial_value, config)
    register_instance(AtomicCounter, counter)
    logger.info("Created and registered AtomicCounter with initial value %d", initial_value)
    return counter


async def initialize_platform_services(
    config: dict[str, Any] | None = None, container: DIContainer | None = None
) -> dict[str, Any]:
    """
    Initialize all platform services in the correct order.

    Order of initialization:
    1. Configuration service (needed by others)
    2. Observability service (for logging/metrics)
    3. Security service (for authentication/authorization)
    4. Service registry (for service discovery)
    5. Messaging service (depends on all others)
    6. Utilities (atomic counter, etc.)

    Args:
        config: Configuration for services
        container: DI container to use (uses global if None)

    Returns:
        Dictionary with initialized service instances

    Raises:
        RuntimeError: If initialization fails
    """
    if container is None:
        container = get_container()

    if config is None:
        config = {}

    logger.info("Starting platform services initialization")
    services = {}

    try:
        # Step 1: Configuration service (first, as others may need config)
        config_service_config = config.get("configuration", {})
        config_service = create_configuration_service(container, config_service_config)
        await config_service.initialize()
        services["configuration"] = config_service

        # Step 2: Observability service (for logging/metrics throughout initialization)
        observability_config = config.get("observability", {})
        observability_service = create_observability_service(container, observability_config)
        await observability_service.initialize()
        services["observability"] = observability_service

        # Step 3: Security service (needed for secure operations)
        security_config = config.get("security", {})
        security_service = create_security_service(container, security_config)
        await security_service.initialize()
        services["security"] = security_service

        # Step 4: Service registry (for service discovery)
        registry_config = config.get("registry", {})
        registry = create_service_registry(container, registry_config)
        await registry.initialize()
        services["registry"] = registry

        # Step 5: Messaging service (may depend on other services)
        messaging_config = config.get("messaging", {})
        messaging_service = create_messaging_service(container, messaging_config)
        await messaging_service.initialize()
        services["messaging"] = messaging_service

        # Step 6: Utilities
        counter_config = config.get("counter", {})
        initial_value = counter_config.get("initial_value", 0)
        counter = create_atomic_counter(container, initial_value, counter_config)
        await counter.initialize()
        services["counter"] = counter

        logger.info("Platform services initialization completed successfully")
        return services

    except Exception as e:
        logger.error("Platform services initialization failed: %s", e)

        # Attempt to shutdown any services that were initialized
        for service_name, service in services.items():
            try:
                if hasattr(service, "shutdown"):
                    await service.shutdown()
                    logger.info("Shutdown service: %s", service_name)
            except (RuntimeError, AttributeError, OSError) as shutdown_error:
                logger.error("Error shutting down service %s: %s", service_name, shutdown_error)

        raise RuntimeError(f"Platform services initialization failed: {e}") from e


async def shutdown_platform_services(services: dict[str, Any] | None = None) -> None:
    """
    Shutdown platform services in reverse order.

    Args:
        services: Dictionary of services to shutdown (if None, gets from DI container)
    """
    logger.info("Starting platform services shutdown")

    if services is None:
        # Get services from DI container
        container = get_container()
        try:
            services = {
                "counter": container.get(AtomicCounter, None),
                "messaging": container.get(MessagingService, None),
                "registry": container.get(ServiceRegistry, None),
                "security": container.get(SecurityService, None),
                "observability": container.get(ObservabilityService, None),
                "configuration": container.get(ConfigurationService, None),
            }
            # Remove None values
            services = {k: v for k, v in services.items() if v is not None}
        except (AttributeError, KeyError, RuntimeError) as e:
            logger.error("Error retrieving services from container: %s", e)
            return

    # Shutdown in reverse order
    shutdown_order = [
        "counter",
        "messaging",
        "registry",
        "security",
        "observability",
        "configuration",
    ]

    for service_name in shutdown_order:
        if service_name in services:
            service = services[service_name]
            try:
                if hasattr(service, "shutdown"):
                    await service.shutdown()
                    logger.info("Shutdown service: %s", service_name)
            except (RuntimeError, AttributeError, OSError) as e:
                logger.error("Error shutting down service %s: %s", service_name, e)

    logger.info("Platform services shutdown completed")
