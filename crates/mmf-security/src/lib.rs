//! Canonical MMF security models, policy engines, state machines, and ports.
//!
//! Credential-protocol parsing, key generation, signatures, and certificate
//! kernels remain owned by `marty-core`. This crate owns reusable framework
//! security behavior, including RFC 6238 TOTP and fail-closed MFA composition.

#![forbid(unsafe_code)]

#[cfg(feature = "cedar")]
pub mod applicant_approval;
pub mod application_event;
mod authorization;
#[cfg(feature = "cedar")]
pub mod cedar;
#[cfg(feature = "cedar")]
pub mod credential_verification;
mod identity;
pub mod jwt_hmac;
pub mod managed_session;
pub mod mfa;
pub mod mtls;
pub mod oauth;
pub mod oidc;
mod policy;
mod providers;
mod rate_limit;
mod security_models;
pub mod security_pipeline;
pub mod session;
pub mod session_configuration;
pub mod session_events;
pub mod session_keys;
pub mod session_manager;
mod uri;
mod workload_identity;

use std::sync::Arc;

#[cfg(feature = "cedar")]
pub use applicant_approval::*;
pub use application_event::*;
pub use authorization::*;
#[cfg(feature = "cedar")]
pub use cedar::*;
#[cfg(feature = "cedar")]
pub use credential_verification::*;
pub use identity::*;
pub use managed_session::*;
pub use mfa::*;
use mmf_core::{ErrorCode, MmfError};
pub use mtls::*;
pub use oauth::*;
pub use oidc::*;
pub use policy::*;
pub use providers::*;
pub use rate_limit::*;
pub use security_models::*;
use serde::{Deserialize, Serialize};
pub use session::*;
pub use session_configuration::*;
pub use session_events::*;
pub use session_keys::*;
pub use session_manager::*;
use thiserror::Error;
pub use workload_identity::*;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SecurityLevel {
    Development,
    Standard,
    High,
    Critical,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
#[allow(clippy::struct_excessive_bools)]
pub struct SecurityConfig {
    pub level: SecurityLevel,
    pub authentication_required: bool,
    pub authorization_required: bool,
    pub session_required: bool,
    pub rate_limit_required: bool,
    pub audit_required: bool,
    pub threat_detection_required: bool,
    pub service_mesh_required: bool,
    pub kms_required: bool,
    pub mfa_required: bool,
    pub allowed_clock_skew_ms: u64,
    pub session: SessionConfiguration,
}

impl Default for SecurityConfig {
    fn default() -> Self {
        Self {
            level: SecurityLevel::Standard,
            authentication_required: true,
            authorization_required: true,
            session_required: true,
            rate_limit_required: true,
            audit_required: true,
            threat_detection_required: false,
            service_mesh_required: false,
            kms_required: false,
            mfa_required: false,
            allowed_clock_skew_ms: 30_000,
            session: SessionConfiguration::default(),
        }
    }
}

impl SecurityConfig {
    pub fn validate(&self) -> Result<(), SecurityError> {
        self.session.validate()
    }
}

/// Provider composition is explicit. Startup validation rejects any required
/// capability that was not installed.
#[derive(Default)]
pub struct SecurityProviders {
    pub authenticator: Option<Arc<dyn Authenticator>>,
    pub identity_provider: Option<Arc<dyn IdentityProvider>>,
    pub policy_provider: Option<Arc<dyn PolicyProvider>>,
    pub session_store: Option<Arc<dyn ManagedSessionStore>>,
    pub rate_limiter: Option<Arc<dyn DistributedRateLimiter>>,
    pub auditor: Option<Arc<dyn Auditor>>,
    pub threat_detector: Option<Arc<dyn ThreatDetector>>,
    pub vulnerability_scanner: Option<Arc<dyn VulnerabilityScanner>>,
    pub service_mesh: Option<Arc<dyn ServiceMeshManager>>,
    pub kms: Option<Arc<dyn KmsProvider>>,
    pub mfa: Option<Arc<dyn MfaProvider>>,
    pub secret_manager: Option<Arc<dyn SecretManager>>,
}

impl SecurityProviders {
    pub fn validate(&self, config: &SecurityConfig) -> Result<(), SecurityError> {
        config.validate()?;
        let mut missing = Vec::new();
        if config.authentication_required && self.authenticator.is_none() {
            missing.push("authenticator");
        }
        if config.authorization_required && self.policy_provider.is_none() {
            missing.push("policy_provider");
        }
        if config.session_required && self.session_store.is_none() {
            missing.push("session_store");
        }
        if config.rate_limit_required && self.rate_limiter.is_none() {
            missing.push("rate_limiter");
        }
        if config.audit_required && self.auditor.is_none() {
            missing.push("auditor");
        }
        if config.threat_detection_required && self.threat_detector.is_none() {
            missing.push("threat_detector");
        }
        if config.service_mesh_required && self.service_mesh.is_none() {
            missing.push("service_mesh");
        }
        if config.kms_required && self.kms.is_none() {
            missing.push("kms");
        }
        if config.mfa_required && self.mfa.is_none() {
            missing.push("mfa");
        }
        if missing.is_empty() {
            Ok(())
        } else {
            Err(SecurityError::RequiredProvidersUnavailable(missing))
        }
    }
}

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

#[cfg(test)]
mod tests {
    use std::collections::{BTreeMap, BTreeSet};

    use super::*;
    use serde_json::Value;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        user: UserFixture,
        rate_limit_keys: Vec<RateLimitKeyFixture>,
        fixed_window: FixedWindowFixture,
        session: SessionFixture,
        authorization: AuthorizationFixture,
    }

    #[derive(Deserialize)]
    struct UserFixture {
        user_id: String,
        roles: BTreeSet<String>,
        permissions: BTreeSet<String>,
        role_checks: BTreeMap<String, bool>,
        permission_checks: BTreeMap<String, bool>,
    }

    #[derive(Deserialize)]
    struct RateLimitKeyFixture {
        scope: RateLimitScope,
        user_id: Option<String>,
        ip_address: Option<String>,
        endpoint: Option<String>,
        service: Option<String>,
        expected: String,
    }

    #[derive(Deserialize)]
    struct FixedWindowFixture {
        limit: u64,
        window_ms: u64,
        timestamps_ms: Vec<u64>,
        allowed: Vec<bool>,
        remaining: Vec<u64>,
    }

    #[derive(Deserialize)]
    struct SessionFixture {
        created_at_ms: u64,
        last_accessed_ms: u64,
        default_timeout_ms: u64,
        max_timeout_ms: u64,
        idle_timeout_ms: u64,
        absolute_timeout_ms: u64,
        requested_timeout_ms: u64,
        now_ms: u64,
        expected_expiration_ms: u64,
        ip_violation: String,
        user_agent_violation: String,
    }

    #[derive(Deserialize)]
    struct AuthorizationFixture {
        default_decision: String,
        deny_overrides_allow: bool,
        wildcard_resource: String,
        matching_resource: String,
        non_matching_resource: String,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!("../../../contracts/security-behavior.json"))
            .expect("valid security fixture")
    }

    #[test]
    fn language_neutral_user_contract() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        let user = AuthenticatedUser {
            user_id: fixture.user.user_id,
            username: None,
            email: None,
            roles: fixture.user.roles,
            permissions: fixture.user.permissions,
            session_id: None,
            auth_method: None,
            expires_at_ms: None,
            created_at_ms: None,
            attributes: BTreeMap::new(),
            user_type: None,
            applicant_id: None,
        };
        for (role, expected) in fixture.user.role_checks {
            assert_eq!(user.has_role(&role), expected);
        }
        for (permission, expected) in fixture.user.permission_checks {
            assert_eq!(user.has_permission(&permission), expected);
        }
    }

    #[test]
    fn language_neutral_rate_limit_contract() {
        let fixture = fixture();
        for case in fixture.rate_limit_keys {
            let rule = RateLimitRule {
                name: "api".to_owned(),
                scope: case.scope,
                strategy: RateLimitStrategy::FixedWindow,
                limit: 1,
                window_ms: 1_000,
                burst_size: 0,
                enabled: true,
            };
            let quota = RateLimitQuota {
                user_id: case.user_id,
                ip_address: case.ip_address,
                endpoint: case.endpoint,
                service: case.service,
                custom_key: None,
            };
            assert_eq!(quota.cache_key(&rule), case.expected);
        }

        let case = fixture.fixed_window;
        let rule = RateLimitRule {
            name: "contract".to_owned(),
            scope: RateLimitScope::Global,
            strategy: RateLimitStrategy::FixedWindow,
            limit: case.limit,
            window_ms: case.window_ms,
            burst_size: 0,
            enabled: true,
        };
        let limiter = InMemoryRateLimiter::default();
        let quota = RateLimitQuota::default();
        for (index, now_ms) in case.timestamps_ms.into_iter().enumerate() {
            let result = limiter
                .check(&rule, &quota, now_ms)
                .expect("rate-limit check");
            assert_eq!(result.allowed, case.allowed[index]);
            assert_eq!(result.remaining, case.remaining[index]);
        }
    }

    #[test]
    fn language_neutral_session_contract() {
        let case = fixture().session;
        let timeout = SessionTimeout {
            idle_timeout_ms: case.idle_timeout_ms,
            absolute_timeout_ms: case.absolute_timeout_ms,
            extend_on_activity: true,
        };
        assert_eq!(
            session_expiration_at(
                timeout,
                case.created_at_ms,
                case.last_accessed_ms,
                case.now_ms,
                Some(case.requested_timeout_ms),
                case.default_timeout_ms,
                case.max_timeout_ms,
            )
            .expect("expiration"),
            case.expected_expiration_ms
        );
        let expected = SessionSecurityContext {
            ip_address: "192.0.2.1".into(),
            user_agent: Some("agent-a".into()),
            secure_connection: true,
            client_fingerprint: None,
            location_info: BTreeMap::new(),
            created_at_ms: 1,
        };
        let current = SessionSecurityContext {
            ip_address: "192.0.2.2".into(),
            user_agent: Some("agent-b".into()),
            ..expected.clone()
        };
        assert_eq!(
            session_security_violations(&expected, &current, true),
            vec![case.ip_violation, case.user_agent_violation]
        );
    }

    #[test]
    fn language_neutral_authorization_contract() {
        let case = fixture().authorization;
        assert_eq!(case.default_decision, "deny");
        assert!(case.deny_overrides_allow);
        let permission = Permission {
            resource: case.wildcard_resource,
            action: "read".to_owned(),
        };
        assert!(permission.matches(&case.matching_resource, "read"));
        assert!(!permission.matches(&case.non_matching_resource, "read"));

        let context = SecurityContext {
            principal: SecurityPrincipal {
                id: "user".to_owned(),
                principal_type: PrincipalType::User,
                roles: BTreeSet::new(),
                permissions: BTreeSet::new(),
                attributes: BTreeMap::new(),
                identity_provider: None,
                session_id: None,
                expires_at_ms: None,
            },
            resource: "credentials/123".to_owned(),
            action: "read".to_owned(),
            resource_attributes: BTreeMap::new(),
            environment: BTreeMap::from([(
                "network".to_owned(),
                Value::String("public".to_owned()),
            )]),
            request_metadata: BTreeMap::new(),
            request_id: None,
            timestamp_ms: 0,
        };
        let mut engine = AbacEngine::default();
        engine
            .replace_policies(vec![
                AbacPolicy {
                    id: "allow".to_owned(),
                    effect: PolicyEffect::Allow,
                    priority: 1,
                    enabled: true,
                    resources: vec!["credentials/*".to_owned()],
                    actions: vec!["read".to_owned()],
                    conditions: Vec::new(),
                },
                AbacPolicy {
                    id: "deny-public".to_owned(),
                    effect: PolicyEffect::Deny,
                    priority: 10,
                    enabled: true,
                    resources: vec!["credentials/*".to_owned()],
                    actions: vec!["read".to_owned()],
                    conditions: vec![AttributeCondition {
                        source: AttributeSource::Environment,
                        attribute: "network".to_owned(),
                        operator: ConditionOperator::Equal,
                        value: Value::String("public".to_owned()),
                    }],
                },
            ])
            .expect("valid policies");
        assert!(!engine.authorize(&context).allowed);
    }

    #[test]
    fn missing_required_providers_fail_closed() {
        let result = SecurityProviders::default().validate(&SecurityConfig::default());
        assert!(matches!(
            result,
            Err(SecurityError::RequiredProvidersUnavailable(_))
        ));
    }
}
