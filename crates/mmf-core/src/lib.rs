//! Stable, dependency-light contracts shared by every MMF service and adapter.

#![forbid(unsafe_code)]

mod json;
mod matching;
mod secret;
pub use json::{JsonObjectOrder, spaced_json};

pub use matching::wildcard_matches;
pub use secret::constant_time_secret_eq;

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

/// Stable machine-readable error categories used across transports.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    InvalidInput,
    InvalidState,
    Configuration,
    Unauthorized,
    Forbidden,
    NotFound,
    Conflict,
    DependencyUnavailable,
    Internal,
}

/// Canonical framework error. Transport crates map this to HTTP/gRPC details.
#[derive(Clone, Debug, Deserialize, Eq, Error, PartialEq, Serialize)]
#[error("{code:?}: {message}")]
pub struct MmfError {
    pub code: ErrorCode,
    pub message: String,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub details: BTreeMap<String, String>,
}

impl MmfError {
    #[must_use]
    pub fn new(code: ErrorCode, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            details: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn with_detail(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.details.insert(key.into(), value.into());
        self
    }
}

/// Runtime lifecycle shared by services and plugins.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LifecycleState {
    Created,
    Initialized,
    Starting,
    Active,
    Draining,
    Stopped,
    Failed,
}

impl LifecycleState {
    #[must_use]
    pub const fn can_transition_to(self, next: Self) -> bool {
        matches!(
            (self, next),
            (Self::Created, Self::Initialized | Self::Failed)
                | (
                    Self::Initialized,
                    Self::Starting | Self::Stopped | Self::Failed
                )
                | (Self::Starting, Self::Active | Self::Failed)
                | (Self::Active, Self::Draining | Self::Failed)
                | (Self::Draining, Self::Stopped | Self::Failed)
                | (Self::Stopped, Self::Starting)
                | (Self::Failed, Self::Stopped)
        )
    }

    pub fn transition_to(&mut self, next: Self) -> Result<(), MmfError> {
        if !self.can_transition_to(next) {
            return Err(MmfError::new(
                ErrorCode::InvalidState,
                format!("invalid lifecycle transition from {self:?} to {next:?}"),
            ));
        }
        *self = next;
        Ok(())
    }
}

/// Ordered health states. Aggregation always chooses the least healthy state.
#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Unknown,
    Unhealthy,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ComponentHealth {
    pub status: HealthStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct HealthReport {
    pub status: HealthStatus,
    #[serde(default)]
    pub components: BTreeMap<String, ComponentHealth>,
}

impl HealthReport {
    #[must_use]
    pub fn from_components(components: BTreeMap<String, ComponentHealth>) -> Self {
        let status = components
            .values()
            .map(|component| component.status)
            .max()
            .unwrap_or(HealthStatus::Unknown);
        Self { status, components }
    }

    #[must_use]
    pub const fn is_available(&self) -> bool {
        matches!(self.status, HealthStatus::Healthy | HealthStatus::Degraded)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct BuildInfo {
    pub service: String,
    pub version: String,
    pub build_revision: String,
    #[serde(default)]
    pub enabled_features: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RequestContext {
    pub request_id: Uuid,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub correlation_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tenant_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subject_id: Option<String>,
}

impl Default for RequestContext {
    fn default() -> Self {
        Self {
            request_id: Uuid::new_v4(),
            correlation_id: None,
            tenant_id: None,
            subject_id: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{ComponentHealth, HealthReport, HealthStatus, LifecycleState};
    use serde::Deserialize;
    use std::collections::BTreeMap;

    #[derive(Deserialize)]
    struct LifecycleFixture {
        valid_transitions: Vec<(LifecycleState, LifecycleState)>,
        invalid_transitions: Vec<(LifecycleState, LifecycleState)>,
        aggregate_health: Vec<HealthFixture>,
    }

    #[derive(Deserialize)]
    struct HealthFixture {
        components: Vec<HealthStatus>,
        expected: HealthStatus,
    }

    #[test]
    fn language_neutral_lifecycle_contract() {
        let fixture: LifecycleFixture =
            serde_json::from_str(include_str!("../../../contracts/core-lifecycle.json"))
                .expect("valid lifecycle fixture");

        for (current, next) in fixture.valid_transitions {
            assert!(current.can_transition_to(next), "{current:?} -> {next:?}");
        }
        for (current, next) in fixture.invalid_transitions {
            assert!(!current.can_transition_to(next), "{current:?} -> {next:?}");
        }

        for (index, case) in fixture.aggregate_health.into_iter().enumerate() {
            let components = case
                .components
                .into_iter()
                .enumerate()
                .map(|(component_index, status)| {
                    (
                        format!("component-{component_index}"),
                        ComponentHealth {
                            status,
                            message: None,
                        },
                    )
                })
                .collect::<BTreeMap<_, _>>();
            assert_eq!(
                HealthReport::from_components(components).status,
                case.expected,
                "health case {index}"
            );
        }
    }
}
