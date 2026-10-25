//! Opt-in component qualification, not installer acceptance. The caller must
//! hold the native installation-directory lock and authenticate the expected
//! engine, owned OpenBao containers and completed ingress receipt before/after
//! this test. No Docker operation or authority mutation is performed here.
#![cfg(target_os = "linux")]

use mmf_platform::{OpenBaoTlsIdentityFiles, read_public_certificates};
use rustls::{
    ClientConfig, RootCertStore,
    pki_types::{CertificateDer, ServerName},
};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::Read,
    path::{Path, PathBuf},
    sync::Arc,
    time::Duration,
};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::{TcpListener, TcpStream},
    time::timeout,
};
use tokio_rustls::TlsConnector;

type Result<T> = std::result::Result<T, &'static str>;
const LIMIT: u64 = 65536;

fn require(ok: bool) -> Result<()> {
    if ok {
        Ok(())
    } else {
        Err("fixture admission refused")
    }
}

fn read(root: &Path, name: &str) -> Result<Vec<u8>> {
    let path = root.join(name);
    require(path.canonicalize().map_err(|_| "fixture path refused")? == path)?;
    let before = fs::symlink_metadata(&path).map_err(|_| "fixture file refused")?;
    require(before.is_file() && before.len() > 0 && before.len() <= LIMIT)?;
    let mut bytes = Vec::new();
    fs::File::open(path)
        .map_err(|_| "fixture file refused")?
        .take(LIMIT + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "fixture read refused")?;
    require(bytes.len() as u64 == before.len())?;
    Ok(bytes)
}

fn sha256_hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

