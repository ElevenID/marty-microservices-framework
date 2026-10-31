use super::*;

const ARN: &str = "arn:aws:kms:us-east-2:111122223333:key/existing-key";

fn config() -> AwsKmsConfig {
    AwsKmsConfig {
        region: "us-east-2".into(),
        authentication: AwsAuth::IamRole,
        endpoint: None,
        request_timeout: Duration::from_secs(2),
    }
}

#[test]
fn opaque_ciphertext_codec_is_versioned_bounded_and_canonical() {
    for value in [vec![0], vec![255; 6144]] {
        let encoded = encode_ciphertext(&value).unwrap();
        assert_eq!(decode_ciphertext(&encoded).unwrap(), value);
        assert!(encoded.starts_with("aws-kms:v1:"));
    }
    assert_eq!(encode_ciphertext(&[]), Err(AwsKmsError::InvalidInput));
    assert_eq!(
        encode_ciphertext(&[0; 6145]),
        Err(AwsKmsError::InvalidInput)
    );
    for value in [
        "",
        "vault:v1:Zg==",
        "aws-kms:v2:Zg==",
        "aws-kms:v1:",
        "aws-kms:v1:Zg",
        "aws-kms:v1:Zh==",
        "aws-kms:v1:_w==",
        "aws-kms:v1:Zg==\n",
        "aws-kms:v1:Zg===",
        "aws-kms:v1: Zg==",
    ] {
        assert_eq!(
            decode_ciphertext(value),
            Err(AwsKmsError::InvalidCiphertext)
        );
    }
    assert_eq!(
        decode_ciphertext(&format!("aws-kms:v1:{}", "A".repeat(8196))),
        Err(AwsKmsError::InvalidCiphertext)
    );
}

#[test]
fn key_reference_rejects_alias_region_partition_and_credentials() {
    assert!(validate_key_arn(ARN, "us-east-2").is_ok());
    for arn in [
        "existing-key",
        "alias/name",
        "arn:aws:kms:us-east-2:111122223333:alias/name",
        "arn:aws:kms:us-west-2:111122223333:key/existing-key",
        "arn:aws-cn:kms:us-east-2:111122223333:key/existing-key",
        "arn:aws:kms:us-east-2:bad-account:key/existing-key",
        "arn:aws:kms:us-east-2:111122223333:key/with/slash",
    ] {
        assert_eq!(
            validate_key_arn(arn, "us-east-2"),
            Err(AwsKmsError::InvalidConfiguration)
        );
    }
    assert!(
        validate_key_arn(
            "arn:aws-cn:kms:cn-north-1:111122223333:key/id",
            "cn-north-1"
        )
        .is_ok()
    );
    assert!(
        validate_key_arn(
            "arn:aws-us-gov:kms:us-gov-west-1:111122223333:key/id",
            "us-gov-west-1"
        )
        .is_ok()
    );
}

