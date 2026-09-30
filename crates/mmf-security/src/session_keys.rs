//! Generic ECDH/HKDF session-key establishment for MMF communication channels.

use std::fmt;
use std::time::{SystemTime, UNIX_EPOCH};

use hkdf::Hkdf;
use p256::elliptic_curve::{Generate, sec1::ToSec1Point};
use p256::pkcs8::{EncodePublicKey, LineEnding};
use serde::{Deserialize, Serialize};
use sha2::Sha256;

use crate::SecurityError;
use crate::managed_session::generate_session_id;

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub enum EllipticCurve {
    #[default]
    #[serde(rename = "P-256")]
    P256,
    #[serde(rename = "P-384")]
    P384,
    #[serde(rename = "P-521")]
    P521,
}

enum PrivateKey {
    P256(p256::SecretKey),
    P384(p384::SecretKey),
    P521(p521::SecretKey),
}

/// An ephemeral key pair whose secret material is intentionally non-serializable.
pub struct EphemeralKeyPair {
    private_key: PrivateKey,
    pub curve: EllipticCurve,
    pub created_at_ms: u64,
}

impl fmt::Debug for EphemeralKeyPair {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("EphemeralKeyPair")
            .field("private_key", &"[REDACTED]")
            .field("curve", &self.curve)
            .field("created_at_ms", &self.created_at_ms)
            .finish()
    }
}

impl EphemeralKeyPair {
    #[must_use]
    pub fn public_key_bytes(&self) -> Vec<u8> {
        match &self.private_key {
            PrivateKey::P256(secret) => {
                p256::PublicKey::from_secret_scalar(&secret.to_nonzero_scalar())
                    .to_sec1_point(false)
                    .as_bytes()
                    .to_vec()
            }
            PrivateKey::P384(secret) => {
                p384::PublicKey::from_secret_scalar(&secret.to_nonzero_scalar())
                    .to_sec1_point(false)
                    .as_bytes()
                    .to_vec()
            }
            PrivateKey::P521(secret) => {
                p521::PublicKey::from_secret_scalar(&secret.to_nonzero_scalar())
                    .to_sec1_point(false)
                    .as_bytes()
                    .to_vec()
            }
        }
    }

    /// Encode the public half as an RFC 7468 `SubjectPublicKeyInfo` PEM document.
    pub fn public_key_pem(&self) -> Result<String, SecurityError> {
        let encode_error =
            || SecurityError::InvalidConfiguration("failed to encode ephemeral public key".into());
        match &self.private_key {
            PrivateKey::P256(secret) => {
                p256::PublicKey::from_secret_scalar(&secret.to_nonzero_scalar())
                    .to_public_key_pem(LineEnding::LF)
                    .map_err(|_| encode_error())
            }
            PrivateKey::P384(secret) => {
                p384::PublicKey::from_secret_scalar(&secret.to_nonzero_scalar())
                    .to_public_key_pem(LineEnding::LF)
                    .map_err(|_| encode_error())
            }
            PrivateKey::P521(secret) => {
                p521::PublicKey::from_secret_scalar(&secret.to_nonzero_scalar())
                    .to_public_key_pem(LineEnding::LF)
                    .map_err(|_| encode_error())
            }
        }
    }

