use std::{collections::BTreeMap, env, fmt, future::Future, time::Duration};

use aws_config::{BehaviorVersion, provider_config::ProviderConfig};
use aws_credential_types::Credentials;
use aws_sdk_kms::{
    config::{Region, retry::RetryConfig, timeout::TimeoutConfig},
    primitives::Blob,
    types::{EncryptionAlgorithmSpec, MacAlgorithmSpec, MessageType, SigningAlgorithmSpec},
};

use crate::{
    AwsAuth, AwsKmsConfig, AwsKmsError, KeyCapability, KeyMetadata, PublicKey, SigningAlgorithm,
    valid_role_arn, validate_key_arn,
};

/// One immutable, region-bound key reference. Neither request input nor a KMS
/// response may replace this key with an alias or another ARN.
#[derive(Clone)]
pub struct AwsKmsKey {
    client: aws_sdk_kms::Client,
    key_arn: String,
    request_timeout: Duration,
}

impl fmt::Debug for AwsKmsKey {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("AwsKmsKey(..)")
    }
}

impl AwsKmsKey {
    /// Configure one client without falling back to environment/profile secrets.
    /// Credential retrieval and every later operation have a bounded lifetime.
    pub async fn connect(config: AwsKmsConfig, key_arn: String) -> Result<Self, AwsKmsError> {
        config.validate()?;
        validate_key_arn(&key_arn, &config.region)?;
        let request_timeout = config.request_timeout;
        let client = tokio::time::timeout(request_timeout, connect_client(&config, &key_arn))
            .await
            .map_err(|_| AwsKmsError::Timeout)??;
        Ok(Self {
            client,
            key_arn,
            request_timeout,
        })
    }

    #[must_use]
    pub fn key_arn(&self) -> &str {
        &self.key_arn
    }

    fn bounded<T>(
        &self,
        operation: impl Future<Output = Result<T, AwsKmsError>>,
    ) -> impl Future<Output = Result<T, AwsKmsError>> {
        // Allocate SDK operation state before constructing the outer future so
        // composed metadata+operation calls do not grow caller stack frames.
        let bounded = tokio::time::timeout(self.request_timeout, Box::pin(operation));
        async move { bounded.await.map_err(|_| AwsKmsError::Timeout)? }
    }

    fn check_key(&self, actual: Option<&str>) -> Result<(), AwsKmsError> {
        if actual == Some(self.key_arn.as_str()) {
            Ok(())
        } else {
            Err(AwsKmsError::InvalidResponse)
        }
    }

    pub async fn metadata(&self) -> Result<KeyMetadata, AwsKmsError> {
        self.bounded(async {
            let output = self
                .client
                .describe_key()
                .key_id(&self.key_arn)
                .send()
                .await
                .map_err(|_| AwsKmsError::Unavailable)?;
            let metadata = output.key_metadata().ok_or(AwsKmsError::InvalidResponse)?;
            self.check_key(metadata.arn())?;
            Ok(KeyMetadata {
                key_arn: self.key_arn.clone(),
                key_spec: metadata
                    .key_spec()
                    .map_or("", |value| value.as_str())
                    .into(),
                key_usage: metadata
                    .key_usage()
                    .map_or("", |value| value.as_str())
                    .into(),
                enabled: metadata.enabled(),
                key_state: metadata
                    .key_state()
                    .map_or("", |value| value.as_str())
                    .into(),
                origin: metadata.origin().map_or("", |value| value.as_str()).into(),
                signing_algorithms: metadata
                    .signing_algorithms()
                    .iter()
                    .map(|v| v.as_str().into())
                    .collect(),
                mac_algorithms: metadata
                    .mac_algorithms()
                    .iter()
                    .map(|v| v.as_str().into())
                    .collect(),
                encryption_algorithms: metadata
                    .encryption_algorithms()
                    .iter()
                    .map(|v| v.as_str().into())
                    .collect(),
            })
        })
        .await
    }

