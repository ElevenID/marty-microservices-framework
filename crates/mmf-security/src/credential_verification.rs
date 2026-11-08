//! Typed credential-evidence adapter for a caller-resolved Cedar policy set.
//!
//! MMF owns schema validation, bounded inputs, and Cedar evaluation. The caller
//! owns policy selection and the rules for formats, compliance, trust, and age.

use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::{
    CedarAuthorizationDecision, CedarAuthorizationRequest, CedarPolicyEngine, SecurityError,
};

/// Schema for the credential facts projected by this adapter.
///
/// This vocabulary contains no default authorization rules. Resolve the active
/// policy in the domain service, then validate it against this schema.
pub const CREDENTIAL_VERIFICATION_SCHEMA: &str = r#"
namespace MIP {
  type CredentialContext = {
    credential_format: String,
    compliance_code: String,
    issuer_id: String,
    issuer_trust_level: Long,
    credential_age_seconds: Long,
    revocation_checked: Bool,
    revocation_required: Bool,
    is_revoked: Bool,
    is_expired: Bool,
    holder_binding_present: Bool,
    algorithm: String,
  };

  entity Organization {};
  entity User in [Organization] { email: String, status: String };
  entity Credential in [Organization] {
    format: String,
    status: String,
    compliance_code: String,
    issuer_id: String,
    trust_level: Long,
  };

  action "credentials:verify" appliesTo {
    principal: [User],
    resource: [Credential],
    context: CredentialContext,
  };
}
"#;

/// Verified, verifier-owned facts supplied to the resolved credential policy.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
#[allow(clippy::struct_excessive_bools)]
pub struct CredentialVerificationAuthorizationFacts {
    pub organization_id: String,
    pub credential_format: String,
    pub compliance_code: String,
    pub issuer_id: String,
    pub issuer_trust_level: u32,
    pub credential_age_seconds: u64,
    pub revocation_checked: bool,
    pub revocation_required: bool,
    pub is_revoked: bool,
    pub is_expired: bool,
    pub holder_binding_present: bool,
    pub algorithm: String,
}

/// Immutable adapter over an explicitly configured Cedar engine.
///
/// There is no default policy or implicit permit. Callers must resolve the active
/// policy and construct a validated [`CedarPolicyEngine`] before using it.
#[derive(Clone, Debug)]
pub struct CredentialVerificationPolicyEngine {
    cedar: CedarPolicyEngine,
}

impl CredentialVerificationPolicyEngine {
    /// Bind the adapter to a policy and schema already validated by MMF.
    pub fn new(cedar: CedarPolicyEngine) -> Self {
        Self { cedar }
    }

    /// Evaluate authenticated evidence. Invalid or incomplete facts are errors, never permits.
    pub fn authorize(
        &self,
        facts: &CredentialVerificationAuthorizationFacts,
    ) -> Result<CedarAuthorizationDecision, SecurityError> {
        validate_facts(facts)?;
        let trust_level = i64::from(facts.issuer_trust_level);
        let credential_age_seconds = i64::try_from(facts.credential_age_seconds).map_err(|_| {
            SecurityError::Authorization("credential age exceeds Cedar Long range".into())
        })?;
        let credential_status = if facts.is_revoked {
            "REVOKED"
        } else if facts.is_expired {
            "EXPIRED"
        } else {
            "ACTIVE"
        };
        self.cedar.authorize_request(CedarAuthorizationRequest {
            principal_type: "MIP::User".into(),
            principal_id: "verifier".into(),
            action_type: "MIP::Action".into(),
            action_id: "credentials:verify".into(),
            resource_type: "MIP::Credential".into(),
            resource_id: "presented-credential".into(),
            context: json!({
                "credential_format": facts.credential_format,
                "compliance_code": facts.compliance_code,
                "issuer_id": facts.issuer_id,
                "issuer_trust_level": trust_level,
                "credential_age_seconds": credential_age_seconds,
                "revocation_checked": facts.revocation_checked,
                "revocation_required": facts.revocation_required,
                "is_revoked": facts.is_revoked,
                "is_expired": facts.is_expired,
                "holder_binding_present": facts.holder_binding_present,
                "algorithm": facts.algorithm,
            }),
            entities: json!([
                {
                    "uid": {"type": "MIP::User", "id": "verifier"},
                    "attrs": {"email": "", "status": "ACTIVE"},
                    "parents": [{"type": "MIP::Organization", "id": facts.organization_id}]
                },
                {
                    "uid": {"type": "MIP::Organization", "id": facts.organization_id},
                    "attrs": {},
                    "parents": []
                },
                {
                    "uid": {"type": "MIP::Credential", "id": "presented-credential"},
                    "attrs": {
                        "format": facts.credential_format,
                        "status": credential_status,
                        "compliance_code": facts.compliance_code,
                        "issuer_id": facts.issuer_id,
                        "trust_level": trust_level
                    },
                    "parents": [{"type": "MIP::Organization", "id": facts.organization_id}]
                }
            ]),
        })
    }
}

