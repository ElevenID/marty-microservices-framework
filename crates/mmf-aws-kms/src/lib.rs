//! AWS KMS effects shared by application signing, authorization and keyless TLS.
//!
//! This crate owns connection and exact-key request binding, not tenant policy,
//! a key registry or local cryptography. Enable `sdk` for remote operations.

use std::{fmt, time::Duration};

use base64::{Engine as _, engine::general_purpose::STANDARD};
use serde::Deserialize;
use thiserror::Error;

#[cfg(feature = "sdk")]
mod client;
#[cfg(feature = "sdk")]
pub use client::AwsKmsKey;

const CIPHERTEXT_PREFIX: &str = "aws-kms:v1:";
const MAX_CIPHERTEXT_BYTES: usize = 6144;

/// Encode an opaque AWS ciphertext for existing storage envelope owners.
/// The tag conveys only codec/version; it never chooses a provider or key.
pub fn encode_ciphertext(ciphertext: &[u8]) -> Result<String, AwsKmsError> {
    if ciphertext.is_empty() || ciphertext.len() > MAX_CIPHERTEXT_BYTES {
        return Err(AwsKmsError::InvalidInput);
    }
    Ok(format!(
        "{CIPHERTEXT_PREFIX}{}",
        STANDARD.encode(ciphertext)
    ))
}

/// Decode only bounded, canonically padded standard Base64 AWS ciphertext.
pub fn decode_ciphertext(ciphertext: &str) -> Result<Vec<u8>, AwsKmsError> {
    if ciphertext.len() > CIPHERTEXT_PREFIX.len() + MAX_CIPHERTEXT_BYTES.div_ceil(3) * 4 {
        return Err(AwsKmsError::InvalidCiphertext);
    }
    let encoded = ciphertext
        .strip_prefix(CIPHERTEXT_PREFIX)
        .ok_or(AwsKmsError::InvalidCiphertext)?;
    let bytes = STANDARD
        .decode(encoded)
        .map_err(|_| AwsKmsError::InvalidCiphertext)?;
    if bytes.is_empty() || bytes.len() > MAX_CIPHERTEXT_BYTES || STANDARD.encode(&bytes) != encoded
    {
        return Err(AwsKmsError::InvalidCiphertext);
    }
    Ok(bytes)
}

/// Fixed error categories deliberately exclude SDK messages and request values.
#[derive(Clone, Copy, Debug, Eq, Error, PartialEq)]
pub enum AwsKmsError {
    #[error("AWS KMS configuration is invalid")]
    InvalidConfiguration,
    #[error("AWS KMS operation input is invalid")]
    InvalidInput,
    #[error("AWS KMS response does not match the requested key or operation")]
    InvalidResponse,
    #[error("AWS KMS is unavailable")]
    Unavailable,
    #[error("AWS KMS operation exceeded its time limit")]
    Timeout,
    #[error("AWS KMS ciphertext or its context is invalid")]
    InvalidCiphertext,
}

/// The selected authentication mode. IAM mode never uses the default credential
/// chain, environment access keys, profile keys or credential-process fallback.
#[derive(Clone, Eq, PartialEq)]
pub enum AwsAuth {
    IamRole,
    AccessKey {
        access_key_id: String,
        secret_access_key: String,
        session_token: Option<String>,
    },
    AssumeRole {
        role_arn: String,
        external_id: Option<String>,
    },
}

impl fmt::Debug for AwsAuth {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::IamRole => "AwsAuth::IamRole",
            Self::AccessKey { .. } => "AwsAuth::AccessKey(..)",
            Self::AssumeRole { .. } => "AwsAuth::AssumeRole(..)",
        })
    }
}

impl AwsAuth {
    /// Decode an existing provider registration's explicit credential reference.
    pub fn from_reference(mode: &str, reference: &str) -> Result<Self, AwsKmsError> {
        #[derive(Deserialize)]
        #[serde(deny_unknown_fields)]
        struct AccessCredential {
            access_key_id: String,
            secret_access_key: String,
            #[serde(default)]
            session_token: Option<String>,
        }
        #[derive(Deserialize)]
        #[serde(deny_unknown_fields)]
        struct AssumeRole {
            role_arn: String,
            #[serde(default)]
            external_id: Option<String>,
        }
        let auth = match mode {
            "iam_role" if reference.is_empty() => Self::IamRole,
            "access_key" if !reference.is_empty() && reference.len() <= 16_384 => {
                let value: AccessCredential = serde_json::from_str(reference)
                    .map_err(|_| AwsKmsError::InvalidConfiguration)?;
                Self::AccessKey {
                    access_key_id: value.access_key_id,
                    secret_access_key: value.secret_access_key,
                    session_token: value.session_token,
                }
            }
            "assume_role" if !reference.is_empty() && reference.len() <= 4096 => {
                let value: AssumeRole = serde_json::from_str(reference)
                    .map_err(|_| AwsKmsError::InvalidConfiguration)?;
                Self::AssumeRole {
                    role_arn: value.role_arn,
                    external_id: value.external_id,
                }
            }
            _ => return Err(AwsKmsError::InvalidConfiguration),
        };
        auth.validate()?;
        Ok(auth)
    }