    pub async fn validate(&self, capability: KeyCapability) -> Result<KeyMetadata, AwsKmsError> {
        let metadata = self.metadata().await?;
        metadata.validate(capability)?;
        Ok(metadata)
    }

    /// Return only public SPKI and its provider capability metadata.
    pub async fn public_key(&self) -> Result<PublicKey, AwsKmsError> {
        self.bounded(async {
            let output = self
                .client
                .get_public_key()
                .key_id(&self.key_arn)
                .send()
                .await
                .map_err(|_| AwsKmsError::Unavailable)?;
            self.check_key(output.key_id())?;
            let spki_der = output
                .public_key()
                .ok_or(AwsKmsError::InvalidResponse)?
                .as_ref();
            let key_spec = output
                .key_spec()
                .ok_or(AwsKmsError::InvalidResponse)?
                .as_str();
            let key_usage = output
                .key_usage()
                .ok_or(AwsKmsError::InvalidResponse)?
                .as_str();
            let signing_algorithms: Vec<String> = output
                .signing_algorithms()
                .iter()
                .map(|v| v.as_str().into())
                .collect();
            if spki_der.is_empty()
                || spki_der.len() > 16_384
                || key_usage != "SIGN_VERIFY"
                || !signing_algorithms.iter().any(|v| {
                    SigningAlgorithm::from_aws_name(v)
                        .is_ok_and(|algorithm| algorithm.accepts_spec(key_spec))
                })
            {
                return Err(AwsKmsError::InvalidResponse);
            }
            Ok(PublicKey {
                spki_der: spki_der.to_vec(),
                key_spec: key_spec.into(),
                key_usage: key_usage.into(),
                signing_algorithms,
            })
        })
        .await
    }

    /// Sign an already hashed message using AWS DIGEST mode, without rehashing.
    pub async fn sign_digest(
        &self,
        algorithm: SigningAlgorithm,
        digest: &[u8],
    ) -> Result<Vec<u8>, AwsKmsError> {
        self.sign_digest_with_timeout(algorithm, digest, self.request_timeout)
            .await
    }

    /// A smaller caller budget also bounds credentials and signing. Metadata
    /// preflight is separate, preserving existing Sign-only IAM capabilities.
    pub async fn sign_digest_with_timeout(
        &self,
        algorithm: SigningAlgorithm,
        digest: &[u8],
        timeout: Duration,
    ) -> Result<Vec<u8>, AwsKmsError> {
        if digest.len() != algorithm.digest_len() || timeout.is_zero() {
            return Err(AwsKmsError::InvalidInput);
        }
        tokio::time::timeout(timeout.min(self.request_timeout), async {
            let output = self
                .client
                .sign()
                .key_id(&self.key_arn)
                .message(Blob::new(digest))
                .message_type(MessageType::Digest)
                .signing_algorithm(SigningAlgorithmSpec::from(algorithm.as_str()))
                .send()
                .await
                .map_err(|_| AwsKmsError::Unavailable)?;
            self.check_key(output.key_id())?;
            if output.signing_algorithm().map(SigningAlgorithmSpec::as_str)
                != Some(algorithm.as_str())
            {
                return Err(AwsKmsError::InvalidResponse);
            }
            bounded_blob(output.signature(), 1, 8192)
        })
        .await
        .map_err(|_| AwsKmsError::Timeout)?
    }

    /// Authenticate the exact input bytes remotely. No implicit prehashing.
    pub async fn generate_mac(&self, message: &[u8]) -> Result<[u8; 32], AwsKmsError> {
        mac_input(message)?;
        self.bounded(async {
            self.validate(KeyCapability::HmacSha256).await?;
            let output = self
                .client
                .generate_mac()
                .key_id(&self.key_arn)
                .mac_algorithm(MacAlgorithmSpec::HmacSha256)
                .message(Blob::new(message))
                .send()
                .await
                .map_err(|_| AwsKmsError::Unavailable)?;
            self.check_key(output.key_id())?;
            if output.mac_algorithm() != Some(&MacAlgorithmSpec::HmacSha256) {
                return Err(AwsKmsError::InvalidResponse);
            }
            output
                .mac()
                .ok_or(AwsKmsError::InvalidResponse)?
                .as_ref()
                .try_into()
                .map_err(|_| AwsKmsError::InvalidResponse)
        })
        .await
    }

