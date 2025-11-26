"""
Common Security Ports

This module defines common interfaces for security operations.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..domain.models.result import ComplianceResult
from ..domain.models.user import SecurityPrincipal
from ..domain.enums import ComplianceFramework


@runtime_checkable
class ISecretManager(Protocol):
    """Interface for secret management."""

    def get_secret(self, key: str) -> str | None:
        """
        Retrieve a secret value by key.

        Args:
            key: Secret identifier

        Returns:
            Secret value or None if not found
        """
        ...

    def store_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        Store a secret value.

        Args:
            key: Secret identifier
            value: Secret value to store
            metadata: Optional metadata for the secret

        Returns:
            True if successfully stored, False otherwise
        """
        ...

    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret.

        Args:
            key: Secret identifier

        Returns:
            True if successfully deleted, False otherwise
        """
        ...


@runtime_checkable
class IAuditor(Protocol):
    """Interface for security audit logging."""

    async def audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """
        Log a security event for auditing.

        Args:
            event_type: Type of security event
            details: Event details and metadata
        """
        ...


@runtime_checkable
class ICacheManager(Protocol):
    """Interface for cache management."""

    def get(self, key: str) -> Any | None:
        """
        Retrieve a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        ...

    def set(
        self, key: str, value: Any, ttl: float | None = None, tags: set[str] | None = None
    ) -> bool:
        """
        Store a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            tags: Tags for cache invalidation

        Returns:
            True if successfully cached
        """
        ...

    def delete(self, key: str) -> bool:
        """
        Delete a value from cache.

        Args:
            key: Cache key

        Returns:
            True if successfully deleted
        """
        ...

    def invalidate_by_tags(self, tags: set[str]) -> int:
        """
        Invalidate cache entries by tags.

        Args:
            tags: Tags to invalidate

        Returns:
            Number of entries invalidated
        """
        ...


@runtime_checkable
class ISessionManager(Protocol):
    """Interface for session management."""

    def create_session(
        self, principal: SecurityPrincipal, metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Create a new session for a principal.

        Args:
            principal: Security principal
            metadata: Optional session metadata

        Returns:
            Session ID
        """
        ...

    def get_session(self, session_id: str) -> SecurityPrincipal | None:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            SecurityPrincipal or None if not found
        """
        ...

    def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate a session.

        Args:
            session_id: Session identifier

        Returns:
            True if successfully invalidated
        """
        ...


@runtime_checkable
class IComplianceScanner(Protocol):
    """Interface for compliance scanners."""

    def scan_compliance(
        self, framework: ComplianceFramework, context: dict[str, Any]
    ) -> ComplianceResult:
        """
        Scan for compliance with a specific framework.

        Args:
            framework: Compliance framework to scan against
            context: Context for the compliance scan

        Returns:
            ComplianceResult with scan results
        """
        ...

    def get_supported_frameworks(self) -> list[ComplianceFramework]:
        """
        Get list of supported compliance frameworks.

        Returns:
            List of supported frameworks
        """
        ...
