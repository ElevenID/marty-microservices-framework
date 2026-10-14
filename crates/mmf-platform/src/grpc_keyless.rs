//! Public-certificate gRPC TLS plumbing for a remotely held signing key.
//!
//! The `SigningKey` implementation is supplied by the service's KMS adapter;
//! this module never accepts a private-key PEM or serializes key material.

use std::{fmt, future::Future, io, sync::Arc, time::Duration};

use http::Uri;
use hyper_util::rt::TokioIo;
use rustls::{
    ClientConfig, RootCertStore, ServerConfig,
    pki_types::{CertificateDer, ServerName},
    server::WebPkiClientVerifier,
    sign::{CertifiedKey, SigningKey, SingleCertAndKey},
};
use tokio::{net::TcpStream, sync::Semaphore, time::timeout_at};
use tokio_rustls::{TlsAcceptor, TlsConnector, server::TlsStream};
use tonic::transport::{Channel, Endpoint};
use tower::service_fn;
use url::Url;

use crate::{PlatformError, install_default_crypto_provider};

tokio::task_local! {
    static HANDSHAKE_DEADLINE: std::time::Instant;
}

pub(crate) fn remaining_handshake_time() -> Option<Duration> {
    HANDSHAKE_DEADLINE
        .try_with(|deadline| deadline.saturating_duration_since(std::time::Instant::now()))
        .ok()
}

fn invalid(message: &str) -> PlatformError {
    PlatformError::InvalidConfiguration(message.into())
}

/// A public certificate chain bound to an opaque Rustls signing implementation.
/// The signer must keep the long-lived private key inside its KMS/HSM boundary.
#[derive(Clone)]
pub struct KeylessTlsIdentity {
    certified: Arc<CertifiedKey>,
}

impl fmt::Debug for KeylessTlsIdentity {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("KeylessTlsIdentity(..)")
    }
}

impl KeylessTlsIdentity {
    pub fn new(
        certificate_chain_der: Vec<Vec<u8>>,
        signer: Arc<dyn SigningKey>,
    ) -> Result<Self, PlatformError> {
        if certificate_chain_der.is_empty() {
            return Err(invalid("TLS certificate chain is required"));
        }
        let chain = certificate_chain_der
            .into_iter()
            .map(CertificateDer::from)
            .collect();
        let certified = CertifiedKey::new(chain, signer);
        certified
            .keys_match()
            .map_err(|_| invalid("TLS certificate does not match the remote signing key"))?;
        Ok(Self {
            certified: Arc::new(certified),
        })
    }

    fn resolver(&self) -> Arc<SingleCertAndKey> {
        Arc::new(SingleCertAndKey::from(self.certified.clone()))
    }
}

fn trusted_roots(ca_certificates_der: Vec<Vec<u8>>) -> Result<RootCertStore, PlatformError> {
    if ca_certificates_der.is_empty() {
        return Err(invalid("TLS CA certificates are required"));
    }
    let mut roots = RootCertStore::empty();
    for certificate in ca_certificates_der {
        roots
            .add(CertificateDer::from(certificate))
            .map_err(|_| invalid("TLS CA certificate is invalid"))?;
    }
    Ok(roots)
}

/// Build an HTTPS listener which authenticates with a remote signer. Use this
/// only for routes whose client authentication is enforced at the application
/// layer; gRPC workload links should use `keyless_grpc_server_config` instead.
pub fn keyless_https_server_config(
    identity: &KeylessTlsIdentity,
) -> Result<Arc<ServerConfig>, PlatformError> {
    install_default_crypto_provider()?;
    let config = ServerConfig::builder()
        .with_no_client_auth()
        .with_cert_resolver(identity.resolver());
    Ok(Arc::new(config))
}