    /// Invalid MACs return false; credential, provider and binding errors do not.
    pub async fn verify_mac(&self, message: &[u8], mac: &[u8]) -> Result<bool, AwsKmsError> {
        mac_input(message)?;
        if mac.len() != 32 {
            return Err(AwsKmsError::InvalidInput);
        }
        self.bounded(async {
            self.validate(KeyCapability::HmacSha256).await?;
            let output = match self
                .client
                .verify_mac()
                .key_id(&self.key_arn)
                .mac_algorithm(MacAlgorithmSpec::HmacSha256)
                .message(Blob::new(message))
                .mac(Blob::new(mac))
                .send()
                .await
            {
                Ok(output) => output,
                Err(error)
                    if error
                        .as_service_error()
                        .is_some_and(aws_sdk_kms::operation::verify_mac::VerifyMacError::is_kms_invalid_mac_exception) =>
                {
                    return Ok(false);
                }
                Err(_) => return Err(AwsKmsError::Unavailable),
            };
            self.check_key(output.key_id())?;
            if output.mac_algorithm() != Some(&MacAlgorithmSpec::HmacSha256) {
                return Err(AwsKmsError::InvalidResponse);
            }
            Ok(output.mac_valid())
        })
        .await
    }

    /// Encrypt at most 4096 bytes remotely under a native symmetric KMS key.
    /// This is not a data-key or chunked encryption implementation.
    pub async fn encrypt(
        &self,
        plaintext: &[u8],
        context: &BTreeMap<String, String>,
    ) -> Result<Vec<u8>, AwsKmsError> {
        if plaintext.is_empty() || plaintext.len() > 4096 {
            return Err(AwsKmsError::InvalidInput);
        }
        validate_context(context)?;
        self.bounded(async {
            self.validate(KeyCapability::SymmetricEncryption).await?;
            let output = self
                .client
                .encrypt()
                .key_id(&self.key_arn)
                .encryption_algorithm(EncryptionAlgorithmSpec::SymmetricDefault)
                .set_encryption_context(Some(context.clone().into_iter().collect()))
                .plaintext(Blob::new(plaintext))
                .send()
                .await
                .map_err(|_| AwsKmsError::Unavailable)?;
            self.check_key(output.key_id())?;
            if output.encryption_algorithm() != Some(&EncryptionAlgorithmSpec::SymmetricDefault) {
                return Err(AwsKmsError::InvalidResponse);
            }
            bounded_blob(output.ciphertext_blob(), 1, 6144)
        })
        .await
    }

    pub async fn decrypt(
        &self,
        ciphertext: &[u8],
        context: &BTreeMap<String, String>,
    ) -> Result<Vec<u8>, AwsKmsError> {
        if ciphertext.is_empty() || ciphertext.len() > 6144 {
            return Err(AwsKmsError::InvalidInput);
        }
        validate_context(context)?;
        self.bounded(async {
            self.validate(KeyCapability::SymmetricEncryption).await?;
            let output = match self
                .client
                .decrypt()
                .key_id(&self.key_arn)
                .encryption_algorithm(EncryptionAlgorithmSpec::SymmetricDefault)
                .set_encryption_context(Some(context.clone().into_iter().collect()))
                .ciphertext_blob(Blob::new(ciphertext))
                .send()
                .await
            {
                Ok(output) => output,
                Err(error)
                    if error
                        .as_service_error()
                        .is_some_and(aws_sdk_kms::operation::decrypt::DecryptError::is_invalid_ciphertext_exception) =>
                {
                    return Err(AwsKmsError::InvalidCiphertext);
                }
                Err(_) => return Err(AwsKmsError::Unavailable),
            };
            self.check_key(output.key_id())?;
            if output.encryption_algorithm() != Some(&EncryptionAlgorithmSpec::SymmetricDefault) {
                return Err(AwsKmsError::InvalidResponse);
            }
            bounded_blob(output.plaintext(), 1, 4096)
        })
        .await
    }
}

