use std::collections::BTreeSet;

use serde::Deserialize;

#[derive(Deserialize)]
struct Contract {
    schema_version: u32,
    identity_source: String,
    server_tls: ServerTls,
    mutual_tls: MutualTls,
}

#[derive(Deserialize)]
struct ServerTls {
    client_authentication: String,
    required_material: BTreeSet<String>,
    private_material_input: String,
}

#[derive(Deserialize)]
struct MutualTls {
    client_authentication: String,
    required_material: BTreeSet<String>,
    peer_authorization: String,
    partial_material_behavior: String,
}

#[test]
fn keyless_server_contract_retains_client_authentication_and_fail_closed_identity() {
    let contract: Contract =
        serde_json::from_str(include_str!("../../../contracts/grpc-server-behavior.json"))
            .expect("keyless server contract");
    assert_eq!(contract.schema_version, 2);
    assert_eq!(
        contract.identity_source,
        "remote_signer_bound_to_public_certificate"
    );
    assert_eq!(
        contract.server_tls.client_authentication,
        "application_routes_only"
    );
    assert_eq!(contract.server_tls.private_material_input, "forbidden");
    assert_eq!(
        contract.server_tls.required_material,
        BTreeSet::from(["server_certificate".into(), "remote_signer".into()])
    );
    assert_eq!(contract.mutual_tls.client_authentication, "required");
    assert_eq!(
        contract.mutual_tls.required_material,
        BTreeSet::from([
            "client_ca_certificate".into(),
            "server_certificate".into(),
            "remote_signer".into()
        ])
    );
    assert_eq!(
        contract.mutual_tls.peer_authorization,
        "certificate_identity_and_workload_policy"
    );
    assert_eq!(contract.mutual_tls.partial_material_behavior, "fail_closed");
}
