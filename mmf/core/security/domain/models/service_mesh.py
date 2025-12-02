"""
Service Mesh Domain Models

Domain models for service mesh integration in the security module.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MeshType(Enum):
    """Supported service mesh types."""

    ISTIO = "istio"
    # Future: LINKERD = "linkerd", CONSUL_CONNECT = "consul_connect"


class TrafficAction(Enum):
    """Traffic policy actions."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    AUDIT = "AUDIT"


class MTLSMode(Enum):
    """mTLS enforcement modes."""

    STRICT = "STRICT"
    PERMISSIVE = "PERMISSIVE"
    DISABLE = "DISABLE"


class PolicyType(Enum):
    """Service mesh policy types."""

    AUTHORIZATION = "authorization"
    AUTHENTICATION = "authentication"
    PEER_AUTHENTICATION = "peer_authentication"
    REQUEST_AUTHENTICATION = "request_authentication"
    RATE_LIMIT = "rate_limit"
    NETWORK_POLICY = "network_policy"


@dataclass
class ServiceMeshPolicy:
    """Service mesh security policy."""

    name: str
    policy_type: PolicyType
    namespace: str
    description: str
    selector: builtins.dict[str, str] = field(default_factory=dict)
    rules: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    action: TrafficAction = TrafficAction.ALLOW
    enabled: bool = True
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_kubernetes_manifest(self) -> builtins.dict[str, Any]:
        """Convert to Kubernetes manifest."""
        api_versions = {
            PolicyType.AUTHORIZATION: "security.istio.io/v1beta1",
            PolicyType.AUTHENTICATION: "security.istio.io/v1beta1",
            PolicyType.PEER_AUTHENTICATION: "security.istio.io/v1beta1",
            PolicyType.REQUEST_AUTHENTICATION: "security.istio.io/v1beta1",
            PolicyType.RATE_LIMIT: "networking.istio.io/v1alpha3",
            PolicyType.NETWORK_POLICY: "networking.k8s.io/v1",
        }

        kind_mapping = {
            PolicyType.AUTHORIZATION: "AuthorizationPolicy",
            PolicyType.AUTHENTICATION: "RequestAuthentication",
            PolicyType.PEER_AUTHENTICATION: "PeerAuthentication",
            PolicyType.REQUEST_AUTHENTICATION: "RequestAuthentication",
            PolicyType.RATE_LIMIT: "EnvoyFilter",
            PolicyType.NETWORK_POLICY: "NetworkPolicy",
        }

        base_manifest = {
            "apiVersion": api_versions[self.policy_type],
            "kind": kind_mapping[self.policy_type],
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/managed-by": "marty-security",
                    "marty.io/policy-type": self.policy_type.value,
                    **self.metadata,
                },
            },
            "spec": self._build_spec(),
        }

        return base_manifest

    def _build_spec(self) -> builtins.dict[str, Any]:
        """Build the spec section based on policy type."""
        spec = {}

        if self.selector:
            spec["selector"] = {"matchLabels": self.selector}

        if self.policy_type == PolicyType.AUTHORIZATION:
            spec["action"] = self.action.value
            spec["rules"] = self.rules
        elif self.policy_type == PolicyType.PEER_AUTHENTICATION:
            spec["mtls"] = {"mode": self.metadata.get("mtls_mode", "STRICT")}
        elif self.policy_type == PolicyType.REQUEST_AUTHENTICATION:
            spec["jwtRules"] = self.rules
        elif self.policy_type == PolicyType.RATE_LIMIT:
            # EnvoyFilter configuration for rate limiting
            spec["configPatches"] = self.rules
        elif self.policy_type == PolicyType.NETWORK_POLICY:
            spec["podSelector"] = {"matchLabels": self.selector}
            spec["policyTypes"] = ["Ingress", "Egress"]
            spec["ingress"] = self.rules.get("ingress", [])
            spec["egress"] = self.rules.get("egress", [])

        return spec


