//! Keyless TLS over the shared AWS KMS client. Only public certificates and
//! pinned key ARNs enter this adapter; no private-key or local-signing fallback.

use std::{
    fmt,
    path::{Path, PathBuf},
    sync::{Arc, atomic::AtomicUsize},
    time::Duration,
};

use mmf_aws_kms::{AwsKmsConfig, AwsKmsKey, KeyCapability, SigningAlgorithm};
use rustls::{
    SignatureAlgorithm, SignatureScheme,
    pki_types::SubjectPublicKeyInfoDer,
    sign::{Signer, SigningKey},
};
use sha2::{Digest, Sha256};
use url::Url;

use crate::{
    KeylessGrpcChannelFactory, KeylessGrpcTlsAcceptor, KeylessGrpcTransportOptions,
    KeylessTlsIdentity, PlatformError,
    grpc_keyless::{RemoteSignPermit, remaining_handshake_time},
    read_public_certificates,
};

const SIGNATURE_SCHEME: SignatureScheme = SignatureScheme::ECDSA_NISTP256_SHA256;

/// Public certificate chain plus one remote AWS P-256 identity.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AwsKmsTlsIdentityFiles {
    pub certificate_chain_file: PathBuf,
    pub kms: AwsKmsConfig,
    pub key_arn: String,
    pub max_concurrent_signs: usize,
}

impl AwsKmsTlsIdentityFiles {
    pub async fn connect(&self) -> Result<KeylessTlsIdentity, PlatformError> {
        let chain = read_public_certificates(&self.certificate_chain_file)?;
        let signer = AwsKmsTlsSigner::connect(
            self.kms.clone(),
            self.key_arn.clone(),
            self.max_concurrent_signs,
        )
        .await?;
        KeylessTlsIdentity::new(chain, Arc::new(signer))
    }

    async fn connect_for_handshake(
        &self,
        timeout: Duration,
    ) -> Result<KeylessTlsIdentity, PlatformError> {
        let mut bounded = self.clone();
        bounded.kms.request_timeout = bounded.kms.request_timeout.min(timeout);
        bounded.connect().await
    }

    pub async fn grpc_channel(
        &self,
        target: &str,
        server_ca_file: &Path,
        options: KeylessGrpcTransportOptions,
    ) -> Result<tonic::transport::Channel, PlatformError> {
        Ok(self
            .grpc_factory(target, server_ca_file, options)
            .await?
            .connect_lazy())
    }

    pub async fn grpc_channel_connected(
        &self,
        target: &str,
        server_ca_file: &Path,
        options: KeylessGrpcTransportOptions,
    ) -> Result<tonic::transport::Channel, PlatformError> {
        self.grpc_factory(target, server_ca_file, options)
            .await?
            .connect()
            .await
    }

    pub async fn grpc_acceptor(
        &self,
        client_ca_file: &Path,
        max_handshakes: usize,
        handshake_timeout: Duration,
    ) -> Result<KeylessGrpcTlsAcceptor, PlatformError> {
        let client_ca = read_public_certificates(client_ca_file)?;
        let identity = self.connect_for_handshake(handshake_timeout).await?;
        KeylessGrpcTlsAcceptor::new(&identity, client_ca, max_handshakes, handshake_timeout)
    }

    pub async fn grpc_acceptor_without_client_auth(
        &self,
        max_handshakes: usize,
        handshake_timeout: Duration,
    ) -> Result<KeylessGrpcTlsAcceptor, PlatformError> {
        let identity = self.connect_for_handshake(handshake_timeout).await?;
        KeylessGrpcTlsAcceptor::without_client_auth(&identity, max_handshakes, handshake_timeout)
    }

    async fn grpc_factory(
        &self,
        target: &str,
        server_ca_file: &Path,
        options: KeylessGrpcTransportOptions,
    ) -> Result<KeylessGrpcChannelFactory, PlatformError> {
        let server_ca = read_public_certificates(server_ca_file)?;
        let server_name = Url::parse(target)
            .ok()
            .filter(|url| url.scheme() == "https")
            .and_then(|url| url.host_str().map(str::to_owned))
            .ok_or_else(|| invalid("gRPC TLS target must have an HTTPS hostname"))?;
        let identity = self.connect_for_handshake(options.connect_timeout).await?;
        KeylessGrpcChannelFactory::with_options(target, &server_name, &identity, server_ca, options)
    }
}

#[derive(Clone)]
pub struct AwsKmsTlsSigner {
    key: AwsKmsKey,
    public_spki_der: Vec<u8>,
    runtime: tokio::runtime::Handle,
    request_timeout: Duration,
    active_signs: Arc<AtomicUsize>,
    max_concurrent_signs: usize,
}

