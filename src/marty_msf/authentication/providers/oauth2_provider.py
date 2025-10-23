"""OAuth2 Identity Provider Implementation (Stub)"""

from typing import Any, Optional

from ..api import IdentityProviderType, IIdentityProvider, SecurityPrincipal


class OAuth2Provider(IIdentityProvider):
    """OAuth2 identity provider implementation"""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def authenticate(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """Authenticate user with OAuth2 provider."""
        # TODO: Implement OAuth2 authentication
        return None

    def get_provider_type(self) -> IdentityProviderType:
        """Get the provider type."""
        return IdentityProviderType.OAUTH2
