from __future__ import annotations

import pytest
from mmf.services.identity.application.ports_in.authenticate_principal import (
    AuthenticatePrincipalCommand,
)
from mmf.services.identity.application.usecases.authenticate_principal import (
    AuthenticatePrincipalUseCase,
    UnknownPrincipalError,
)
from mmf.services.identity.domain.models.security_principal import SecurityPrincipal


class StubPrincipalRepository:
    def __init__(self, principals: dict[str, SecurityPrincipal]):
        self._principals = principals

    async def get_by_id(self, principal_id: str) -> SecurityPrincipal | None:
        return self._principals.get(principal_id)


@pytest.mark.asyncio
async def test_usecase_returns_principal_when_found():
    principal = SecurityPrincipal.create(
        principal_id="user-123",
        principal_type="user",
        identity_provider="local",
    )
    repository = StubPrincipalRepository({"user-123": principal})
    usecase = AuthenticatePrincipalUseCase(repository=repository)

    command = AuthenticatePrincipalCommand(principal_id="user-123")
    result = await usecase.execute(command)

    assert result.principal == principal


@pytest.mark.asyncio
async def test_usecase_raises_for_missing_principal():
    repository = StubPrincipalRepository({})
    usecase = AuthenticatePrincipalUseCase(repository=repository)
    command = AuthenticatePrincipalCommand(principal_id="missing")

    with pytest.raises(UnknownPrincipalError):
        await usecase.execute(command)