@dataclass
class NetworkSegment:
    """Network segment definition for zero-trust."""

    name: str
    namespace: str
    services: builtins.list[str]
    security_level: str = "internal"  # public, internal, restricted, confidential
    ingress_rules: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    egress_rules: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    allowed_sources: builtins.list[str] = field(default_factory=list)
    allowed_destinations: builtins.list[str] = field(default_factory=list)

    def to_network_policy(self) -> ServiceMeshPolicy:
        """Convert to network policy."""
        return ServiceMeshPolicy(
            name=f"{self.name}-network-policy",
            policy_type=PolicyType.NETWORK_POLICY,
            namespace=self.namespace,
            description=f"Network policy for {self.name} segment",
            selector={"marty.io/segment": self.name},
            rules={
                "ingress": self.ingress_rules,
                "egress": self.egress_rules,
            },
            metadata={
                "segment": self.name,
                "security-level": self.security_level,
            },
        )

    def to_authorization_policies(self) -> builtins.list[ServiceMeshPolicy]:
        """Convert to Istio authorization policies."""
        policies = []

        for service in self.services:
            # Create authorization policy for each service
            auth_rules = []

            if self.allowed_sources:
                for source in self.allowed_sources:
                    auth_rules.append(
                        {
                            "from": [{"source": {"principals": [source]}}],
                            "to": [{"operation": {"methods": ["*"]}}],
                        }
                    )

            policy = ServiceMeshPolicy(
                name=f"{service}-{self.name}-authz",
                policy_type=PolicyType.AUTHORIZATION,
                namespace=self.namespace,
                description=f"Authorization policy for {service} in {self.name} segment",
                selector={"app": service},
                rules=auth_rules,
                action=TrafficAction.ALLOW,
                metadata={"segment": self.name, "service": service},
            )
            policies.append(policy)

        return policies


@dataclass
class ServiceMeshConfiguration:
    """Service mesh configuration."""

    mesh_type: MeshType = MeshType.ISTIO
    namespace: str = "default"
    istio_namespace: str = "istio-system"
    mtls_mode: MTLSMode = MTLSMode.STRICT
    enable_policy_sync: bool = True
    policy_sync_interval_minutes: int = 10
    kubectl_command: str = "kubectl"
    dry_run: bool = False


@dataclass
class PolicySyncResult:
    """Result of policy synchronization."""

    success: bool
    policies_applied: int = 0
    policies_failed: int = 0
    errors: builtins.list[str] = field(default_factory=list)
    warnings: builtins.list[str] = field(default_factory=list)
    sync_time: datetime = field(default_factory=datetime.utcnow)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceMeshStatus:
    """Service mesh status information."""

    mesh_type: MeshType
    installed: bool
    version: str | None = None
    namespace: str = "default"
    istio_namespace: str = "istio-system"
    mtls_enabled: bool = False
    mtls_mode: MTLSMode = MTLSMode.PERMISSIVE
    policies_applied: int = 0
    last_sync: datetime | None = None
    health_status: str = "unknown"  # healthy, degraded, unhealthy, unknown
    components: builtins.dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """Check if mesh is healthy."""
        return self.installed and self.health_status == "healthy"


@dataclass
class ServiceMeshMetrics:
    """Service mesh metrics."""

    total_policies: int = 0
    applied_policies: int = 0
    failed_policies: int = 0
    sync_operations: int = 0
    successful_syncs: int = 0
    failed_syncs: int = 0
    average_sync_time_seconds: float = 0.0
    last_sync_time: datetime | None = None
    policy_violations: int = 0
    mtls_connections: int = 0
    non_mtls_connections: int = 0

    @property
    def sync_success_rate(self) -> float:
        """Calculate sync success rate percentage."""
        if self.sync_operations == 0:
            return 0.0
        return (self.successful_syncs / self.sync_operations) * 100

    @property
    def policy_success_rate(self) -> float:
        """Calculate policy application success rate."""
        if self.total_policies == 0:
            return 0.0
        return (self.applied_policies / self.total_policies) * 100

    @property
    def mtls_adoption_rate(self) -> float:
        """Calculate mTLS adoption rate."""
        total_connections = self.mtls_connections + self.non_mtls_connections
        if total_connections == 0:
            return 0.0
        return (self.mtls_connections / total_connections) * 100
