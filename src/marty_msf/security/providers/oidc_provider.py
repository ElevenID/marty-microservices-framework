"""
OIDC (OpenID Connect) Identity Provider Implementation

Provides integration with OIDC-compliant identity providers like:
- Auth0
- Azure AD
- Google Identity
- Keycloak
- AWS Cognito
- Okta
"""

import base64
import hashlib
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional, Union
from urllib.parse import urlencode

import aiohttp
import jwt

from ..interfaces import IdentityProvider, SecurityPrincipal

logger = logging.getLogger(__name__)


class OIDCProvider(IdentityProvider):
    """OpenID Connect identity provider implementation"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.issuer_url = config["issuer_url"]
        self.redirect_uri = config.get("redirect_uri")

        # OIDC endpoints (will be discovered)
        self.authorization_endpoint = None
        self.token_endpoint = None
        self.userinfo_endpoint = None
        self.jwks_uri = None

        # Cached JWKS for token validation
        self.jwks_cache = {}
        self.jwks_cache_expiry = 0

        # Session management
        self.state_store = {}  # In production, use Redis or database

    async def initialize(self) -> bool:
        """Initialize OIDC provider by discovering endpoints"""
        try:
            # Discover OIDC configuration
            discovery_url = f"{self.issuer_url.rstrip('/')}/.well-known/openid-configuration"

            async with aiohttp.ClientSession() as session:
                async with session.get(discovery_url) as response:
                    if response.status == 200:
                        oidc_config = await response.json()

                        self.authorization_endpoint = oidc_config["authorization_endpoint"]
                        self.token_endpoint = oidc_config["token_endpoint"]
                        self.userinfo_endpoint = oidc_config["userinfo_endpoint"]
                        self.jwks_uri = oidc_config["jwks_uri"]

                        logger.info(f"OIDC provider initialized for issuer: {self.issuer_url}")
                        return True
                    else:
                        logger.error(f"Failed to discover OIDC configuration: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"OIDC initialization error: {e}")
            return False

    async def authenticate(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """
        Authenticate user with OIDC provider

        Supports multiple authentication flows:
        1. Authorization code flow (credentials contain authorization_code)
        2. Password flow (credentials contain username/password) - if supported
        3. Client credentials flow (for service-to-service)
        """
        try:
            if "authorization_code" in credentials:
                return await self._handle_authorization_code_flow(credentials)
            elif "username" in credentials and "password" in credentials:
                return await self._handle_password_flow(credentials)
            elif "client_id" in credentials and "client_secret" in credentials:
                return await self._handle_client_credentials_flow(credentials)
            else:
                logger.error("Unsupported OIDC authentication credentials")
                return None

        except Exception as e:
            logger.error(f"OIDC authentication error: {e}")
            return None

    async def validate_token(self, token: str) -> SecurityPrincipal | None:
        """Validate JWT token from OIDC provider"""
        try:
            # Get JWKS for token validation
            jwks = await self._get_jwks()
            if not jwks:
                logger.error("Could not fetch JWKS for token validation")
                return None

            # Decode and validate JWT
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            if kid not in jwks:
                logger.error(f"Token kid {kid} not found in JWKS")
                return None

            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwks[kid])

            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=self.issuer_url,
                audience=self.client_id
            )

            # Create security principal from token claims
            principal = SecurityPrincipal(
                id=payload["sub"],
                type="user",
                attributes={
                    "email": payload.get("email"),
                    "name": payload.get("name"),
                    "preferred_username": payload.get("preferred_username"),
                    "groups": payload.get("groups", []),
                    "roles": payload.get("roles", []),
                    "token_type": "oidc_jwt"
                },
                identity_provider="oidc",
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            )

            # Map OIDC roles/groups to framework roles
            await self._map_oidc_roles_to_framework_roles(principal)

            return principal

        except jwt.ExpiredSignatureError:
            logger.warning("OIDC token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid OIDC token: {e}")
            return None
        except Exception as e:
            logger.error(f"OIDC token validation error: {e}")
            return None

    async def refresh_token(self, refresh_token: str) -> str | None:
        """Refresh access token using refresh token"""
        try:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_endpoint,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                ) as response:
                    if response.status == 200:
                        token_response = await response.json()
                        return token_response["access_token"]
                    else:
                        logger.error(f"Token refresh failed: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None

    async def get_user_attributes(self, principal_id: str) -> dict[str, Any]:
        """Get additional user attributes from OIDC userinfo endpoint"""
        try:
            # This would typically require an access token
            # For now, return cached attributes
            return {}

        except Exception as e:
            logger.error(f"Error fetching user attributes: {e}")
            return {}

    def get_authorization_url(self, state: str | None = None) -> str:
        """Generate authorization URL for OIDC flow"""
        if not state:
            state = secrets.token_urlsafe(32)

        # Store state for validation
        self.state_store[state] = {
            "created_at": time.time(),
            "expires_at": time.time() + 600  # 10 minutes
        }

        # Generate PKCE challenge (recommended for security)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')

        # Store code verifier for later use
        self.state_store[state]["code_verifier"] = code_verifier

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "openid profile email",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }

        return f"{self.authorization_endpoint}?{urlencode(params)}"

    # Private methods

    async def _handle_authorization_code_flow(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """Handle OIDC authorization code flow"""
        authorization_code = credentials["authorization_code"]
        state = credentials.get("state")

        # Validate state
        if state and state in self.state_store:
            state_data = self.state_store[state]
            if time.time() > state_data["expires_at"]:
                logger.error("OIDC state has expired")
                return None
            code_verifier = state_data.get("code_verifier")
        else:
            logger.error("Invalid or missing OIDC state")
            return None

        # Exchange authorization code for tokens
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        if code_verifier:
            data["code_verifier"] = code_verifier

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status == 200:
                    token_response = await response.json()
                    access_token = token_response["access_token"]

                    # Validate access token and create principal
                    return await self.validate_token(access_token)
                else:
                    logger.error(f"Token exchange failed: {response.status}")
                    return None

    async def _handle_password_flow(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """Handle OIDC password flow (Resource Owner Password Credentials)"""
        username = credentials["username"]
        password = credentials["password"]

        data = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "openid profile email"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status == 200:
                    token_response = await response.json()
                    access_token = token_response["access_token"]

                    # Validate access token and create principal
                    return await self.validate_token(access_token)
                else:
                    logger.error(f"Password flow authentication failed: {response.status}")
                    return None

    async def _handle_client_credentials_flow(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """Handle OIDC client credentials flow (for service-to-service authentication)"""
        client_id = credentials["client_id"]
        client_secret = credentials["client_secret"]

        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": credentials.get("scope", "")
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status == 200:
                    token_response = await response.json()
                    token_response["access_token"]

                    # For client credentials, create service principal
                    principal = SecurityPrincipal(
                        id=client_id,
                        type="service",
                        attributes={
                            "client_id": client_id,
                            "token_type": "oidc_client_credentials"
                        },
                        identity_provider="oidc"
                    )

                    return principal
                else:
                    logger.error(f"Client credentials flow failed: {response.status}")
                    return None

    async def _get_jwks(self) -> dict[str, Any]:
        """Get JWKS (JSON Web Key Set) for token validation"""
        try:
            # Check cache first
            if time.time() < self.jwks_cache_expiry and self.jwks_cache:
                return self.jwks_cache

            # Fetch JWKS from provider
            async with aiohttp.ClientSession() as session:
                async with session.get(self.jwks_uri) as response:
                    if response.status == 200:
                        jwks_response = await response.json()

                        # Convert JWKS to kid -> key mapping
                        jwks = {}
                        for key in jwks_response["keys"]:
                            jwks[key["kid"]] = key

                        # Cache for 1 hour
                        self.jwks_cache = jwks
                        self.jwks_cache_expiry = time.time() + 3600

                        return jwks
                    else:
                        logger.error(f"Failed to fetch JWKS: {response.status}")
                        return {}

        except Exception as e:
            logger.error(f"JWKS fetch error: {e}")
            return {}

    async def _map_oidc_roles_to_framework_roles(self, principal: SecurityPrincipal) -> None:
        """Map OIDC roles/groups to framework roles"""
        role_mapping = self.config.get("role_mapping", {})

        oidc_roles = principal.attributes.get("roles", [])
        oidc_groups = principal.attributes.get("groups", [])

        framework_roles = set()

        # Map roles
        for oidc_role in oidc_roles:
            if oidc_role in role_mapping:
                framework_roles.add(role_mapping[oidc_role])

        # Map groups
        for oidc_group in oidc_groups:
            if oidc_group in role_mapping:
                framework_roles.add(role_mapping[oidc_group])

        # Default role mapping
        if not framework_roles:
            if "admin" in oidc_roles or "administrator" in oidc_groups:
                framework_roles.add("admin")
            elif "user" in oidc_roles or "users" in oidc_groups:
                framework_roles.add("user")
            else:
                framework_roles.add("guest")

        principal.roles = framework_roles
