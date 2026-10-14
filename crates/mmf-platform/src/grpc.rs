//! Public-trust gRPC channels. Workload mTLS identities use the keyless
//! connector in `grpc_keyless`; this module never accepts a private key.

use std::{fs, path::Path, time::Duration};

use serde::{Deserialize, Serialize};
use tonic::transport::{Certificate, Channel, ClientTlsConfig, Endpoint};
use url::Url;

use crate::PlatformError;

/// Installs MMF's process-wide Rustls crypto policy when no provider has been
/// selected yet. Feature unification can make multiple providers available.
pub fn install_default_crypto_provider() -> Result<(), PlatformError> {
    if rustls::crypto::CryptoProvider::get_default().is_none()
        && rustls::crypto::ring::default_provider()
            .install_default()
            .is_err()
        && rustls::crypto::CryptoProvider::get_default().is_none()
    {
        return Err(PlatformError::ProviderUnavailable(
            "Rustls crypto provider".into(),
        ));
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GrpcTransportSecurity {
    #[default]
    Plaintext,
    ServerTls,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GrpcTrustMode {
    #[default]
    NativeRoots,
    CustomCa,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct GrpcChannelConfig {
    pub target: String,
    #[serde(default)]
    pub security: GrpcTransportSecurity,
    #[serde(default)]
    pub trust: GrpcTrustMode,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub server_name: Option<String>,
    #[serde(default = "default_connect_timeout_ms")]
    pub connect_timeout_ms: u64,
    #[serde(default = "default_request_timeout_ms")]
    pub request_timeout_ms: u64,
    #[serde(default = "default_tcp_keepalive_ms")]
    pub tcp_keepalive_ms: u64,
    #[serde(default = "default_http2_keepalive_interval_ms")]
    pub http2_keepalive_interval_ms: u64,
    #[serde(default = "default_http2_keepalive_timeout_ms")]
    pub http2_keepalive_timeout_ms: u64,
}

impl GrpcChannelConfig {
    pub fn validate(&self, material: &GrpcTlsMaterial) -> Result<(), PlatformError> {
        let url = validated_target(&self.target)?;
        for (value, name) in [
            (self.connect_timeout_ms, "connect timeout"),
            (self.request_timeout_ms, "request timeout"),
            (self.tcp_keepalive_ms, "TCP keepalive"),
            (
                self.http2_keepalive_interval_ms,
                "HTTP/2 keepalive interval",
            ),
            (self.http2_keepalive_timeout_ms, "HTTP/2 keepalive timeout"),
        ] {
            bounded_milliseconds(value, name)?;
        }
        if let Some(server_name) = &self.server_name {
            validate_server_name(server_name)?;
        }
        match self.security {
            GrpcTransportSecurity::Plaintext => {
                if url.scheme() != "http"
                    || self.trust != GrpcTrustMode::NativeRoots
                    || self.server_name.is_some()
                    || material.ca_certificate_pem.is_some()
                {
                    return Err(invalid("plaintext gRPC configuration includes TLS state"));
                }
            }
            GrpcTransportSecurity::ServerTls => {
                if url.scheme() != "https" {
                    return Err(invalid("TLS gRPC target must use https"));
                }
                match self.trust {
                    GrpcTrustMode::NativeRoots if material.ca_certificate_pem.is_some() => {
                        return Err(invalid("native-root trust cannot include a custom CA"));
                    }
                    GrpcTrustMode::CustomCa => {
                        validate_certificate(material.ca_certificate_pem.as_deref())?;
                    }
                    GrpcTrustMode::NativeRoots => {}
                }
            }
        }
        Ok(())
    }
}

impl Default for GrpcChannelConfig {
    fn default() -> Self {
        Self {
            target: "http://127.0.0.1:50051".into(),
            security: GrpcTransportSecurity::Plaintext,
            trust: GrpcTrustMode::NativeRoots,
            server_name: None,
            connect_timeout_ms: default_connect_timeout_ms(),
            request_timeout_ms: default_request_timeout_ms(),
            tcp_keepalive_ms: default_tcp_keepalive_ms(),
            http2_keepalive_interval_ms: default_http2_keepalive_interval_ms(),
            http2_keepalive_timeout_ms: default_http2_keepalive_timeout_ms(),
        }
    }
}

/// Public CA material only. Client identities use `KeylessTlsIdentity`.
#[derive(Clone, Default)]
pub struct GrpcTlsMaterial {
    pub ca_certificate_pem: Option<Vec<u8>>,
}

impl GrpcTlsMaterial {
    pub fn from_ca_pem_file(ca_certificate: Option<&Path>) -> Result<Self, PlatformError> {
        let ca_certificate_pem = ca_certificate
            .map(|path| {
                fs::read(path).map_err(|_| invalid("gRPC CA certificate could not be read"))
            })
            .transpose()?;
        Ok(Self { ca_certificate_pem })
    }
}

#[derive(Clone)]
pub struct GrpcChannelFactory {
    config: GrpcChannelConfig,
    material: GrpcTlsMaterial,
}

impl GrpcChannelFactory {
    pub fn new(
        config: GrpcChannelConfig,
        material: GrpcTlsMaterial,
    ) -> Result<Self, PlatformError> {
        config.validate(&material)?;
        if config.security == GrpcTransportSecurity::ServerTls {
            install_default_crypto_provider()?;
        }
        Ok(Self { config, material })
    }

    #[must_use]
    pub const fn config(&self) -> &GrpcChannelConfig {
        &self.config
    }

    pub fn endpoint(&self) -> Result<Endpoint, PlatformError> {
        self.config.validate(&self.material)?;
        let mut endpoint = Endpoint::from_shared(self.config.target.clone())
            .map_err(|_| invalid("gRPC target is invalid"))?
            .connect_timeout(Duration::from_millis(self.config.connect_timeout_ms))
            .timeout(Duration::from_millis(self.config.request_timeout_ms))
            .tcp_keepalive(Some(Duration::from_millis(self.config.tcp_keepalive_ms)))
            .http2_keep_alive_interval(Duration::from_millis(
                self.config.http2_keepalive_interval_ms,
            ))
            .keep_alive_timeout(Duration::from_millis(
                self.config.http2_keepalive_timeout_ms,
            ))
            .keep_alive_while_idle(true);
        if self.config.security == GrpcTransportSecurity::ServerTls {
            let host = Url::parse(&self.config.target)
                .ok()
                .and_then(|url| url.host_str().map(str::to_owned))
                .ok_or_else(|| invalid("gRPC target host is invalid"))?;
            let tls =
                ClientTlsConfig::new().domain_name(self.config.server_name.clone().unwrap_or(host));
            let tls = match self.config.trust {
                GrpcTrustMode::NativeRoots => tls.with_native_roots(),
                GrpcTrustMode::CustomCa => tls.ca_certificate(Certificate::from_pem(
                    self.material
                        .ca_certificate_pem
                        .clone()
                        .ok_or_else(|| invalid("custom CA certificate is required"))?,
                )),
            };
            endpoint = endpoint
                .tls_config(tls)
                .map_err(|_| invalid("gRPC TLS material is invalid"))?;
        }
        Ok(endpoint)
    }

    pub fn connect_lazy(&self) -> Result<Channel, PlatformError> {
        self.endpoint().map(|endpoint| endpoint.connect_lazy())
    }

    pub async fn connect(&self) -> Result<Channel, PlatformError> {
        self.endpoint()?
            .connect()
            .await
            .map_err(|_| PlatformError::ProviderUnavailable("gRPC dependency".into()))
    }
}

fn validated_target(target: &str) -> Result<Url, PlatformError> {
    let url = Url::parse(target).map_err(|_| invalid("gRPC target is invalid"))?;
    if !matches!(url.scheme(), "http" | "https")
        || url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
        || !matches!(url.path(), "" | "/")
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err(invalid(
            "gRPC target must be a credential-free HTTP(S) origin",
        ));
    }
    Ok(url)
}

fn validate_server_name(value: &str) -> Result<(), PlatformError> {
    let candidate = Url::parse(&format!("https://{value}"))
        .map_err(|_| invalid("gRPC TLS server name is invalid"))?;
    if candidate.host_str() != Some(value)
        || candidate.port().is_some()
        || candidate.path() != "/"
        || candidate.query().is_some()
        || candidate.fragment().is_some()
    {
        return Err(invalid("gRPC TLS server name is invalid"));
    }
    Ok(())
}

fn validate_certificate(value: Option<&[u8]>) -> Result<(), PlatformError> {
    if value.is_some_and(|value| {
        value
            .windows(b"-----BEGIN CERTIFICATE-----".len())
            .any(|window| window == b"-----BEGIN CERTIFICATE-----")
            && !value
                .windows(b"PRIVATE KEY".len())
                .any(|window| window == b"PRIVATE KEY")
    }) {
        Ok(())
    } else {
        Err(invalid("custom CA certificate is missing or malformed"))
    }
}

fn bounded_milliseconds(value: u64, name: &str) -> Result<(), PlatformError> {
    if (1..=300_000).contains(&value) {
        Ok(())
    } else {
        Err(invalid(&format!("{name} must be between 1 and 300000 ms")))
    }
}

fn invalid(message: &str) -> PlatformError {
    PlatformError::InvalidConfiguration(message.into())
}

const fn default_connect_timeout_ms() -> u64 {
    5_000
}
const fn default_request_timeout_ms() -> u64 {
    10_000
}
const fn default_tcp_keepalive_ms() -> u64 {
    30_000
}
const fn default_http2_keepalive_interval_ms() -> u64 {
    30_000
}
const fn default_http2_keepalive_timeout_ms() -> u64 {
    10_000
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn public_ca_material_rejects_bundled_private_key() {
        let config = GrpcChannelConfig {
            target: "https://example.test:443".into(),
            security: GrpcTransportSecurity::ServerTls,
            trust: GrpcTrustMode::CustomCa,
            ..GrpcChannelConfig::default()
        };
        let material = GrpcTlsMaterial {
            ca_certificate_pem: Some(
                b"-----BEGIN CERTIFICATE-----\npublic\n-----END CERTIFICATE-----\n-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----".to_vec(),
            ),
        };
        assert!(GrpcChannelFactory::new(config, material).is_err());
    }
}