    pub fn validate(&self) -> Result<(), AwsKmsError> {
        let valid = match self {
            Self::IamRole => true,
            Self::AccessKey {
                access_key_id,
                secret_access_key,
                session_token,
            } => {
                valid_secret(access_key_id, 256)
                    && valid_secret(secret_access_key, 4096)
                    && session_token
                        .as_deref()
                        .is_none_or(|v| valid_secret(v, 16_384))
            }
            Self::AssumeRole {
                role_arn,
                external_id,
            } => {
                valid_role_arn(role_arn)
                    && external_id
                        .as_deref()
                        .is_none_or(|v| v.is_empty() || valid_secret(v, 1224))
            }
        };
        if valid {
            Ok(())
        } else {
            Err(AwsKmsError::InvalidConfiguration)
        }
    }
}

fn valid_secret(value: &str, limit: usize) -> bool {
    !value.trim().is_empty() && value.len() <= limit && !value.chars().any(char::is_control)
}

#[must_use]
pub fn valid_role_arn(value: &str) -> bool {
    let parts = value.split(':').collect::<Vec<_>>();
    parts.len() == 6
        && parts[0] == "arn"
        && matches!(parts[1], "aws" | "aws-us-gov" | "aws-cn")
        && parts[2] == "iam"
        && parts[3].is_empty()
        && account_id(parts[4])
        && parts[5].starts_with("role/")
        && parts[5].len() > 5
        && value.len() <= 2048
        && !value.chars().any(|v| v.is_whitespace() || v.is_control())
}

/// Explicit connection inputs; production endpoints are derived from the ARN.
#[derive(Clone, Eq, PartialEq)]
pub struct AwsKmsConfig {
    pub region: String,
    pub authentication: AwsAuth,
    /// Only debug builds accept an explicit loopback origin for contract tests.
    /// Release builds reject every endpoint override.
    pub endpoint: Option<String>,
    pub request_timeout: Duration,
}

impl fmt::Debug for AwsKmsConfig {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("AwsKmsConfig(..)")
    }
}

impl AwsKmsConfig {
    pub fn validate(&self) -> Result<(), AwsKmsError> {
        validate_region(&self.region)?;
        self.authentication.validate()?;
        if self.request_timeout.is_zero() || self.request_timeout > Duration::from_secs(30) {
            return Err(AwsKmsError::InvalidConfiguration);
        }
        if let Some(endpoint) = self.endpoint.as_deref().filter(|v| !v.is_empty()) {
            let url = url::Url::parse(endpoint).map_err(|_| AwsKmsError::InvalidConfiguration)?;
            if !cfg!(debug_assertions)
                || !matches!(url.scheme(), "http" | "https")
                || !matches!(url.host_str(), Some("localhost" | "127.0.0.1" | "[::1]"))
                || !url.username().is_empty()
                || url.password().is_some()
                || url.path() != "/"
                || url.query().is_some()
                || url.fragment().is_some()
            {
                return Err(AwsKmsError::InvalidConfiguration);
            }
        }
        Ok(())
    }
}

pub fn validate_region(region: &str) -> Result<(), AwsKmsError> {
    if region.len() > 64
        || !region
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-')
        || !region
            .as_bytes()
            .first()
            .is_some_and(u8::is_ascii_lowercase)
        || !region.as_bytes().last().is_some_and(u8::is_ascii_digit)
    {
        return Err(AwsKmsError::InvalidConfiguration);
    }
    Ok(())
}

fn account_id(value: &str) -> bool {
    value.len() == 12 && value.bytes().all(|b| b.is_ascii_digit())
}

