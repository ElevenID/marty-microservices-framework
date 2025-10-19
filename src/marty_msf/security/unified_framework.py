"""
Unified Security Framework for Marty Microservices Framework

This module consolidates all authorization, authentication, and access control capabilities
into a single, pluggable security framework that supports:

- Advanced RBAC (Role-Based Access Control) with hierarchical roles
- ABAC (Attribute-Based Access Control) with policy engines
- Identity Provider integration (OIDC, OAuth2, SAML)
- Service mesh security policy enforcement
- Compliance scanning and automated policy validation
- Fine-grained permission management

Key Features:
- Pluggable architecture for different identity providers
- Real-time policy evaluation with caching
- Service mesh integration for traffic-level security
- Automated compliance scanning and reporting
- Unified API for all security operations
"""

import asyncio
import ipaddress
import logging
import re
import time
import weakref
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any, Optional, Union
from uuid import uuid4

import jsonschema

from ..framework.service_mesh import create_enhanced_service_mesh_manager
from .compliance.unified_scanner import UnifiedComplianceScanner
from .engines.acl_engine import ACLPolicyEngine
from .engines.builtin_engine import BuiltinPolicyEngine
from .engines.opa_engine import OPAPolicyEngine
from .engines.oso_engine import OsoPolicyEngine
from .mesh.istio_security import IstioSecurityManager
from .mesh.linkerd_security import LinkerdSecurityManager
from .providers.local_provider import LocalProvider
from .providers.oauth2_provider import OAuth2Provider
from .providers.oidc_provider import OIDCProvider
from .providers.saml_provider import SAMLProvider

logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)


class SecurityPolicyType(Enum):
    """Types of security policies"""
    RBAC = "rbac"
    ABAC = "abac"
    ACL = "acl"
    CUSTOM = "custom"


class IdentityProviderType(Enum):
    """Supported identity provider types"""
    OIDC = "oidc"
    OAUTH2 = "oauth2"
    SAML = "saml"
    LDAP = "ldap"
    LOCAL = "local"


class ComplianceFramework(Enum):
    """Supported compliance frameworks"""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOX = "sox"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"
    NIST = "nist"


@dataclass
class SecurityPrincipal:
    """Represents a security principal (user, service, device)"""
    id: str
    type: str  # user, service, device
    roles: set[str] = field(default_factory=set)
    attributes: dict[str, Any] = field(default_factory=dict)
    permissions: set[str] = field(default_factory=set)
    identity_provider: str | None = None
    session_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    def get_effective_roles(self, role_hierarchy: dict[str, set[str]]) -> set[str]:
        """Get effective roles including inherited roles from hierarchy"""
        effective_roles = set(self.roles)

        def add_inherited_roles(role: str):
            if role in role_hierarchy:
                for inherited_role in role_hierarchy[role]:
                    if inherited_role not in effective_roles:
                        effective_roles.add(inherited_role)
                        add_inherited_roles(inherited_role)  # Recursive inheritance

        for role in self.roles:
            add_inherited_roles(role)

        return effective_roles

    def get_effective_permissions(self, role_hierarchy: dict[str, set[str]], role_permissions: dict[str, set[str]]) -> set[str]:
        """Get effective permissions from roles and hierarchy"""
        effective_permissions = set(self.permissions)  # Direct permissions
        effective_roles = self.get_effective_roles(role_hierarchy)

        # Add permissions from all effective roles
        for role in effective_roles:
            if role in role_permissions:
                effective_permissions.update(role_permissions[role])

        return effective_permissions


@dataclass
class SecurityContext:
    """Security context for policy evaluation"""
    principal: SecurityPrincipal
    resource: str
    action: str
    environment: dict[str, Any] = field(default_factory=dict)
    request_metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SecurityDecision:
    """Result of security policy evaluation"""
    allowed: bool
    reason: str
    policies_evaluated: list[str] = field(default_factory=list)
    required_attributes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_time_ms: float = 0.0


@dataclass
class CacheEntry:
    """Represents a cache entry with TTL and metadata"""
    value: Any
    created_at: float
    ttl_seconds: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    tags: set[str] = field(default_factory=set)

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return time.time() > (self.created_at + self.ttl_seconds)

    def touch(self) -> None:
        """Update last access time and increment access count"""
        self.last_accessed = time.time()
        self.access_count += 1