    #[cfg(test)]
    fn from_scalar(curve: EllipticCurve, scalar: u64, now_ms: u64) -> Result<Self, SecurityError> {
        let width = match curve {
            EllipticCurve::P256 => 32,
            EllipticCurve::P384 => 48,
            EllipticCurve::P521 => 66,
        };
        let mut bytes = vec![0_u8; width];
        bytes[width - 8..].copy_from_slice(&scalar.to_be_bytes());
        let private_key = match curve {
            EllipticCurve::P256 => {
                PrivateKey::P256(p256::SecretKey::from_slice(&bytes).map_err(|_| {
                    SecurityError::InvalidConfiguration("invalid P-256 private scalar".into())
                })?)
            }
            EllipticCurve::P384 => {
                PrivateKey::P384(p384::SecretKey::from_slice(&bytes).map_err(|_| {
                    SecurityError::InvalidConfiguration("invalid P-384 private scalar".into())
                })?)
            }
            EllipticCurve::P521 => {
                PrivateKey::P521(p521::SecretKey::from_slice(&bytes).map_err(|_| {
                    SecurityError::InvalidConfiguration("invalid P-521 private scalar".into())
                })?)
            }
        };
        Ok(Self {
            private_key,
            curve,
            created_at_ms: now_ms,
        })
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SessionKeyMaterial {
    pub session_id: String,
    #[serde(skip_serializing)]
    pub encryption_key: Vec<u8>,
    #[serde(skip_serializing)]
    pub decryption_key: Vec<u8>,
    #[serde(skip_serializing)]
    pub mac_key: Vec<u8>,
    pub established_at_ms: u64,
    pub expires_at_ms: Option<u64>,
}

impl SessionKeyMaterial {
    #[must_use]
    pub fn is_expired_at(&self, now_ms: u64) -> bool {
        self.expires_at_ms.is_some_and(|expiry| now_ms > expiry)
    }
}

#[derive(Clone, Debug)]
pub struct EcdhSessionEstablishment {
    pub default_curve: EllipticCurve,
    pub key_length: usize,
}

/// Provider-neutral port for ephemeral ECDH session establishment.
pub trait SessionKeyEstablishment: Send + Sync {
    fn generate_ephemeral_keypair(&self, curve: Option<EllipticCurve>) -> EphemeralKeyPair;

    fn establish_session(
        &self,
        local_keypair: &EphemeralKeyPair,
        peer_public_key_bytes: &[u8],
        session_id: Option<String>,
        expires_in_seconds: u64,
        info_context: &[u8],
    ) -> Result<SessionKeyMaterial, SecurityError>;
}

impl Default for EcdhSessionEstablishment {
    fn default() -> Self {
        Self {
            default_curve: EllipticCurve::P256,
            key_length: 32,
        }
    }
}

impl EcdhSessionEstablishment {
    pub fn new(default_curve: EllipticCurve, key_length: usize) -> Result<Self, SecurityError> {
        if !(16..=64).contains(&key_length) {
            return Err(SecurityError::InvalidConfiguration(
                "session key length must be between 16 and 64 bytes".into(),
            ));
        }
        Ok(Self {
            default_curve,
            key_length,
        })
    }

    #[must_use]
    pub fn generate_ephemeral_keypair(&self, curve: Option<EllipticCurve>) -> EphemeralKeyPair {
        let curve = curve.unwrap_or(self.default_curve);
        let private_key = match curve {
            EllipticCurve::P256 => PrivateKey::P256(p256::SecretKey::generate()),
            EllipticCurve::P384 => PrivateKey::P384(p384::SecretKey::generate()),
            EllipticCurve::P521 => PrivateKey::P521(p521::SecretKey::generate()),
        };
        EphemeralKeyPair {
            private_key,
            curve,
            created_at_ms: now_ms(),
        }
    }

    pub fn establish_session(
        &self,
        local_keypair: &EphemeralKeyPair,
        peer_public_key_bytes: &[u8],
        session_id: Option<String>,
        expires_in_seconds: u64,
        info_context: &[u8],
    ) -> Result<SessionKeyMaterial, SecurityError> {
        self.establish_session_at(
            local_keypair,
            peer_public_key_bytes,
            session_id,
            expires_in_seconds,
            info_context,
            now_ms(),
        )
    }

    pub fn establish_session_at(
        &self,
        local_keypair: &EphemeralKeyPair,
        peer_public_key_bytes: &[u8],
        session_id: Option<String>,
        expires_in_seconds: u64,
        info_context: &[u8],
        established_at_ms: u64,
    ) -> Result<SessionKeyMaterial, SecurityError> {
        if expires_in_seconds == 0 {
            return Err(SecurityError::InvalidConfiguration(
                "session key expiration must be positive".into(),
            ));
        }
        let shared_secret = shared_secret(local_keypair, peer_public_key_bytes)?;
        let session_id = session_id.unwrap_or_else(|| generate_session_id(16));
        if session_id.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "session ID cannot be empty".into(),
            ));
        }
        let encryption_key = self.derive_key(
            &shared_secret,
            b"MMF Session Encryption",
            info_context,
            &session_id,
        )?;
        let decryption_key = self.derive_key(
            &shared_secret,
            b"MMF Session Decryption",
            info_context,
            &session_id,
        )?;
        let mac_key = self.derive_key(
            &shared_secret,
            b"MMF Session MAC",
            info_context,
            &session_id,
        )?;
        Ok(SessionKeyMaterial {
            session_id,
            encryption_key,
            decryption_key,
            mac_key,
            established_at_ms,
            expires_at_ms: Some(
                established_at_ms.saturating_add(expires_in_seconds.saturating_mul(1_000)),
            ),
        })
    }

    fn derive_key(
        &self,
        shared_secret: &[u8],
        label: &[u8],
        info_context: &[u8],
        session_id: &str,
    ) -> Result<Vec<u8>, SecurityError> {
        let mut info = Vec::with_capacity(label.len() + info_context.len() + session_id.len());
        info.extend_from_slice(label);
        info.extend_from_slice(info_context);
        info.extend_from_slice(session_id.as_bytes());
        let mut output = vec![0_u8; self.key_length];
        Hkdf::<Sha256>::new(None, shared_secret)
            .expand(&info, &mut output)
            .map_err(|_| {
                SecurityError::InvalidConfiguration("session key derivation failed".into())
            })?;
        Ok(output)
    }
}

