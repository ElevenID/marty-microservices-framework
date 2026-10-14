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
use tokio::{net::TcpStream, sync::Semaphore, time::timeout};
use tokio_rustls::{TlsAcceptor, TlsConnector, server::TlsStream};
use tonic::transport::{Channel, Endpoint};
use tower::service_fn;
use url::Url;

use crate::{PlatformError, install_default_crypto_provider};

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

/// A Tonic channel whose TCP socket is wrapped by Rustls with a keyless mTLS
/// identity. Tonic's PEM-only TLS connector is bypassed, while gRPC requests
/// retain an HTTPS origin and HTTP/2 ALPN.
#[derive(Clone)]
pub struct KeylessGrpcChannelFactory {
    endpoint: Endpoint,
    tls: Arc<ClientConfig>,
    server_name: ServerName<'static>,
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
        if connect_timeout.is_zero() || request_timeout.is_zero() {
            return Err(invalid("gRPC TLS timeouts must be positive"));
        }
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
            .connect_timeout(connect_timeout)
            .timeout(request_timeout);
        let tls = keyless_grpc_client_config(identity, server_ca_der)?;
        Ok(Self {
            endpoint,
            tls,
            server_name: name,
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
        service_fn(move |uri: Uri| {
            let tls = tls.clone();
            let server_name = server_name.clone();
            async move {
                let authority = uri.authority().ok_or_else(|| {
                    io::Error::new(io::ErrorKind::InvalidInput, "missing gRPC authority")
                })?;
                let stream = TcpStream::connect(authority.as_str()).await?;
                stream.set_nodelay(true)?;
                let encrypted = TlsConnector::from(tls).connect(server_name, stream).await?;
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
        if max_handshakes == 0 || handshake_timeout.is_zero() {
            return Err(invalid("gRPC TLS handshake limits must be positive"));
        }
        let tls = keyless_grpc_server_config(identity, client_ca_der)?;
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
        timeout(self.handshake_timeout, self.tls.accept(stream))
            .await
            .map_err(|_| io::Error::new(io::ErrorKind::TimedOut, "gRPC TLS handshake timeout"))?
    }
}
