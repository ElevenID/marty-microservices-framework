from __future__ import annotations

from dataclasses import dataclass

from mmf.services.identity.application.ports_in.authenticate_principal import (
    AuthenticatePrincipalCommand,
    AuthenticatePrincipalPort,
    AuthenticatePrincipalResult,
)
from mmf.services.identity.application.ports_out.principal_repository import (
    PrincipalRepository,
)


class UnknownPrincipalError(RuntimeError):
    """Raised when the requested principal cannot be found."""


@dataclass
class AuthenticatePrincipalUseCase(AuthenticatePrincipalPort):
    repository: PrincipalRepository

    async def execute(self, command: AuthenticatePrincipalCommand) -> AuthenticatePrincipalResult:
        principal = await self.repository.get_by_id(command.principal_id)
        if principal is None:
            raise UnknownPrincipalError(f"Principal '{command.principal_id}' was not found.")

        if command.session_id:
            principal = principal.with_session(command.session_id)

        return AuthenticatePrincipalResult(principal=principal)