async fn exercise() -> Result<()> {
    let root = PathBuf::from(
        std::env::var("MMF_INSTALLER_TLS_ROOT").map_err(|_| "fixture root required")?,
    );
    require(
        root.is_absolute() && root.canonicalize().map_err(|_| "fixture root refused")? == root,
    )?;
    let id = std::env::var("MMF_INSTALLER_TLS_UUID").map_err(|_| "fixture UUID required")?;
    let uuid = uuid::Uuid::parse_str(&id).map_err(|_| "fixture UUID refused")?;
    require(uuid.to_string() == id)?;
    let engine =
        std::env::var("MMF_INSTALLER_TLS_ENGINE_ID").map_err(|_| "fixture engine required")?;
    require(!engine.is_empty() && engine.len() <= 128)?;
    let names = [
        "installation.json",
        "evidence/installer-ingress.json",
        "evidence/ingress-container-removed.json",
        "secrets/installer_ingress_ca_cert",
        "secrets/installer_ingress_tls_cert",
        "secrets/openbao_tls_ca_cert",
    ];
    let before = names
        .iter()
        .map(|name| read(&root, name))
        .collect::<Result<Vec<_>>>()?;
    let journal: Value = serde_json::from_slice(&before[0]).map_err(|_| "journal refused")?;
    let metadata: Value = serde_json::from_slice(&before[1]).map_err(|_| "metadata refused")?;
    let receipt: Value = serde_json::from_slice(&before[2]).map_err(|_| "receipt refused")?;
    let key = format!("installer-ingress-{}", uuid.simple());
    require(
        journal["installation_id"] == id
            && journal["runtime"]["engine_id"] == engine
            && journal["runtime"]["docker_host"] == "unix:///var/run/docker.sock",
    )?;
    require(
        metadata["schema"] == "elevenid.installer-ingress/v1"
            && metadata["installation_id"] == id
            && metadata["key_name"] == key
            && metadata["key_version"] == 1
            && metadata["installation_ready"] == false,
    )?;
    require(
        receipt["installation_id"] == id
            && receipt["engine_id"] == engine
            && receipt["authority_name"] == key
            && receipt["container_removed"] == true
            && receipt["installation_ready"] == false,
    )?;
    require(
        metadata["ca_pem_sha256"] == sha256_hex(&before[3])
            && metadata["certificate_pem_sha256"] == sha256_hex(&before[4]),
    )?;
    let port = journal["runtime"]["openbao_port"]
        .as_u64()
        .filter(|v| (1024..=65535).contains(v))
        .ok_or("fixture port refused")?;
    let token = root.join("secrets/installer_ingress_tls_kms_token");
    require(token.canonicalize().map_err(|_| "token path refused")? == token)?;
    let token_metadata = fs::symlink_metadata(&token).map_err(|_| "token file refused")?;
    require(token_metadata.is_file() && token_metadata.len() > 0 && token_metadata.len() <= LIMIT)?;
    // Only the production signer reads the scoped token; no root/private key is used.
    let identity = OpenBaoTlsIdentityFiles {
        certificate_chain_file: root.join(names[4]),
        kms_ca_cert_file: root.join(names[5]),
        kms_endpoint: format!("https://127.0.0.1:{port}"),
        kms_token_file: token,
        kms_key_name: key,
        kms_key_version: 1,
        request_timeout: Duration::from_secs(5),
        max_concurrent_signs: 2,
    };
    let acceptor = identity
        .grpc_acceptor_without_client_auth(2, Duration::from_secs(8))
        .await
        .map_err(|_| "remote signer connection failed")?;
    let mut roots = RootCertStore::empty();
    for cert in read_public_certificates(&root.join(names[3])).map_err(|_| "trust refused")? {
        roots
            .add(CertificateDer::from(cert))
            .map_err(|_| "trust refused")?;
    }
    let mut config = ClientConfig::builder()
        .with_root_certificates(roots)
        .with_no_client_auth();
    config.alpn_protocols = vec![b"h2".to_vec()];
    let connector = TlsConnector::from(Arc::new(config));
    for valid_name in [true, false] {
        let listener = TcpListener::bind("127.0.0.1:0")
            .await
            .map_err(|_| "listener failed")?;
        let address = listener.local_addr().map_err(|_| "listener failed")?;
        let acceptor = acceptor.clone();
        let server = async move {
            let (stream, _) = listener.accept().await.map_err(|_| "accept failed")?;
            match acceptor.accept(stream).await {
                Ok(mut tls) => {
                    require(valid_name)?;
                    require(tls.get_ref().1.alpn_protocol() == Some(b"h2".as_slice()))?;
                    let mut request = [0; 4];
                    tls.read_exact(&mut request)
                        .await
                        .map_err(|_| "application read failed")?;
                    require(request == *b"ping")?;
                    tls.write_all(b"pong")
                        .await
                        .map_err(|_| "application write failed")?;
                    Ok(())
                }
                Err(_) if !valid_name => Ok(()),
                Err(_) => Err("server handshake failed"),
            }
        };
        let client = async {
            let stream = TcpStream::connect(address)
                .await
                .map_err(|_| "connect failed")?;
            let name = ServerName::try_from(if valid_name {
                "localhost"
            } else {
                "wrong.invalid"
            })
            .map_err(|_| "server name refused")?;
            match connector.connect(name, stream).await {
                Ok(mut tls) => {
                    require(valid_name)?;
                    require(tls.get_ref().1.alpn_protocol() == Some(b"h2".as_slice()))?;
                    tls.write_all(b"ping")
                        .await
                        .map_err(|_| "application write failed")?;
                    let mut response = [0; 4];
                    tls.read_exact(&mut response)
                        .await
                        .map_err(|_| "application read failed")?;
                    require(response == *b"pong")
                }
                Err(error) if !valid_name => require(matches!(
                    error
                        .get_ref()
                        .and_then(|e| e.downcast_ref::<rustls::Error>()),
                    Some(rustls::Error::InvalidCertificate(
                        rustls::CertificateError::NotValidForName
                            | rustls::CertificateError::NotValidForNameContext { .. }
                    ))
                )),
                Err(_) => Err("client handshake failed"),
            }
        };
        let (server, client) = timeout(Duration::from_secs(12), async {
            tokio::join!(server, client)
        })
        .await
        .map_err(|_| "handshake deadline expired")?;
        server?;
        client?;
    }
    for (name, expected) in names.iter().zip(before) {
        require(read(&root, name)? == expected)?;
    }
    Ok(())
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
#[ignore = "requires externally locked, authenticated live installer ingress fixture"]
async fn actual_scoped_openbao_signer_completes_tls_and_rejects_wrong_sni() {
    let result = timeout(Duration::from_secs(40), exercise()).await;
    assert!(
        matches!(result, Ok(Ok(()))),
        "live TLS component qualification failed (details redacted)"
    );
}