fn validate_facts(facts: &CredentialVerificationAuthorizationFacts) -> Result<(), SecurityError> {
    for (name, value) in [
        ("organization_id", facts.organization_id.as_str()),
        ("credential_format", facts.credential_format.as_str()),
        ("compliance_code", facts.compliance_code.as_str()),
        ("issuer_id", facts.issuer_id.as_str()),
        ("algorithm", facts.algorithm.as_str()),
    ] {
        if value.trim().is_empty() || value.len() > 4_096 {
            return Err(SecurityError::Authorization(format!(
                "credential authorization {name} must be non-empty and bounded"
            )));
        }
    }
    if facts.issuer_trust_level > 100 {
        return Err(SecurityError::Authorization(
            "credential authorization trust level must be between 0 and 100".into(),
        ));
    }
    if facts.revocation_required && !facts.revocation_checked {
        return Err(SecurityError::Authorization(
            "required credential status evidence is unavailable".into(),
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::CedarConfig;
    use serde_json::Value;
    use std::collections::BTreeMap;

    #[derive(Deserialize)]
    struct Contract {
        schema_version: u32,
        policy_sources: BTreeMap<String, String>,
        base_facts: CredentialVerificationAuthorizationFacts,
        cases: Vec<Case>,
    }

    #[derive(Deserialize)]
    struct Case {
        name: String,
        policy: String,
        patch: Value,
        allowed: bool,
        #[serde(default)]
        expected_reasons: Vec<String>,
    }

    fn contract() -> Contract {
        serde_json::from_str(include_str!(
            "../../../contracts/credential-verification-authorization-behavior.json"
        ))
        .unwrap()
    }

    fn engine(source: &str) -> CredentialVerificationPolicyEngine {
        CredentialVerificationPolicyEngine::new(
            CedarPolicyEngine::from_human_schema(
                source,
                CREDENTIAL_VERIFICATION_SCHEMA,
                CedarConfig::default(),
            )
            .unwrap(),
        )
    }

    #[test]
    fn language_neutral_resolved_policy_contract() {
        let contract = contract();
        assert_eq!(contract.schema_version, 2);
        for case in contract.cases {
            let engine = engine(&contract.policy_sources[&case.policy]);
            let mut value = serde_json::to_value(&contract.base_facts).unwrap();
            for (key, patch) in case.patch.as_object().unwrap() {
                value[key] = patch.clone();
            }
            let facts: CredentialVerificationAuthorizationFacts =
                serde_json::from_value(value).unwrap();
            let decision = engine.authorize(&facts).unwrap();
            assert_eq!(decision.allowed, case.allowed, "{}", case.name);
            assert_eq!(
                decision.determining_policies, case.expected_reasons,
                "{}",
                case.name
            );
        }
    }

    #[test]
    fn changing_resolved_policy_changes_the_decision_without_changing_facts() {
        let contract = contract();
        let standard = engine(&contract.policy_sources["standard"]);
        let strict = engine(&contract.policy_sources["strict"]);
        assert!(standard.authorize(&contract.base_facts).unwrap().allowed);
        assert!(!strict.authorize(&contract.base_facts).unwrap().allowed);
    }

    #[test]
    fn invalid_or_missing_policy_cannot_construct_an_engine() {
        for source in [
            "",
            "not a Cedar policy",
            "permit(principal, action, resource) when { context.missing };",
        ] {
            assert!(
                CedarPolicyEngine::from_human_schema(
                    source,
                    CREDENTIAL_VERIFICATION_SCHEMA,
                    CedarConfig::default(),
                )
                .is_err()
            );
        }
    }

    #[test]
    fn incompatible_schema_cannot_authorize_projected_facts() {
        let cedar = CedarPolicyEngine::from_human_schema(
            "permit(principal, action, resource);",
            "entity User; entity Resource; action \"read\" appliesTo { principal: User, resource: Resource, context: {} };",
            CedarConfig::default(),
        ).unwrap();
        assert!(
            CredentialVerificationPolicyEngine::new(cedar)
                .authorize(&contract().base_facts)
                .is_err()
        );
    }

    #[test]
    fn invalid_facts_fail_closed_even_with_an_explicit_permit() {
        let mut facts = contract().base_facts;
        let engine = engine("permit(principal, action, resource);");
        facts.issuer_trust_level = 101;
        assert!(engine.authorize(&facts).is_err());
        facts.issuer_trust_level = 87;
        facts.credential_age_seconds = u64::MAX;
        assert!(engine.authorize(&facts).is_err());
        facts.credential_age_seconds = 30;
        facts.algorithm.clear();
        assert!(engine.authorize(&facts).is_err());
        facts.algorithm = "x".repeat(4097);
        assert!(engine.authorize(&facts).is_err());
        facts.algorithm = "EdDSA".into();
        facts.revocation_required = true;
        facts.revocation_checked = false;
        assert!(engine.authorize(&facts).is_err());
    }

    #[test]
    fn entity_status_cannot_contradict_verified_revocation_or_expiry() {
        let engine =
            engine("permit(principal, action, resource) when { resource.status == \"ACTIVE\" };");
        let mut facts = contract().base_facts;
        assert!(engine.authorize(&facts).unwrap().allowed);
        facts.is_revoked = true;
        assert!(!engine.authorize(&facts).unwrap().allowed);
        facts.is_revoked = false;
        facts.is_expired = true;
        assert!(!engine.authorize(&facts).unwrap().allowed);
    }
}
