"""
MMF Adapters

This module provides adapters implementing the hexagonal architecture ports.

Structure:
- auth/: Authentication key adapters (challenge signing, device keys)
- cache/: Caching adapters (Redis, etc.)
- credentials/: Credential interface re-exports (implementations in application layer)
- session/: Session management adapters

Key ID Namespacing:
- auth:* - Authentication keys (MMF infrastructure)
- cred:* - Credential keys (application layer, e.g., Marty)
"""

from . import auth, cache, credentials, session

__all__ = ["auth", "cache", "credentials", "session"]
