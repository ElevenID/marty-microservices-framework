"""
Authentication Factory

Factory for creating authentication components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mmf_new.core.security.ports.authentication import IAuthenticator
from mmf_new.framework.infrastructure.dependency_injection import register_instance
from mmf_new.framework.security.adapters.authentication.adapter import (
    IdentityServiceAuthenticator,
)
from mmf_new.services.identity.config import AuthenticationConfig
from mmf_new.services.identity.di_config import IdentityDIContainer


@dataclass
class RegistrationEntry:
    """Service registration entry."""

    interface: type
    instance: Any


class AuthenticationFactory:
    """Factory for authentication components."""

    @staticmethod
    def create_registrations() -> list[RegistrationEntry]:
        """Create authentication components and return registration entries."""
        entries = []

        # Initialize Identity Service via DI Container
        auth_config = AuthenticationConfig()
        container = IdentityDIContainer(auth_config)
        container.initialize()

        # Seed demo user
        container.seed_demo_user()

        # Get the authentication manager
        auth_manager = container.authentication_manager

        # Wrap it in our adapter
        authenticator = IdentityServiceAuthenticator(auth_manager)
        entries.append(RegistrationEntry(IAuthenticator, authenticator))

        return entries
