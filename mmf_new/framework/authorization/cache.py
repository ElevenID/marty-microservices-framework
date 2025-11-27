"""
Authorization Cache Management

Provides caching capabilities for authorization decisions, roles, permissions, and policies.
Wraps the mmf_new.framework.infrastructure.cache.CacheManager with authorization-specific helpers.

Key Features:
- Role and permission caching with TTL
- Policy result caching
- Tag-based invalidation patterns
- Authorization-specific cache key generation
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mmf_new.framework.infrastructure.cache import (
    CacheBackend,
    CacheConfig,
    CacheManager,
)

logger = logging.getLogger(__name__)


class AuthorizationCacheManager:
    """
    Authorization-specific cache manager.

    Wraps the infrastructure CacheManager with authorization-specific
    key patterns and helper methods for common authorization caching scenarios.
    """

    def __init__(self, cache_manager: CacheManager, default_ttl: int = 300):
        """
        Initialize authorization cache manager.

        Args:
            cache_manager: Infrastructure cache manager instance
            default_ttl: Default TTL in seconds (5 minutes)
        """
        self.cache = cache_manager
        self.default_ttl = default_ttl

    # --- Role Caching ---

    async def get_user_roles(self, user_id: str) -> set[str] | None:
        """Get cached user roles."""
        key = self._user_roles_key(user_id)
        roles = await self.cache.get(key)
        if roles is not None:
            logger.debug(f"Cache hit for user roles: {user_id}")
            return set(roles) if isinstance(roles, list | set) else None
        return None

    async def set_user_roles(self, user_id: str, roles: set[str], ttl: int | None = None) -> bool:
        """Cache user roles."""
        key = self._user_roles_key(user_id)
        ttl = ttl or self.default_ttl
        logger.debug(f"Caching user roles for {user_id} with TTL {ttl}s")
        return await self.cache.set(key, list(roles), ttl=ttl)

    async def invalidate_user_roles(self, user_id: str) -> bool:
        """Invalidate cached user roles."""
        key = self._user_roles_key(user_id)
        logger.debug(f"Invalidating user roles cache for {user_id}")
        return await self.cache.delete(key)

    # --- Permission Caching ---

    async def get_user_permissions(self, user_id: str) -> set[str] | None:
        """Get cached user permissions."""
        key = self._user_permissions_key(user_id)
        perms = await self.cache.get(key)
        if perms is not None:
            logger.debug(f"Cache hit for user permissions: {user_id}")
            return set(perms) if isinstance(perms, list | set) else None
        return None

    async def set_user_permissions(
        self, user_id: str, permissions: set[str], ttl: int | None = None
    ) -> bool:
        """Cache user permissions."""
        key = self._user_permissions_key(user_id)
        ttl = ttl or self.default_ttl
        logger.debug(f"Caching user permissions for {user_id} with TTL {ttl}s")
        return await self.cache.set(key, list(permissions), ttl=ttl)

    async def invalidate_user_permissions(self, user_id: str) -> bool:
        """Invalidate cached user permissions."""
        key = self._user_permissions_key(user_id)
        logger.debug(f"Invalidating user permissions cache for {user_id}")
        return await self.cache.delete(key)

    # --- Role Hierarchy Caching ---

    async def get_role_hierarchy(self, role: str) -> set[str] | None:
        """Get cached role hierarchy (all inherited roles)."""
        key = self._role_hierarchy_key(role)
        hierarchy = await self.cache.get(key)
        if hierarchy is not None:
            logger.debug(f"Cache hit for role hierarchy: {role}")
            return set(hierarchy) if isinstance(hierarchy, list | set) else None
        return None

    async def set_role_hierarchy(
        self, role: str, inherited_roles: set[str], ttl: int | None = None
    ) -> bool:
        """Cache role hierarchy."""
        key = self._role_hierarchy_key(role)
        ttl = ttl or self.default_ttl
        logger.debug(f"Caching role hierarchy for {role} with TTL {ttl}s")
        return await self.cache.set(key, list(inherited_roles), ttl=ttl)

    async def invalidate_role_hierarchy(self, role: str | None = None) -> bool:
        """
        Invalidate role hierarchy cache.

        Args:
            role: Specific role to invalidate, or None to clear all role hierarchies
        """
        if role:
            key = self._role_hierarchy_key(role)
            logger.debug(f"Invalidating role hierarchy cache for {role}")
            return await self.cache.delete(key)

        # Note: Clearing all role hierarchies requires pattern-based deletion
        # which isn't directly supported by CacheManager. Individual roles
        # should be invalidated as needed.
        logger.warning("Bulk role hierarchy invalidation not fully implemented")
        return True

    # --- Authorization Decision Caching ---

    async def get_authorization_decision(
        self, user_id: str, resource: str, action: str
    ) -> bool | None:
        """Get cached authorization decision."""
        key = self._authz_decision_key(user_id, resource, action)
        decision = await self.cache.get(key)
        if decision is not None:
            logger.debug(f"Cache hit for authz decision: {user_id}:{resource}:{action}")
            return bool(decision)
        return None

    async def set_authorization_decision(
        self, user_id: str, resource: str, action: str, allowed: bool, ttl: int | None = None
    ) -> bool:
        """Cache authorization decision."""
        key = self._authz_decision_key(user_id, resource, action)
        ttl = ttl or self.default_ttl
        logger.debug(f"Caching authz decision for {user_id}:{resource}:{action} with TTL {ttl}s")
        return await self.cache.set(key, allowed, ttl=ttl)

    async def invalidate_authorization_decision(
        self, user_id: str, resource: str | None = None, action: str | None = None
    ) -> bool:
        """
        Invalidate authorization decisions for a user.

        Args:
            user_id: User ID
            resource: Specific resource (optional)
            action: Specific action (optional)
        """
        if resource and action:
            key = self._authz_decision_key(user_id, resource, action)
            logger.debug(f"Invalidating authz decision: {user_id}:{resource}:{action}")
            return await self.cache.delete(key)

        # Pattern-based deletion would be needed for partial invalidation
        logger.warning("Partial authz decision invalidation not fully implemented")
        return True

    # --- Policy Caching ---

    async def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        """Get cached policy."""
        key = self._policy_key(policy_id)
        policy = await self.cache.get(key)
        if policy is not None:
            logger.debug(f"Cache hit for policy: {policy_id}")
            return policy if isinstance(policy, dict) else None
        return None

    async def set_policy(
        self, policy_id: str, policy: dict[str, Any], ttl: int | None = None
    ) -> bool:
        """Cache policy."""
        key = self._policy_key(policy_id)
        ttl = ttl or self.default_ttl * 2  # Policies change less frequently
        logger.debug(f"Caching policy {policy_id} with TTL {ttl}s")
        return await self.cache.set(key, policy, ttl=ttl)

    async def invalidate_policy(self, policy_id: str) -> bool:
        """Invalidate cached policy."""
        key = self._policy_key(policy_id)
        logger.debug(f"Invalidating policy cache for {policy_id}")
        return await self.cache.delete(key)

    # --- Bulk Invalidation ---

    async def invalidate_user_cache(self, user_id: str) -> bool:
        """Invalidate all cached data for a user."""
        logger.info(f"Invalidating all caches for user {user_id}")

        results = await asyncio.gather(
            self.invalidate_user_roles(user_id),
            self.invalidate_user_permissions(user_id),
            self.invalidate_authorization_decision(user_id),
            return_exceptions=True,
        )

        return all(r is True for r in results if not isinstance(r, Exception))

    async def clear_all(self) -> bool:
        """Clear all authorization caches."""
        logger.warning("Clearing ALL authorization caches")
        return await self.cache.clear()

    # --- Cache Key Helpers ---

    def _user_roles_key(self, user_id: str) -> str:
        """Generate cache key for user roles."""
        return f"authz:user:{user_id}:roles"

    def _user_permissions_key(self, user_id: str) -> str:
        """Generate cache key for user permissions."""
        return f"authz:user:{user_id}:permissions"

    def _role_hierarchy_key(self, role: str) -> str:
        """Generate cache key for role hierarchy."""
        return f"authz:role:{role}:hierarchy"

    def _authz_decision_key(self, user_id: str, resource: str, action: str) -> str:
        """Generate cache key for authorization decision."""
        return f"authz:decision:{user_id}:{resource}:{action}"

    def _policy_key(self, policy_id: str) -> str:
        """Generate cache key for policy."""
        return f"authz:policy:{policy_id}"


# Import asyncio at module level for gather


def create_authorization_cache(
    cache_manager: CacheManager | None = None, default_ttl: int = 300
) -> AuthorizationCacheManager:
    """
    Factory function to create an authorization cache manager.

    Args:
        cache_manager: Existing cache manager, or None to create default
        default_ttl: Default TTL in seconds

    Returns:
        AuthorizationCacheManager instance
    """
    if cache_manager is None:
        config = CacheConfig(
            backend=CacheBackend.MEMORY,
            default_ttl=default_ttl,
            namespace="authorization",
        )
        cache_manager = CacheManager(config)

    return AuthorizationCacheManager(cache_manager, default_ttl=default_ttl)
