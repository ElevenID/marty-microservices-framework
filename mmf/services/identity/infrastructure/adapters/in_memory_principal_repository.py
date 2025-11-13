from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from mmf.services.identity.application.ports_out.principal_repository import (
    PrincipalRepository,
)
from mmf.services.identity.domain.models.security_principal import SecurityPrincipal


@dataclass
class InMemoryPrincipalRepository(PrincipalRepository):
    principals: Mapping[str, SecurityPrincipal] = field(default_factory=dict)

    async def get_by_id(self, principal_id: str) -> SecurityPrincipal | None:
        return self.principals.get(principal_id)
