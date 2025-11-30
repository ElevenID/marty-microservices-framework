"""
Authorization Factory

Factory for creating authorization components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mmf_new.core.security.ports.authorization import IAuthorizer
from mmf_new.framework.authorization.bootstrap import create_role_based_authorizer
from mmf_new.framework.security.adapters.authorization.adapter import (
    CoreAuthorizerAdapter,
)


@dataclass
class RegistrationEntry:
    """Service registration entry."""

    interface: type
    instance: Any


class AuthorizationFactory:
    """Factory for authorization components."""

    @staticmethod
    def create_registrations() -> list[RegistrationEntry]:
        """Create authorization components and return registration entries."""
        entries = []

        # Create a default authorizer (e.g., RBAC)
        core_authorizer = create_role_based_authorizer()
        authorizer = CoreAuthorizerAdapter(core_authorizer)
        entries.append(RegistrationEntry(IAuthorizer, authorizer))

        return entries