class AdvancedCache:
    """Advanced caching system with TTL, LRU eviction, and tag-based invalidation"""

    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: float = 300.0,  # 5 minutes
        cleanup_interval: float = 60.0,  # 1 minute
        enable_metrics: bool = True
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self.enable_metrics = enable_metrics

        self._cache: dict[str, CacheEntry] = {}
        self._lock = RLock()
        self._last_cleanup = time.time()

        # Metrics
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "cleanups": 0,
            "invalidations": 0
        }

    def get(self, key: str) -> Any | None:
        """Get value from cache, returning None if expired or not found"""
        with self._lock:
            self._maybe_cleanup()

            entry = self._cache.get(key)
            if entry is None:
                if self.enable_metrics:
                    self._metrics["misses"] += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                if self.enable_metrics:
                    self._metrics["misses"] += 1
                return None

            entry.touch()
            if self.enable_metrics:
                self._metrics["hits"] += 1
            return entry.value

    def put(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
        tags: set[str] | None = None
    ) -> None:
        """Put value in cache with optional TTL and tags"""
        with self._lock:
            self._maybe_cleanup()

            # Check if we need to evict entries
            if len(self._cache) >= self.max_size:
                self._evict_lru()

            ttl = ttl or self.default_ttl
            tags = tags or set()

            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl_seconds=ttl,
                tags=tags
            )

            self._cache[key] = entry

    def delete(self, key: str) -> bool:
        """Delete specific key from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_by_tags(self, tags: set[str]) -> int:
        """Invalidate all cache entries that have any of the specified tags"""
        count = 0
        with self._lock:
            keys_to_delete = []
            for key, entry in self._cache.items():
                if entry.tags & tags:  # Intersection
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                del self._cache[key]
                count += 1

            if self.enable_metrics:
                self._metrics["invalidations"] += count

        return count

    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get current cache size"""
        return len(self._cache)

    def get_metrics(self) -> dict[str, Any]:
        """Get cache metrics"""
        with self._lock:
            hit_rate = 0.0
            total_requests = self._metrics["hits"] + self._metrics["misses"]
            if total_requests > 0:
                hit_rate = self._metrics["hits"] / total_requests

            return {
                **self._metrics,
                "size": len(self._cache),
                "hit_rate": hit_rate,
                "max_size": self.max_size
            }

    def _maybe_cleanup(self) -> None:
        """Clean up expired entries if needed"""
        current_time = time.time()
        if current_time - self._last_cleanup > self.cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = current_time

    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache"""
        expired_keys = []
        # current_time = time.time()  # Reserved for future TTL implementation

        for key, entry in self._cache.items():
            if entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        if self.enable_metrics:
            self._metrics["cleanups"] += 1

    def _evict_lru(self) -> None:
        """Evict least recently used entry"""
        if not self._cache:
            return

        # Find LRU entry
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        del self._cache[lru_key]

        if self.enable_metrics:
            self._metrics["evictions"] += 1


class SecurityCacheManager:
    """Manages multiple specialized caches for security operations"""

    def __init__(self, config: dict[str, Any]):
        self.config = config.get("caching", {})

        # Create specialized caches
        self.policy_cache = AdvancedCache(
            max_size=self.config.get("policy_cache_size", 5000),
            default_ttl=self.config.get("policy_cache_ttl", 300),
            cleanup_interval=self.config.get("cleanup_interval", 60)
        )

        self.role_cache = AdvancedCache(
            max_size=self.config.get("role_cache_size", 2000),
            default_ttl=self.config.get("role_cache_ttl", 600),  # 10 minutes
            cleanup_interval=self.config.get("cleanup_interval", 60)
        )

        self.identity_cache = AdvancedCache(
            max_size=self.config.get("identity_cache_size", 1000),
            default_ttl=self.config.get("identity_cache_ttl", 1800),  # 30 minutes
            cleanup_interval=self.config.get("cleanup_interval", 60)
        )

        self.permission_cache = AdvancedCache(
            max_size=self.config.get("permission_cache_size", 3000),
            default_ttl=self.config.get("permission_cache_ttl", 180),  # 3 minutes
            cleanup_interval=self.config.get("cleanup_interval", 60)
        )

    def get_policy_decision(self, cache_key: str) -> SecurityDecision | None:
        """Get cached policy decision"""
        return self.policy_cache.get(cache_key)

    def cache_policy_decision(
        self,
        cache_key: str,
        decision: SecurityDecision,
        ttl: float | None = None,
        tags: set[str] | None = None
    ) -> None:
        """Cache policy decision"""
        self.policy_cache.put(cache_key, decision, ttl, tags)

    def get_effective_roles(self, principal_id: str) -> set[str] | None:
        """Get cached effective roles for principal"""
        return self.role_cache.get(f"roles:{principal_id}")

    def cache_effective_roles(
        self,
        principal_id: str,
        roles: set[str],
        ttl: float | None = None
    ) -> None:
        """Cache effective roles for principal"""
        tags = {"roles", f"principal:{principal_id}"}
        self.role_cache.put(f"roles:{principal_id}", roles, ttl, tags)

    def get_effective_permissions(self, principal_id: str, resource: str) -> set[str] | None:
        """Get cached effective permissions"""
        cache_key = f"perms:{principal_id}:{resource}"
        return self.permission_cache.get(cache_key)

    def cache_effective_permissions(
        self,
        principal_id: str,
        resource: str,
        permissions: set[str],
        ttl: float | None = None
    ) -> None:
        """Cache effective permissions"""
        cache_key = f"perms:{principal_id}:{resource}"
        tags = {"permissions", f"principal:{principal_id}", f"resource:{resource}"}
        self.permission_cache.put(cache_key, permissions, ttl, tags)

    def get_identity(self, identity_key: str) -> SecurityPrincipal | None:
        """Get cached identity"""
        return self.identity_cache.get(f"identity:{identity_key}")

    def cache_identity(
        self,
        identity_key: str,
        principal: SecurityPrincipal,
        ttl: float | None = None
    ) -> None:
        """Cache identity principal"""
        tags = {"identity", f"principal:{principal.id}"}
        self.identity_cache.put(f"identity:{identity_key}", principal, ttl, tags)

    def invalidate_principal_cache(self, principal_id: str) -> int:
        """Invalidate all cache entries for a principal"""
        tags = {f"principal:{principal_id}"}
        total_invalidated = 0

        total_invalidated += self.policy_cache.invalidate_by_tags(tags)
        total_invalidated += self.role_cache.invalidate_by_tags(tags)
        total_invalidated += self.identity_cache.invalidate_by_tags(tags)
        total_invalidated += self.permission_cache.invalidate_by_tags(tags)

        return total_invalidated

    def invalidate_resource_cache(self, resource: str) -> int:
        """Invalidate all cache entries for a resource"""
        tags = {f"resource:{resource}"}
        total_invalidated = 0

        total_invalidated += self.policy_cache.invalidate_by_tags(tags)
        total_invalidated += self.permission_cache.invalidate_by_tags(tags)

        return total_invalidated

    def invalidate_by_category(self, category: str) -> int:
        """Invalidate cache entries by category (roles, permissions, identity, policy)"""
        tags = {category}
        total_invalidated = 0

        if category == "roles":
            total_invalidated += self.role_cache.invalidate_by_tags(tags)
        elif category == "permissions":
            total_invalidated += self.permission_cache.invalidate_by_tags(tags)
        elif category == "identity":
            total_invalidated += self.identity_cache.invalidate_by_tags(tags)
        elif category == "policy":
            total_invalidated += self.policy_cache.invalidate_by_tags(tags)
        else:
            # Invalidate all caches
            total_invalidated += self.policy_cache.invalidate_by_tags(tags)
            total_invalidated += self.role_cache.invalidate_by_tags(tags)
            total_invalidated += self.identity_cache.invalidate_by_tags(tags)
            total_invalidated += self.permission_cache.invalidate_by_tags(tags)

        return total_invalidated

    def clear_all_caches(self) -> None:
        """Clear all caches"""
        self.policy_cache.clear()
        self.role_cache.clear()
        self.identity_cache.clear()
        self.permission_cache.clear()

    def get_cache_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all caches"""
        return {
            "policy_cache": self.policy_cache.get_metrics(),
            "role_cache": self.role_cache.get_metrics(),
            "identity_cache": self.identity_cache.get_metrics(),
            "permission_cache": self.permission_cache.get_metrics()
        }


class IdentityProvider(ABC):
    """Abstract base class for identity providers"""

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """Authenticate user and return security principal"""
        pass

    @abstractmethod
    async def validate_token(self, token: str) -> SecurityPrincipal | None:
        """Validate token and return security principal"""
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> str | None:
        """Refresh access token"""
        pass

    @abstractmethod
    async def get_user_attributes(self, principal_id: str) -> dict[str, Any]:
        """Get additional user attributes"""
        pass


class PolicyEngine(ABC):
    """Abstract base class for policy engines"""

    @abstractmethod
    async def evaluate_policy(self, context: SecurityContext) -> SecurityDecision:
        """Evaluate security policy against context"""
        pass

    @abstractmethod
    async def load_policies(self, policies: list[dict[str, Any]]) -> bool:
        """Load security policies"""
        pass

    @abstractmethod
    async def validate_policies(self) -> list[str]:
        """Validate loaded policies and return any errors"""
        pass