/// Build a server configuration which requires a trusted client certificate.
/// The caller must bind the authenticated peer identity to its own workload
/// authorization after the handshake.
pub fn keyless_grpc_server_config(
    identity: &KeylessTlsIdentity,
    client_ca_der: Vec<Vec<u8>>,
) -> Result<Arc<ServerConfig>, PlatformError> {
    install_default_crypto_provider()?;
    let verifier = WebPkiClientVerifier::builder(Arc::new(trusted_roots(client_ca_der)?))
        .build()
        .map_err(|_| invalid("TLS client CA configuration is invalid"))?;
    let mut config = ServerConfig::builder()
        .with_client_cert_verifier(verifier)
        .with_cert_resolver(identity.resolver());
    config.alpn_protocols = vec![b"h2".to_vec()];
    Ok(Arc::new(config))
}

/// Build a keyless gRPC listener whose callers authenticate at the application
/// layer. The HTTP/2 ALPN setting is required even without client mTLS.
pub fn keyless_grpc_server_config_without_client_auth(
    identity: &KeylessTlsIdentity,
) -> Result<Arc<ServerConfig>, PlatformError> {
    install_default_crypto_provider()?;
    let mut config = ServerConfig::builder()
        .with_no_client_auth()
        .with_cert_resolver(identity.resolver());
    config.alpn_protocols = vec![b"h2".to_vec()];
    Ok(Arc::new(config))
}

/// Build a client configuration for CA-validated gRPC mTLS.
pub fn keyless_grpc_client_config(
    identity: &KeylessTlsIdentity,
    server_ca_der: Vec<Vec<u8>>,
) -> Result<Arc<ClientConfig>, PlatformError> {
    install_default_crypto_provider()?;
    let roots = trusted_roots(server_ca_der)?;
    let mut config = ClientConfig::builder()
        .with_root_certificates(roots)
        .with_client_cert_resolver(identity.resolver());
    config.alpn_protocols = vec![b"h2".to_vec()];
    Ok(Arc::new(config))
}

/// Bounded connection and keepalive settings for a keyless gRPC channel.
#[derive(Clone, Copy, Debug)]
pub struct KeylessGrpcTransportOptions {
    pub connect_timeout: Duration,
    pub request_timeout: Duration,
    pub tcp_keepalive: Duration,
    pub http2_keepalive_interval: Duration,
    pub http2_keepalive_timeout: Duration,
}

impl Default for KeylessGrpcTransportOptions {
    fn default() -> Self {
        Self {
            connect_timeout: Duration::from_secs(5),
            request_timeout: Duration::from_secs(10),
            tcp_keepalive: Duration::from_secs(30),
            http2_keepalive_interval: Duration::from_secs(30),
            http2_keepalive_timeout: Duration::from_secs(10),
        }
    }
}

impl KeylessGrpcTransportOptions {
    fn validate(self) -> Result<(), PlatformError> {
        let bounded =
            |value: Duration| value >= Duration::from_millis(1) && value <= Duration::from_mins(5);
        if !bounded(self.connect_timeout)
            || !bounded(self.request_timeout)
            || !bounded(self.tcp_keepalive)
            || !bounded(self.http2_keepalive_interval)
            || !bounded(self.http2_keepalive_timeout)
        {
            return Err(invalid(
                "gRPC TLS transport durations must be within 1 ms and 5 minutes",
            ));
        }
        Ok(())
    }
}

/// A Tonic channel whose TCP socket is wrapped by Rustls with a keyless mTLS
/// identity. Tonic's PEM-only TLS connector is bypassed, while gRPC requests
/// retain an HTTPS origin and HTTP/2 ALPN.
#[derive(Clone)]
pub struct KeylessGrpcChannelFactory {
    endpoint: Endpoint,
    tls: Arc<ClientConfig>,
    server_name: ServerName<'static>,
    connect_timeout: Duration,
}

impl KeylessGrpcChannelFactory {
    pub fn new(
        target: &str,
        server_name: &str,
        identity: &KeylessTlsIdentity,
        server_ca_der: Vec<Vec<u8>>,
        connect_timeout: Duration,
        request_timeout: Duration,
    ) -> Result<Self, PlatformError> {
        Self::with_options(
            target,
            server_name,
            identity,
            server_ca_der,
            KeylessGrpcTransportOptions {
                connect_timeout,
                request_timeout,
                ..KeylessGrpcTransportOptions::default()
            },
        )
    }

