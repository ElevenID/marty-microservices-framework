"""
Authentication Management Module

Advanced authentication management including principal registration,
multi-method authentication, token management, and security policies.
"""

import builtins
import hashlib
import re
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from ..cryptography.manager import CryptographyManager
from ..models import AuthenticationMethod, SecurityPrincipal, SecurityToken


class AuthenticationManager:
    """Advanced authentication management."""

    def __init__(self, service_name: str, crypto_manager: CryptographyManager):
        """Initialize authentication manager."""
        self.service_name = service_name
        self.crypto_manager = crypto_manager

        # Token storage
        self.active_tokens: builtins.dict[str, SecurityToken] = {}
        self.revoked_tokens: builtins.set[str] = set()

        # User/principal storage
        self.principals: builtins.dict[str, SecurityPrincipal] = {}

        # Authentication settings
        self.jwt_secret = secrets.token_urlsafe(64)
        self.token_expiry = timedelta(hours=24)
        self.refresh_token_expiry = timedelta(days=30)

        # Rate limiting
        self.failed_attempts: builtins.dict[str, builtins.list[datetime]] = defaultdict(list)
        self.locked_accounts: builtins.dict[str, datetime] = {}

        # Security policies
        self.password_policy = {
            "min_length": 12,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_numbers": True,
            "require_special_chars": True,
            "max_age_days": 90,
        }

    def register_principal(self, principal: SecurityPrincipal) -> bool:
        """Register a new security principal."""
        try:
            # Validate principal data
            if not self._validate_principal(principal):
                return False

            # Check if principal already exists
            if principal.id in self.principals:
                return False

            # Store principal
            self.principals[principal.id] = principal

            return True

        except Exception as e:
            print(f"Error registering principal: {e}")
            return False

    def authenticate(
        self,
        principal_id: str,
        credentials: builtins.dict[str, Any],
        method: AuthenticationMethod,
    ) -> SecurityToken | None:
        """Authenticate principal and return security token."""
        try:
            # Check if account is locked
            if self._is_account_locked(principal_id):
                self._record_failed_attempt(principal_id)
                return None

            # Get principal
            principal = self.principals.get(principal_id)
            if not principal or not principal.is_active:
                self._record_failed_attempt(principal_id)
                return None

            # Authenticate based on method
            if method == AuthenticationMethod.PASSWORD:
                if not self._authenticate_password(principal, credentials):
                    self._record_failed_attempt(principal_id)
                    return None
            elif method == AuthenticationMethod.API_KEY:
                if not self._authenticate_api_key(principal, credentials):
                    self._record_failed_attempt(principal_id)
                    return None
            elif method == AuthenticationMethod.JWT_TOKEN:
                if not self._authenticate_jwt_token(principal, credentials):
                    self._record_failed_attempt(principal_id)
                    return None
            else:
                return None

            # Clear failed attempts on successful authentication
            self.failed_attempts.pop(principal_id, None)

            # Update last access
            principal.last_access = datetime.now(timezone.utc)

            # Generate security token
            token = self._generate_security_token(principal, method)
            self.active_tokens[token.token_id] = token

            return token

        except Exception as e:
            print(f"Authentication error: {e}")
            return None

    def validate_token(self, token_id: str) -> SecurityPrincipal | None:
        """Validate security token and return principal."""
        try:
            # Check if token exists and is not revoked
            if token_id not in self.active_tokens or token_id in self.revoked_tokens:
                return None

            token = self.active_tokens[token_id]

            # Check if token is expired
            if datetime.now(timezone.utc) >= token.expires_at:
                self.revoke_token(token_id)
                return None

            # Get principal
            principal = self.principals.get(token.principal_id)
            if not principal or not principal.is_active:
                self.revoke_token(token_id)
                return None

            return principal

        except Exception as e:
            print(f"Token validation error: {e}")
            return None

    def revoke_token(self, token_id: str) -> bool:
        """Revoke a security token."""
        try:
            if token_id in self.active_tokens:
                token = self.active_tokens[token_id]
                token.is_revoked = True
                self.revoked_tokens.add(token_id)
                del self.active_tokens[token_id]
                return True
            return False
        except Exception:
            return False

    def refresh_token(self, token_id: str) -> SecurityToken | None:
        """Refresh a security token."""
        principal = self.validate_token(token_id)
        if not principal:
            return None

        # Revoke old token
        old_token = self.active_tokens.get(token_id)
        if old_token:
            self.revoke_token(token_id)

            # Generate new token
            new_token = self._generate_security_token(principal, old_token.token_type)
            self.active_tokens[new_token.token_id] = new_token

            return new_token

        return None

    def _validate_principal(self, principal: SecurityPrincipal) -> bool:
        """Validate principal data."""
        if not principal.id or not principal.name:
            return False

        if principal.type not in ["user", "service", "system"]:
            return False

        return True

    def _authenticate_password(
        self, principal: SecurityPrincipal, credentials: builtins.dict[str, Any]
    ) -> bool:
        """Authenticate using password."""
        password = credentials.get("password")
        if not password:
            return False

        stored_hash = principal.attributes.get("password_hash")
        if not stored_hash:
            return False

        return self.crypto_manager.verify_password(password, stored_hash)

    def _authenticate_api_key(
        self, principal: SecurityPrincipal, credentials: builtins.dict[str, Any]
    ) -> bool:
        """Authenticate using API key."""
        api_key = credentials.get("api_key")
        if not api_key:
            return False

        stored_keys = principal.attributes.get("api_keys", [])

        # Hash the provided key and compare
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        return api_key_hash in stored_keys

    def _authenticate_jwt_token(
        self, principal: SecurityPrincipal, credentials: builtins.dict[str, Any]
    ) -> bool:
        """Authenticate using JWT token."""
        token = credentials.get("jwt_token")
        if not token:
            return False

        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload.get("sub") == principal.id
        except jwt.InvalidTokenError:
            return False

    def _generate_security_token(
        self, principal: SecurityPrincipal, method: AuthenticationMethod
    ) -> SecurityToken:
        """Generate a new security token."""
        token_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + self.token_expiry

        return SecurityToken(
            token_id=token_id,
            principal_id=principal.id,
            token_type=method,
            expires_at=expires_at,
            scopes=principal.permissions.copy(),
            metadata={
                "issued_at": datetime.now(timezone.utc).isoformat(),
                "issuer": self.service_name,
                "security_level": principal.security_level.value,
            },
        )

    def _is_account_locked(self, principal_id: str) -> bool:
        """Check if account is locked."""
        if principal_id in self.locked_accounts:
            unlock_time = self.locked_accounts[principal_id]
            if datetime.now(timezone.utc) >= unlock_time:
                del self.locked_accounts[principal_id]
                return False
            return True
        return False

    def _record_failed_attempt(self, principal_id: str):
        """Record failed authentication attempt."""
        now = datetime.now(timezone.utc)
        attempts = self.failed_attempts[principal_id]

        # Add current attempt
        attempts.append(now)

        # Remove attempts older than 1 hour
        cutoff = now - timedelta(hours=1)
        self.failed_attempts[principal_id] = [a for a in attempts if a >= cutoff]

        # Lock account if too many failed attempts
        if len(self.failed_attempts[principal_id]) >= 5:
            self.locked_accounts[principal_id] = now + timedelta(minutes=30)

    def validate_password_policy(self, password: str) -> builtins.tuple[bool, builtins.list[str]]:
        """Validate password against policy."""
        errors = []

        if len(password) < self.password_policy["min_length"]:
            errors.append(
                f"Password must be at least {self.password_policy['min_length']} characters"
            )

        if self.password_policy["require_uppercase"] and not re.search(r"[A-Z]", password):
            errors.append("Password must contain uppercase letters")

        if self.password_policy["require_lowercase"] and not re.search(r"[a-z]", password):
            errors.append("Password must contain lowercase letters")

        if self.password_policy["require_numbers"] and not re.search(r"\d", password):
            errors.append("Password must contain numbers")

        if self.password_policy["require_special_chars"] and not re.search(
            r'[!@#$%^&*(),.?":{}|<>]', password
        ):
            errors.append("Password must contain special characters")

        return len(errors) == 0, errors
