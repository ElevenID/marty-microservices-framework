from datetime import datetime

import pytest

from mmf.core.security.domain.models.service_mesh import (
    MeshType,
    MTLSMode,
    NetworkSegment,
    PolicySyncResult,
    PolicyType,
    ServiceMeshConfiguration,
    ServiceMeshMetrics,
    ServiceMeshPolicy,
    ServiceMeshStatus,
    TrafficAction,
)


class TestServiceMeshModels:
    def test_service_mesh_policy_manifest_authorization(self):
        policy = ServiceMeshPolicy(
            name="test-authz",
            policy_type=PolicyType.AUTHORIZATION,
            namespace="default",
            description="Test authorization policy",
            selector={"app": "test-app"},
            rules=[{"from": [{"source": {"principals": ["cluster.local/ns/default/sa/test-sa"]}}]}],
            action=TrafficAction.ALLOW,
        )

        manifest = policy.to_kubernetes_manifest()

        assert manifest["apiVersion"] == "security.istio.io/v1beta1"
        assert manifest["kind"] == "AuthorizationPolicy"
        assert manifest["metadata"]["name"] == "test-authz"
        assert manifest["metadata"]["namespace"] == "default"
        assert manifest["spec"]["selector"]["matchLabels"] == {"app": "test-app"}
        assert manifest["spec"]["action"] == "ALLOW"
        assert len(manifest["spec"]["rules"]) == 1

    def test_service_mesh_policy_manifest_peer_authentication(self):
        policy = ServiceMeshPolicy(
            name="test-peer-auth",
            policy_type=PolicyType.PEER_AUTHENTICATION,
            namespace="default",
            description="Test peer authentication",
            metadata={"mtls_mode": "STRICT"},
        )

        manifest = policy.to_kubernetes_manifest()

        assert manifest["apiVersion"] == "security.istio.io/v1beta1"
        assert manifest["kind"] == "PeerAuthentication"
        assert manifest["spec"]["mtls"]["mode"] == "STRICT"

    def test_service_mesh_policy_manifest_network_policy(self):
        policy = ServiceMeshPolicy(
            name="test-net-pol",
            policy_type=PolicyType.NETWORK_POLICY,
            namespace="default",
            description="Test network policy",
            selector={"app": "test-app"},
            rules={
                "ingress": [{"from": [{"podSelector": {"matchLabels": {"role": "frontend"}}}]}],
                "egress": [{"to": [{"ipBlock": {"cidr": "10.0.0.0/24"}}]}],
            },
        )

        manifest = policy.to_kubernetes_manifest()

        assert manifest["apiVersion"] == "networking.k8s.io/v1"
        assert manifest["kind"] == "NetworkPolicy"
        assert manifest["spec"]["podSelector"]["matchLabels"] == {"app": "test-app"}
        assert "Ingress" in manifest["spec"]["policyTypes"]
        assert "Egress" in manifest["spec"]["policyTypes"]
        assert len(manifest["spec"]["ingress"]) == 1
        assert len(manifest["spec"]["egress"]) == 1

    def test_network_segment_to_network_policy(self):
        segment = NetworkSegment(
            name="backend",
            namespace="default",
            services=["api", "worker"],
            security_level="restricted",
            ingress_rules=[{"from": [{"podSelector": {"matchLabels": {"role": "frontend"}}}]}],
            egress_rules=[{"to": [{"ipBlock": {"cidr": "10.0.0.0/24"}}]}],
        )

        policy = segment.to_network_policy()

        assert policy.name == "backend-network-policy"
        assert policy.policy_type == PolicyType.NETWORK_POLICY
        assert policy.selector == {"marty.io/segment": "backend"}
        assert policy.rules["ingress"] == segment.ingress_rules
        assert policy.rules["egress"] == segment.egress_rules
        assert policy.metadata["segment"] == "backend"
        assert policy.metadata["security-level"] == "restricted"

    def test_network_segment_to_authorization_policies(self):
        segment = NetworkSegment(
            name="backend",
            namespace="default",
            services=["api", "worker"],
            allowed_sources=["cluster.local/ns/default/sa/frontend"],
        )

        policies = segment.to_authorization_policies()

        assert len(policies) == 2

        api_policy = next(p for p in policies if p.selector["app"] == "api")
        assert api_policy.name == "api-backend-authz"
        assert api_policy.policy_type == PolicyType.AUTHORIZATION
        assert len(api_policy.rules) == 1
        assert api_policy.rules[0]["from"][0]["source"]["principals"] == [
            "cluster.local/ns/default/sa/frontend"
        ]

    def test_service_mesh_configuration(self):
        config = ServiceMeshConfiguration(
            mesh_type=MeshType.ISTIO, namespace="custom-ns", mtls_mode=MTLSMode.STRICT, dry_run=True
        )

        assert config.mesh_type == MeshType.ISTIO
        assert config.namespace == "custom-ns"
        assert config.mtls_mode == MTLSMode.STRICT
        assert config.dry_run is True

    def test_policy_sync_result(self):
        result = PolicySyncResult(
            success=True, policies_applied=5, policies_failed=0, sync_time=datetime.utcnow()
        )

        assert result.success is True
        assert result.policies_applied == 5
        assert result.policies_failed == 0
        assert isinstance(result.sync_time, datetime)

    def test_service_mesh_status_health(self):
        healthy_status = ServiceMeshStatus(
            mesh_type=MeshType.ISTIO, installed=True, health_status="healthy"
        )
        assert healthy_status.is_healthy is True

        unhealthy_status = ServiceMeshStatus(
            mesh_type=MeshType.ISTIO, installed=True, health_status="degraded"
        )
        assert unhealthy_status.is_healthy is False

        not_installed_status = ServiceMeshStatus(
            mesh_type=MeshType.ISTIO, installed=False, health_status="healthy"
        )
        assert not_installed_status.is_healthy is False

    def test_service_mesh_metrics_calculations(self):
        metrics = ServiceMeshMetrics(
            total_policies=10,
            applied_policies=8,
            sync_operations=5,
            successful_syncs=4,
            mtls_connections=80,
            non_mtls_connections=20,
        )

        assert metrics.policy_success_rate == 80.0
        assert metrics.sync_success_rate == 80.0
        assert metrics.mtls_adoption_rate == 80.0

    def test_service_mesh_metrics_zero_division(self):
        metrics = ServiceMeshMetrics()

        assert metrics.policy_success_rate == 0.0
        assert metrics.sync_success_rate == 0.0
        assert metrics.mtls_adoption_rate == 0.0