fn bounded_blob(
    blob: Option<&Blob>,
    minimum: usize,
    maximum: usize,
) -> Result<Vec<u8>, AwsKmsError> {
    let bytes = blob.ok_or(AwsKmsError::InvalidResponse)?.as_ref();
    if !(minimum..=maximum).contains(&bytes.len()) {
        return Err(AwsKmsError::InvalidResponse);
    }
    Ok(bytes.to_vec())
}

fn mac_input(message: &[u8]) -> Result<(), AwsKmsError> {
    if message.is_empty() || message.len() > 4096 {
        Err(AwsKmsError::InvalidInput)
    } else {
        Ok(())
    }
}

fn validate_context(context: &BTreeMap<String, String>) -> Result<(), AwsKmsError> {
    if context.len() > 64
        || context.iter().any(|(key, value)| {
            key.is_empty()
                || key.len() > 256
                || value.len() > 1024
                || key.chars().chain(value.chars()).any(char::is_control)
        })
        || context
            .iter()
            .map(|(key, value)| key.len() + value.len())
            .sum::<usize>()
            > 8192
    {
        return Err(AwsKmsError::InvalidInput);
    }
    Ok(())
}

fn timeout_config(timeout: Duration) -> TimeoutConfig {
    TimeoutConfig::builder()
        .connect_timeout(timeout)
        .read_timeout(timeout)
        .operation_timeout(timeout)
        .operation_attempt_timeout(timeout)
        .build()
}

fn official_endpoint(service: &str, region: &str, key_arn: &str) -> String {
    let suffix = if key_arn.starts_with("arn:aws-cn:") {
        "amazonaws.com.cn"
    } else {
        "amazonaws.com"
    };
    format!("https://{service}.{region}.{suffix}")
}

fn present(name: &str) -> bool {
    env::var(name).is_ok_and(|v| !v.trim().is_empty())
}

fn imds_endpoint(mode: Option<&str>, endpoint: Option<&str>) -> Result<&'static str, AwsKmsError> {
    let selected = match mode {
        None => "http://169.254.169.254",
        Some(value) if value.eq_ignore_ascii_case("ipv4") => "http://169.254.169.254",
        Some(value) if value.eq_ignore_ascii_case("ipv6") => "http://[fd00:ec2::254]",
        Some(_) => return Err(AwsKmsError::InvalidConfiguration),
    };
    if endpoint.is_some_and(|value| value.trim_end_matches('/') != selected) {
        return Err(AwsKmsError::InvalidConfiguration);
    }
    Ok(selected)
}

