use super::*;

use axum::{
    Router,
    body::{Body, to_bytes},
    extract::{Request, State},
    response::IntoResponse,
    routing::post,
};
use base64::{Engine as _, engine::general_purpose::STANDARD};
use mmf_aws_kms::AwsAuth;
use serde_json::{Value, json};
use std::sync::Mutex;

const ARN: &str = "arn:aws:kms:us-east-2:111122223333:key/tls-existing";
const PUBLIC: &str = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE808enVR9XO/NlkhM83gTqewR40pSHC0UMOFYYVilSNLZBem1zfrjoS+NNSgn4f5cVFic+i5SLwYs/u4d2crkjg==";
// Public-only fixture from marty-ui c8e62e1, public_certificates/root-ca.pem.
// Used only for certificate/SPKI binding, not as a server-auth certificate.
const CERTIFICATE: &str = "-----BEGIN CERTIFICATE-----\nMIIB4zCCAYmgAwIBAgIUYpQvlnGTkA7M3om4B/KDGoZA+YgwCgYIKoZIzj0EAwIw\nPzELMAkGA1UEBhMCVVMxEzARBgNVBAoTCkRpc3Bvc2FibGUxGzAZBgNVBAMTEkRp\nc3Bvc2FibGUgUm9vdCBDQTAeFw0yNjEwMDcwOTExMDlaFw0zNjEwMDQwOTExMzla\nMD8xCzAJBgNVBAYTAlVTMRMwEQYDVQQKEwpEaXNwb3NhYmxlMRswGQYDVQQDExJE\naXNwb3NhYmxlIFJvb3QgQ0EwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAATzTx6d\nVH1c782WSEzzeBOp7BHjSlIcLRQw4VhhWKVI0tkF6bXN+uOhL401KCfh/lxUWJz6\nLlIvBiz+7h3ZyuSOo2MwYTAOBgNVHQ8BAf8EBAMCAQYwDwYDVR0TAQH/BAUwAwEB\n/zAdBgNVHQ4EFgQUWvEQKsiY7F+P3GPOZkaNMrN1mpkwHwYDVR0jBBgwFoAUWvEQ\nKsiY7F+P3GPOZkaNMrN1mpkwCgYIKoZIzj0EAwIDSAAwRQIhAJUsT7rFkj6Gs9vv\n/HU5NHBeq1axCQ6/ty+heazA2mGBAiAKy2pr6ymFNwHz4bwCT0eggVAyv652xXaq\nm8WRiJ8gAA==\n-----END CERTIFICATE-----\n";

#[derive(Clone)]
struct Stub {
    origin: &'static str,
    wrong_sign_key: bool,
    calls: Arc<Mutex<Vec<(String, Value)>>>,
}

async fn handler(State(state): State<Stub>, request: Request<Body>) -> axum::response::Response {
    let target = request.headers()["x-amz-target"]
        .to_str()
        .unwrap()
        .rsplit('.')
        .next()
        .unwrap()
        .to_owned();
    let body: Value =
        serde_json::from_slice(&to_bytes(request.into_body(), 16_384).await.unwrap()).unwrap();
    state.calls.lock().unwrap().push((target.clone(), body));
    let value = match target.as_str() {
        "DescribeKey" => {
            json!({"KeyMetadata":{"KeyId":"tls-existing","Arn":ARN,"Enabled":true,"KeyState":"Enabled","KeyUsage":"SIGN_VERIFY","KeySpec":"ECC_NIST_P256","Origin":state.origin,"SigningAlgorithms":["ECDSA_SHA_256"]}})
        }
        "GetPublicKey" => {
            json!({"KeyId":ARN,"KeySpec":"ECC_NIST_P256","KeyUsage":"SIGN_VERIFY","SigningAlgorithms":["ECDSA_SHA_256"],"PublicKey":PUBLIC})
        }
        "Sign" => {
            json!({"KeyId":if state.wrong_sign_key {"wrong-key"} else {ARN},"SigningAlgorithm":"ECDSA_SHA_256","Signature":STANDARD.encode([0x30,0])})
        }
        _ => panic!("unexpected operation"),
    };
    axum::Json(value).into_response()
}