    pub fn with_options(
        target: &str,
        server_name: &str,
        identity: &KeylessTlsIdentity,
        server_ca_der: Vec<Vec<u8>>,
        options: KeylessGrpcTransportOptions,
    ) -> Result<Self, PlatformError> {
        options.validate()?;
        let target_url = Url::parse(target).map_err(|_| invalid("gRPC TLS target is invalid"))?;
        if target_url.scheme() != "https"
            || target_url.host_str().is_none()
            || !target_url.username().is_empty()
            || target_url.password().is_some()
            || target_url.path() != "/"
            || target_url.query().is_some()
            || target_url.fragment().is_some()
        {
            return Err(invalid(
                "gRPC TLS target must be a credential-free HTTPS origin",
            ));
        }
        let name = ServerName::try_from(server_name.to_owned())
            .map_err(|_| invalid("gRPC TLS server name is invalid"))?;
        let port = target_url
            .port_or_known_default()
            .ok_or_else(|| invalid("gRPC TLS target port is invalid"))?;
        let mut transport_url = target_url.clone();
        transport_url
            .set_scheme("http")
            .map_err(|()| invalid("gRPC TLS target scheme is invalid"))?;
        transport_url
            .set_port(Some(port))
            .map_err(|()| invalid("gRPC TLS target port is invalid"))?;
        let origin: Uri = target
            .parse()
            .map_err(|_| invalid("gRPC TLS origin is invalid"))?;
        let endpoint = Endpoint::from_shared(transport_url.as_str().to_owned())
            .map_err(|_| invalid("gRPC TLS target is invalid"))?
            .origin(origin)
            .connect_timeout(options.connect_timeout)
            .timeout(options.request_timeout)
            .tcp_keepalive(Some(options.tcp_keepalive))
            .http2_keep_alive_interval(options.http2_keepalive_interval)
            .keep_alive_timeout(options.http2_keepalive_timeout)
            .keep_alive_while_idle(true);
        let tls = keyless_grpc_client_config(identity, server_ca_der)?;
        Ok(Self {
            endpoint,
            tls,
            server_name: name,
            connect_timeout: options.connect_timeout,
        })
    }

    fn connector(
        &self,
    ) -> impl tower::Service<
        Uri,
        Response = TokioIo<tokio_rustls::client::TlsStream<TcpStream>>,
        Error = io::Error,
        Future = impl Future<Output = io::Result<TokioIo<tokio_rustls::client::TlsStream<TcpStream>>>>
                 + Send,
    > + Clone
    + Send
    + 'static {
        let tls = self.tls.clone();
        let server_name = self.server_name.clone();
        let connect_timeout = self.connect_timeout;
        service_fn(move |uri: Uri| {
            let tls = tls.clone();
            let server_name = server_name.clone();
            async move {
                let authority = uri.authority().ok_or_else(|| {
                    io::Error::new(io::ErrorKind::InvalidInput, "missing gRPC authority")
                })?;
                let stream =
                    tokio::time::timeout(connect_timeout, TcpStream::connect(authority.as_str()))
                        .await
                        .map_err(|_| {
                            io::Error::new(io::ErrorKind::TimedOut, "gRPC TCP connect timeout")
                        })??;
                stream.set_nodelay(true)?;
                let deadline = tokio::time::Instant::now() + connect_timeout;
                let encrypted = HANDSHAKE_DEADLINE
                    .scope(deadline.into_std(), async {
                        timeout_at(
                            deadline,
                            TlsConnector::from(tls).connect(server_name, stream),
                        )
                        .await
                    })
                    .await
                    .map_err(|_| {
                        io::Error::new(io::ErrorKind::TimedOut, "gRPC TLS handshake timeout")
                    })??;
                Ok(TokioIo::new(encrypted))
            }
        })
    }

    pub fn connect_lazy(&self) -> Channel {
        self.endpoint.connect_with_connector_lazy(self.connector())
    }

    pub async fn connect(&self) -> Result<Channel, PlatformError> {
        self.endpoint
            .connect_with_connector(self.connector())
            .await
            .map_err(|_| PlatformError::ProviderUnavailable("gRPC TLS dependency".into()))
    }
}