impl SessionKeyEstablishment for EcdhSessionEstablishment {
    fn generate_ephemeral_keypair(&self, curve: Option<EllipticCurve>) -> EphemeralKeyPair {
        Self::generate_ephemeral_keypair(self, curve)
    }

    fn establish_session(
        &self,
        local_keypair: &EphemeralKeyPair,
        peer_public_key_bytes: &[u8],
        session_id: Option<String>,
        expires_in_seconds: u64,
        info_context: &[u8],
    ) -> Result<SessionKeyMaterial, SecurityError> {
        Self::establish_session(
            self,
            local_keypair,
            peer_public_key_bytes,
            session_id,
            expires_in_seconds,
            info_context,
        )
    }
}

fn shared_secret(
    local: &EphemeralKeyPair,
    peer_public_key_bytes: &[u8],
) -> Result<Vec<u8>, SecurityError> {
    let malformed = || {
        SecurityError::InvalidConfiguration(
            "peer public key is invalid for the selected curve".into(),
        )
    };
    match &local.private_key {
        PrivateKey::P256(secret) => {
            let peer =
                p256::PublicKey::from_sec1_bytes(peer_public_key_bytes).map_err(|_| malformed())?;
            Ok(
                p256::ecdh::diffie_hellman(secret.to_nonzero_scalar(), peer.as_affine())
                    .raw_secret_bytes()
                    .to_vec(),
            )
        }
        PrivateKey::P384(secret) => {
            let peer =
                p384::PublicKey::from_sec1_bytes(peer_public_key_bytes).map_err(|_| malformed())?;
            Ok(
                p384::ecdh::diffie_hellman(secret.to_nonzero_scalar(), peer.as_affine())
                    .raw_secret_bytes()
                    .to_vec(),
            )
        }
        PrivateKey::P521(secret) => {
            let peer =
                p521::PublicKey::from_sec1_bytes(peer_public_key_bytes).map_err(|_| malformed())?;
            Ok(
                p521::ecdh::diffie_hellman(secret.to_nonzero_scalar(), peer.as_affine())
                    .raw_secret_bytes()
                    .to_vec(),
            )
        }
    }
}

#[derive(Clone, Copy, Debug, Default)]
pub struct SessionKeyPrefix;

impl SessionKeyPrefix {
    pub const PREFIX: &'static str = "auth:session:";

    #[must_use]
    pub fn session_key_id(session_id: &str) -> String {
        format!("{}{session_id}", Self::PREFIX)
    }

    #[must_use]
    pub fn is_session_key(key_id: &str) -> bool {
        key_id.starts_with(Self::PREFIX)
    }

    #[must_use]
    pub fn parse_session_id(key_id: &str) -> Option<&str> {
        key_id.strip_prefix(Self::PREFIX)
    }
}

fn now_ms() -> u64 {
    u64::try_from(
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis(),
    )
    .unwrap_or(u64::MAX)
}

#[cfg(test)]
mod tests {
    use p256::pkcs8::DecodePublicKey;

    use super::*;
    use serde::Deserialize;

    #[derive(Deserialize)]
    struct Fixture {
        ecdh: EcdhFixture,
    }

    #[derive(Deserialize)]
    struct EcdhFixture {
        session_id: String,
        info_context_hex: String,
        expires_in_seconds: u64,
        key_length: usize,
        vectors: Vec<Vector>,
    }

