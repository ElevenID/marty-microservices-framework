//! Canonical service-platform primitives for MMF.
//!
//! Gateway services, discovery clients, mesh managers, and deployment tools
//! compose these types instead of carrying service-local route matchers, load
//! balancers, health state, or deployment models.

#![forbid(unsafe_code)]

mod client;
mod deployment;
mod discovery;
mod gateway;
mod grpc;
mod http;
mod ports;
mod proxy;

pub use client::*;
pub use deployment::*;
pub use discovery::*;
pub use gateway::*;
pub use grpc::*;
pub use http::*;
pub use mmf_security_contracts::{MeshType, ServiceMeshManager, ServiceMeshPolicy};
pub use ports::*;
pub use proxy::*;

use mmf_core::{ErrorCode, MmfError};
use thiserror::Error;

#[derive(Clone, Debug, Eq, Error, PartialEq)]
pub enum PlatformError {
    #[error("invalid platform configuration: {0}")]
    InvalidConfiguration(String),
    #[error("service not found: {0}")]
    ServiceNotFound(String),
    #[error("no healthy service instance is available: {0}")]
    NoHealthyInstance(String),
    #[error("route not found for {method} {path}")]
    RouteNotFound { method: String, path: String },
    #[error("platform provider is unavailable: {0}")]
    ProviderUnavailable(String),
    #[error("platform state conflict: {0}")]
    Conflict(String),
    #[error("platform operation failed: {0}")]
    Operation(String),
    #[error("upstream request timed out: {0}")]
    UpstreamTimeout(String),
    #[error("upstream transport failed: {0}")]
    UpstreamTransport(String),
}

impl From<PlatformError> for MmfError {
    fn from(error: PlatformError) -> Self {
        let code = match &error {
            PlatformError::InvalidConfiguration(_) => ErrorCode::Configuration,
            PlatformError::ServiceNotFound(_) | PlatformError::RouteNotFound { .. } => {
                ErrorCode::NotFound
            }
            PlatformError::NoHealthyInstance(_)
            | PlatformError::ProviderUnavailable(_)
            | PlatformError::UpstreamTimeout(_)
            | PlatformError::UpstreamTransport(_) => ErrorCode::DependencyUnavailable,
            PlatformError::Conflict(_) => ErrorCode::Conflict,
            PlatformError::Operation(_) => ErrorCode::Internal,
        };
        MmfError::new(code, error.to_string())
    }
}

#[cfg(test)]
mod tests {
    use std::collections::{BTreeMap, BTreeSet};

    use serde::Deserialize;

