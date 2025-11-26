"""
Service Mesh Security Integration for Zero-Trust Architecture

Integrates with Istio service mesh to provide:
- Automatic mTLS for all service communication
- Fine-grained traffic policies
- Security monitoring and observability
- Policy enforcement at the mesh level
- Zero-trust network segmentation
"""

import builtins
from dataclasses import dataclass
from enum import Enum
from typing import Any

import yaml

# Kubernetes and Istio API objects
ISTIO_API_VERSION = "security.istio.io/v1beta1"
NETWORKING_API_VERSION = "networking.istio.io/v1beta1"


class TrafficAction(Enum):
    """Traffic policy actions"""

    ALLOW = "ALLOW"
    DENY = "DENY"
    AUDIT = "AUDIT"


@dataclass
class ServiceMeshPolicy:
    """Service mesh security policy"""

    name: str
    namespace: str
    description: str
    selector: builtins.dict[str, str]
    rules: builtins.list[builtins.dict[str, Any]]
    action: TrafficAction = TrafficAction.ALLOW

    def to_istio_authorization_policy(self) -> builtins.dict[str, Any]:
        """Convert to Istio AuthorizationPolicy"""
        return {
            "apiVersion": ISTIO_API_VERSION,
            "kind": "AuthorizationPolicy",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/managed-by": "marty-security",
                    "marty.io/policy-type": "zero-trust",
                },
            },
            "spec": {
                "selector": {"matchLabels": self.selector},
                "action": self.action.value,
                "rules": self.rules,
            },
        }


@dataclass
class NetworkSegment:
    """Network segment definition"""

    name: str
    namespace: str
    services: builtins.list[str]
    ingress_rules: builtins.list[builtins.dict[str, Any]]
    egress_rules: builtins.list[builtins.dict[str, Any]]
    security_level: str = "internal"

    def to_network_policy(self) -> builtins.dict[str, Any]:
        """Convert to Kubernetes NetworkPolicy"""
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": f"{self.name}-network-policy",
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/managed-by": "marty-security",
                    "marty.io/segment": self.name,
                    "marty.io/security-level": self.security_level,
                },
            },
            "spec": {
                "podSelector": {"matchLabels": {"marty.io/segment": self.name}},
                "policyTypes": ["Ingress", "Egress"],
                "ingress": self.ingress_rules,
                "egress": self.egress_rules,
            },
        }