    #[derive(Deserialize)]
    struct Vector {
        curve: EllipticCurve,
        local_private_scalar: u64,
        peer_private_scalar: u64,
        local_public_key_hex: String,
        peer_public_key_hex: String,
        encryption_key_hex: String,
        decryption_key_hex: String,
        mac_key_hex: String,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!(
            "../../../contracts/session-platform-behavior.json"
        ))
        .expect("valid session platform behavior fixture")
    }

    fn decode_hex(value: &str) -> Vec<u8> {
        value
            .as_bytes()
            .chunks_exact(2)
            .map(|pair| {
                u8::from_str_radix(std::str::from_utf8(pair).expect("ASCII hex"), 16)
                    .expect("valid hex")
            })
            .collect()
    }

    #[test]
    fn python_and_rust_ecdh_hkdf_vectors_match_for_all_supported_curves() {
        let fixture = fixture().ecdh;
        let establishment = EcdhSessionEstablishment::new(EllipticCurve::P256, fixture.key_length)
            .expect("valid configuration");
        for vector in fixture.vectors {
            let local =
                EphemeralKeyPair::from_scalar(vector.curve, vector.local_private_scalar, 1_000)
                    .expect("local key");
            let peer =
                EphemeralKeyPair::from_scalar(vector.curve, vector.peer_private_scalar, 1_000)
                    .expect("peer key");
            assert_eq!(
                local.public_key_bytes(),
                decode_hex(&vector.local_public_key_hex)
            );
            assert_eq!(
                peer.public_key_bytes(),
                decode_hex(&vector.peer_public_key_hex)
            );
            let material = establishment
                .establish_session_at(
                    &local,
                    &peer.public_key_bytes(),
                    Some(fixture.session_id.clone()),
                    fixture.expires_in_seconds,
                    &decode_hex(&fixture.info_context_hex),
                    1_000,
                )
                .expect("session material");
            assert_eq!(
                material.encryption_key,
                decode_hex(&vector.encryption_key_hex)
            );
            assert_eq!(
                material.decryption_key,
                decode_hex(&vector.decryption_key_hex)
            );
            assert_eq!(material.mac_key, decode_hex(&vector.mac_key_hex));
        }
    }

    #[test]
    fn malformed_keys_and_configuration_fail_closed_and_secrets_are_redacted() {
        assert!(EcdhSessionEstablishment::new(EllipticCurve::P256, 0).is_err());
        let establishment = EcdhSessionEstablishment::default();
        let keypair = establishment.generate_ephemeral_keypair(None);
        assert!(
            establishment
                .establish_session(&keypair, &[1, 2, 3], None, 3_600, b"")
                .is_err()
        );
        assert!(!format!("{keypair:?}").contains("private_key: P256"));
        let fixture = fixture().ecdh;
        let local = EphemeralKeyPair::from_scalar(EllipticCurve::P256, 1, 1_000).expect("keypair");
        let peer = EphemeralKeyPair::from_scalar(EllipticCurve::P256, 2, 1_000).expect("peer");
        let material = establishment
            .establish_session_at(
                &local,
                &peer.public_key_bytes(),
                Some(fixture.session_id),
                fixture.expires_in_seconds,
                b"",
                1_000,
            )
            .expect("material");
        let serialized = serde_json::to_string(&material).expect("serialize");
        assert!(!serialized.contains("encryption_key"));
        assert!(!serialized.contains("decryption_key"));
        assert!(!serialized.contains("mac_key"));
        assert!(SessionKeyPrefix::is_session_key("auth:session:example"));
        assert_eq!(
            SessionKeyPrefix::parse_session_id("auth:session:example"),
            Some("example")
        );
    }

    #[test]
    fn public_key_pem_and_provider_port_preserve_the_legacy_surface() {
        let establishment = EcdhSessionEstablishment::default();
        let provider: &dyn SessionKeyEstablishment = &establishment;

        for curve in [
            EllipticCurve::P256,
            EllipticCurve::P384,
            EllipticCurve::P521,
        ] {
            let generated = provider.generate_ephemeral_keypair(Some(curve));
            assert_eq!(generated.curve, curve);
            assert!(!generated.public_key_bytes().is_empty());
            let keypair = EphemeralKeyPair::from_scalar(curve, 1, 1_000).expect("keypair");
            let pem = keypair.public_key_pem().expect("public PEM");
            assert!(pem.starts_with("-----BEGIN PUBLIC KEY-----\n"));
            assert!(pem.ends_with("-----END PUBLIC KEY-----\n"));
            let encoded = match curve {
                EllipticCurve::P256 => p256::PublicKey::from_public_key_pem(&pem)
                    .expect("P-256 PEM")
                    .to_sec1_point(false)
                    .as_bytes()
                    .to_vec(),
                EllipticCurve::P384 => p384::PublicKey::from_public_key_pem(&pem)
                    .expect("P-384 PEM")
                    .to_sec1_point(false)
                    .as_bytes()
                    .to_vec(),
                EllipticCurve::P521 => p521::PublicKey::from_public_key_pem(&pem)
                    .expect("P-521 PEM")
                    .to_sec1_point(false)
                    .as_bytes()
                    .to_vec(),
            };
            assert_eq!(encoded, keypair.public_key_bytes());
        }
    }
}