fn workload_source(
    loader: aws_config::ConfigLoader,
    config: &AwsKmsConfig,
) -> Result<aws_config::ConfigLoader, AwsKmsError> {
    let provider = ProviderConfig::default()
        .with_region(Some(Region::new(config.region.clone())))
        .with_retry_config(RetryConfig::standard().with_max_attempts(1))
        .with_timeout_config(timeout_config(config.request_timeout));
    if present("AWS_WEB_IDENTITY_TOKEN_FILE") || present("AWS_ROLE_ARN") {
        if !present("AWS_WEB_IDENTITY_TOKEN_FILE")
            || !env::var("AWS_ROLE_ARN").is_ok_and(|v| valid_role_arn(&v))
            // This SDK provider does not expose an explicit STS endpoint. Its
            // fresh ProviderConfig has no loaded profile; deny environment
            // overrides rather than send a web identity token to them.
            || present("AWS_ENDPOINT_URL") || present("AWS_ENDPOINT_URL_STS")
        {
            return Err(AwsKmsError::InvalidConfiguration);
        }
        return Ok(loader.credentials_provider(
            aws_config::web_identity_token::WebIdentityTokenCredentialsProvider::builder()
                .configure(&provider)
                .build(),
        ));
    }
    if present("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
        || present("AWS_CONTAINER_CREDENTIALS_FULL_URI")
    {
        return Ok(loader.credentials_provider(
            aws_config::ecs::EcsCredentialsProvider::builder()
                .configure(&provider)
                .build(),
        ));
    }
    if env::var("AWS_EC2_METADATA_DISABLED").is_ok_and(|v| v.eq_ignore_ascii_case("true")) {
        return Err(AwsKmsError::InvalidConfiguration);
    }
    let endpoint = imds_endpoint(
        env::var("AWS_EC2_METADATA_SERVICE_ENDPOINT_MODE")
            .ok()
            .as_deref(),
        env::var("AWS_EC2_METADATA_SERVICE_ENDPOINT")
            .ok()
            .as_deref(),
    )?;
    let imds = aws_config::imds::Client::builder()
        .configure(&provider)
        .endpoint(endpoint)
        .map_err(|_| AwsKmsError::InvalidConfiguration)?
        .max_attempts(1)
        .connect_timeout(config.request_timeout)
        .read_timeout(config.request_timeout)
        .operation_timeout(config.request_timeout)
        .operation_attempt_timeout(config.request_timeout)
        .build();
    Ok(loader.credentials_provider(
        aws_config::imds::credentials::ImdsCredentialsProvider::builder()
            .configure(&provider)
            .imds_client(imds)
            .build(),
    ))
}

async fn connect_client(
    config: &AwsKmsConfig,
    key_arn: &str,
) -> Result<aws_sdk_kms::Client, AwsKmsError> {
    // Explicit endpoints take precedence over AWS_ENDPOINT_URL*, shared
    // configuration files and service-specific endpoint settings in the SDK.
    let sts_endpoint = official_endpoint("sts", &config.region, key_arn);
    let loader = || {
        aws_config::defaults(BehaviorVersion::latest())
            .region(Region::new(config.region.clone()))
            .endpoint_url(&sts_endpoint)
            .retry_config(RetryConfig::standard().with_max_attempts(1))
            .timeout_config(timeout_config(config.request_timeout))
    };
    let sdk = match &config.authentication {
        AwsAuth::IamRole => workload_source(loader(), config)?.load().await,
        AwsAuth::AccessKey {
            access_key_id,
            secret_access_key,
            session_token,
        } => {
            loader()
                .credentials_provider(Credentials::new(
                    access_key_id.clone(),
                    secret_access_key.clone(),
                    session_token.clone(),
                    None,
                    "mmf-explicit-credential",
                ))
                .load()
                .await
        }
        AwsAuth::AssumeRole {
            role_arn,
            external_id,
        } => {
            let source = workload_source(loader(), config)?.load().await;
            let mut provider = aws_config::sts::AssumeRoleProvider::builder(role_arn)
                .session_name("mmf-kms")
                .configure(&source);
            if let Some(external_id) = external_id.as_deref().filter(|v| !v.is_empty()) {
                provider = provider.external_id(external_id);
            }
            loader()
                .credentials_provider(provider.build().await)
                .load()
                .await
        }
    };
    let endpoint = config
        .endpoint
        .as_deref()
        .filter(|v| !v.is_empty())
        .map_or_else(
            || official_endpoint("kms", &config.region, key_arn),
            str::to_owned,
        );
    let mut builder = aws_sdk_kms::config::Builder::from(&sdk)
        .endpoint_url(&endpoint)
        .retry_config(RetryConfig::standard().with_max_attempts(1))
        .timeout_config(timeout_config(config.request_timeout));
    if endpoint.starts_with("http://") {
        builder = builder.http_client(aws_smithy_http_client::Builder::new().build_http());
    }
    Ok(aws_sdk_kms::Client::from_conf(builder.build()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn imds_is_pinned_to_the_selected_link_local_origin() {
        assert_eq!(imds_endpoint(None, None).unwrap(), "http://169.254.169.254");
        assert_eq!(
            imds_endpoint(Some("IPv6"), None).unwrap(),
            "http://[fd00:ec2::254]"
        );
        assert_eq!(
            imds_endpoint(Some("IPv4"), Some("http://169.254.169.254/")).unwrap(),
            "http://169.254.169.254"
        );
        for (mode, endpoint) in [
            (Some("custom"), None),
            (None, Some("https://attacker.example")),
            (Some("IPv6"), Some("http://169.254.169.254")),
            (None, Some("http://127.0.0.1:8080")),
        ] {
            assert_eq!(
                imds_endpoint(mode, endpoint),
                Err(AwsKmsError::InvalidConfiguration)
            );
        }
    }

    #[test]
    fn ambient_access_keys_cannot_restore_a_disabled_workload_identity() {
        const CHILD: &str = "MMF_AWS_WORKLOAD_TEST_CHILD";
        if env::var_os(CHILD).is_some() {
            let runtime = tokio::runtime::Runtime::new().unwrap();
            let config = AwsKmsConfig {
                region: "us-east-2".into(),
                authentication: AwsAuth::IamRole,
                endpoint: None,
                request_timeout: Duration::from_secs(1),
            };
            let result = runtime.block_on(AwsKmsKey::connect(
                config,
                "arn:aws:kms:us-east-2:111122223333:key/id".into(),
            ));
            assert!(matches!(result, Err(AwsKmsError::InvalidConfiguration)));
            return;
        }
        let mut command = std::process::Command::new(std::env::current_exe().unwrap());
        command
            .args([
                "--exact",
                "client::tests::ambient_access_keys_cannot_restore_a_disabled_workload_identity",
            ])
            .env(CHILD, "1")
            .env("AWS_ACCESS_KEY_ID", "ambient-test-key")
            .env("AWS_SECRET_ACCESS_KEY", "ambient-test-secret")
            .env("AWS_EC2_METADATA_DISABLED", "true");
        for name in [
            "AWS_WEB_IDENTITY_TOKEN_FILE",
            "AWS_ROLE_ARN",
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
            "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        ] {
            command.env_remove(name);
        }
        assert!(command.output().unwrap().status.success());
    }

    #[test]
    fn sdk_endpoint_overrides_cannot_change_pinned_kms_authority() {
        const CHILD: &str = "MMF_AWS_ENDPOINT_TEST_CHILD";
        if env::var_os(CHILD).is_some() {
            let runtime = tokio::runtime::Runtime::new().unwrap();
            let config = AwsKmsConfig {
                region: "us-east-2".into(),
                authentication: AwsAuth::AccessKey {
                    access_key_id: "explicit".into(),
                    secret_access_key: "test-secret".into(),
                    session_token: None,
                },
                endpoint: None,
                request_timeout: Duration::from_secs(1),
            };
            let client = runtime
                .block_on(connect_client(
                    &config,
                    "arn:aws:kms:us-east-2:111122223333:key/id",
                ))
                .unwrap();
            let observed = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
            let captured = observed.clone();
            // Fail before signing/transmission: this observes the actual SDK
            // resolved URI without sending a request to AWS or an override.
            let result = runtime.block_on(
                client
                    .describe_key()
                    .key_id("arn:aws:kms:us-east-2:111122223333:key/id")
                    .customize()
                    .map_request(move |request| {
                        assert_eq!(
                            request.uri().to_string(),
                            "https://kms.us-east-2.amazonaws.com/"
                        );
                        captured.store(true, std::sync::atomic::Ordering::Release);
                        Err(std::io::Error::other("contract stops before transport"))
                    })
                    .send(),
            );
            assert!(result.is_err());
            assert!(observed.load(std::sync::atomic::Ordering::Acquire));
            return;
        }
        let output = std::process::Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "client::tests::sdk_endpoint_overrides_cannot_change_pinned_kms_authority",
            ])
            .env(CHILD, "1")
            .env("AWS_ENDPOINT_URL", "http://127.0.0.1:1")
            .env("AWS_ENDPOINT_URL_KMS", "http://127.0.0.1:2")
            .output()
            .unwrap();
        assert!(output.status.success());
    }
}
