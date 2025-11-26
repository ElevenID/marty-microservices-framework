"""
Default Service Implementations for Platform Layer.

This module provides concrete implementations of the platform service
protocols that can be registered with the dependency injection container.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from mmf_new.core.platform.base_services import BaseService, ServiceWithDependencies
from mmf_new.core.platform.contracts import (
    IConfigurationService,
    IMessagingService,
    IObservabilityService,
    ISecurityService,
)
from .utilities import Registry
from mmf_new.framework.infrastructure.dependency_injection import DIContainer
from mmf_new.core.security.domain.config import ThreatDetectionConfig
from mmf_new.framework.security.adapters.threat_detection.event_processor import EventProcessorThreatDetector
from mmf_new.framework.security.adapters.threat_detection.pattern_detector import PatternBasedThreatDetector
from mmf_new.framework.security.adapters.threat_detection.scanner import VulnerabilityScanner
from mmf_new.framework.security.adapters.threat_detection.ml_analyzer import MLThreatDetector

logger = logging.getLogger(__name__)


class ServiceRegistry(Registry):
    """Default implementation of IServiceRegistry using Registry utility."""


class ConfigurationService(BaseService, IConfigurationService):
    """Default configuration service implementation."""

    def __init__(self, container: DIContainer, config: dict[str, Any] | None = None):
        super().__init__(container, config)
        self._config_data: dict[str, Any] = {}
        self._is_loaded = False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config_data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._config_data[key] = value

    def has(self, key: str) -> bool:
        """Check if a configuration key exists."""
        return key in self._config_data

    def reload(self) -> None:
        """Reload configuration from source."""
        # Default implementation - can be overridden
        logger.info("Configuration reload requested")

    def is_loaded(self) -> bool:
        """Check if configuration is loaded."""
        return self._is_loaded

    def load_from_env(self, prefix: str = "") -> None:
        """Load configuration from environment variables."""
        import os

        for key, value in os.environ.items():
            if prefix and key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                self._config_data[config_key] = value
            elif not prefix:
                self._config_data[key.lower()] = value

        self._is_loaded = True
        logger.info("Configuration loaded from environment")

    def load_from_file(self, config_path: str | Path) -> None:
        """Load configuration from file."""
        import json
        import yaml

        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with path.open(encoding='utf-8') as f:
            if path.suffix.lower() in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)

        self._config_data.update(data)
        self._is_loaded = True
        logger.info("Configuration loaded from file: %s", config_path)

    async def _on_initialize(self) -> None:
        """Initialize the configuration service."""
        # Load from config if specified
        if 'config_file' in self._config:
            self.load_from_file(self._config['config_file'])
        elif self._config.get('load_from_env', False):
            self.load_from_env(self._config.get('env_prefix', ''))

        logger.info("ConfigurationService initialized")

    async def _on_shutdown(self) -> None:
        """Shutdown the configuration service."""
        logger.info("ConfigurationService shutdown")


class ObservabilityService(BaseService, IObservabilityService):
    """Default observability service implementation."""

    def __init__(self, container: DIContainer, config: dict[str, Any] | None = None):
        super().__init__(container, config)
        self._service_name = config.get('service_name', 'unknown') if config else 'unknown'

    def log(self, level: str, message: str, **kwargs: Any) -> None:
        """Log a message."""
        log_level = getattr(logging, level.upper(), logging.INFO)
        logger.log(log_level, message, extra=kwargs)

    def metric(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Record a metric."""
        # Default implementation - logs metric
        tag_str = f" tags={tags}" if tags else ""
        logger.info("METRIC: %s=%s%s", name, value, tag_str)

    def trace(self, operation: str) -> Any:
        """Start a trace for an operation."""
        # Default implementation - returns a context manager that logs
        from contextlib import contextmanager

        @contextmanager
        def trace_context():
            logger.debug("TRACE START: %s", operation)
            try:
                yield
            finally:
                logger.debug("TRACE END: %s", operation)

        return trace_context()

    def is_enabled(self) -> bool:
        """Check if observability is enabled."""
        return self._config.get('enabled', True)

    async def _on_initialize(self) -> None:
        """Initialize the observability service."""
        logger.info("ObservabilityService initialized for service: %s", self._service_name)

    async def _on_shutdown(self) -> None:
        """Shutdown the observability service."""
        logger.info("ObservabilityService shutdown")


