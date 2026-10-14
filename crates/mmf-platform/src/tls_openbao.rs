//! A Rustls signing key backed only by a versioned, non-exportable `OpenBao`
//! Transit P-256 key. Token files contain authorization, never key material.

use std::{
    fmt, fs,
    path::PathBuf,
    sync::{
        Arc,
        atomic::{AtomicUsize, Ordering},
    },
    time::Duration,
};

use base64::{Engine, engine::general_purpose::STANDARD};
use rustls::{
    SignatureAlgorithm, SignatureScheme,
    pki_types::SubjectPublicKeyInfoDer,
    sign::{Signer, SigningKey},
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use url::Url;

use crate::PlatformError;

const SIGNATURE_SCHEME: SignatureScheme = SignatureScheme::ECDSA_NISTP256_SHA256;

/// The public identity and bounded remote-signing contract for one TLS key version.
pub struct OpenBaoTlsSigner {
    client: reqwest::blocking::Client,
    endpoint: Url,
    key_name: String,
    key_version: u32,
    token_file: PathBuf,
    public_spki_der: Vec<u8>,
    active_signs: Arc<AtomicUsize>,
    max_concurrent_signs: usize,
}

impl fmt::Debug for OpenBaoTlsSigner {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("OpenBaoTlsSigner")
            .field("key_name", &self.key_name)
            .field("key_version", &self.key_version)
            .finish_non_exhaustive()
    }
}

impl OpenBaoTlsSigner {
    /// Load the public key from `OpenBao` and reject exportable or backupable keys.
    /// The endpoint must be HTTPS; the certificate authority is explicitly supplied.
    pub fn new(
        endpoint: &str,
        ca_certificate_der: &[u8],
        key_name: &str,
        key_version: u32,
        token_file: PathBuf,
        request_timeout: Duration,
        max_concurrent_signs: usize,
    ) -> Result<Self, PlatformError> {
        let endpoint =
            Url::parse(endpoint).map_err(|_| invalid("OpenBao TLS endpoint is invalid"))?;
        if endpoint.scheme() != "https"
            || endpoint.host_str().is_none()
            || !endpoint.username().is_empty()
            || endpoint.password().is_some()
            || endpoint.path() != "/"
            || endpoint.query().is_some()
            || endpoint.fragment().is_some()
        {
            return Err(invalid(
                "OpenBao TLS endpoint must be a credential-free HTTPS origin",
            ));
        }
        if key_name.is_empty()
            || !key_name
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-' || byte == b'_')
            || key_version == 0
            || request_timeout.is_zero()
            || max_concurrent_signs == 0
        {
            return Err(invalid("OpenBao TLS signer configuration is invalid"));
        }
        let ca = reqwest::Certificate::from_der(ca_certificate_der)
            .map_err(|_| invalid("OpenBao TLS CA certificate is invalid"))?;
        let client = reqwest::blocking::Client::builder()
            .add_root_certificate(ca)
            .https_only(true)
            .timeout(request_timeout)
            .build()
            .map_err(|_| invalid("OpenBao TLS HTTP client is invalid"))?;
        let mut signer = Self {
            client,
            endpoint,
            key_name: key_name.into(),
            key_version,
            token_file,
            public_spki_der: Vec::new(),
            active_signs: Arc::new(AtomicUsize::new(0)),
            max_concurrent_signs,
        };
        signer.public_spki_der = signer.load_public_key()?;
        Ok(signer)
    }

    fn token(&self) -> Result<String, PlatformError> {
        let token = fs::read_to_string(&self.token_file)
            .map_err(|_| PlatformError::ProviderUnavailable("OpenBao TLS authorization".into()))?;
        let token = token.trim();
        if token.is_empty() || token.contains(char::is_whitespace) {
            return Err(PlatformError::ProviderUnavailable(
                "OpenBao TLS authorization".into(),
            ));
        }
        Ok(token.into())
    }

    fn url(&self, path: &str) -> Url {
        self.endpoint
            .join(path)
            .expect("validated OpenBao origin and key name")
    }

    fn load_public_key(&self) -> Result<Vec<u8>, PlatformError> {
        let metadata: Value = self
            .client
            .get(self.url(&format!("v1/transit/keys/{}", self.key_name)))
            .header("X-Vault-Token", self.token()?)
            .send()
            .and_then(reqwest::blocking::Response::error_for_status)
            .and_then(reqwest::blocking::Response::json)
            .map_err(|_| PlatformError::ProviderUnavailable("OpenBao TLS key metadata".into()))?;
        parse_public_key(&metadata, self.key_version)
    }

    fn sign_remote(&self, message: &[u8]) -> Result<Vec<u8>, rustls::Error> {
        let _permit = SignPermit::acquire(&self.active_signs, self.max_concurrent_signs)?;
        let token = self.token().map_err(|_| unavailable())?;
        let response: Value = self
            .client
            .post(self.url(&format!("v1/transit/sign/{}", self.key_name)))
            .header("X-Vault-Token", token)
            .json(&json!({
                "input": STANDARD.encode(Sha256::digest(message)),
                "prehashed": true,
                "hash_algorithm": "sha2-256",
                "marshaling_algorithm": "asn1",
                "key_version": self.key_version,
            }))
            .send()
            .and_then(reqwest::blocking::Response::error_for_status)
            .and_then(reqwest::blocking::Response::json)
            .map_err(|_| unavailable())?;
        let prefix = format!("vault:v{}:", self.key_version);
        let encoded = response
            .pointer("/data/signature")
            .and_then(Value::as_str)
            .and_then(|signature| signature.strip_prefix(&prefix))
            .ok_or_else(|| {
                rustls::Error::General("OpenBao TLS signature version mismatch".into())
            })?;
        STANDARD
            .decode(encoded)
            .map_err(|_| rustls::Error::General("OpenBao TLS signature is invalid".into()))
    }
}