impl fmt::Debug for AwsKmsTlsSigner {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("AwsKmsTlsSigner(..)")
    }
}

impl AwsKmsTlsSigner {
    /// The owning multithreaded runtime must remain alive while TLS uses this
    /// signer. A current-thread runtime cannot make a blocking Rustls callback
    /// drive its own asynchronous network I/O, so construction rejects it.
    pub async fn connect(
        config: AwsKmsConfig,
        key_arn: String,
        max_concurrent_signs: usize,
    ) -> Result<Self, PlatformError> {
        config
            .validate()
            .map_err(|_| invalid("AWS TLS configuration is invalid"))?;
        if max_concurrent_signs == 0 || max_concurrent_signs > 512 {
            return Err(invalid("AWS TLS signing limit is invalid"));
        }
        let runtime = tokio::runtime::Handle::try_current()
            .map_err(|_| invalid("AWS TLS requires a running multithreaded runtime"))?;
        if runtime.runtime_flavor() != tokio::runtime::RuntimeFlavor::MultiThread {
            return Err(invalid("AWS TLS requires a multithreaded runtime"));
        }
        let request_timeout = config.request_timeout;
        // One activation budget covers credential setup, metadata and SPKI;
        // each individual remote call also retains its provider timeout.
        tokio::time::timeout(request_timeout, async {
            let key = AwsKmsKey::connect(config, key_arn)
                .await
                .map_err(|_| unavailable_platform())?;
            let metadata = key
                .validate(KeyCapability::Signing(SigningAlgorithm::EcdsaSha256))
                .await
                .map_err(|_| unavailable_platform())?;
            if metadata.origin != "AWS_KMS" {
                return Err(invalid(
                    "AWS TLS requires a native non-exportable P-256 KMS key",
                ));
            }
            let public_key = key.public_key().await.map_err(|_| unavailable_platform())?;
            if public_key.key_spec != "ECC_NIST_P256"
                || !public_key
                    .signing_algorithms
                    .iter()
                    .any(|v| v == "ECDSA_SHA_256")
            {
                return Err(invalid("AWS TLS public key is not P-256"));
            }
            Ok(Self {
                key,
                public_spki_der: public_key.spki_der,
                runtime,
                request_timeout,
                active_signs: Arc::new(AtomicUsize::new(0)),
                max_concurrent_signs,
            })
        })
        .await
        .map_err(|_| unavailable_platform())?
    }

    fn sign_remote(&self, message: &[u8], timeout: Duration) -> Result<Vec<u8>, rustls::Error> {
        let _permit = RemoteSignPermit::acquire(&self.active_signs, self.max_concurrent_signs)?;
        if timeout.is_zero() {
            return Err(unavailable());
        }
        let digest = Sha256::digest(message);
        self.runtime
            .block_on(self.key.sign_digest_with_timeout(
                SigningAlgorithm::EcdsaSha256,
                digest.as_slice(),
                timeout,
            ))
            .map_err(|_| unavailable())
    }
}

impl SigningKey for AwsKmsTlsSigner {
    fn choose_scheme(&self, offered: &[SignatureScheme]) -> Option<Box<dyn Signer>> {
        offered
            .contains(&SIGNATURE_SCHEME)
            .then(|| Box::new(self.clone()) as Box<dyn Signer>)
    }

    fn public_key(&self) -> Option<SubjectPublicKeyInfoDer<'_>> {
        Some(SubjectPublicKeyInfoDer::from(
            self.public_spki_der.as_slice(),
        ))
    }

    fn algorithm(&self) -> SignatureAlgorithm {
        SignatureAlgorithm::ECDSA
    }
}

impl Signer for AwsKmsTlsSigner {
    fn sign(&self, message: &[u8]) -> Result<Vec<u8>, rustls::Error> {
        // Capture the task-local deadline before entering the blocking section.
        let timeout = remaining_handshake_time()
            .map_or(self.request_timeout, |v| v.min(self.request_timeout));
        match tokio::runtime::Handle::try_current() {
            Ok(handle) if handle.runtime_flavor() == tokio::runtime::RuntimeFlavor::MultiThread => {
                tokio::task::block_in_place(|| self.sign_remote(message, timeout))
            }
            Ok(_) => Err(unavailable()),
            Err(_) => self.sign_remote(message, timeout),
        }
    }

    fn scheme(&self) -> SignatureScheme {
        SIGNATURE_SCHEME
    }
}

fn invalid(message: &str) -> PlatformError {
    PlatformError::InvalidConfiguration(message.into())
}

fn unavailable_platform() -> PlatformError {
    PlatformError::ProviderUnavailable("AWS TLS remote key".into())
}

fn unavailable() -> rustls::Error {
    rustls::Error::General("AWS TLS signing unavailable".into())
}

#[cfg(test)]
mod tests;
