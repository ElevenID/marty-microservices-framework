from datetime import datetime

import pytest

from mmf.core.security.domain.models.service_mesh import (
    MeshType,
    MTLSMode,
    NetworkSegment,
    PolicyType,
    ServiceMeshConfiguration,
    ServiceMeshMetrics,
    ServiceMeshPolicy,
    ServiceMeshStatus,
    TrafficAction,
)


class TestServiceMeshPolicy:
    def test_authorization_policy_manifest(self):
        policy = ServiceMeshPolicy(
            name="test-authz",
            policy_type=PolicyType.AUTHORIZATION,
            namespace="default",
            description="Test policy",
            selector={"app": "test-app"},
            rules=[{"from": [{"source": {"principals": ["cluster.local/ns/default/sa/admin"]}}]}],
            action=TrafficAction.ALLOW,
        )

        manifest = policy.to_kubernetes_manifest()
        assert manifest["apiVersion"] == "security.istio.io/v1beta1"
        assert manifest["kind"] == "AuthorizationPolicy"
        assert manifest["metadata"]["name"] == "test-authz"
        assert manifest["spec"]["selector"]["matchLabels"] == {"app": "test-app"}
        assert manifest["spec"]["action"] == "ALLOW"
        assert len(manifest["spec"]["rules"]) == 1

    def test_peer_authentication_manifest(self):
        policy = ServiceMeshPolicy(
            name="test-peer-auth",
            policy_type=PolicyType.PEER_AUTHENTICATION,
            namespace="default",
            description="mTLS policy",
            metadata={"mtls_mode": "STRICT"},
        )

        manifest = policy.to_kubernetes_manifest()
        assert manifest["kind"] == "PeerAuthentication"
        assert manifest["spec"]["mtls"]["mode"] == "STRICT"


class TestNetworkSegment:
    def test_network_segment_to_network_policy(self):
        segment = NetworkSegment(
            name="backend",
            namespace="prod",
            services=["api", "db"],
            ingress_rules=[{"from": [{"podSelector": {"matchLabels": {"role": "frontend"}}}]}],
            egress_rules=[{"to": [{"ipBlock": {"cidr": "10.0.0.0/24"}}]}],
        )

        policy = segment.to_network_policy()
        assert policy.policy_type == PolicyType.NETWORK_POLICY
        assert policy.namespace == "prod"
        assert policy.selector == {"marty.io/segment": "backend"}
        assert "ingress" in policy.rules
        assert "egress" in policy.rules

    def test_network_segment_to_authorization_policies(self):
        segment = NetworkSegment(
            name="backend",
            namespace="prod",
            services=["api", "db"],
            allowed_sources=["cluster.local/ns/prod/sa/frontend"],
        )

        policies = segment.to_authorization_policies()
        assert len(policies) == 2
        assert policies[0].policy_type == PolicyType.AUTHORIZATION
        assert policies[0].selector["app"] == "api"
        assert policies[1].selector["app"] == "db"
        assert policies[0].rules[0]["from"][0]["source"]["principals"] == [
            "cluster.local/ns/prod/sa/frontend"
        ]


class TestServiceMeshConfiguration:
    def test_defaults(self):
        config = ServiceMeshConfiguration()
        assert config.mesh_type == MeshType.ISTIO
        assert config.namespace == "default"
        assert config.mtls_mode == MTLSMode.STRICT
        assert config.enable_policy_sync is True


class TestServiceMeshStatus:
    def test_is_healthy(self):
        status = ServiceMeshStatus(
            mesh_type=MeshType.ISTIO, installed=True, health_status="healthy"
        )
        assert status.is_healthy

    def test_is_not_healthy(self):
        status = ServiceMeshStatus(
            mesh_type=MeshType.ISTIO, installed=True, health_status="degraded"
        )
        assert not status.is_healthy

        status_not_installed = ServiceMeshStatus(
            mesh_type=MeshType.ISTIO, installed=False, health_status="healthy"
        )
        assert not status_not_installed.is_healthy


class TestServiceMeshMetrics:
    def test_metrics_calculations(self):
        metrics = ServiceMeshMetrics(
            sync_operations=10,
            successful_syncs=8,
            total_policies=20,
            applied_policies=15,
            mtls_connections=80,
            non_mtls_connections=20,
        )

        assert metrics.sync_success_rate == 80.0
        assert metrics.policy_success_rate == 75.0
        assert metrics.mtls_adoption_rate == 80.0

    def test_empty_metrics(self):
        metrics = ServiceMeshMetrics()
        assert metrics.sync_success_rate == 0.0
        assert metrics.policy_success_rate == 0.0
        assert metrics.mtls_adoption_rate == 0.0
