//! Shared lifecycle, health, readiness, and version HTTP surface for MMF services.

#![forbid(unsafe_code)]

pub mod managed_task;
mod shutdown;

pub use shutdown::{shutdown_signal, shutdown_signal_best_effort, wait_for_shutdown};
mod native_backend;
pub use native_backend::{NativeBackendDiagnostics, native_backend_router};
mod services;

pub use services::*;

use std::{
    collections::{BTreeMap, BTreeSet},
    sync::{Arc, RwLock},
};

use axum::{
    Json, Router,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::get,
};
use mmf_core::{
    BuildInfo, ComponentHealth, ErrorCode, HealthReport, HealthStatus, LifecycleState, MmfError,
};
use serde::Serialize;
use serde_json::Value;

/// Converts the canonical health report into a consumer-compatible JSON body.
///
/// The projector controls representation only. MMF continues to own the HTTP
/// status code so an unhealthy service cannot be made available by an adapter.
pub type HealthProjector = fn(&HealthReport) -> Value;

#[derive(Clone, Copy, Debug, Default)]
pub struct SystemRouteOptions {
    health_projector: Option<HealthProjector>,
}

impl SystemRouteOptions {
    #[must_use]
    pub const fn with_health_projector(mut self, projector: HealthProjector) -> Self {
        self.health_projector = Some(projector);
        self
    }
}

#[derive(Clone)]
struct SystemRouteState {
    runtime: RuntimeState,
    options: SystemRouteOptions,
}

#[derive(Clone)]
pub struct RuntimeState {
    inner: Arc<RwLock<RuntimeInner>>,
}

struct RuntimeInner {
    build: BuildInfo,
    lifecycle: LifecycleState,
    components: BTreeMap<String, ComponentHealth>,
    required_components: BTreeSet<String>,
}

#[derive(Debug, Serialize)]
pub struct ReadinessReport {
    pub ready: bool,
    pub lifecycle: LifecycleState,
    pub health: HealthStatus,
    pub required_components_healthy: bool,
}

impl RuntimeState {
    #[must_use]
    pub fn new(build: BuildInfo) -> Self {
        Self {
            inner: Arc::new(RwLock::new(RuntimeInner {
                build,
                lifecycle: LifecycleState::Created,
                components: BTreeMap::new(),
                required_components: BTreeSet::new(),
            })),
        }
    }

    pub fn transition(&self, next: LifecycleState) -> Result<(), MmfError> {
        let mut inner = self
            .inner
            .write()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))?;
        if next == LifecycleState::Active && !required_components_healthy(&inner) {
            return Err(MmfError::new(
                ErrorCode::DependencyUnavailable,
                "required runtime components are not healthy",
            )
            .with_detail(
                "components",
                unhealthy_required_components(&inner).join(","),
            ));
        }
        inner.lifecycle.transition_to(next)
    }

    pub fn register_required_component(&self, name: impl Into<String>) -> Result<(), MmfError> {
        let name = name.into();
        let name = component_name(&name)?;
        let mut inner = self
            .inner
            .write()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))?;
        inner.required_components.insert(name.clone());
        inner.components.entry(name).or_insert(ComponentHealth {
            status: HealthStatus::Unknown,
            message: Some("component has not completed its health check".into()),
        });
        Ok(())
    }

    pub fn register_optional_component(&self, name: impl Into<String>) -> Result<(), MmfError> {
        let name = name.into();
        let name = component_name(&name)?;
        self.inner
            .write()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))?
            .components
            .entry(name)
            .or_insert(ComponentHealth {
                status: HealthStatus::Unknown,
                message: Some("component has not completed its health check".into()),
            });
        Ok(())
    }

    pub fn set_component_health(
        &self,
        name: impl Into<String>,
        health: ComponentHealth,
    ) -> Result<(), MmfError> {
        self.inner
            .write()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))?
            .components
            .insert(name.into(), health);
        Ok(())
    }

    pub fn health(&self) -> Result<HealthReport, MmfError> {
        let inner = self
            .inner
            .read()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))?;
        Ok(HealthReport::from_components(inner.components.clone()))
    }

    pub fn readiness(&self) -> Result<ReadinessReport, MmfError> {
        let inner = self
            .inner
            .read()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))?;
        let health = HealthReport::from_components(inner.components.clone()).status;
        let required_components_healthy = required_components_healthy(&inner);
        Ok(ReadinessReport {
            ready: inner.lifecycle == LifecycleState::Active
                && required_components_healthy
                && matches!(health, HealthStatus::Healthy | HealthStatus::Degraded),
            lifecycle: inner.lifecycle,
            health,
            required_components_healthy,
        })
    }

    pub fn build_info(&self) -> Result<BuildInfo, MmfError> {
        self.inner
            .read()
            .map(|inner| inner.build.clone())
            .map_err(|_| MmfError::new(ErrorCode::Internal, "runtime lock poisoned"))
    }
}

