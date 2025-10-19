"""
Local Identity Provider Implementation

Provides local user authentication and management for development
and scenarios where external identity providers are not needed.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import bcrypt

from ..interfaces import IdentityProvider, SecurityPrincipal

logger = logging.getLogger(__name__)


class LocalProvider(IdentityProvider):
    """Local identity provider for development and simple deployments"""

    def __init__(self, config: dict[str, Any]):
        self.config = config

        # In-memory user store (in production, use database)
        self.users = {}
        self.sessions = {}

        # Initialize with default users if configured
        self._initialize_default_users()

    async def authenticate(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """Authenticate user with username/password"""
        try:
            username = credentials.get("username")
            password = credentials.get("password")

            if not username or not password:
                logger.warning("Missing username or password")
                return None

            user_data = self.users.get(username)
            if not user_data:
                logger.warning(f"User {username} not found")
                return None

            # Verify password
            if not bcrypt.checkpw(password.encode('utf-8'), user_data["password_hash"]):
                logger.warning(f"Invalid password for user {username}")
                return None

            # Check if account is active
            if not user_data.get("active", True):
                logger.warning(f"Account {username} is disabled")
                return None

            # Create security principal
            principal = SecurityPrincipal(
                id=user_data["user_id"],
                type="user",
                roles=set(user_data.get("roles", ["user"])),
                attributes={
                    "username": username,
                    "email": user_data.get("email"),
                    "full_name": user_data.get("full_name"),
                    "created_at": user_data.get("created_at"),
                    "last_login": datetime.now(timezone.utc).isoformat()
                },
                permissions=set(user_data.get("permissions", [])),
                identity_provider="local"
            )

            # Update last login
            user_data["last_login"] = datetime.now(timezone.utc).isoformat()

            logger.info(f"Local authentication successful for user {username}")
            return principal

        except Exception as e:
            logger.error(f"Local authentication error: {e}")
            return None

    async def validate_token(self, token: str) -> SecurityPrincipal | None:
        """Validate session token"""
        try:
            session_data = self.sessions.get(token)
            if not session_data:
                logger.warning("Invalid session token")
                return None

            # Check if session has expired
            expires_at = datetime.fromisoformat(session_data["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                logger.warning("Session token has expired")
                del self.sessions[token]
                return None

            # Get user data
            username = session_data["username"]
            user_data = self.users.get(username)
            if not user_data:
                logger.warning(f"User {username} not found for session")
                return None

            # Create security principal
            principal = SecurityPrincipal(
                id=user_data["user_id"],
                type="user",
                roles=set(user_data.get("roles", ["user"])),
                attributes={
                    "username": username,
                    "email": user_data.get("email"),
                    "full_name": user_data.get("full_name"),
                    "session_token": token
                },
                permissions=set(user_data.get("permissions", [])),
                identity_provider="local",
                session_id=token,
                expires_at=expires_at
            )

            return principal

        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None

    async def refresh_token(self, refresh_token: str) -> str | None:
        """Refresh session token"""
        try:
            # For local provider, just extend the session
            session_data = self.sessions.get(refresh_token)
            if not session_data:
                return None

            # Extend session by 1 hour
            new_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            session_data["expires_at"] = new_expires_at.isoformat()

            return refresh_token  # Same token, just extended

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None

    async def get_user_attributes(self, principal_id: str) -> dict[str, Any]:
        """Get additional user attributes"""
        try:
            for user_data in self.users.values():
                if user_data["user_id"] == principal_id:
                    return {
                        "email": user_data.get("email"),
                        "full_name": user_data.get("full_name"),
                        "roles": user_data.get("roles", []),
                        "permissions": user_data.get("permissions", []),
                        "created_at": user_data.get("created_at"),
                        "last_login": user_data.get("last_login")
                    }
            return {}

        except Exception as e:
            logger.error(f"Error fetching user attributes: {e}")
            return {}

    def create_user(
        self,
        username: str,
        password: str,
        email: str | None = None,
        full_name: str | None = None,
        roles: list | None = None
    ) -> bool:
        """Create a new user"""
        try:
            if username in self.users:
                logger.warning(f"User {username} already exists")
                return False

            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

            user_data = {
                "user_id": str(uuid4()),
                "username": username,
                "password_hash": password_hash,
                "email": email,
                "full_name": full_name,
                "roles": roles or ["user"],
                "permissions": [],
                "active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_login": None
            }

            self.users[username] = user_data
            logger.info(f"User {username} created successfully")
            return True

        except Exception as e:
            logger.error(f"User creation error: {e}")
            return False

    def create_session(self, username: str) -> str | None:
        """Create a session token for user"""
        try:
            if username not in self.users:
                return None

            session_token = str(uuid4())
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

            session_data = {
                "username": username,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at.isoformat()
            }

            self.sessions[session_token] = session_data
            return session_token

        except Exception as e:
            logger.error(f"Session creation error: {e}")
            return None

    def _initialize_default_users(self) -> None:
        """Initialize default users from configuration"""
        default_users = self.config.get("default_users", [])

        for user_config in default_users:
            username = user_config["username"]
            password = user_config["password"]
            email = user_config.get("email")
            full_name = user_config.get("full_name")
            roles = user_config.get("roles", ["user"])

            self.create_user(username, password, email, full_name, roles)

        # Always create admin user if not exists
        if "admin" not in self.users:
            admin_password = self.config.get("admin_password", "admin123")
            self.create_user(
                "admin",
                admin_password,
                "admin@example.com",
                "System Administrator",
                ["admin", "user"]
            )
            logger.info("Default admin user created")
