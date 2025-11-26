"""Core security services initialization.

Handles bootstrapping and DI registration of fundamental security services
like authentication, authorization, secrets management, caching, and auditing.
"""

from __future__ import annotations

import logging
from typing import Any

from ..core.di_container import register_instance
from .api import (
    IAuditor,
    IAuthenticator,
    IAuthorizer,
    ICacheManager,
    ISecretManager,
    ISessionManager,
)
from .bootstrap import SecurityHardeningFramework

logger = logging.getLogger(__name__)


class CoreSecurityInitializer:
    """Handles initialization of core security services via bootstrap."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def initialize_core_services(self) -> None:
        """Initialize core security services via SecurityHardeningFramework."""
        service_name = self.config.get("service_name", "default_service")
        bootstrap = SecurityHardeningFramework(service_name, self.config)
        bootstrap.initialize_security()

        logger.info(
            "Core security services registered: %s",
            [
                ISecretManager.__name__,
                IAuthenticator.__name__,
                IAuthorizer.__name__,
                IAuditor.__name__,
                ICacheManager.__name__,
                ISessionManager.__name__,
            ],
        )
