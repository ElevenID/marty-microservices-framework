//! Small shared security contracts that do not require policy, Redis, or crypto implementations.

#![forbid(unsafe_code)]

use std::collections::{BTreeMap, BTreeSet};

use async_trait::async_trait;
use mmf_core::{ErrorCode, MmfError};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum SecurityError {
    #[error("invalid security configuration: {0}")]
    InvalidConfiguration(String),
    #[error("required native security provider is unavailable: {0}")]
    ProviderUnavailable(String),
    #[error("security operation is unauthorized: {0}")]
    Unauthorized(String),
    #[error("security state conflict: {0}")]
    Conflict(String),
    #[error("security record was not found: {0}")]
    NotFound(String),
    #[error("invalid identity: {0}")]
    InvalidIdentity(String),
    #[error("invalid authentication result")]
    InvalidAuthenticationResult,
    #[error("authentication failed: {0}")]
    Authentication(String),
    #[error("authorization denied: {0}")]
    Authorization(String),
    #[error("invalid policy: {0}")]
    InvalidPolicy(String),
    #[error("invalid rate-limit rule: {0}")]
    InvalidRateLimitRule(String),
    #[error("rate limit exceeded")]
    RateLimitExceeded,
    #[error("invalid session state")]
    InvalidSessionState,
    #[error("invalid session configuration")]
    InvalidSessionConfiguration,
    #[error("session limit exceeded")]
    SessionLimitExceeded,
    #[error("session already exists")]
    SessionAlreadyExists,
    #[error("session not found")]
    SessionNotFound,
    #[error("invalid threat score")]
    InvalidThreatScore,
    #[error("invalid threat rule: {0}")]
    InvalidThreatRule(String),
    #[error("threat detection failed: {0}")]
    ThreatDetection(String),
    #[error("KMS operation failed: {0}")]
    Kms(String),
    #[error("MFA operation failed: {0}")]
    Mfa(String),
    #[error("secret manager failed: {0}")]
    Secret(String),
    #[error("audit failed: {0}")]
    Audit(String),
    #[error("service mesh operation failed: {0}")]
    ServiceMesh(String),
    #[error("required security providers unavailable: {0:?}")]
    RequiredProvidersUnavailable(Vec<&'static str>),
}

impl From<SecurityError> for MmfError {
    fn from(error: SecurityError) -> Self {
        let code = match error {
            SecurityError::Authentication(_)
            | SecurityError::Unauthorized(_)
            | SecurityError::InvalidAuthenticationResult => ErrorCode::Unauthorized,
            SecurityError::Authorization(_) => ErrorCode::Forbidden,
            SecurityError::RequiredProvidersUnavailable(_)
            | SecurityError::ProviderUnavailable(_) => ErrorCode::DependencyUnavailable,
            SecurityError::RateLimitExceeded | SecurityError::Conflict(_) => ErrorCode::Conflict,
            SecurityError::SessionNotFound | SecurityError::NotFound(_) => ErrorCode::NotFound,
            _ => ErrorCode::InvalidInput,
        };
        MmfError::new(code, error.to_string())
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MeshType {
    Istio,
    Linkerd,
    Consul,
    Kuma,
    None,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MtlsMode {
    Strict,
    Permissive,
    Disabled,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ServiceMeshPolicy {
    pub name: String,
    pub source_identities: BTreeSet<String>,
    pub destination_services: BTreeSet<String>,
    pub allowed_methods: BTreeSet<String>,
    pub allowed_paths: BTreeSet<String>,
    pub mtls_mode: MtlsMode,
    #[serde(default)]
    pub rate_limit_rule: Option<String>,
}

#[async_trait]
pub trait ServiceMeshManager: Send + Sync {
    async fn apply_policy(&self, policy: &ServiceMeshPolicy) -> Result<(), SecurityError>;
    async fn remove_policy(&self, name: &str) -> Result<(), SecurityError>;
    async fn list_policies(&self) -> Result<Vec<ServiceMeshPolicy>, SecurityError>;
    async fn health(&self) -> Result<BTreeMap<String, String>, SecurityError>;
}
