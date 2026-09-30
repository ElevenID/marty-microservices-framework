//! Fail-closed workload identity authorization shared by MMF gRPC servers.

use std::collections::{BTreeMap, BTreeSet};

pub use mmf_core::constant_time_secret_eq;
use serde::{Deserialize, Serialize};

use crate::SecurityError;

const MINIMUM_SERVICE_TOKEN_BYTES: usize = 32;

#[derive(Clone)]
pub struct ServiceTokenAuthenticator {
    expected: Option<Vec<u8>>,
}

impl ServiceTokenAuthenticator {
    pub fn new(secret: Option<String>, required: bool) -> Result<Self, SecurityError> {
        let expected = match secret {
            Some(secret) if secret.len() >= MINIMUM_SERVICE_TOKEN_BYTES => {
                Some(secret.into_bytes())
            }
            Some(_) => {
                return Err(SecurityError::InvalidConfiguration(format!(
                    "service token must contain at least {MINIMUM_SERVICE_TOKEN_BYTES} bytes"
                )));
            }
            None if required => {
                return Err(SecurityError::RequiredProvidersUnavailable(vec![
                    "service_token",
                ]));
            }
            None => None,
        };
        Ok(Self { expected })
    }

    #[must_use]
    pub fn is_configured(&self) -> bool {
        self.expected.is_some()
    }

    pub fn authenticate(&self, candidate: Option<&str>) -> Result<(), SecurityError> {
        let Some(expected) = self.expected.as_deref() else {
            return Ok(());
        };
        let candidate = candidate.map(str::as_bytes).unwrap_or_default();
        if constant_time_secret_eq(expected, candidate) {
            Ok(())
        } else {
            Err(SecurityError::Authentication(
                "service authentication failed".into(),
            ))
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkloadAuthorizationDecision {
    Allow,
    Unauthenticated,
    Forbidden,
}

#[derive(Clone, Debug)]
pub struct WorkloadIdentityPolicy {
    allowed_identities_by_method: BTreeMap<String, BTreeSet<String>>,
}

impl WorkloadIdentityPolicy {
    pub fn new(
        allowed_identities_by_method: BTreeMap<String, BTreeSet<String>>,
    ) -> Result<Self, SecurityError> {
        if allowed_identities_by_method.is_empty()
            || allowed_identities_by_method
                .iter()
                .any(|(method, identities)| {
                    !valid_method(method)
                        || identities.is_empty()
                        || identities.iter().any(|identity| !valid_identity(identity))
                })
        {
            return Err(SecurityError::InvalidConfiguration(
                "workload authorization requires exact gRPC methods and SPIFFE URI identities"
                    .into(),
            ));
        }
        Ok(Self {
            allowed_identities_by_method,
        })
    }

    #[must_use]
    pub fn authorize<'a>(
        &self,
        method: &str,
        peer_identities: impl IntoIterator<Item = &'a str>,
    ) -> WorkloadAuthorizationDecision {
        let peer_identities = peer_identities.into_iter().collect::<BTreeSet<_>>();
        if peer_identities.is_empty() {
            return WorkloadAuthorizationDecision::Unauthenticated;
        }
        self.allowed_identities_by_method
            .get(method)
            .filter(|allowed| {
                peer_identities
                    .iter()
                    .any(|identity| allowed.contains(*identity))
            })
            .map_or(WorkloadAuthorizationDecision::Forbidden, |_| {
                WorkloadAuthorizationDecision::Allow
            })
    }
}

fn valid_method(value: &str) -> bool {
    let mut segments = value.split('/');
    segments.next() == Some("")
        && segments.next().is_some_and(|value| !value.is_empty())
        && segments.next().is_some_and(|value| !value.is_empty())
        && segments.next().is_none()
}

fn valid_identity(value: &str) -> bool {
    value.starts_with("spiffe://")
        && value.len() <= 2_048
        && !value.chars().any(char::is_whitespace)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn policy() -> WorkloadIdentityPolicy {
        WorkloadIdentityPolicy::new(BTreeMap::from([(
            "/marty.test.v1.Verifier/Evaluate".into(),
            BTreeSet::from(["spiffe://marty.internal/service/flow".into()]),
        )]))
        .unwrap()
    }

    #[test]
    fn exact_authenticated_identity_is_required() {
        let policy = policy();
        assert_eq!(
            policy.authorize(
                "/marty.test.v1.Verifier/Evaluate",
                ["spiffe://marty.internal/service/flow"],
            ),
            WorkloadAuthorizationDecision::Allow
        );
        assert_eq!(
            policy.authorize("/marty.test.v1.Verifier/Evaluate", []),
            WorkloadAuthorizationDecision::Unauthenticated
        );
        assert_eq!(
            policy.authorize(
                "/marty.test.v1.Verifier/Evaluate",
                ["spiffe://marty.internal/service/notification"],
            ),
            WorkloadAuthorizationDecision::Forbidden
        );
        assert_eq!(
            policy.authorize(
                "/marty.test.v1.Verifier/Other",
                ["spiffe://marty.internal/service/flow"],
            ),
            WorkloadAuthorizationDecision::Forbidden
        );
    }

    #[test]
    fn malformed_policy_and_secret_comparisons_fail_closed() {
        assert!(WorkloadIdentityPolicy::new(BTreeMap::new()).is_err());
        assert!(
            WorkloadIdentityPolicy::new(BTreeMap::from([(
                "Evaluate".into(),
                BTreeSet::from(["bearer-token".into()]),
            )]))
            .is_err()
        );
        assert!(constant_time_secret_eq(b"same", b"same"));
        assert!(!constant_time_secret_eq(b"same", b"different"));
        assert!(!constant_time_secret_eq(b"same", b"samf"));
    }

    #[test]
    fn required_service_tokens_fail_closed_at_startup_and_request_time() {
        assert!(ServiceTokenAuthenticator::new(None, true).is_err());
        assert!(ServiceTokenAuthenticator::new(Some("short".into()), false).is_err());
        let authenticator = ServiceTokenAuthenticator::new(Some("s".repeat(32)), true).unwrap();
        assert!(authenticator.is_configured());
        assert!(authenticator.authenticate(Some(&"s".repeat(32))).is_ok());
        assert!(authenticator.authenticate(None).is_err());
        assert!(authenticator.authenticate(Some(&"s".repeat(31))).is_err());
    }

    #[test]
    fn optional_unconfigured_service_authentication_supports_local_development() {
        let authenticator = ServiceTokenAuthenticator::new(None, false).unwrap();
        assert!(!authenticator.is_configured());
        assert!(authenticator.authenticate(None).is_ok());
    }
}