/// Caps simultaneous TLS handshakes and fails closed when the KMS signer or
/// peer validation fails. The signer itself must bound its synchronous KMS call.
#[derive(Clone)]
pub struct KeylessGrpcTlsAcceptor {
    tls: TlsAcceptor,
    permits: Arc<Semaphore>,
    handshake_timeout: Duration,
}

impl KeylessGrpcTlsAcceptor {
    pub fn new(
        identity: &KeylessTlsIdentity,
        client_ca_der: Vec<Vec<u8>>,
        max_handshakes: usize,
        handshake_timeout: Duration,
    ) -> Result<Self, PlatformError> {
        let tls = keyless_grpc_server_config(identity, client_ca_der)?;
        Self::from_config(tls, max_handshakes, handshake_timeout)
    }

    pub fn without_client_auth(
        identity: &KeylessTlsIdentity,
        max_handshakes: usize,
        handshake_timeout: Duration,
    ) -> Result<Self, PlatformError> {
        let tls = keyless_grpc_server_config_without_client_auth(identity)?;
        Self::from_config(tls, max_handshakes, handshake_timeout)
    }

    fn from_config(
        tls: Arc<ServerConfig>,
        max_handshakes: usize,
        handshake_timeout: Duration,
    ) -> Result<Self, PlatformError> {
        if max_handshakes == 0 || handshake_timeout.is_zero() {
            return Err(invalid("gRPC TLS handshake limits must be positive"));
        }
        Ok(Self {
            tls: TlsAcceptor::from(tls),
            permits: Arc::new(Semaphore::new(max_handshakes)),
            handshake_timeout,
        })
    }

    pub async fn accept(&self, stream: TcpStream) -> io::Result<TlsStream<TcpStream>> {
        let _permit =
            self.permits.clone().try_acquire_owned().map_err(|_| {
                io::Error::new(io::ErrorKind::WouldBlock, "gRPC TLS handshake limit")
            })?;
        let deadline = tokio::time::Instant::now() + self.handshake_timeout;
        HANDSHAKE_DEADLINE
            .scope(deadline.into_std(), async {
                timeout_at(deadline, self.tls.accept(stream)).await
            })
            .await
            .map_err(|_| io::Error::new(io::ErrorKind::TimedOut, "gRPC TLS handshake timeout"))?
    }
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use super::{HANDSHAKE_DEADLINE, KeylessGrpcTransportOptions, remaining_handshake_time};

    #[tokio::test(flavor = "multi_thread")]
    async fn synchronous_signer_sees_remaining_handshake_deadline() {
        assert!(remaining_handshake_time().is_none());
        HANDSHAKE_DEADLINE
            .scope(std::time::Instant::now() + Duration::from_secs(1), async {
                tokio::task::block_in_place(|| {
                    let remaining = remaining_handshake_time().unwrap();
                    assert!(!remaining.is_zero());
                    assert!(remaining <= Duration::from_secs(1));
                });
            })
            .await;
        assert!(remaining_handshake_time().is_none());
    }

    #[test]
    fn keyless_transport_preserves_bounded_keepalive_controls() {
        let defaults = KeylessGrpcTransportOptions::default();
        assert_eq!(defaults.tcp_keepalive, Duration::from_secs(30));
        assert_eq!(defaults.http2_keepalive_interval, Duration::from_secs(30));
        assert_eq!(defaults.http2_keepalive_timeout, Duration::from_secs(10));
        assert!(defaults.validate().is_ok());
        for timeout in [
            Duration::ZERO,
            Duration::from_micros(1),
            Duration::from_secs(301),
        ] {
            let options = KeylessGrpcTransportOptions {
                http2_keepalive_timeout: timeout,
                ..defaults
            };
            assert!(options.validate().is_err());
        }
    }
}