class SecurityService(BaseService, ISecurityService):
    """Default security service implementation."""

    def __init__(self, container: DIContainer, config: dict[str, Any] | None = None):
        super().__init__(container, config)
        self._configured = False

        # Threat Detection Adapters
        self.threat_config = ThreatDetectionConfig()
        self.event_processor = EventProcessorThreatDetector(self.threat_config)
        self.pattern_detector = PatternBasedThreatDetector("default-service")
        self.scanner = VulnerabilityScanner("default-service")
        self.ml_detector = MLThreatDetector(self.threat_config)

    def authenticate(self, credentials: dict[str, Any]) -> bool:
        """Authenticate with credentials."""
        # Default implementation - always returns True (unsafe, override in production)
        username = credentials.get('username')
        password = credentials.get('password')

        if not username or not password:
            return False

        # In real implementation, check against user store
        logger.warning("Using default security service - authentication always succeeds!")
        return True

    def authorize(self, user: str, resource: str, action: str) -> bool:
        """Authorize user action on resource."""
        # Default implementation - always returns True (unsafe, override in production)
        logger.warning("Using default security service - authorization always succeeds!")
        return True

    def encrypt(self, data: str) -> str:
        """Encrypt data."""
        # Default implementation - base64 encoding (not secure, override in production)
        import base64
        logger.warning("Using default security service - using base64 encoding (not secure)!")
        return base64.b64encode(data.encode()).decode()

    def decrypt(self, data: str) -> str:
        """Decrypt data."""
        # Default implementation - base64 decoding
        import base64
        return base64.b64decode(data.encode()).decode()

    def is_secure(self) -> bool:
        """Check if security is enabled."""
        return self._configured

    async def analyze_event(self, event: Any) -> Any:
        """Analyze a security event for threats."""
        # Use pattern detector for immediate analysis
        result = await self.pattern_detector.analyze_event(event)

        # Also queue for event processor (async)
        # await self.event_processor.analyze_event(event)

        return result

    def scan_code(self, code: str, file_path: str = "") -> list[Any]:
        """Scan code for vulnerabilities."""
        return self.scanner.scan_code(code, file_path)

    async def _on_initialize(self) -> None:
        """Initialize the security service."""
        self._configured = True
        logger.warning("SecurityService initialized with default (insecure) implementation!")

    async def _on_shutdown(self) -> None:
        """Shutdown the security service."""
        self._configured = False
        logger.info("SecurityService shutdown")


class MessagingService(ServiceWithDependencies, IMessagingService):
    """Default messaging service implementation."""

    def __init__(self, container: DIContainer, config: dict[str, Any] | None = None):
        super().__init__(container, config)
        self._connected = False
        self._subscriptions: dict[str, list[Any]] = {}

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        """Publish a message to a topic."""
        if not self._connected:
            logger.warning("MessagingService not connected, message not published")
            return

        # Default implementation - logs and notifies local subscribers
        logger.info("PUBLISH to %s: %s", topic, message)

        # Notify local subscribers
        if topic in self._subscriptions:
            for handler in self._subscriptions[topic]:
                try:
                    if hasattr(handler, '__call__'):
                        if hasattr(handler, '__await__'):
                            await handler(message)
                        else:
                            handler(message)
                except (TypeError, AttributeError, RuntimeError) as e:
                    logger.error("Error in message handler for topic %s: %s", topic, e)

    async def subscribe(self, topic: str, handler: Any) -> None:
        """Subscribe to a topic with a handler."""
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []

        self._subscriptions[topic].append(handler)
        logger.info("Subscribed to topic: %s", topic)

    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        if topic in self._subscriptions:
            del self._subscriptions[topic]
            logger.info("Unsubscribed from topic: %s", topic)

    def is_connected(self) -> bool:
        """Check if messaging is connected."""
        return self._connected

    async def _on_initialize(self) -> None:
        """Initialize the messaging service."""
        # Resolve dependencies first
        await super()._on_initialize()

        self._connected = True
        logger.info("MessagingService initialized (in-memory implementation)")

    async def _on_shutdown(self) -> None:
        """Shutdown the messaging service."""
        self._connected = False
        self._subscriptions.clear()
        logger.info("MessagingService shutdown")