class ServiceMeshSecurityManager(ABC):
    """Abstract base class for service mesh security integration"""

    @abstractmethod
    async def apply_traffic_policies(self, policies: list[dict[str, Any]]) -> bool:
        """Apply security policies to service mesh traffic"""
        pass

    @abstractmethod
    async def get_mesh_status(self) -> dict[str, Any]:
        """Get current service mesh security status"""
        pass

    @abstractmethod
    async def enforce_mTLS(self, services: list[str]) -> bool:
        """Enforce mutual TLS for specified services"""
        pass


class ComplianceScanner(ABC):
    """Abstract base class for compliance scanning"""

    @abstractmethod
    async def scan_compliance(
        self,
        framework: ComplianceFramework,
        scope: dict[str, Any]
    ) -> dict[str, Any]:
        """Scan for compliance violations"""
        pass

    @abstractmethod
    async def generate_compliance_report(
        self,
        scan_results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Generate compliance report"""
        pass


class UnifiedSecurityFramework:
    """
    Unified Security Framework that consolidates all security capabilities

    This is the main entry point for all security operations in the MMF framework.
    It provides a single, unified API for:
    - Authentication and authorization
    - Policy evaluation and enforcement
    - Identity provider integration
    - Service mesh security
    - Compliance scanning and reporting
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.identity_providers: dict[str, IdentityProvider] = {}
        self.policy_engines: dict[str, PolicyEngine] = {}
        self.service_mesh_manager: ServiceMeshSecurityManager | None = None
        self.compliance_scanner: ComplianceScanner | None = None

        # Security state
        self.active_sessions: dict[str, SecurityPrincipal] = {}
        self.audit_log: list[dict[str, Any]] = []

        # Advanced caching system
        self._initialize_advanced_caching()

        # Role and permission management
        self.role_hierarchy: dict[str, set[str]] = {}  # role -> set of inherited roles
        self.role_permissions: dict[str, set[str]] = {}  # role -> set of permissions
        self.predefined_roles: dict[str, dict[str, Any]] = {}

        # Performance metrics
        self.metrics = {
            "authentication_attempts": 0,
            "authorization_checks": 0,
            "policy_evaluations": 0,
            "compliance_scans": 0
        }

        # Initialize default roles and hierarchy
        self._initialize_default_roles()

    def _initialize_advanced_caching(self) -> None:
        """Initialize the advanced caching system"""
        self.cache_manager = SecurityCacheManager(self.config)

        # Create property-like access for backward compatibility
        self.policy_cache = self.cache_manager.policy_cache._cache  # For direct dict-like access

    async def initialize(self) -> bool:
        """Initialize the security framework"""
        try:
            # Initialize identity providers
            await self._initialize_identity_providers()

            # Initialize policy engines
            await self._initialize_policy_engines()

            # Initialize service mesh security
            await self._initialize_service_mesh_security()

            # Initialize compliance scanning
            await self._initialize_compliance_scanning()

            logger.info("Unified Security Framework initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize security framework: {e}")
            return False

    async def authenticate(
        self,
        credentials: dict[str, Any],
        provider: str | None = None
    ) -> SecurityPrincipal | None:
        """Authenticate user with specified or default identity provider"""
        self.metrics["authentication_attempts"] += 1

        try:
            # Use specified provider or default
            provider_name = provider or self.config.get("default_identity_provider", "local")

            if provider_name not in self.identity_providers:
                logger.error(f"Identity provider {provider_name} not found")
                return None

            provider_instance = self.identity_providers[provider_name]
            principal = await provider_instance.authenticate(credentials)

            if principal:
                # Create session
                session_id = str(uuid4())
                principal.session_id = session_id
                self.active_sessions[session_id] = principal

                # Audit log
                await self._audit_log_event("authentication_success", {
                    "principal_id": principal.id,
                    "provider": provider_name,
                    "session_id": session_id
                })

                logger.info(f"Authentication successful for principal {principal.id}")
            else:
                await self._audit_log_event("authentication_failure", {
                    "provider": provider_name,
                    "credentials_type": list(credentials.keys())
                })

            return principal

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            await self._audit_log_event("authentication_error", {"error": str(e)})
            return None

    async def authorize(
        self,
        principal: SecurityPrincipal,
        resource: str,
        action: str,
        context: dict[str, Any] | None = None
    ) -> SecurityDecision:
        """Authorize action on resource for principal"""
        self.metrics["authorization_checks"] += 1

        try:
            # Create security context
            security_context = SecurityContext(
                principal=principal,
                resource=resource,
                action=action,
                environment=context or {},
                request_metadata={}
            )

            # Check cache first
            cache_key = f"{principal.id}:{resource}:{action}"
            cached_decision = self.cache_manager.get_policy_decision(cache_key)
            if cached_decision:
                return cached_decision

            # Evaluate policies
            decision = await self._evaluate_all_policies(security_context)

            # Cache decision with tags for invalidation
            tags = {"policy", f"principal:{principal.id}", f"resource:{resource}"}
            self.cache_manager.cache_policy_decision(cache_key, decision, tags=tags)

            # Audit log
            await self._audit_log_event("authorization_check", {
                "principal_id": principal.id,
                "resource": resource,
                "action": action,
                "decision": decision.allowed,
                "reason": decision.reason
            })

            return decision

        except Exception as e:
            logger.error(f"Authorization error: {e}")
            return SecurityDecision(
                allowed=False,
                reason=f"Authorization error: {e}",
                evaluation_time_ms=0.0
            )

    async def register_identity_provider(
        self,
        name: str,
        provider: IdentityProvider
    ) -> bool:
        """Register a new identity provider"""
        try:
            self.identity_providers[name] = provider
            logger.info(f"Identity provider {name} registered successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to register identity provider {name}: {e}")
            return False

    async def register_policy_engine(
        self,
        name: str,
        engine: PolicyEngine
    ) -> bool:
        """Register a new policy engine"""
        try:
            self.policy_engines[name] = engine
            logger.info(f"Policy engine {name} registered successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to register policy engine {name}: {e}")
            return False

    async def apply_service_mesh_policies(
        self,
        policies: list[dict[str, Any]]
    ) -> bool:
        """Apply security policies to service mesh"""
        if not self.service_mesh_manager:
            logger.warning("Service mesh manager not initialized")
            return False

        try:
            result = await self.service_mesh_manager.apply_traffic_policies(policies)
            await self._audit_log_event("service_mesh_policy_applied", {
                "policies_count": len(policies),
                "success": result
            })
            return result
        except Exception as e:
            logger.error(f"Failed to apply service mesh policies: {e}")
            return False

    async def scan_compliance(
        self,
        framework: ComplianceFramework,
        scope: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Perform compliance scan"""
        self.metrics["compliance_scans"] += 1

        if not self.compliance_scanner:
            logger.warning("Compliance scanner not initialized")
            return {"error": "Compliance scanner not available"}

        try:
            scan_results = await self.compliance_scanner.scan_compliance(
                framework,
                scope or {}
            )

            await self._audit_log_event("compliance_scan", {
                "framework": framework.value,
                "scope": scope,
                "violations_count": len(scan_results.get("violations", []))
            })

            return scan_results

        except Exception as e:
            logger.error(f"Compliance scan error: {e}")
            return {"error": str(e)}

    async def get_security_status(self) -> dict[str, Any]:
        """Get comprehensive security status"""
        return {
            "framework_status": "active",
            "active_sessions": len(self.active_sessions),
            "identity_providers": list(self.identity_providers.keys()),
            "policy_engines": list(self.policy_engines.keys()),
            "service_mesh_enabled": self.service_mesh_manager is not None,
            "compliance_scanner_enabled": self.compliance_scanner is not None,
            "metrics": self.metrics,
            "policy_cache_size": self.cache_manager.policy_cache.size(),
            "audit_log_size": len(self.audit_log)
        }

    def get_service_mesh_manager(self, mesh_type: str) -> Any | None:
        """
        Get service mesh security manager for the specified mesh type

        Args:
            mesh_type: Type of service mesh (istio, linkerd)

        Returns:
            Service mesh security manager instance
        """
        # For compatibility with existing service mesh integration
        return self.service_mesh_manager

    async def enable_service_mesh_integration(
        self,
        mesh_type: str = "istio",
        namespace: str = "default"
    ) -> bool:
        """
        Enable service mesh integration with unified security framework

        Args:
            mesh_type: Type of service mesh to integrate with
            namespace: Kubernetes namespace for integration

        Returns:
            bool: True if integration successful
        """
        try:
            # Import here to avoid circular dependency

            # Create enhanced service mesh manager with security integration
            enhanced_manager = create_enhanced_service_mesh_manager(
                service_mesh_type=mesh_type,
                config={"namespace": namespace},
                security_manager=self
            )

            # Deploy service mesh with security policies
            default_policies = [
                {
                    "metadata": {"name": "default-deny-all"},
                    "type": "authorization",
                    "spec": {
                        "action": "DENY",
                        "rules": [{"from": [{"source": {"notPrincipals": ["*"]}}]}]
                    }
                }
            ]

            success = await enhanced_manager.deploy_service_mesh(
                namespace=namespace,
                security_policies=default_policies
            )

            if success:
                # Store the enhanced manager for runtime operations
                self._enhanced_mesh_manager = enhanced_manager
                logger.info(f"Service mesh integration enabled for {mesh_type}")

            return success

        except Exception as e:
            logger.error(f"Failed to enable service mesh integration: {e}")
            return False

    async def enforce_service_policies(
        self,
        service_name: str,
        namespace: str,
        policies: list[dict[str, Any]]
    ) -> bool:
        """
        Enforce runtime security policies for a service through service mesh

        Args:
            service_name: Name of the service
            namespace: Kubernetes namespace
            policies: List of security policies to enforce

        Returns:
            bool: True if policies enforced successfully
        """
        if not hasattr(self, '_enhanced_mesh_manager'):
            logger.error("Service mesh integration not enabled")
            return False

        try:
            return await self._enhanced_mesh_manager.enforce_runtime_policies(
                service_name=service_name,
                namespace=namespace,
                policies=policies
            )
        except Exception as e:
            logger.error(f"Failed to enforce service policies: {e}")
            return False

    async def monitor_service_mesh_security(self, namespace: str = "default") -> list[dict[str, Any]]:
        """
        Monitor security events from the service mesh

        Args:
            namespace: Kubernetes namespace to monitor

        Returns:
            List of security events
        """
        if not hasattr(self, '_enhanced_mesh_manager'):
            logger.warning("Service mesh integration not enabled")
            return []

        try:
            return await self._enhanced_mesh_manager.monitor_security_events(namespace)
        except Exception as e:
            logger.error(f"Failed to monitor service mesh security: {e}")
            return []

    # Private methods

    async def _initialize_identity_providers(self) -> None:
        """Initialize configured identity providers"""
        providers_config = self.config.get("identity_providers", {})

        for name, provider_config in providers_config.items():
            provider_type = provider_config.get("type")

            if provider_type == "oidc":
                provider = OIDCProvider(provider_config)
            elif provider_type == "oauth2":
                provider = OAuth2Provider(provider_config)
            elif provider_type == "saml":
                provider = SAMLProvider(provider_config)
            elif provider_type == "local":
                provider = LocalProvider(provider_config)
            else:
                logger.warning(f"Unknown identity provider type: {provider_type}")
                continue

            await self.register_identity_provider(name, provider)

    async def _initialize_policy_engines(self) -> None:
        """Initialize configured policy engines"""
        engines_config = self.config.get("policy_engines", {})

        for name, engine_config in engines_config.items():
            engine_type = engine_config.get("type")

            if engine_type == "opa":
                engine = OPAPolicyEngine(engine_config)
            elif engine_type == "oso":
                engine = OsoPolicyEngine(engine_config)
            elif engine_type == "builtin":
                engine = BuiltinPolicyEngine(engine_config)
            elif engine_type == "acl":
                engine = ACLPolicyEngine(engine_config)
            else:
                logger.warning(f"Unknown policy engine type: {engine_type}")
                continue

            await self.register_policy_engine(name, engine)

    async def _initialize_service_mesh_security(self) -> None:
        """Initialize service mesh security manager"""
        mesh_config = self.config.get("service_mesh", {})

        if mesh_config.get("enabled", False):
            mesh_type = mesh_config.get("type", "istio")

            if mesh_type == "istio":
                self.service_mesh_manager = IstioSecurityManager(mesh_config)
            elif mesh_type == "linkerd":
                self.service_mesh_manager = LinkerdSecurityManager(mesh_config)
            else:
                logger.warning(f"Unknown service mesh type: {mesh_type}")

    async def _initialize_compliance_scanning(self) -> None:
        """Initialize compliance scanner"""
        compliance_config = self.config.get("compliance", {})

        if compliance_config.get("enabled", False):
            self.compliance_scanner = UnifiedComplianceScanner(compliance_config)

    async def _evaluate_all_policies(self, context: SecurityContext) -> SecurityDecision:
        """Evaluate security policies across all engines"""
        start_time = datetime.now(timezone.utc)
        decisions = []
        policies_evaluated = []

        for engine_name, engine in self.policy_engines.items():
            try:
                decision = await engine.evaluate_policy(context)
                decisions.append(decision)
                policies_evaluated.extend(decision.policies_evaluated)
            except Exception as e:
                logger.error(f"Policy engine {engine_name} evaluation error: {e}")
                decisions.append(SecurityDecision(
                    allowed=False,
                    reason=f"Engine {engine_name} error: {e}"
                ))

        # Combine decisions (default to deny-by-default)
        final_decision = self._combine_decisions(decisions)
        final_decision.policies_evaluated = policies_evaluated

        end_time = datetime.now(timezone.utc)
        final_decision.evaluation_time_ms = (end_time - start_time).total_seconds() * 1000

        self.metrics["policy_evaluations"] += 1
        return final_decision

    def _combine_decisions(self, decisions: list[SecurityDecision]) -> SecurityDecision:
        """Combine multiple policy decisions using secure defaults"""
        if not decisions:
            return SecurityDecision(
                allowed=False,
                reason="No policy engines available"
            )

        # If any decision explicitly denies, deny
        for decision in decisions:
            if not decision.allowed and "deny" in decision.reason.lower():
                return SecurityDecision(
                    allowed=False,
                    reason=f"Explicit deny: {decision.reason}"
                )

        # If all decisions allow, allow
        if all(decision.allowed for decision in decisions):
            return SecurityDecision(
                allowed=True,
                reason="All policy engines allow access"
            )

        # Otherwise, deny by default
        denied_reasons = [d.reason for d in decisions if not d.allowed]
        return SecurityDecision(
            allowed=False,
            reason=f"Access denied: {'; '.join(denied_reasons)}"
        )

    async def _audit_log_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Log security event for auditing"""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details,
            "event_id": str(uuid4())
        }

        self.audit_log.append(event)

        # Keep audit log size manageable
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-5000:]  # Keep last 5000 events

        logger.info(f"Security event logged: {event_type}")

    # Role and Permission Management Methods

    def _initialize_default_roles(self) -> None:
        """Initialize default roles and hierarchy"""
        # Default roles with permissions
        self.predefined_roles = {
            "viewer": {
                "description": "Read-only access",
                "permissions": {"read"},
                "inherits": set()
            },
            "editor": {
                "description": "Read and write access",
                "permissions": {"read", "write"},
                "inherits": {"viewer"}
            },
            "moderator": {
                "description": "Editor with delete permissions",
                "permissions": {"read", "write", "delete"},
                "inherits": {"editor"}
            },
            "admin": {
                "description": "Full administrative access",
                "permissions": {"read", "write", "delete", "admin", "execute"},
                "inherits": {"moderator"}
            },
            "service": {
                "description": "Service-to-service access",
                "permissions": {"read", "write", "execute"},
                "inherits": set()
            }
        }

        # Build role hierarchy from predefined roles
        for role_name, role_data in self.predefined_roles.items():
            self.role_hierarchy[role_name] = role_data["inherits"]
            self.role_permissions[role_name] = role_data["permissions"]

    def create_role(
        self,
        role_name: str,
        description: str,
        permissions: set[str],
        inherits: set[str] | None = None
    ) -> bool:
        """Create a new role with permissions and inheritance"""
        try:
            if role_name in self.predefined_roles:
                logger.warning(f"Role {role_name} already exists")
                return False

            inherits = inherits or set()

            # Validate inherited roles exist
            for inherited_role in inherits:
                if inherited_role not in self.predefined_roles:
                    logger.error(f"Inherited role {inherited_role} does not exist")
                    return False

            # Create role
            self.predefined_roles[role_name] = {
                "description": description,
                "permissions": permissions,
                "inherits": inherits
            }

            # Update hierarchy and permissions
            self.role_hierarchy[role_name] = inherits
            self.role_permissions[role_name] = permissions

            logger.info(f"Created role: {role_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create role {role_name}: {e}")
            return False

    def delete_role(self, role_name: str) -> bool:
        """Delete a role and update hierarchy"""
        try:
            if role_name not in self.predefined_roles:
                logger.warning(f"Role {role_name} does not exist")
                return False

            # Remove from other roles' inheritance
            for _role, inherited_roles in self.role_hierarchy.items():
                if role_name in inherited_roles:
                    inherited_roles.remove(role_name)

            # Remove role
            del self.predefined_roles[role_name]
            del self.role_hierarchy[role_name]
            del self.role_permissions[role_name]

            # Clear cache since role structure changed
            self.cache_manager.invalidate_by_category("roles")

            logger.info(f"Deleted role: {role_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete role {role_name}: {e}")
            return False

    def get_role_info(self, role_name: str) -> dict[str, Any] | None:
        """Get information about a role"""
        if role_name not in self.predefined_roles:
            return None

        role_data = self.predefined_roles[role_name].copy()
        role_data["effective_permissions"] = self._get_effective_permissions_for_role(role_name)
        return role_data

    def list_roles(self) -> dict[str, dict[str, Any]]:
        """List all roles with their information"""
        result = {}
        for role_name in self.predefined_roles.keys():
            role_info = self.get_role_info(role_name)
            if role_info is not None:
                result[role_name] = role_info
        return result

    def _get_effective_permissions_for_role(self, role_name: str) -> set[str]:
        """Get effective permissions for a role including inherited permissions"""
        if role_name not in self.predefined_roles:
            return set()

        effective_permissions = set(self.role_permissions.get(role_name, set()))

        def add_inherited_permissions(role: str):
            if role in self.role_hierarchy:
                for inherited_role in self.role_hierarchy[role]:
                    if inherited_role in self.role_permissions:
                        effective_permissions.update(self.role_permissions[inherited_role])
                        add_inherited_permissions(inherited_role)  # Recursive inheritance

        add_inherited_permissions(role_name)
        return effective_permissions

    def validate_role_hierarchy(self) -> list[str]:
        """Validate role hierarchy for circular dependencies"""
        errors = []

        def has_circular_dependency(role: str, visited: set[str], path: set[str]) -> bool:
            if role in path:
                return True
            if role in visited:
                return False

            visited.add(role)
            path.add(role)

            for inherited_role in self.role_hierarchy.get(role, set()):
                if has_circular_dependency(inherited_role, visited, path):
                    return True

            path.remove(role)
            return False

        visited = set()
        for role in self.role_hierarchy.keys():
            if has_circular_dependency(role, visited, set()):
                errors.append(f"Circular dependency detected in role hierarchy involving: {role}")

        return errors

    # ACL Management Methods

    def add_acl_rule(
        self,
        resource_pattern: str,
        principal: str,
        permissions: set[str],
        allow: bool = True,
        conditions: dict[str, Any] | None = None,
        engine_name: str = "acl"
    ) -> bool:
        """Add an ACL rule to the specified ACL engine"""
        try:
            if engine_name not in self.policy_engines:
                logger.error(f"ACL engine '{engine_name}' not found")
                return False

            engine = self.policy_engines[engine_name]
            if not hasattr(engine, 'add_acl_entry'):
                logger.error(f"Engine '{engine_name}' does not support ACL operations")
                return False

            success = getattr(engine, 'add_acl_entry', lambda *args, **kwargs: False)(resource_pattern, principal, permissions, allow, conditions)
            if success:
                # Clear policy cache since ACL rules changed
                self.cache_manager.invalidate_by_category("policy")

                # Log audit event
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._audit_log_event("acl_rule_added", {
                        "resource_pattern": resource_pattern,
                        "principal": principal,
                        "permissions": list(permissions),
                        "allow": allow,
                        "engine": engine_name
                    }))
                except RuntimeError:
                    pass  # No event loop, skip audit logging

            return success

        except Exception as e:
            logger.error(f"Failed to add ACL rule: {e}")
            return False

    def remove_acl_rules(
        self,
        resource_pattern: str,
        principal: str,
        engine_name: str = "acl"
    ) -> int:
        """Remove ACL rules matching the pattern and principal"""
        try:
            if engine_name not in self.policy_engines:
                logger.error(f"ACL engine '{engine_name}' not found")
                return 0

            engine = self.policy_engines[engine_name]
            if not hasattr(engine, 'remove_acl_entries'):
                logger.error(f"Engine '{engine_name}' does not support ACL operations")
                return 0

            removed_count = getattr(engine, 'remove_acl_entries', lambda *args, **kwargs: 0)(resource_pattern, principal)
            if removed_count > 0:
                # Clear policy cache since ACL rules changed
                self.cache_manager.invalidate_by_category("policy")

                # Log audit event
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._audit_log_event("acl_rules_removed", {
                        "resource_pattern": resource_pattern,
                        "principal": principal,
                        "removed_count": removed_count,
                        "engine": engine_name
                    }))
                except RuntimeError:
                    pass  # No event loop, skip audit logging

            return removed_count

        except Exception as e:
            logger.error(f"Failed to remove ACL rules: {e}")
            return 0

    def list_acl_rules(
        self,
        resource_pattern: str | None = None,
        engine_name: str = "acl"
    ) -> list[dict[str, Any]]:
        """List ACL rules, optionally filtered by resource pattern"""
        try:
            if engine_name not in self.policy_engines:
                logger.error(f"ACL engine '{engine_name}' not found")
                return []

            engine = self.policy_engines[engine_name]
            if not hasattr(engine, 'list_acl_entries'):
                logger.error(f"Engine '{engine_name}' does not support ACL operations")
                return []

            return getattr(engine, 'list_acl_entries', lambda *args, **kwargs: [])(resource_pattern)

        except Exception as e:
            logger.error(f"Failed to list ACL rules: {e}")
            return []

    def get_effective_permissions(
        self,
        resource: str,
        principal: SecurityPrincipal,
        engine_name: str = "acl"
    ) -> set[str]:
        """Get effective permissions for a principal on a resource"""
        try:
            if engine_name not in self.policy_engines:
                logger.warning(f"ACL engine '{engine_name}' not found")
                return set()

            engine = self.policy_engines[engine_name]
            if not hasattr(engine, 'get_effective_permissions'):
                logger.warning(f"Engine '{engine_name}' does not support effective permissions")
                return set()

            # Get principal's roles and groups
            principal_roles = set(principal.roles)
            principal_groups = set(getattr(principal, 'groups', []))

            get_perms_func = getattr(engine, 'get_effective_permissions', lambda *args, **kwargs: set())
            return get_perms_func(
                resource,
                principal.id,
                principal_roles,
                principal_groups
            )

        except Exception as e:
            logger.error(f"Failed to get effective permissions: {e}")
            return set()

    def create_resource_acl(
        self,
        resource: str,
        owner: str,
        default_permissions: dict[str, set[str]] | None = None,
        engine_name: str = "acl"
    ) -> bool:
        """Create ACL rules for a new resource with owner and default permissions"""
        try:
            success = True

            # Add owner permissions (full access)
            owner_permissions = {"read", "write", "delete", "admin", "execute"}
            if not self.add_acl_rule(resource, owner, owner_permissions, True, None, engine_name):
                success = False

            # Add default permissions for roles/groups
            if default_permissions:
                for principal, permissions in default_permissions.items():
                    if not self.add_acl_rule(resource, principal, permissions, True, None, engine_name):
                        success = False

            return success

        except Exception as e:
            logger.error(f"Failed to create resource ACL: {e}")
            return False

    def check_resource_access(
        self,
        resource: str,
        action: str,
        principal: SecurityPrincipal,
        context: dict[str, Any] | None = None
    ) -> bool:
        """Quick check if principal has access to perform action on resource"""
        try:
            # Use the authorize method which handles all policy engines
            try:
                loop = asyncio.get_event_loop()
                decision = loop.run_until_complete(
                    self.authorize(principal, resource, action, context)
                )
                return decision.allowed
            except RuntimeError:
                # Create new event loop if none exists
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                decision = loop.run_until_complete(
                    self.authorize(principal, resource, action, context)
                )
                return decision.allowed

        except Exception as e:
            logger.error(f"Failed to check resource access: {e}")
            return False

    # Enhanced Policy Validation Methods

    async def validate_all_policies(
        self,
        include_schema_validation: bool = True,
        include_conflict_detection: bool = True,
        include_performance_check: bool = True
    ) -> dict[str, list[str]]:
        """Comprehensive policy validation across all engines"""
        validation_results = {
            "syntax_errors": [],
            "schema_errors": [],
            "conflict_errors": [],
            "performance_warnings": [],
            "engine_specific": {}
        }

        try:
            # Validate each policy engine
            for engine_name, engine in self.policy_engines.items():
                logger.info(f"Validating policies for engine: {engine_name}")

                try:
                    # Basic engine validation
                    engine_errors = await engine.validate_policies()
                    validation_results["engine_specific"][engine_name] = engine_errors

                    # Schema validation for supported engines
                    if include_schema_validation:
                        schema_errors = await self._validate_policy_schemas(engine_name, engine)
                        validation_results["schema_errors"].extend(schema_errors)

                    # Performance checks
                    if include_performance_check:
                        perf_warnings = await self._check_policy_performance(engine_name, engine)
                        validation_results["performance_warnings"].extend(perf_warnings)

                except Exception as e:
                    validation_results["syntax_errors"].append(
                        f"Engine '{engine_name}' validation failed: {str(e)}"
                    )

            # Cross-engine conflict detection
            if include_conflict_detection and len(self.policy_engines) > 1:
                conflict_errors = await self._detect_cross_engine_conflicts()
                validation_results["conflict_errors"].extend(conflict_errors)

            # Role hierarchy validation
            role_errors = self.validate_role_hierarchy()
            validation_results["syntax_errors"].extend(role_errors)

            # Policy cache consistency check
            cache_errors = self._validate_policy_cache()
            validation_results["syntax_errors"].extend(cache_errors)

            logger.info(f"Policy validation completed. Total issues found: {self._count_validation_issues(validation_results)}")

        except Exception as e:
            logger.error(f"Policy validation failed: {e}")
            validation_results["syntax_errors"].append(f"Validation system error: {str(e)}")

        return validation_results

    async def _validate_policy_schemas(self, engine_name: str, engine: PolicyEngine) -> list[str]:
        """Validate policy schemas using JSON Schema where applicable"""
        errors = []

        try:
            # Check if engine supports schema validation
            if hasattr(engine, 'get_policy_schema'):
                schema = engine.get_policy_schema()
                if schema:
                    # Validate against schema
                    errors.extend(await self._validate_against_schema(engine_name, engine, schema))

            # Built-in validation patterns
            if engine_name == "builtin":
                errors.extend(await self._validate_builtin_schemas(engine))
            elif engine_name == "acl":
                errors.extend(await self._validate_acl_schemas(engine))
            elif engine_name == "opa":
                errors.extend(await self._validate_opa_schemas(engine))
            elif engine_name == "oso":
                errors.extend(await self._validate_oso_schemas(engine))

        except Exception as e:
            errors.append(f"{engine_name}: Schema validation error: {str(e)}")

        return errors

    async def _validate_against_schema(self, engine_name: str, engine: PolicyEngine, schema: dict[str, Any]) -> list[str]:
        """Validate engine policies against JSON schema"""
        errors = []

        try:
            try:

                # Get policies from engine if possible
                if hasattr(engine, 'policies'):
                    policies = engine.policies
                    for i, policy in enumerate(policies):
                        try:
                            jsonschema.validate(policy, schema)
                        except jsonschema.ValidationError as e:
                            errors.append(f"{engine_name} policy {i}: {e.message}")
                        except jsonschema.SchemaError as e:
                            errors.append(f"{engine_name} schema error: {e.message}")

            except ImportError:
                logger.warning("jsonschema not available, skipping JSON schema validation")
        except Exception as e:
            errors.append(f"{engine_name}: Schema validation failed: {str(e)}")

        return errors

    async def _validate_builtin_schemas(self, engine) -> list[str]:
        """Validate builtin engine policy schemas"""
        errors = []

        if not hasattr(engine, 'policies'):
            return errors

        for i, policy in enumerate(engine.policies):
            # Check required fields
            if 'name' not in policy:
                errors.append(f"Builtin policy {i}: Missing 'name' field")

            if 'rules' not in policy:
                errors.append(f"Builtin policy {i}: Missing 'rules' field")
            else:
                # Validate rules structure
                rules = policy['rules']
                if not isinstance(rules, list):
                    errors.append(f"Builtin policy {i}: 'rules' must be a list")
                else:
                    for j, rule in enumerate(rules):
                        if not isinstance(rule, dict):
                            errors.append(f"Builtin policy {i}, rule {j}: Must be an object")
                            continue

                        if 'effect' not in rule:
                            errors.append(f"Builtin policy {i}, rule {j}: Missing 'effect' field")
                        elif rule['effect'] not in ['allow', 'deny']:
                            errors.append(f"Builtin policy {i}, rule {j}: Invalid effect '{rule['effect']}'")

        return errors

    async def _validate_acl_schemas(self, engine) -> list[str]:
        """Validate ACL engine schemas"""
        errors = []

        if not hasattr(engine, 'acl_entries'):
            return errors

        for i, entry in enumerate(engine.acl_entries):
            # Validate resource pattern
            try:
                re.compile(entry.resource_pattern)
            except re.error as e:
                errors.append(f"ACL entry {i}: Invalid resource pattern '{entry.resource_pattern}': {e}")

            # Validate principal format
            if entry.principal.startswith(('role:', 'group:')):
                parts = entry.principal.split(':', 1)
                if len(parts) != 2 or not parts[1]:
                    errors.append(f"ACL entry {i}: Invalid principal format '{entry.principal}'")

            # Validate permissions
            if not entry.permissions:
                errors.append(f"ACL entry {i}: Empty permissions set")

            # Validate conditions
            if entry.conditions:
                condition_errors = self._validate_acl_conditions(entry.conditions, i)
                errors.extend(condition_errors)

        return errors

    def _validate_acl_conditions(self, conditions: dict[str, Any], entry_index: int) -> list[str]:
        """Validate ACL entry conditions"""
        errors = []

        for condition_type, condition_value in conditions.items():
            if condition_type == "time_range":
                if not isinstance(condition_value, dict):
                    errors.append(f"ACL entry {entry_index}: time_range must be an object")
                elif 'start' not in condition_value or 'end' not in condition_value:
                    errors.append(f"ACL entry {entry_index}: time_range missing start/end")
                else:
                    # Validate time format
                    try:
                        datetime.strptime(condition_value['start'], '%H:%M')
                        datetime.strptime(condition_value['end'], '%H:%M')
                    except ValueError:
                        errors.append(f"ACL entry {entry_index}: Invalid time format in time_range")

            elif condition_type == "ip_range":
                if not isinstance(condition_value, list):
                    errors.append(f"ACL entry {entry_index}: ip_range must be a list")
                else:
                    for ip_range in condition_value:
                        try:
                            ipaddress.ip_network(ip_range)
                        except ipaddress.AddressValueError:
                            errors.append(f"ACL entry {entry_index}: Invalid IP range '{ip_range}'")

            elif condition_type == "request_method":
                if not isinstance(condition_value, list):
                    errors.append(f"ACL entry {entry_index}: request_method must be a list")
                else:
                    valid_methods = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'}
                    for method in condition_value:
                        if method.upper() not in valid_methods:
                            errors.append(f"ACL entry {entry_index}: Invalid HTTP method '{method}'")

        return errors

    async def _validate_opa_schemas(self, engine) -> list[str]:
        """Validate OPA engine schemas"""
        errors = []

        # OPA-specific validation would go here
        # For now, just check if policies are valid Rego
        if hasattr(engine, 'policies'):
            for i, policy in enumerate(engine.policies):
                if 'rego' in policy:
                    # Basic Rego syntax check
                    rego_code = policy['rego']
                    if not isinstance(rego_code, str):
                        errors.append(f"OPA policy {i}: Rego code must be a string")
                    elif not rego_code.strip():
                        errors.append(f"OPA policy {i}: Empty Rego code")

        return errors

    async def _validate_oso_schemas(self, engine) -> list[str]:
        """Validate Oso engine schemas"""
        errors = []

        # Oso-specific validation would go here
        if hasattr(engine, 'policies'):
            for i, policy in enumerate(engine.policies):
                if 'polar' in policy:
                    # Basic Polar syntax check
                    polar_code = policy['polar']
                    if not isinstance(polar_code, str):
                        errors.append(f"Oso policy {i}: Polar code must be a string")
                    elif not polar_code.strip():
                        errors.append(f"Oso policy {i}: Empty Polar code")

        return errors

    async def _check_policy_performance(self, engine_name: str, engine: PolicyEngine) -> list[str]:
        """Check for potential performance issues in policies"""
        warnings = []

        try:
            # Check policy count
            policy_count = 0
            if hasattr(engine, 'policies'):
                policy_count = len(getattr(engine, 'policies', []))
            elif hasattr(engine, 'acl_entries'):
                policy_count = len(getattr(engine, 'acl_entries', []))

            if policy_count > 1000:
                warnings.append(f"{engine_name}: Large number of policies ({policy_count}) may impact performance")

            # Engine-specific performance checks
            if engine_name == "acl":
                warnings.extend(await self._check_acl_performance(engine))
            elif engine_name == "builtin":
                warnings.extend(await self._check_builtin_performance(engine))

        except Exception as e:
            warnings.append(f"{engine_name}: Performance check failed: {str(e)}")

        return warnings

    async def _check_acl_performance(self, engine) -> list[str]:
        """Check ACL engine performance issues"""
        warnings = []

        if hasattr(engine, 'acl_entries'):
            # Check for overly broad patterns
            broad_patterns = 0
            complex_conditions = 0

            for entry in engine.acl_entries:
                if '*' in entry.resource_pattern or '.*' in entry.resource_pattern:
                    broad_patterns += 1

                if entry.conditions and len(entry.conditions) > 3:
                    complex_conditions += 1

            if broad_patterns > 100:
                warnings.append(f"ACL: Many broad resource patterns ({broad_patterns}) may impact performance")

            if complex_conditions > 50:
                warnings.append(f"ACL: Many complex conditions ({complex_conditions}) may impact performance")

        return warnings

    async def _check_builtin_performance(self, engine) -> list[str]:
        """Check builtin engine performance issues"""
        warnings = []

        if hasattr(engine, 'policies'):
            for i, policy in enumerate(engine.policies):
                if 'rules' in policy:
                    rule_count = len(policy['rules'])
                    if rule_count > 100:
                        warnings.append(f"Builtin policy {i}: Large number of rules ({rule_count}) may impact performance")

        return warnings

    async def _detect_cross_engine_conflicts(self) -> list[str]:
        """Detect conflicts between different policy engines"""
        conflicts = []

        try:
            # Sample common resources to test for conflicts
            test_resources = [
                "api:users", "api:admin", "service:auth",
                "data:sensitive", "system:config"
            ]

            test_actions = ["read", "write", "delete", "admin"]

            # Create test principal
            test_principal = SecurityPrincipal(
                id="test_user",
                type="user",
                roles={"user", "editor"}
            )

            for resource in test_resources:
                for action in test_actions:
                    engine_results = {}

                    # Test each engine
                    for engine_name, engine in self.policy_engines.items():
                        try:
                            context = SecurityContext(
                                principal=test_principal,
                                resource=resource,
                                action=action,
                                environment={},
                                request_metadata={}
                            )

                            decision = await engine.evaluate_policy(context)
                            engine_results[engine_name] = decision.allowed

                        except Exception as e:
                            logger.debug(f"Engine {engine_name} failed test evaluation: {e}")
                            continue

                    # Check for conflicts
                    if len(set(engine_results.values())) > 1:
                        conflicts.append(
                            f"Conflicting decisions for {resource}:{action} - " +
                            ", ".join(f"{engine}: {'allow' if result else 'deny'}"
                                    for engine, result in engine_results.items())
                        )

        except Exception as e:
            conflicts.append(f"Cross-engine conflict detection failed: {str(e)}")

        return conflicts

    def _validate_policy_cache(self) -> list[str]:
        """Validate policy cache consistency"""
        errors = []

        try:
            # Check cache size using cache manager
            cache_metrics = self.cache_manager.get_cache_metrics()
            policy_cache_size = cache_metrics["policy_cache"]["size"]
            if policy_cache_size > 10000:
                errors.append(f"Policy cache is very large ({policy_cache_size} entries) - consider cleanup")

            # Check for overall cache health
            for cache_name, metrics in cache_metrics.items():
                if metrics["hit_rate"] < 0.5 and metrics["size"] > 100:
                    errors.append(f"{cache_name} has low hit rate ({metrics['hit_rate']:.2f}) - consider tuning TTL")



        except Exception as e:
            errors.append(f"Policy cache validation error: {str(e)}")

        return errors

    def _count_validation_issues(self, results: dict[str, list[str]]) -> int:
        """Count total validation issues"""
        total = 0
        for category, issues_data in results.items():
            if category == "engine_specific":
                if isinstance(issues_data, dict):
                    for engine_issues in issues_data.values():
                        total += len(engine_issues)
            else:
                if isinstance(issues_data, list):
                    total += len(issues_data)
        return total

    def generate_validation_report(self, results: dict[str, list[str]]) -> str:
        """Generate a formatted validation report"""
        report = ["# Security Policy Validation Report", ""]

        total_issues = self._count_validation_issues(results)
        report.append(f"**Total Issues Found:** {total_issues}")
        report.append("")

        for category, issues_data in results.items():
            if category == "engine_specific":
                if not isinstance(issues_data, dict) or not any(issues_data.values()):
                    continue
                report.append("## Engine-Specific Issues")
                for engine_name, engine_issues in issues_data.items():
                    if engine_issues:
                        report.append(f"### {engine_name.upper()} Engine")
                        for issue in engine_issues:
                            report.append(f"- {issue}")
                        report.append("")
            else:
                if not isinstance(issues_data, list) or not issues_data:
                    continue
                category_name = category.replace("_", " ").title()
                report.append(f"## {category_name}")
                for issue in issues_data:
                    report.append(f"- {issue}")
                report.append("")

        if total_issues == 0:
            report.append("✅ **All policies passed validation!**")

        return "\n".join(report)

    # Cache Management Methods

    def get_cache_metrics(self) -> dict[str, dict[str, Any]]:
        """Get comprehensive cache metrics"""
        return self.cache_manager.get_cache_metrics()

    def clear_caches(self, cache_type: str | None = None) -> None:
        """Clear specified cache type or all caches"""
        if cache_type is None:
            self.cache_manager.clear_all_caches()
        else:
            self.cache_manager.invalidate_by_category(cache_type)

    def invalidate_principal_cache(self, principal_id: str) -> int:
        """Invalidate all cache entries for a principal"""
        return self.cache_manager.invalidate_principal_cache(principal_id)

    def invalidate_resource_cache(self, resource: str) -> int:
        """Invalidate all cache entries for a resource"""
        return self.cache_manager.invalidate_resource_cache(resource)

    def optimize_caches(self) -> dict[str, Any]:
        """Optimize cache performance and report results"""
        results = {
            "before_metrics": self.get_cache_metrics(),
            "actions_taken": [],
            "after_metrics": {}
        }

        # Force cleanup of expired entries
        for cache_name in ["policy_cache", "role_cache", "identity_cache", "permission_cache"]:
            cache = getattr(self.cache_manager, cache_name)
            cache._cleanup_expired()
            results["actions_taken"].append(f"Cleaned up expired entries in {cache_name}")

        # Get updated metrics
        results["after_metrics"] = self.get_cache_metrics()

        return results


# Convenience functions for framework integration

async def create_unified_security_framework(
    config: dict[str, Any]
) -> UnifiedSecurityFramework:
    """Create and initialize unified security framework"""
    framework = UnifiedSecurityFramework(config)
    await framework.initialize()
    return framework


def get_default_security_config() -> dict[str, Any]:
    """Get default security configuration"""
    return {
        "default_identity_provider": "local",
        "identity_providers": {
            "local": {
                "type": "local",
                "enabled": True
            }
        },
        "policy_engines": {
            "builtin": {
                "type": "builtin",
                "enabled": True
            }
        },
        "service_mesh": {
            "enabled": False,
            "type": "istio"
        },
        "compliance": {
            "enabled": True,
            "frameworks": ["gdpr", "hipaa"]
        },
        "audit": {
            "enabled": True,
            "retention_days": 90
        }
    }
