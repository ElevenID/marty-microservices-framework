use std::collections::{BTreeMap, BTreeSet};

use mmf_security::{
    WorkloadAuthorizationDecision, WorkloadIdentityPolicy, constant_time_secret_eq,
};
use serde::Deserialize;

#[derive(Deserialize)]
struct Contract {
    schema_version: u32,
    identity_source: String,
    bearer_identity_allowed: bool,
    unlisted_method_decision: WorkloadAuthorizationDecision,
    missing_identity_decision: WorkloadAuthorizationDecision,
    cases: Vec<Case>,
    server_tls: ServerTlsContract,
    service_secret_comparison: String,
}

#[derive(Deserialize)]
struct Case {
    method: String,
    peer_identities: Vec<String>,
    decision: WorkloadAuthorizationDecision,
}

#[derive(Deserialize)]
struct ServerTlsContract {
    client_certificate_required: bool,
    required_material: Vec<String>,
    partial_material_behavior: String,
}

#[test]
fn workload_authorization_matches_language_neutral_vectors() {
    let contract: Contract = serde_json::from_str(include_str!(
        "../../../contracts/workload-grpc-security.json"
    ))
    .expect("workload contract");
    assert_eq!(contract.schema_version, 1);
    assert_eq!(contract.identity_source, "mutual_tls_certificate_uri_san");
    assert!(!contract.bearer_identity_allowed);
    assert_eq!(
        contract.unlisted_method_decision,
        WorkloadAuthorizationDecision::Forbidden
    );
    assert_eq!(
        contract.missing_identity_decision,
        WorkloadAuthorizationDecision::Unauthenticated
    );
    assert!(contract.server_tls.client_certificate_required);
    assert_eq!(
        contract
            .server_tls
            .required_material
            .into_iter()
            .collect::<BTreeSet<_>>(),
        BTreeSet::from([
            "ca_certificate".into(),
            "server_certificate".into(),
            "remote_signer".into(),
        ])
    );
    assert_eq!(contract.server_tls.partial_material_behavior, "fail_closed");
    assert_eq!(contract.service_secret_comparison, "constant_time");

    let policy = WorkloadIdentityPolicy::new(BTreeMap::from([(
        "/marty.test.v1.Verifier/Evaluate".into(),
        BTreeSet::from(["spiffe://marty.internal/service/flow".into()]),
    )]))
    .expect("policy");
    for case in contract.cases {
        assert_eq!(
            policy.authorize(
                &case.method,
                case.peer_identities.iter().map(String::as_str),
            ),
            case.decision
        );
    }
    assert!(constant_time_secret_eq(
        b"0123456789abcdef",
        b"0123456789abcdef"
    ));
    assert!(!constant_time_secret_eq(
        b"0123456789abcdef",
        b"0123456789abcdeg"
    ));
}
