from __future__ import annotations

from typing import Protocol

from mmf.services.identity.domain.models.security_principal import SecurityPrincipal


class PrincipalRepository(Protocol):
    async def get_by_id(self, principal_id: str) -> SecurityPrincipal | None:
        ...
