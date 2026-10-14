use std::{collections::BTreeSet, path::PathBuf};

use mmf_platform::{GrpcChannelConfig, GrpcChannelFactory, GrpcTlsMaterial};
use serde::Deserialize;

const CERTIFICATE: &[u8] = b"-----BEGIN CERTIFICATE-----\nZml4dHVyZQ==\n-----END CERTIFICATE-----";

#[derive(Deserialize)]
struct Contract {
    schema_version: u32,
    accepted: Vec<Case>,
    rejected: Vec<Case>,
    requirements: Requirements,
}

#[derive(Deserialize)]
struct Case {
    name: String,
    config: GrpcChannelConfig,
    material: BTreeSet<String>,
}

#[derive(Deserialize)]
struct Requirements {
    redirects: String,
    credentials_in_target: String,
    tls_downgrade: String,
    client_identity: String,
    connect_mode: BTreeSet<String>,
    timeouts: BTreeSet<String>,
}

fn contract() -> Contract {
    let path =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../contracts/grpc-client-behavior.json");
    serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap()
}

fn material(names: &BTreeSet<String>) -> GrpcTlsMaterial {
    GrpcTlsMaterial {
        ca_certificate_pem: names
            .contains("ca_certificate")
            .then(|| CERTIFICATE.to_vec()),
    }
}

#[test]
fn language_neutral_grpc_channel_policy_fails_closed() {
    let contract = contract();
    assert_eq!(contract.schema_version, 2);
    for case in contract.accepted {
        assert!(
            case.config.validate(&material(&case.material)).is_ok(),
            "{}",
            case.name
        );
    }
    for case in contract.rejected {
        assert!(
            case.config.validate(&material(&case.material)).is_err(),
            "{}",
            case.name
        );
    }
}

#[tokio::test]
async fn channel_factory_exposes_both_startup_modes_and_bounded_transport() {
    let contract = contract();
    assert_eq!(contract.requirements.redirects, "not_applicable");
    assert_eq!(contract.requirements.credentials_in_target, "reject");
    assert_eq!(contract.requirements.tls_downgrade, "reject");
    assert_eq!(
        contract.requirements.client_identity,
        "keyless_channel_only"
    );
    assert_eq!(
        contract.requirements.connect_mode,
        BTreeSet::from(["eager".into(), "lazy".into()])
    );
    assert_eq!(contract.requirements.timeouts.len(), 4);

    let factory = GrpcChannelFactory::new(GrpcChannelConfig::default(), GrpcTlsMaterial::default())
        .expect("plaintext development channel policy");
    assert!(factory.endpoint().is_ok());
    assert!(factory.connect_lazy().is_ok());
}

#[test]
fn pem_era_mutual_tls_channel_mode_is_not_configurable() {
    let old_mode = r#"{"target":"https://service.internal:50051","security":"mutual_tls"}"#;
    assert!(serde_json::from_str::<GrpcChannelConfig>(old_mode).is_err());
}