fn component_name(name: &str) -> Result<String, MmfError> {
    let name = name.trim();
    if name.is_empty() || name.len() > 128 {
        return Err(MmfError::new(
            ErrorCode::InvalidInput,
            "component name must contain 1 to 128 characters",
        ));
    }
    Ok(name.to_owned())
}

fn required_components_healthy(inner: &RuntimeInner) -> bool {
    inner.required_components.iter().all(|name| {
        inner
            .components
            .get(name)
            .is_some_and(|health| health.status == HealthStatus::Healthy)
    })
}

fn unhealthy_required_components(inner: &RuntimeInner) -> Vec<String> {
    inner
        .required_components
        .iter()
        .filter(|name| {
            inner
                .components
                .get(*name)
                .is_none_or(|health| health.status != HealthStatus::Healthy)
        })
        .cloned()
        .collect()
}

pub fn system_router(state: RuntimeState) -> Router {
    system_router_with_options(state, SystemRouteOptions::default())
}

/// Creates the shared diagnostics router with optional representation adapters.
///
/// Lifecycle, readiness, availability, and error decisions always remain owned
/// by MMF. Options may only adapt successful response bodies for compatibility
/// with an existing service contract.
pub fn system_router_with_options(state: RuntimeState, options: SystemRouteOptions) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/ready", get(readiness))
        .route("/version", get(version))
        .with_state(SystemRouteState {
            runtime: state,
            options,
        })
}

async fn health(State(state): State<SystemRouteState>) -> Response {
    match state.runtime.health() {
        Ok(report) => {
            let status = if report.status == HealthStatus::Unhealthy {
                StatusCode::SERVICE_UNAVAILABLE
            } else {
                StatusCode::OK
            };
            match state.options.health_projector {
                Some(project) => (status, Json(project(&report))).into_response(),
                None => (status, Json(report)).into_response(),
            }
        }
        Err(error) => internal_error(error),
    }
}

async fn readiness(State(state): State<SystemRouteState>) -> Response {
    match state.runtime.readiness() {
        Ok(report) => {
            let status = if report.ready {
                StatusCode::OK
            } else {
                StatusCode::SERVICE_UNAVAILABLE
            };
            (status, Json(report)).into_response()
        }
        Err(error) => internal_error(error),
    }
}

async fn version(State(state): State<SystemRouteState>) -> Response {
    match state.runtime.build_info() {
        Ok(build) => (StatusCode::OK, Json(build)).into_response(),
        Err(error) => internal_error(error),
    }
}

fn internal_error(error: MmfError) -> Response {
    (StatusCode::INTERNAL_SERVER_ERROR, Json(error)).into_response()
}

#[cfg(test)]
mod tests {
    use axum::{body::Body, http::Request};
    use http_body_util::BodyExt;
    use mmf_core::{BuildInfo, ComponentHealth, HealthStatus, LifecycleState};
    use serde::Deserialize;
    use serde_json::{Value, json};
    use tower::ServiceExt;

    use super::{RuntimeState, SystemRouteOptions, system_router, system_router_with_options};

    #[derive(Deserialize)]
    struct ProjectionFixture {
        default_body: Value,
        projected_body: Value,
        healthy_status: u16,
        unhealthy_status: u16,
    }

    fn projection_fixture() -> ProjectionFixture {
        serde_json::from_str(include_str!(
            "../../../contracts/system-route-projection.json"
        ))
        .expect("valid system-route projection fixture")
    }

    fn legacy_health(_report: &mmf_core::HealthReport) -> Value {
        json!({"status": "healthy", "service": "issuance-service"})
    }

    async fn response_json(response: axum::response::Response) -> Value {
        serde_json::from_slice(
            &response
                .into_body()
                .collect()
                .await
                .expect("body")
                .to_bytes(),
        )
        .expect("json")
    }

    fn runtime() -> RuntimeState {
        RuntimeState::new(BuildInfo {
            service: "contract-service".to_owned(),
            version: "1.2.3".to_owned(),
            build_revision: "abc123".to_owned(),
            enabled_features: vec!["http".to_owned()],
        })
    }

    #[tokio::test]
    async fn readiness_fails_closed_until_active_and_healthy() {
        let state = runtime();
        let router = system_router(state.clone());
        let unavailable = router
            .clone()
            .oneshot(Request::get("/ready").body(Body::empty()).expect("request"))
            .await
            .expect("response");
        assert_eq!(unavailable.status(), 503);

        state
            .transition(LifecycleState::Initialized)
            .expect("initialize");
        state.transition(LifecycleState::Starting).expect("start");
        state.transition(LifecycleState::Active).expect("active");
        state
            .set_component_health(
                "database",
                ComponentHealth {
                    status: HealthStatus::Healthy,
                    message: None,
                },
            )
            .expect("health");

        let available = router
            .oneshot(Request::get("/ready").body(Body::empty()).expect("request"))
            .await
            .expect("response");
        assert_eq!(available.status(), 200);
        let body: Value = serde_json::from_slice(
            &available
                .into_body()
                .collect()
                .await
                .expect("body")
                .to_bytes(),
        )
        .expect("json");
        assert_eq!(body["ready"], true);
        assert_eq!(body["lifecycle"], "active");
        assert_eq!(body["required_components_healthy"], true);
    }

