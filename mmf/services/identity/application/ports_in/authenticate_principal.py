from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mmf.services.identity.domain.models.security_principal import SecurityPrincipal


@dataclass(frozen=True)
class AuthenticatePrincipalCommand:
    principal_id: str
    session_id: str | None = None


@dataclass(frozen=True)
class AuthenticatePrincipalResult:
    principal: SecurityPrincipal


class AuthenticatePrincipalPort(Protocol):
    async def execute(
        self, command: AuthenticatePrincipalCommand
    ) -> AuthenticatePrincipalResult: ...