#[test]
fn explicit_authentication_never_reinterprets_secrets_or_unknown_modes() {
    assert!(AwsAuth::from_reference("iam_role", "").is_ok());
    for (mode, reference) in [
        ("iam_role", "secret"),
        ("default", ""),
        (
            "access_key",
            r#"{"access_key_id":"id","secret_access_key":"secret","extra":"bad"}"#,
        ),
        (
            "assume_role",
            r#"{"role_arn":"arn:aws:iam::111122223333:user/not-a-role"}"#,
        ),
    ] {
        assert!(AwsAuth::from_reference(mode, reference).is_err());
    }
    let auth = AwsAuth::from_reference("access_key", r#"{"access_key_id":"secret-id","secret_access_key":"secret-value","session_token":"secret-token"}"#).unwrap();
    let formatted = format!("{auth:?}");
    assert!(!formatted.contains("secret"));
    let mut conf = config();
    conf.authentication = auth;
    assert!(!format!("{conf:?}").contains("secret"));
}

#[test]
fn endpoints_and_timeouts_cannot_escape_the_provider_boundary() {
    for endpoint in [
        "https://attacker.example",
        "http://169.254.169.254",
        "http://user:secret@127.0.0.1",
        "http://127.0.0.1/path",
        "http://127.0.0.1?query",
        "http://127.0.0.1#fragment",
    ] {
        let mut conf = config();
        conf.endpoint = Some(endpoint.into());
        assert_eq!(conf.validate(), Err(AwsKmsError::InvalidConfiguration));
    }
    for duration in [Duration::ZERO, Duration::from_secs(31)] {
        let mut conf = config();
        conf.request_timeout = duration;
        assert_eq!(conf.validate(), Err(AwsKmsError::InvalidConfiguration));
    }
    let mut conf = config();
    conf.endpoint = Some("http://127.0.0.1:12345".into());
    assert_eq!(conf.validate().is_ok(), cfg!(debug_assertions));
}

fn metadata(capability: KeyCapability) -> KeyMetadata {
    let (usage, spec, signing, mac, encryption) = match capability {
        KeyCapability::Signing(algorithm) => (
            "SIGN_VERIFY",
            "ECC_NIST_P256",
            vec![algorithm.as_str().into()],
            vec![],
            vec![],
        ),
        KeyCapability::HmacSha256 => (
            "GENERATE_VERIFY_MAC",
            "HMAC_256",
            vec![],
            vec!["HMAC_SHA_256".into()],
            vec![],
        ),
        KeyCapability::SymmetricEncryption => (
            "ENCRYPT_DECRYPT",
            "SYMMETRIC_DEFAULT",
            vec![],
            vec![],
            vec!["SYMMETRIC_DEFAULT".into()],
        ),
    };
    KeyMetadata {
        key_arn: ARN.into(),
        key_spec: spec.into(),
        key_usage: usage.into(),
        enabled: true,
        key_state: "Enabled".into(),
        origin: "AWS_KMS".into(),
        signing_algorithms: signing,
        mac_algorithms: mac,
        encryption_algorithms: encryption,
    }
}

#[test]
fn operation_metadata_does_not_confuse_key_usages_or_exported_origins() {
    for capability in [
        KeyCapability::Signing(SigningAlgorithm::EcdsaSha256),
        KeyCapability::HmacSha256,
        KeyCapability::SymmetricEncryption,
    ] {
        let original = metadata(capability);
        assert!(original.validate(capability).is_ok());
        let mut disabled = original.clone();
        disabled.enabled = false;
        assert!(disabled.validate(capability).is_err());
        let mut pending = original.clone();
        pending.key_state = "PendingDeletion".into();
        assert!(pending.validate(capability).is_err());
        let mut wrong = original.clone();
        wrong.key_usage = "KEY_AGREEMENT".into();
        assert!(wrong.validate(capability).is_err());
        let mut imported = original;
        imported.origin = "EXTERNAL".into();
        assert_eq!(
            imported.validate(capability).is_ok(),
            matches!(capability, KeyCapability::Signing(_))
        );
    }
    let mut wrong_curve = metadata(KeyCapability::Signing(SigningAlgorithm::EcdsaSha256));
    wrong_curve.key_spec = "ECC_NIST_P384".into();
    assert!(
        wrong_curve
            .validate(KeyCapability::Signing(SigningAlgorithm::EcdsaSha256))
            .is_err()
    );
    let mut invalid_usage = metadata(KeyCapability::HmacSha256);
    invalid_usage.key_usage = "GENERATE_VERIFY".into();
    assert!(invalid_usage.validate(KeyCapability::HmacSha256).is_err());
}

#[cfg(feature = "sdk")]
mod sdk {
    use super::*;
    use axum::{
        Router,
        body::{Body, to_bytes},
        extract::{Request, State},
        http::StatusCode,
        response::IntoResponse,
        routing::post,
    };
    use base64::engine::general_purpose::STANDARD;
    use serde_json::{Value, json};
    use std::{
        collections::BTreeMap,
        sync::{Arc, Mutex},
    };

    #[derive(Clone)]
    struct Stub {
        metadata: Value,
        fault: Option<(&'static str, StatusCode, Value)>,
        delay: Duration,
        captured: Arc<Mutex<Vec<(String, Value, String)>>>,
    }

    async fn handler(
        State(state): State<Stub>,
        request: Request<Body>,
    ) -> axum::response::Response {
        let target = request.headers()["x-amz-target"]
            .to_str()
            .unwrap()
            .rsplit('.')
            .next()
            .unwrap()
            .to_owned();
        let authorization = request.headers()["authorization"]
            .to_str()
            .unwrap()
            .to_owned();
        let body: Value =
            serde_json::from_slice(&to_bytes(request.into_body(), 20_000).await.unwrap()).unwrap();
        state
            .captured
            .lock()
            .unwrap()
            .push((target.clone(), body, authorization));
        if !state.delay.is_zero() {
            tokio::time::sleep(state.delay).await;
        }
        if let Some((operation, status, value)) = &state.fault
            && *operation == target
        {
            return (*status, axum::Json(value.clone())).into_response();
        }
        let value = match target.as_str() {
            "DescribeKey" => state.metadata,
            "GetPublicKey" => {
                json!({"KeyId":ARN,"KeyUsage":"SIGN_VERIFY","KeySpec":"ECC_NIST_P256","SigningAlgorithms":["ECDSA_SHA_256"],"PublicKey":STANDARD.encode([1,2,3])})
            }
            "Sign" => {
                json!({"KeyId":ARN,"SigningAlgorithm":"ECDSA_SHA_256","Signature":STANDARD.encode([0x30,0])})
            }
            "GenerateMac" => {
                json!({"KeyId":ARN,"MacAlgorithm":"HMAC_SHA_256","Mac":STANDARD.encode([7;32])})
            }
            "VerifyMac" => json!({"KeyId":ARN,"MacAlgorithm":"HMAC_SHA_256","MacValid":true}),
            "Encrypt" => {
                json!({"KeyId":ARN,"EncryptionAlgorithm":"SYMMETRIC_DEFAULT","CiphertextBlob":STANDARD.encode(b"opaque-ciphertext")})
            }
            "Decrypt" => {
                json!({"KeyId":ARN,"EncryptionAlgorithm":"SYMMETRIC_DEFAULT","Plaintext":STANDARD.encode(b"plaintext-secret")})
            }
            _ => panic!("unexpected operation"),
        };
        axum::Json(value).into_response()
    }

    struct Fixture {
        key: AwsKmsKey,
        state: Stub,
        task: tokio::task::JoinHandle<()>,
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            self.task.abort();
        }
    }

    fn wire_metadata(capability: KeyCapability) -> Value {
        let m = metadata(capability);
        if capability == KeyCapability::HmacSha256 {
            assert_eq!(
                m.key_usage,
                aws_sdk_kms::types::KeyUsageType::GenerateVerifyMac.as_str()
            );
        }
        json!({"KeyMetadata":{"KeyId":"existing-key","Arn":ARN,"KeySpec":m.key_spec,
            "KeyUsage":m.key_usage,"Enabled":true,"KeyState":"Enabled","Origin":"AWS_KMS",
            "SigningAlgorithms":m.signing_algorithms,"MacAlgorithms":m.mac_algorithms,"EncryptionAlgorithms":m.encryption_algorithms}})
    }

    async fn fixture(
        capability: KeyCapability,
        fault: Option<(&'static str, StatusCode, Value)>,
        delay: Duration,
    ) -> Fixture {
        let state = Stub {
            metadata: wire_metadata(capability),
            fault,
            delay,
            captured: Arc::new(Mutex::new(Vec::new())),
        };
        let app = Router::new()
            .route("/", post(handler))
            .with_state(state.clone());
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let endpoint = format!("http://{}", listener.local_addr().unwrap());
        let task = tokio::spawn(async {
            axum::serve(listener, app).await.unwrap();
        });
        let mut conf = config();
        conf.authentication = AwsAuth::AccessKey {
            access_key_id: "explicit-access".into(),
            secret_access_key: "fixture-secret".into(),
            session_token: None,
        };
        conf.endpoint = Some(endpoint);
        let key = AwsKmsKey::connect(conf, ARN.into()).await.unwrap();
        Fixture { key, state, task }
    }

    #[tokio::test]
    async fn exact_input_and_key_are_preserved_for_sign_mac_and_encryption() {
        let f = fixture(
            KeyCapability::Signing(SigningAlgorithm::EcdsaSha256),
            None,
            Duration::ZERO,
        )
        .await;
        f.key
            .sign_digest(SigningAlgorithm::EcdsaSha256, &[9; 32])
            .await
            .unwrap();
        {
            let calls = f.state.captured.lock().unwrap();
            assert_eq!(calls.len(), 1);
            assert_eq!(calls[0].0, "Sign");
            assert_eq!(calls[0].1["MessageType"], "DIGEST");
            assert_eq!(calls[0].1["Message"], STANDARD.encode([9; 32]));
            assert!(calls.iter().all(|(_, body, auth)| body["KeyId"] == ARN
                && auth.contains("Credential=explicit-access/")));
        }
        let f = fixture(KeyCapability::HmacSha256, None, Duration::ZERO).await;
        assert_eq!(
            f.key
                .generate_mac(b"domain-separated-bound-claims")
                .await
                .unwrap(),
            [7; 32]
        );
        assert!(
            f.key
                .verify_mac(b"domain-separated-bound-claims", &[7; 32])
                .await
                .unwrap()
        );
        {
            let calls = f.state.captured.lock().unwrap();
            for (_, body, _) in calls
                .iter()
                .filter(|(target, _, _)| target != "DescribeKey")
            {
                assert_eq!(
                    body["Message"],
                    STANDARD.encode(b"domain-separated-bound-claims")
                );
                assert_eq!(body["MacAlgorithm"], "HMAC_SHA_256");
            }
        }
        let f = fixture(KeyCapability::SymmetricEncryption, None, Duration::ZERO).await;
        let context = BTreeMap::from([
            ("tenant".into(), "tenant-1".into()),
            ("purpose".into(), "secret".into()),
        ]);
        let ciphertext = f.key.encrypt(b"plaintext-secret", &context).await.unwrap();
        assert_eq!(
            f.key.decrypt(&ciphertext, &context).await.unwrap(),
            b"plaintext-secret"
        );
        let calls = f.state.captured.lock().unwrap();
        for (_, body, _) in calls
            .iter()
            .filter(|(target, _, _)| target != "DescribeKey")
        {
            assert_eq!(body["EncryptionContext"], json!(context));
            assert_eq!(body["KeyId"], ARN);
        }
    }

    #[tokio::test]
    async fn wrong_key_algorithm_and_malformed_responses_fail_closed() {
        for response in [
            json!({"KeyId":"arn:aws:kms:us-east-2:111122223333:key/other","MacAlgorithm":"HMAC_SHA_256","Mac":STANDARD.encode([7;32])}),
            json!({"KeyId":ARN,"MacAlgorithm":"HMAC_SHA_512","Mac":STANDARD.encode([7;32])}),
            json!({"KeyId":ARN,"MacAlgorithm":"HMAC_SHA_256","Mac":STANDARD.encode([7;31])}),
            json!({"MacAlgorithm":"HMAC_SHA_256","Mac":STANDARD.encode([7;32])}),
        ] {
            let f = fixture(
                KeyCapability::HmacSha256,
                Some(("GenerateMac", StatusCode::OK, response)),
                Duration::ZERO,
            )
            .await;
            assert_eq!(
                f.key.generate_mac(b"bound").await,
                Err(AwsKmsError::InvalidResponse)
            );
        }
        for (operation, response) in ["Sign", "GetPublicKey", "Encrypt", "Decrypt", "VerifyMac"]
            .into_iter()
            .flat_map(|operation| {
                [json!({"KeyId":"wrong-key"}), json!({})].map(|response| (operation, response))
            })
        {
            let capability = match operation {
                "Sign" | "GetPublicKey" => KeyCapability::Signing(SigningAlgorithm::EcdsaSha256),
                "VerifyMac" => KeyCapability::HmacSha256,
                _ => KeyCapability::SymmetricEncryption,
            };
            let f = fixture(
                capability,
                Some((operation, StatusCode::OK, response)),
                Duration::ZERO,
            )
            .await;
            let result = match operation {
                "Sign" => f
                    .key
                    .sign_digest(SigningAlgorithm::EcdsaSha256, &[0; 32])
                    .await
                    .map(|_| ()),
                "GetPublicKey" => f.key.public_key().await.map(|_| ()),
                "Encrypt" => f.key.encrypt(b"secret", &BTreeMap::new()).await.map(|_| ()),
                "Decrypt" => f
                    .key
                    .decrypt(b"ciphertext", &BTreeMap::new())
                    .await
                    .map(|_| ()),
                _ => f.key.verify_mac(b"bound", &[0; 32]).await.map(|_| ()),
            };
            assert_eq!(result, Err(AwsKmsError::InvalidResponse));
        }
    }

    #[tokio::test]
    async fn invalid_mac_is_distinct_from_provider_outage_and_wrong_metadata() {
        let f = fixture(
            KeyCapability::HmacSha256,
            Some((
                "VerifyMac",
                StatusCode::BAD_REQUEST,
                json!({"__type":"KMSInvalidMacException","message":"do-not-echo"}),
            )),
            Duration::ZERO,
        )
        .await;
        assert!(!f.key.verify_mac(b"bound", &[0; 32]).await.unwrap());
        let f = fixture(
            KeyCapability::HmacSha256,
            Some((
                "VerifyMac",
                StatusCode::FORBIDDEN,
                json!({"__type":"AccessDeniedException","message":"do-not-echo"}),
            )),
            Duration::ZERO,
        )
        .await;
        assert_eq!(
            f.key.verify_mac(b"bound", &[0; 32]).await,
            Err(AwsKmsError::Unavailable)
        );
        for response_arn in [Some("wrong-key"), None] {
            let mut metadata = wire_metadata(KeyCapability::HmacSha256);
            if let Some(arn) = response_arn {
                metadata["KeyMetadata"]["Arn"] = json!(arn);
            } else {
                metadata["KeyMetadata"]
                    .as_object_mut()
                    .unwrap()
                    .remove("Arn");
            }
            let f = fixture(
                KeyCapability::HmacSha256,
                Some(("DescribeKey", StatusCode::OK, metadata)),
                Duration::ZERO,
            )
            .await;
            assert_eq!(
                f.key.generate_mac(b"bound").await,
                Err(AwsKmsError::InvalidResponse)
            );
            assert_eq!(f.state.captured.lock().unwrap().len(), 1);
        }
    }

    #[tokio::test]
    async fn oversize_inputs_never_reach_kms_and_deadline_bounds_the_whole_operation() {
        let f = fixture(KeyCapability::HmacSha256, None, Duration::ZERO).await;
        assert_eq!(
            f.key.generate_mac(&[0; 4097]).await,
            Err(AwsKmsError::InvalidInput)
        );
        assert_eq!(
            f.key.verify_mac(b"bound", &[0; 31]).await,
            Err(AwsKmsError::InvalidInput)
        );
        assert_eq!(
            f.key.encrypt(&[0; 4097], &BTreeMap::new()).await,
            Err(AwsKmsError::InvalidInput)
        );
        assert_eq!(
            f.key
                .sign_digest(SigningAlgorithm::EcdsaSha256, &[0; 64])
                .await,
            Err(AwsKmsError::InvalidInput)
        );
        assert!(f.state.captured.lock().unwrap().is_empty());
        let f = fixture(
            KeyCapability::Signing(SigningAlgorithm::EcdsaSha256),
            None,
            Duration::from_millis(80),
        )
        .await;
        assert_eq!(
            f.key
                .sign_digest_with_timeout(
                    SigningAlgorithm::EcdsaSha256,
                    &[0; 32],
                    Duration::from_millis(15)
                )
                .await,
            Err(AwsKmsError::Timeout)
        );
        assert!(
            f.state
                .captured
                .lock()
                .unwrap()
                .iter()
                .all(|(target, _, _)| target == "Sign")
        );
    }
}