    #[tokio::test]
    async fn default_health_representation_is_unchanged() {
        let fixture = projection_fixture();
        let response = system_router(runtime())
            .oneshot(
                Request::get("/health")
                    .body(Body::empty())
                    .expect("request"),
            )
            .await
            .expect("response");

        assert_eq!(response.status(), fixture.healthy_status);
        assert_eq!(response_json(response).await, fixture.default_body);
    }

    #[tokio::test]
    async fn health_projection_preserves_framework_status_semantics() {
        let fixture = projection_fixture();
        let state = runtime();
        let router = system_router_with_options(
            state.clone(),
            SystemRouteOptions::default().with_health_projector(legacy_health),
        );

        let healthy = router
            .clone()
            .oneshot(
                Request::get("/health")
                    .body(Body::empty())
                    .expect("request"),
            )
            .await
            .expect("response");
        assert_eq!(healthy.status(), fixture.healthy_status);
        assert_eq!(response_json(healthy).await, fixture.projected_body);

        state
            .set_component_health(
                "database",
                ComponentHealth {
                    status: HealthStatus::Unhealthy,
                    message: Some("connection lost".into()),
                },
            )
            .expect("health");
        let unhealthy = router
            .oneshot(
                Request::get("/health")
                    .body(Body::empty())
                    .expect("request"),
            )
            .await
            .expect("response");
        assert_eq!(unhealthy.status(), fixture.unhealthy_status);
        assert_eq!(response_json(unhealthy).await, fixture.projected_body);
    }

    #[tokio::test]
    async fn health_projection_does_not_change_readiness_or_version() {
        let state = runtime();
        state
            .set_component_health(
                "http",
                ComponentHealth {
                    status: HealthStatus::Healthy,
                    message: None,
                },
            )
            .expect("health");
        state
            .transition(LifecycleState::Initialized)
            .expect("initialize");
        state.transition(LifecycleState::Starting).expect("start");
        state.transition(LifecycleState::Active).expect("active");
        let router = system_router_with_options(
            state,
            SystemRouteOptions::default().with_health_projector(legacy_health),
        );

        let ready = router
            .clone()
            .oneshot(Request::get("/ready").body(Body::empty()).expect("request"))
            .await
            .expect("response");
        assert_eq!(ready.status(), 200);
        assert_eq!(response_json(ready).await["ready"], true);

        let version = router
            .oneshot(
                Request::get("/version")
                    .body(Body::empty())
                    .expect("request"),
            )
            .await
            .expect("response");
        assert_eq!(version.status(), 200);
        let body = response_json(version).await;
        assert_eq!(body["service"], "contract-service");
        assert_eq!(body["version"], "1.2.3");
        assert_eq!(body["build_revision"], "abc123");
    }

    #[tokio::test]
    async fn required_components_gate_activation_and_live_readiness() {
        let state = runtime();
        state
            .register_required_component("database")
            .expect("database");
        state
            .register_required_component("policy-provider")
            .expect("provider");
        state
            .register_optional_component("telemetry")
            .expect("telemetry");
        state
            .transition(LifecycleState::Initialized)
            .expect("initialize");
        state.transition(LifecycleState::Starting).expect("start");
        let error = state
            .transition(LifecycleState::Active)
            .expect_err("unknown dependency must block activation");
        assert_eq!(error.code, mmf_core::ErrorCode::DependencyUnavailable);
        assert_eq!(error.details["components"], "database,policy-provider");

        for component in ["database", "policy-provider"] {
            state
                .set_component_health(
                    component,
                    ComponentHealth {
                        status: HealthStatus::Healthy,
                        message: None,
                    },
                )
                .expect("health");
        }
        state
            .set_component_health(
                "telemetry",
                ComponentHealth {
                    status: HealthStatus::Degraded,
                    message: Some("export is delayed".into()),
                },
            )
            .expect("optional health");
        state.transition(LifecycleState::Active).expect("active");
        assert!(state.readiness().expect("ready").ready);

        state
            .set_component_health(
                "policy-provider",
                ComponentHealth {
                    status: HealthStatus::Degraded,
                    message: Some("connection lost".into()),
                },
            )
            .expect("degraded");
        let readiness = state.readiness().expect("readiness");
        assert!(!readiness.ready);
        assert!(!readiness.required_components_healthy);
        assert_eq!(readiness.lifecycle, LifecycleState::Active);
    }

    #[test]
    fn component_registration_rejects_ambiguous_names() {
        let state = runtime();
        assert!(state.register_required_component(" ").is_err());
        assert!(state.register_optional_component("x".repeat(129)).is_err());
    }
}