class ServiceMeshSecurityManager:
    """
    Service mesh security manager for zero-trust implementation

    Features:
    - Automatic mTLS enforcement
    - Service-to-service authorization
    - Network micro-segmentation
    - Traffic policy management
    - Security observability
    """

    def __init__(self, namespace: str = "istio-system"):
        self.namespace = namespace
        self.policies: builtins.dict[str, ServiceMeshPolicy] = {}
        self.network_segments: builtins.dict[str, NetworkSegment] = {}

        # Default security configuration
        self.default_mtls_enabled = True
        self.default_deny_all = True

    def create_default_policies(self) -> builtins.list[builtins.dict[str, Any]]:
        """Create default zero-trust security policies"""
        policies = []

        # 1. Default deny-all policy
        deny_all = {
            "apiVersion": ISTIO_API_VERSION,
            "kind": "AuthorizationPolicy",
            "metadata": {
                "name": "default-deny-all",
                "namespace": "istio-system",
                "labels": {"app.kubernetes.io/managed-by": "marty-security"},
            },
            "spec": {},  # Empty spec means deny all
        }
        policies.append(deny_all)

        # 2. Istio system communication
        istio_system = {
            "apiVersion": ISTIO_API_VERSION,
            "kind": "AuthorizationPolicy",
            "metadata": {"name": "istio-system-allow", "namespace": "istio-system"},
            "spec": {
                "action": "ALLOW",
                "rules": [{"from": [{"source": {"namespaces": ["istio-system"]}}]}],
            },
        }
        policies.append(istio_system)

        # 3. Health check allowance
        health_check = {
            "apiVersion": ISTIO_API_VERSION,
            "kind": "AuthorizationPolicy",
            "metadata": {"name": "health-check-allow", "namespace": "istio-system"},
            "spec": {
                "action": "ALLOW",
                "rules": [{"to": [{"operation": {"paths": ["/health", "/ready", "/live"]}}]}],
            },
        }
        policies.append(health_check)

        # 4. Observability traffic
        observability = {
            "apiVersion": ISTIO_API_VERSION,
            "kind": "AuthorizationPolicy",
            "metadata": {"name": "observability-allow", "namespace": "istio-system"},
            "spec": {
                "action": "ALLOW",
                "rules": [
                    {
                        "from": [
                            {
                                "source": {
                                    "principals": [
                                        "cluster.local/ns/istio-system/sa/prometheus",
                                        "cluster.local/ns/istio-system/sa/grafana",
                                        "cluster.local/ns/istio-system/sa/jaeger",
                                    ]
                                }
                            }
                        ]
                    }
                ],
            },
        }
        policies.append(observability)

        return policies

    def create_mtls_policy(self, namespace: str = None) -> builtins.dict[str, Any]:
        """Create strict mTLS policy"""
        return {
            "apiVersion": ISTIO_API_VERSION,
            "kind": "PeerAuthentication",
            "metadata": {
                "name": "default-mtls-strict",
                "namespace": namespace or "istio-system",
                "labels": {"app.kubernetes.io/managed-by": "marty-security"},
            },
            "spec": {"mtls": {"mode": "STRICT"}},
        }

    def create_service_authorization_policy(
        self,
        service_name: str,
        namespace: str,
        allowed_sources: builtins.list[builtins.dict[str, Any]],
        allowed_operations: builtins.list[builtins.dict[str, Any]] = None,
    ) -> ServiceMeshPolicy:
        """Create authorization policy for a specific service"""

        rules = []

        # Create rule with sources and operations
        rule = {}

        if allowed_sources:
            rule["from"] = [{"source": source} for source in allowed_sources]

        if allowed_operations:
            rule["to"] = [{"operation": op} for op in allowed_operations]

        if rule:
            rules.append(rule)

        policy = ServiceMeshPolicy(
            name=f"{service_name}-authorization",
            namespace=namespace,
            description=f"Authorization policy for {service_name}",
            selector={"app": service_name},
            rules=rules,
            action=TrafficAction.ALLOW,
        )

        self.policies[f"{namespace}/{service_name}"] = policy
        return policy

    def create_inter_service_policy(
        self,
        source_service: str,
        source_namespace: str,
        target_service: str,
        target_namespace: str,
        allowed_methods: builtins.list[str] = None,
        allowed_paths: builtins.list[str] = None,
    ) -> ServiceMeshPolicy:
        """Create policy for inter-service communication"""

        # Define source
        source = {"principals": [f"cluster.local/ns/{source_namespace}/sa/{source_service}"]}

        # Define operation constraints
        operations = []
        if allowed_methods or allowed_paths:
            operation = {}
            if allowed_methods:
                operation["methods"] = allowed_methods
            if allowed_paths:
                operation["paths"] = allowed_paths
            operations.append(operation)

        return self.create_service_authorization_policy(
            target_service, target_namespace, [source], operations
        )

    def create_network_segment(
        self,
        segment_name: str,
        namespace: str,
        services: builtins.list[str],
        security_level: str = "internal",
    ) -> NetworkSegment:
        """Create network micro-segment"""

        # Allow ingress from same segment and observability
        ingress_rules = [
            {
                "from": [
                    {"podSelector": {"matchLabels": {"marty.io/segment": segment_name}}},
                    {"namespaceSelector": {"matchLabels": {"name": "istio-system"}}},
                ],
                "ports": [
                    {"protocol": "TCP", "port": 8080},
                    {"protocol": "TCP", "port": 9090},
                    {"protocol": "TCP", "port": 15000},  # Envoy admin
                ],
            }
        ]

        # Allow egress to same segment, DNS, and external (controlled)
        egress_rules = [
            {"to": [{"podSelector": {"matchLabels": {"marty.io/segment": segment_name}}}]},
            {
                "to": [{"namespaceSelector": {"matchLabels": {"name": "kube-system"}}}],
                "ports": [{"protocol": "UDP", "port": 53}],  # DNS
            },
        ]

        # Restrict external access for high security levels
        if security_level in ["confidential", "restricted"]:
            # No external egress for high security services
            pass
        else:
            # Allow controlled external access
            egress_rules.append(
                {
                    "to": [],  # External traffic
                    "ports": [
                        {"protocol": "TCP", "port": 443},  # HTTPS
                        {"protocol": "TCP", "port": 80},  # HTTP
                    ],
                }
            )

        segment = NetworkSegment(
            name=segment_name,
            namespace=namespace,
            services=services,
            ingress_rules=ingress_rules,
            egress_rules=egress_rules,
            security_level=security_level,
        )

        self.network_segments[f"{namespace}/{segment_name}"] = segment
        return segment

    def create_security_telemetry_config(self) -> builtins.dict[str, Any]:
        """Create telemetry configuration for security monitoring"""
        return {
            "apiVersion": "telemetry.istio.io/v1alpha1",
            "kind": "Telemetry",
            "metadata": {"name": "security-telemetry", "namespace": "istio-system"},
            "spec": {
                "metrics": [
                    {
                        "providers": [{"name": "prometheus"}],
                        "overrides": [
                            {
                                "match": {"metric": "ALL_METRICS"},
                                "tagOverrides": {
                                    "source_security_level": {"value": "%{SOURCE_APP | 'unknown'}"},
                                    "destination_security_level": {
                                        "value": "%{DESTINATION_APP | 'unknown'}"
                                    },
                                },
                            }
                        ],
                    }
                ],
                "accessLogging": [
                    {
                        "providers": [{"name": "otel"}],
                        "filter": {
                            "expression": "response.code >= 400 || has(request.headers['x-security-audit'])"
                        },
                    }
                ],
            },
        }

    def generate_kubernetes_manifests(self) -> builtins.list[builtins.dict[str, Any]]:
        """Generate all Kubernetes manifests for zero-trust setup"""
        manifests = []

        # Default policies
        manifests.extend(self.create_default_policies())

        # mTLS policy
        manifests.append(self.create_mtls_policy())

        # Service policies
        for policy in self.policies.values():
            manifests.append(policy.to_istio_authorization_policy())

        # Network policies
        for segment in self.network_segments.values():
            manifests.append(segment.to_network_policy())

        # Telemetry configuration
        manifests.append(self.create_security_telemetry_config())

        return manifests

    def export_policies_yaml(self, file_path: str):
        """Export all policies to YAML file"""
        manifests = self.generate_kubernetes_manifests()

        with open(file_path, "w") as f:
            for i, manifest in enumerate(manifests):
                if i > 0:
                    f.write("---\n")
                yaml.dump(manifest, f, default_flow_style=False)

    def create_service_security_config(
        self,
        service_name: str,
        namespace: str = "default",
        security_level: str = "internal",
        allowed_sources: builtins.list[str] = None,
        external_access: bool = False,
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Create complete security configuration for a service"""
        configs = []

        # 1. Service authorization policy
        sources = []
        if allowed_sources:
            for source in allowed_sources:
                if "/" in source:  # namespace/service format
                    src_namespace, src_service = source.split("/")
                    sources.append(
                        {"principals": [f"cluster.local/ns/{src_namespace}/sa/{src_service}"]}
                    )
                else:  # just service name, same namespace
                    sources.append({"principals": [f"cluster.local/ns/{namespace}/sa/{source}"]})

        if external_access:
            # Allow ingress gateway
            sources.append(
                {"principals": ["cluster.local/ns/istio-system/sa/istio-ingressgateway"]}
            )

        auth_policy = self.create_service_authorization_policy(service_name, namespace, sources)
        configs.append(auth_policy.to_istio_authorization_policy())

        # 2. Network segment
        segment = self.create_network_segment(
            f"{service_name}-segment", namespace, [service_name], security_level
        )
        configs.append(segment.to_network_policy())

        # 3. Destination rule for mTLS
        destination_rule = {
            "apiVersion": NETWORKING_API_VERSION,
            "kind": "DestinationRule",
            "metadata": {"name": f"{service_name}-mtls", "namespace": namespace},
            "spec": {
                "host": f"{service_name}.{namespace}.svc.cluster.local",
                "trafficPolicy": {"tls": {"mode": "ISTIO_MUTUAL"}},
            },
        }
        configs.append(destination_rule)

        return configs


def create_production_security_policies() -> ServiceMeshSecurityManager:
    """Create production-ready security policies"""
    manager = ServiceMeshSecurityManager()

    # API Gateway policies
    manager.create_service_authorization_policy(
        "api-gateway",
        "production",
        [
            # Allow from ingress gateway
            {"principals": ["cluster.local/ns/istio-system/sa/istio-ingressgateway"]},
        ],
        [
            {"methods": ["GET", "POST", "PUT", "DELETE"]},
            {"paths": ["/api/*", "/health", "/metrics"]},
        ],
    )

    # User service policies
    manager.create_inter_service_policy(
        "api-gateway",
        "production",
        "user-service",
        "production",
        ["GET", "POST", "PUT"],
        ["/api/v1/users/*", "/api/v1/auth/*"],
    )

    # Payment service policies (high security)
    manager.create_inter_service_policy(
        "user-service",
        "production",
        "payment-service",
        "production",
        ["POST"],
        ["/api/v1/payments/*"],
    )

    # Order service policies
    manager.create_inter_service_policy(
        "user-service",
        "production",
        "order-service",
        "production",
        ["GET", "POST"],
        ["/api/v1/orders/*"],
    )

    manager.create_inter_service_policy(
        "payment-service",
        "production",
        "order-service",
        "production",
        ["PUT"],
        ["/api/v1/orders/*/payment-status"],
    )

    # Create network segments
    manager.create_network_segment("frontend-tier", "production", ["api-gateway"], "internal")

    manager.create_network_segment(
        "business-tier", "production", ["user-service", "order-service"], "confidential"
    )

    manager.create_network_segment("payment-tier", "production", ["payment-service"], "restricted")

    return manager


# Example usage
if __name__ == "__main__":
    # Create production security setup
    security_manager = create_production_security_policies()

    # Export to YAML
    security_manager.export_policies_yaml("zero-trust-policies.yaml")

    print("Generated zero-trust security policies:")
    for policy_name in security_manager.policies.keys():
        print(f"  - {policy_name}")

    print("Generated network segments:")
    for segment_name in security_manager.network_segments.keys():
        print(f"  - {segment_name}")

    # Example: Create security config for new service
    new_service_configs = security_manager.create_service_security_config(
        "notification-service",
        "production",
        security_level="internal",
        allowed_sources=["user-service", "order-service"],
        external_access=False,
    )

    print(f"\nGenerated {len(new_service_configs)} security configs for notification-service")