    use super::*;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        endpoints: Vec<EndpointCase>,
        route_matches: Vec<RouteCase>,
        load_balancing: LoadBalancingCase,
        deployment: DeploymentCase,
    }

    #[derive(Deserialize)]
    struct EndpointCase {
        host: String,
        port: u16,
        protocol: EndpointProtocol,
        path: String,
        url: String,
    }

    #[derive(Deserialize)]
    struct RouteCase {
        match_type: RouteMatchType,
        pattern: String,
        path: String,
        matched: bool,
        params: BTreeMap<String, String>,
    }

    #[derive(Deserialize)]
    struct LoadBalancingCase {
        instances: Vec<InstanceCase>,
        round_robin_sequence: Vec<String>,
        least_connections: String,
        same_zone: String,
        same_region: String,
    }

    #[derive(Deserialize)]
    struct InstanceCase {
        id: String,
        host: String,
        weight: u32,
        connections: u32,
        region: String,
        zone: String,
    }

    #[derive(Deserialize)]
    struct DeploymentCase {
        statuses: Vec<DeploymentStatus>,
        strategies: Vec<DeploymentStrategy>,
        production_requires_digest: bool,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!("../../../contracts/platform-behavior.json"))
            .expect("valid platform behavior fixture")
    }

    fn instances(case: &[InstanceCase]) -> Vec<ServiceInstance> {
        case.iter()
            .map(|item| {
                let mut instance = ServiceInstance::new(
                    "gateway",
                    ServiceEndpoint {
                        host: item.host.clone(),
                        port: 8080,
                        protocol: EndpointProtocol::Http,
                        path: String::new(),
                        verify_tls: true,
                        connect_timeout_ms: 5_000,
                        read_timeout_ms: 30_000,
                    },
                    0,
                )
                .expect("instance");
                instance.instance_id.clone_from(&item.id);
                instance.metadata.weight = item.weight;
                instance.metadata.region.clone_from(&item.region);
                instance.metadata.availability_zone.clone_from(&item.zone);
                instance.active_connections = item.connections;
                instance
            })
            .collect()
    }

    #[test]
    fn language_neutral_endpoint_contract() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        for case in fixture.endpoints {
            let endpoint = ServiceEndpoint {
                host: case.host,
                port: case.port,
                protocol: case.protocol,
                path: case.path,
                verify_tls: true,
                connect_timeout_ms: 5_000,
                read_timeout_ms: 30_000,
            };
            endpoint.validate().expect("endpoint");
            assert_eq!(endpoint.url(), case.url);
        }
    }

    #[test]
    fn language_neutral_route_matching_contract() {
        for case in fixture().route_matches {
            let result = match_path(case.match_type, &case.pattern, &case.path).expect("match");
            assert_eq!(result.is_some(), case.matched);
            assert_eq!(result.unwrap_or_default(), case.params);
        }
    }

    #[test]
    fn language_neutral_load_balancing_contract() {
        let case = fixture().load_balancing;
        let instances = instances(&case.instances);
        let mut balancer = LoadBalancer::default();
        let mut sequence = Vec::new();
        for _ in &case.round_robin_sequence {
            sequence.push(
                balancer
                    .select(
                        "gateway",
                        LoadBalancingStrategy::RoundRobin,
                        &instances,
                        &LoadBalancingContext::default(),
                    )
                    .expect("round robin")
                    .instance_id,
            );
        }
        assert_eq!(sequence, case.round_robin_sequence);
        assert_eq!(
            balancer
                .select(
                    "gateway",
                    LoadBalancingStrategy::LeastConnections,
                    &instances,
                    &LoadBalancingContext::default(),
                )
                .expect("least connections")
                .instance_id,
            case.least_connections
        );
        assert_eq!(
            balancer
                .select(
                    "gateway",
                    LoadBalancingStrategy::LocalityAware,
                    &instances,
                    &LoadBalancingContext {
                        preferred_zone: Some("us-east-1a".into()),
                        preferred_region: Some("us-east-1".into()),
                        ..LoadBalancingContext::default()
                    },
                )
                .expect("same zone")
                .instance_id,
            case.same_zone
        );
        assert_eq!(
            balancer
                .select(
                    "gateway",
                    LoadBalancingStrategy::LocalityAware,
                    &instances[1..],
                    &LoadBalancingContext {
                        preferred_zone: Some("missing".into()),
                        preferred_region: Some("us-east-1".into()),
                        ..LoadBalancingContext::default()
                    },
                )
                .expect("same region")
                .instance_id,
            case.same_region
        );
    }

    fn deployment_config(environment: EnvironmentType) -> DeploymentConfig {
        DeploymentConfig {
            service_name: "gateway".into(),
            image: "registry.example/gateway:v1".into(),
            image_digest: None,
            target: DeploymentTarget {
                provider: InfrastructureProvider::Kubernetes,
                environment,
                cluster: "beta".into(),
                namespace: "marty-beta".into(),
                region: Some("us-east-1".into()),
                account_id: None,
            },
            strategy: DeploymentStrategy::RollingUpdate,
            resources: ResourceRequirements {
                cpu_request_millicores: 100,
                cpu_limit_millicores: 500,
                memory_request_mebibytes: 128,
                memory_limit_mebibytes: 512,
                minimum_replicas: 1,
                maximum_replicas: 3,
            },
            ports: BTreeMap::from([("http".into(), 8080)]),
            environment: BTreeMap::new(),
            secret_references: BTreeMap::new(),
            labels: BTreeMap::from([("app.kubernetes.io/part-of".into(), "marty".into())]),
            readiness: DeploymentHealthCheck {
                path: "/ready".into(),
                port: 8080,
                initial_delay_seconds: 2,
                period_seconds: 10,
                timeout_seconds: 2,
                failure_threshold: 3,
            },
            liveness: DeploymentHealthCheck {
                path: "/health".into(),
                port: 8080,
                initial_delay_seconds: 5,
                period_seconds: 10,
                timeout_seconds: 2,
                failure_threshold: 3,
            },
            service_account: Some("gateway".into()),
        }
    }

    #[test]
    fn deployment_contract_and_manifest_are_fail_closed() {
        let case = fixture().deployment;
        assert!(case.statuses.contains(&DeploymentStatus::Deployed));
        assert!(case.strategies.contains(&DeploymentStrategy::Canary));
        assert!(case.production_requires_digest);
        assert!(
            deployment_config(EnvironmentType::Beta)
                .kubernetes_manifest()
                .is_ok()
        );
        assert!(
            deployment_config(EnvironmentType::Production)
                .validate()
                .is_err()
        );
        let mut pinned = deployment_config(EnvironmentType::Production);
        pinned.image_digest = Some("sha256:abc".into());
        let manifest = pinned.kubernetes_manifest().expect("manifest");
        assert!(manifest.contains("registry.example/gateway:v1@sha256:abc"));
    }

    #[test]
    fn route_table_honors_method_host_headers_and_priority() {
        let mut table = RouteTable::default();
        table
            .add(RouteConfig {
                name: "users".into(),
                pattern: "/users/{id}".into(),
                match_type: RouteMatchType::Template,
                upstream_service: "users".into(),
                methods: BTreeSet::from([HttpMethod::Get]),
                host: Some("api.example".into()),
                required_headers: BTreeMap::from([("x-api-version".into(), "1".into())]),
                rewrite_path: None,
                timeout_ms: 30_000,
                retries: 3,
                auth_required: true,
                authentication_type: AuthenticationType::Jwt,
                priority: 100,
                tags: BTreeSet::new(),
            })
            .expect("route");
        let mut request = GatewayRequest::new(HttpMethod::Get, "/users/123", 0);
        request.headers.insert("Host".into(), "api.example".into());
        request.headers.insert("X-API-Version".into(), "1".into());
        assert_eq!(
            table.find(&request).expect("match").params.get("id"),
            Some(&"123".to_owned())
        );
    }
}