pub fn validate_key_arn(reference: &str, region: &str) -> Result<(), AwsKmsError> {
    validate_region(region)?;
    let parts = reference.split(':').collect::<Vec<_>>();
    if parts.len() != 6
        || parts[0] != "arn"
        || !matches!(parts[1], "aws" | "aws-us-gov" | "aws-cn")
        || parts[2] != "kms"
        || parts[3] != region
        || !account_id(parts[4])
        || reference.len() > 2048
        || !parts[5].strip_prefix("key/").is_some_and(|key| {
            !key.is_empty() && key.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-')
        })
        || (parts[1] == "aws-cn") != region.starts_with("cn-")
        || (parts[1] == "aws-us-gov") != region.starts_with("us-gov-")
    {
        return Err(AwsKmsError::InvalidConfiguration);
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SigningAlgorithm {
    EcdsaSha256,
    EcdsaSha384,
    EcdsaSha512,
    RsassaPkcs1V15Sha256,
    RsassaPkcs1V15Sha384,
    RsassaPkcs1V15Sha512,
    RsassaPssSha256,
    RsassaPssSha384,
    RsassaPssSha512,
}

impl SigningAlgorithm {
    pub fn from_aws_name(name: &str) -> Result<Self, AwsKmsError> {
        match name {
            "ECDSA_SHA_256" => Ok(Self::EcdsaSha256),
            "ECDSA_SHA_384" => Ok(Self::EcdsaSha384),
            "ECDSA_SHA_512" => Ok(Self::EcdsaSha512),
            "RSASSA_PKCS1_V1_5_SHA_256" => Ok(Self::RsassaPkcs1V15Sha256),
            "RSASSA_PKCS1_V1_5_SHA_384" => Ok(Self::RsassaPkcs1V15Sha384),
            "RSASSA_PKCS1_V1_5_SHA_512" => Ok(Self::RsassaPkcs1V15Sha512),
            "RSASSA_PSS_SHA_256" => Ok(Self::RsassaPssSha256),
            "RSASSA_PSS_SHA_384" => Ok(Self::RsassaPssSha384),
            "RSASSA_PSS_SHA_512" => Ok(Self::RsassaPssSha512),
            _ => Err(AwsKmsError::InvalidInput),
        }
    }

    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::EcdsaSha256 => "ECDSA_SHA_256",
            Self::EcdsaSha384 => "ECDSA_SHA_384",
            Self::EcdsaSha512 => "ECDSA_SHA_512",
            Self::RsassaPkcs1V15Sha256 => "RSASSA_PKCS1_V1_5_SHA_256",
            Self::RsassaPkcs1V15Sha384 => "RSASSA_PKCS1_V1_5_SHA_384",
            Self::RsassaPkcs1V15Sha512 => "RSASSA_PKCS1_V1_5_SHA_512",
            Self::RsassaPssSha256 => "RSASSA_PSS_SHA_256",
            Self::RsassaPssSha384 => "RSASSA_PSS_SHA_384",
            Self::RsassaPssSha512 => "RSASSA_PSS_SHA_512",
        }
    }

    #[must_use]
    pub const fn digest_len(self) -> usize {
        match self {
            Self::EcdsaSha256 | Self::RsassaPkcs1V15Sha256 | Self::RsassaPssSha256 => 32,
            Self::EcdsaSha384 | Self::RsassaPkcs1V15Sha384 | Self::RsassaPssSha384 => 48,
            Self::EcdsaSha512 | Self::RsassaPkcs1V15Sha512 | Self::RsassaPssSha512 => 64,
        }
    }

    fn accepts_spec(self, key_spec: &str) -> bool {
        match self {
            Self::EcdsaSha256 => key_spec == "ECC_NIST_P256",
            Self::EcdsaSha384 => key_spec == "ECC_NIST_P384",
            Self::EcdsaSha512 => key_spec == "ECC_NIST_P521",
            _ => matches!(key_spec, "RSA_2048" | "RSA_3072" | "RSA_4096"),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum KeyCapability {
    Signing(SigningAlgorithm),
    HmacSha256,
    SymmetricEncryption,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct KeyMetadata {
    pub key_arn: String,
    pub key_spec: String,
    pub key_usage: String,
    pub enabled: bool,
    pub key_state: String,
    pub origin: String,
    pub signing_algorithms: Vec<String>,
    pub mac_algorithms: Vec<String>,
    pub encryption_algorithms: Vec<String>,
}

impl KeyMetadata {
    pub fn validate(&self, capability: KeyCapability) -> Result<(), AwsKmsError> {
        let matches = match capability {
            KeyCapability::Signing(algorithm) => {
                self.key_usage == "SIGN_VERIFY"
                    && algorithm.accepts_spec(&self.key_spec)
                    && self
                        .signing_algorithms
                        .iter()
                        .any(|v| v == algorithm.as_str())
            }
            KeyCapability::HmacSha256 => {
                self.key_usage == "GENERATE_VERIFY_MAC"
                    && self.key_spec == "HMAC_256"
                    && self.mac_algorithms.iter().any(|v| v == "HMAC_SHA_256")
                    && self.origin == "AWS_KMS"
            }
            KeyCapability::SymmetricEncryption => {
                self.key_usage == "ENCRYPT_DECRYPT"
                    && self.key_spec == "SYMMETRIC_DEFAULT"
                    && self
                        .encryption_algorithms
                        .iter()
                        .any(|v| v == "SYMMETRIC_DEFAULT")
                    && self.origin == "AWS_KMS"
            }
        };
        if self.enabled && self.key_state == "Enabled" && matches {
            Ok(())
        } else {
            Err(AwsKmsError::InvalidResponse)
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PublicKey {
    pub spki_der: Vec<u8>,
    pub key_spec: String,
    pub key_usage: String,
    pub signing_algorithms: Vec<String>,
}

#[cfg(test)]
mod tests;