async fn fixture(
    origin: &'static str,
    wrong_sign_key: bool,
) -> (AwsKmsConfig, Stub, tokio::task::JoinHandle<()>) {
    let state = Stub {
        origin,
        wrong_sign_key,
        calls: Arc::new(Mutex::new(Vec::new())),
    };
    let app = Router::new()
        .route("/", post(handler))
        .with_state(state.clone());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let config = AwsKmsConfig {
        region: "us-east-2".into(),
        authentication: AwsAuth::AccessKey {
            access_key_id: "explicit-tls".into(),
            secret_access_key: "fixture-secret".into(),
            session_token: None,
        },
        endpoint: Some(format!("http://{}", listener.local_addr().unwrap())),
        request_timeout: Duration::from_secs(2),
    };
    let task = tokio::spawn(async {
        axum::serve(listener, app).await.unwrap();
    });
    (config, state, task)
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn signer_binds_public_certificate_and_hashes_the_exact_handshake_message() {
    let (config, state, task) = fixture("AWS_KMS", false).await;
    let signer = AwsKmsTlsSigner::connect(config, ARN.into(), 1)
        .await
        .unwrap();
    assert!(
        signer
            .choose_scheme(&[SignatureScheme::RSA_PSS_SHA256])
            .is_none()
    );
    assert!(signer.choose_scheme(&[SIGNATURE_SCHEME]).is_some());
    let certificate = rustls_pemfile::certs(&mut CERTIFICATE.as_bytes())
        .next()
        .unwrap()
        .unwrap()
        .to_vec();
    assert!(KeylessTlsIdentity::new(vec![certificate.clone()], Arc::new(signer.clone())).is_ok());
    let mut mismatch = signer.clone();
    mismatch.public_spki_der[30] ^= 1;
    assert!(KeylessTlsIdentity::new(vec![certificate], Arc::new(mismatch)).is_err());
    assert_eq!(
        signer.sign(b"exact TLS handshake transcript").unwrap(),
        vec![0x30, 0]
    );
    let calls = state.calls.lock().unwrap();
    let (_, request) = calls.iter().find(|(target, _)| target == "Sign").unwrap();
    assert_eq!(request["KeyId"], ARN);
    assert_eq!(request["MessageType"], "DIGEST");
    assert_eq!(
        request["Message"],
        STANDARD.encode(Sha256::digest(b"exact TLS handshake transcript"))
    );
    task.abort();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn no_imported_key_wrong_response_or_exhausted_capacity_can_sign() {
    let (config, state, task) = fixture("EXTERNAL", false).await;
    assert!(
        AwsKmsTlsSigner::connect(config, ARN.into(), 1)
            .await
            .is_err()
    );
    assert_eq!(state.calls.lock().unwrap().len(), 1);
    task.abort();
    let (config, state, task) = fixture("AWS_KMS", true).await;
    let signer = AwsKmsTlsSigner::connect(config, ARN.into(), 1)
        .await
        .unwrap();
    let permit = RemoteSignPermit::acquire(&signer.active_signs, 1).unwrap();
    assert!(signer.sign(b"handshake").is_err());
    assert_eq!(state.calls.lock().unwrap().len(), 2);
    drop(permit);
    assert!(signer.sign(b"handshake").is_err());
    assert_eq!(state.calls.lock().unwrap().len(), 3);
    let count = state.calls.lock().unwrap().len();
    assert!(signer.sign_remote(b"handshake", Duration::ZERO).is_err());
    assert_eq!(state.calls.lock().unwrap().len(), count);
    task.abort();
}

#[tokio::test]
async fn current_thread_runtime_fails_before_provider_access() {
    let config = AwsKmsConfig {
        region: "us-east-2".into(),
        authentication: AwsAuth::IamRole,
        endpoint: None,
        request_timeout: Duration::from_secs(1),
    };
    assert!(matches!(
        AwsKmsTlsSigner::connect(config, ARN.into(), 1).await,
        Err(PlatformError::InvalidConfiguration(_))
    ));
}