fn parse_public_key(metadata: &Value, key_version: u32) -> Result<Vec<u8>, PlatformError> {
    let data = &metadata["data"];
    if data["type"] != "ecdsa-p256"
        || data["exportable"] != false
        || data["allow_plaintext_backup"] != false
    {
        return Err(invalid(
            "OpenBao TLS key must be non-exportable, non-backupable P-256",
        ));
    }
    let pem = data["keys"][key_version.to_string()]["public_key"]
        .as_str()
        .ok_or_else(|| invalid("OpenBao TLS key version has no public key"))?;
    let body = pem
        .strip_prefix("-----BEGIN PUBLIC KEY-----")
        .and_then(|part| part.strip_suffix("-----END PUBLIC KEY-----"))
        .ok_or_else(|| invalid("OpenBao TLS public key PEM is invalid"))?;
    let encoded: String = body
        .chars()
        .filter(|ch| !ch.is_ascii_whitespace())
        .collect();
    STANDARD
        .decode(encoded)
        .map_err(|_| invalid("OpenBao TLS public key is invalid"))
}

impl SigningKey for OpenBaoTlsSigner {
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

impl Signer for OpenBaoTlsSigner {
    fn sign(&self, message: &[u8]) -> Result<Vec<u8>, rustls::Error> {
        match tokio::runtime::Handle::try_current() {
            Ok(handle) if handle.runtime_flavor() == tokio::runtime::RuntimeFlavor::MultiThread => {
                tokio::task::block_in_place(|| self.sign_remote(message))
            }
            Ok(_) => Err(unavailable()),
            Err(_) => self.sign_remote(message),
        }
    }

    fn scheme(&self) -> SignatureScheme {
        SIGNATURE_SCHEME
    }
}

impl Clone for OpenBaoTlsSigner {
    fn clone(&self) -> Self {
        Self {
            client: self.client.clone(),
            endpoint: self.endpoint.clone(),
            key_name: self.key_name.clone(),
            key_version: self.key_version,
            token_file: self.token_file.clone(),
            public_spki_der: self.public_spki_der.clone(),
            active_signs: self.active_signs.clone(),
            max_concurrent_signs: self.max_concurrent_signs,
        }
    }
}

struct SignPermit(Arc<AtomicUsize>);

impl SignPermit {
    fn acquire(counter: &Arc<AtomicUsize>, limit: usize) -> Result<Self, rustls::Error> {
        counter
            .fetch_update(Ordering::AcqRel, Ordering::Acquire, |count| {
                (count < limit).then_some(count + 1)
            })
            .map_err(|_| rustls::Error::General("OpenBao TLS signing limit".into()))?;
        Ok(Self(counter.clone()))
    }
}

impl Drop for SignPermit {
    fn drop(&mut self) {
        self.0.fetch_sub(1, Ordering::AcqRel);
    }
}

fn invalid(message: &str) -> PlatformError {
    PlatformError::InvalidConfiguration(message.into())
}
fn unavailable() -> rustls::Error {
    rustls::Error::General("OpenBao TLS signing unavailable".into())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn public_key_requires_non_exportable_non_backupable_p256_and_exact_version() {
        let public = STANDARD.encode([1, 2, 3]);
        let metadata = json!({"data": {
            "type": "ecdsa-p256", "exportable": false,
            "allow_plaintext_backup": false,
            "keys": {"2": {"public_key": format!(
                "-----BEGIN PUBLIC KEY-----\n{public}\n-----END PUBLIC KEY-----")}}
        }});
        assert_eq!(parse_public_key(&metadata, 2).unwrap(), [1, 2, 3]);
        assert!(parse_public_key(&metadata, 1).is_err());
        for (field, value) in [
            ("type", json!("rsa-2048")),
            ("exportable", json!(true)),
            ("allow_plaintext_backup", json!(true)),
        ] {
            let mut rejected = metadata.clone();
            rejected["data"][field] = value;
            assert!(parse_public_key(&rejected, 2).is_err());
        }
    }

    #[test]
    fn signer_rejects_plain_http_before_opening_a_connection() {
        let result = OpenBaoTlsSigner::new(
            "http://127.0.0.1:8200",
            &[1],
            "tls-key",
            1,
            PathBuf::from("unread-token"),
            Duration::from_secs(1),
            1,
        );
        assert!(matches!(
            result,
            Err(PlatformError::InvalidConfiguration(_))
        ));
    }

    #[test]
    fn concurrent_signs_are_bounded_and_permit_releases_on_drop() {
        let counter = Arc::new(AtomicUsize::new(0));
        let first = SignPermit::acquire(&counter, 1).unwrap();
        assert!(SignPermit::acquire(&counter, 1).is_err());
        drop(first);
        assert!(SignPermit::acquire(&counter, 1).is_ok());
    }
}
