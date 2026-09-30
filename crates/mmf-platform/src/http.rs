//! Provider-neutral HTTP behavior shared by MMF gateways and services.

use std::{
    collections::{BTreeMap, BTreeSet},
    sync::{Arc, Mutex},
};

use async_trait::async_trait;
#[cfg(feature = "redis")]
use redis::aio::MultiplexedConnection;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
#[cfg(feature = "redis")]
use tokio::sync::Mutex as AsyncMutex;
use uuid::Uuid;

use crate::PlatformError;

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ProtocolVersionPolicy {
    pub current: String,
    pub supported: BTreeSet<String>,
}

impl ProtocolVersionPolicy {
    pub fn new(
        current: impl Into<String>,
        supported: impl IntoIterator<Item = impl Into<String>>,
    ) -> Result<Self, PlatformError> {
        let policy = Self {
            current: current.into(),
            supported: supported.into_iter().map(Into::into).collect(),
        };
        policy.validate()?;
        Ok(policy)
    }

    pub fn validate(&self) -> Result<(), PlatformError> {
        if self.current.trim().is_empty()
            || self.supported.is_empty()
            || !self.supported.contains(&self.current)
            || self
                .supported
                .iter()
                .any(|version| version.trim().is_empty())
        {
            return Err(PlatformError::InvalidConfiguration(
                "protocol versions must be nonempty and include the current version".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn negotiate(&self, advertised: Option<&str>) -> ProtocolVersionDecision {
        advertised.map_or(ProtocolVersionDecision::Accepted, |version| {
            if self.supported.contains(version) {
                ProtocolVersionDecision::Accepted
            } else {
                ProtocolVersionDecision::Unsupported {
                    advertised: version.to_owned(),
                    supported: self.supported.iter().cloned().collect(),
                }
            }
        })
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ProtocolVersionDecision {
    Accepted,
    Unsupported {
        advertised: String,
        supported: Vec<String>,
    },
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ContentTypePolicy {
    pub body_methods: BTreeSet<String>,
    pub allowed_media_types: BTreeSet<String>,
    pub exempt_path_prefixes: Vec<String>,
}

impl ContentTypePolicy {
    pub fn validate(&self) -> Result<(), PlatformError> {
        if self.body_methods.is_empty()
            || self.allowed_media_types.is_empty()
            || self
                .body_methods
                .iter()
                .chain(self.allowed_media_types.iter())
                .any(|value| value.trim().is_empty())
            || self
                .exempt_path_prefixes
                .iter()
                .any(|prefix| !prefix.starts_with('/'))
        {
            return Err(PlatformError::InvalidConfiguration(
                "content-type policy contains an invalid method, media type, or path prefix".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn evaluate(
        &self,
        method: &str,
        path: &str,
        content_type: Option<&str>,
    ) -> ContentTypeDecision {
        if !self.body_methods.contains(&method.to_ascii_uppercase())
            || self
                .exempt_path_prefixes
                .iter()
                .any(|prefix| path.starts_with(prefix))
        {
            return ContentTypeDecision::Accepted;
        }
        let Some(content_type) = content_type else {
            return ContentTypeDecision::Accepted;
        };
        let media_type = content_type
            .split(';')
            .next()
            .unwrap_or_default()
            .trim()
            .to_ascii_lowercase();
        if media_type.is_empty() || self.allowed_media_types.contains(&media_type) {
            ContentTypeDecision::Accepted
        } else {
            ContentTypeDecision::Unsupported { media_type }
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ContentTypeDecision {
    Accepted,
    Unsupported { media_type: String },
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum EntityTagDecision {
    Bypass,
    Attach { entity_tag: String },
    NotModified { entity_tag: String },
}

pub struct EntityTagPolicy;

impl EntityTagPolicy {
    #[must_use]
    pub fn evaluate(
        method: &str,
        authenticated: bool,
        status: u16,
        cache_control: Option<&str>,
        if_none_match: Option<&str>,
        body: &[u8],
    ) -> EntityTagDecision {
        if !method.eq_ignore_ascii_case("GET")
            || authenticated
            || !(200..300).contains(&status)
            || cache_control.is_some_and(cache_control_disables_entity_tag)
        {
            return EntityTagDecision::Bypass;
        }
        let entity_tag = weak_entity_tag(body);
        if if_none_match == Some(entity_tag.as_str()) {
            EntityTagDecision::NotModified { entity_tag }
        } else {
            EntityTagDecision::Attach { entity_tag }
        }
    }
}

fn cache_control_disables_entity_tag(value: &str) -> bool {
    let value = value.to_ascii_lowercase();
    ["no-store", "no-cache", "private"]
        .iter()
        .any(|token| value.contains(token))
}

#[must_use]
pub fn weak_entity_tag(body: &[u8]) -> String {
    let digest = Sha256::digest(body);
    format!("W/\"{}\"", hex_prefix(&digest, 8))
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct IdempotencyRequest {
    pub principal_id: String,
    pub key: String,
    pub method: String,
    pub path: String,
    pub query: String,
    pub body: Vec<u8>,
}

impl IdempotencyRequest {
    pub fn validate(&self) -> Result<(), PlatformError> {
        if self.principal_id.trim().is_empty()
            || self.key.trim().is_empty()
            || self.method.trim().is_empty()
            || !self.path.starts_with('/')
        {
            return Err(PlatformError::InvalidConfiguration(
                "idempotency request requires a principal, key, method, and absolute path".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn namespace(&self) -> String {
        format!("{}:{}", self.principal_id, self.key)
    }

    #[must_use]
    pub fn fingerprint(&self) -> String {
        let body_digest = hex_digest(&self.body);
        hex_digest(
            format!(
                "{}\n{}\n{}\n{}",
                self.method.to_ascii_uppercase(),
                self.path,
                self.query,
                body_digest
            )
            .as_bytes(),
        )
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct IdempotencyResponse {
    pub status: u16,
    pub body: Vec<u8>,
    pub content_type: Option<String>,
    pub headers: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct IdempotencyLease {
    pub namespace: String,
    pub fingerprint: String,
    pub token: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum IdempotencyBegin {
    Started(IdempotencyLease),
    Replay(IdempotencyResponse),
    Conflict,
    InProgress,
}

#[async_trait]
pub trait IdempotencyStore: Send + Sync {
    async fn begin(
        &self,
        request: &IdempotencyRequest,
        now_ms: u64,
    ) -> Result<IdempotencyBegin, PlatformError>;

    async fn complete(
        &self,
        lease: &IdempotencyLease,
        response: IdempotencyResponse,
        now_ms: u64,
    ) -> Result<(), PlatformError>;

    async fn abort(&self, lease: &IdempotencyLease) -> Result<(), PlatformError>;
}

#[derive(Clone, Debug)]
enum IdempotencyEntry {
    InFlight {
        fingerprint: String,
        token: String,
        expires_at_ms: u64,
    },
    Complete {
        fingerprint: String,
        response: IdempotencyResponse,
        expires_at_ms: u64,
    },
}

#[derive(Clone, Debug)]
pub struct InMemoryIdempotencyStore {
    entries: Arc<Mutex<BTreeMap<String, IdempotencyEntry>>>,
    response_ttl_ms: u64,
    lock_ttl_ms: u64,
}

impl InMemoryIdempotencyStore {
    pub fn new(response_ttl_ms: u64, lock_ttl_ms: u64) -> Result<Self, PlatformError> {
        if response_ttl_ms == 0 || lock_ttl_ms == 0 {
            return Err(PlatformError::InvalidConfiguration(
                "idempotency response and lock TTLs must be nonzero".into(),
            ));
        }
        Ok(Self {
            entries: Arc::new(Mutex::new(BTreeMap::new())),
            response_ttl_ms,
            lock_ttl_ms,
        })
    }

    fn entries(&self) -> std::sync::MutexGuard<'_, BTreeMap<String, IdempotencyEntry>> {
        self.entries
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }
}

#[async_trait]
impl IdempotencyStore for InMemoryIdempotencyStore {
    async fn begin(
        &self,
        request: &IdempotencyRequest,
        now_ms: u64,
    ) -> Result<IdempotencyBegin, PlatformError> {
        request.validate()?;
        let namespace = request.namespace();
        let fingerprint = request.fingerprint();
        let mut entries = self.entries();
        if entries.get(&namespace).is_some_and(|entry| match entry {
            IdempotencyEntry::InFlight { expires_at_ms, .. }
            | IdempotencyEntry::Complete { expires_at_ms, .. } => *expires_at_ms <= now_ms,
        }) {
            entries.remove(&namespace);
        }
        if let Some(entry) = entries.get(&namespace) {
            return Ok(match entry {
                IdempotencyEntry::InFlight {
                    fingerprint: current,
                    ..
                } if current == &fingerprint => IdempotencyBegin::InProgress,
                IdempotencyEntry::Complete {
                    fingerprint: current,
                    response,
                    ..
                } if current == &fingerprint => IdempotencyBegin::Replay(response.clone()),
                IdempotencyEntry::InFlight { .. } | IdempotencyEntry::Complete { .. } => {
                    IdempotencyBegin::Conflict
                }
            });
        }
        let token = Uuid::new_v4().simple().to_string();
        entries.insert(
            namespace.clone(),
            IdempotencyEntry::InFlight {
                fingerprint: fingerprint.clone(),
                token: token.clone(),
                expires_at_ms: now_ms.saturating_add(self.lock_ttl_ms),
            },
        );
        Ok(IdempotencyBegin::Started(IdempotencyLease {
            namespace,
            fingerprint,
            token,
        }))
    }

    async fn complete(
        &self,
        lease: &IdempotencyLease,
        response: IdempotencyResponse,
        now_ms: u64,
    ) -> Result<(), PlatformError> {
        let mut entries = self.entries();
        let valid = matches!(
            entries.get(&lease.namespace),
            Some(IdempotencyEntry::InFlight { fingerprint, token, expires_at_ms })
                if fingerprint == &lease.fingerprint && token == &lease.token && *expires_at_ms > now_ms
        );
        if !valid {
            return Err(PlatformError::Conflict(
                "idempotency lease is missing, expired, or owned by another operation".into(),
            ));
        }
        entries.insert(
            lease.namespace.clone(),
            IdempotencyEntry::Complete {
                fingerprint: lease.fingerprint.clone(),
                response,
                expires_at_ms: now_ms.saturating_add(self.response_ttl_ms),
            },
        );
        Ok(())
    }

    async fn abort(&self, lease: &IdempotencyLease) -> Result<(), PlatformError> {
        let mut entries = self.entries();
        let owned = matches!(
            entries.get(&lease.namespace),
            Some(IdempotencyEntry::InFlight { fingerprint, token, .. })
                if fingerprint == &lease.fingerprint && token == &lease.token
        );
        if owned {
            entries.remove(&lease.namespace);
        }
        Ok(())
    }
}

#[cfg(feature = "redis")]
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
struct RedisCachedResponse {
    fingerprint: String,
    response: IdempotencyResponse,
}

#[cfg(feature = "redis")]
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
struct RedisLeaseState {
    fingerprint: String,
    token: String,
}

/// Atomic Redis idempotency storage for multi-instance gateways and services.
#[cfg(feature = "redis")]
pub struct RedisIdempotencyStore {
    connection: AsyncMutex<MultiplexedConnection>,
    key_prefix: String,
    response_ttl_ms: u64,
    lock_ttl_ms: u64,
}

#[cfg(feature = "redis")]
impl std::fmt::Debug for RedisIdempotencyStore {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("RedisIdempotencyStore")
            .field("key_prefix", &self.key_prefix)
            .field("response_ttl_ms", &self.response_ttl_ms)
            .field("lock_ttl_ms", &self.lock_ttl_ms)
            .finish_non_exhaustive()
    }
}

#[cfg(feature = "redis")]
impl RedisIdempotencyStore {
    pub async fn connect(
        redis_url: &str,
        key_prefix: impl Into<String>,
        response_ttl_ms: u64,
        lock_ttl_ms: u64,
    ) -> Result<Self, PlatformError> {
        if redis_url.trim().is_empty() {
            return Err(PlatformError::InvalidConfiguration(
                "Redis idempotency URL is required".into(),
            ));
        }
        let client = redis::Client::open(redis_url).map_err(|_| {
            PlatformError::ProviderUnavailable("Redis idempotency URL is invalid".into())
        })?;
        let connection = client
            .get_multiplexed_async_connection()
            .await
            .map_err(|_| {
                PlatformError::ProviderUnavailable("Redis idempotency connection failed".into())
            })?;
        Self::from_connection(connection, key_prefix, response_ttl_ms, lock_ttl_ms)
    }

    pub fn from_connection(
        connection: MultiplexedConnection,
        key_prefix: impl Into<String>,
        response_ttl_ms: u64,
        lock_ttl_ms: u64,
    ) -> Result<Self, PlatformError> {
        let key_prefix = key_prefix.into();
        if key_prefix.trim().is_empty() || response_ttl_ms == 0 || lock_ttl_ms == 0 {
            return Err(PlatformError::InvalidConfiguration(
                "Redis idempotency prefix and positive TTLs are required".into(),
            ));
        }
        Ok(Self {
            connection: AsyncMutex::new(connection),
            key_prefix,
            response_ttl_ms,
            lock_ttl_ms,
        })
    }

    pub async fn health_check(&self) -> Result<(), PlatformError> {
        let mut connection = self.connection.lock().await;
        let response: String = redis::cmd("PING")
            .query_async(&mut *connection)
            .await
            .map_err(|_| {
                PlatformError::ProviderUnavailable("Redis idempotency health check failed".into())
            })?;
        if response == "PONG" {
            Ok(())
        } else {
            Err(PlatformError::ProviderUnavailable(
                "Redis idempotency health check returned an invalid response".into(),
            ))
        }
    }

    fn keys(&self, namespace: &str) -> (String, String) {
        redis_idempotency_keys(&self.key_prefix, namespace)
    }
}

#[cfg(feature = "redis")]
fn redis_idempotency_keys(prefix: &str, namespace: &str) -> (String, String) {
    let digest = hex_digest(namespace.as_bytes());
    let data = format!("{prefix}:{digest}");
    let lock = format!("{data}:lock");
    (data, lock)
}

#[cfg(feature = "redis")]
const REDIS_IDEMPOTENCY_BEGIN_SCRIPT: &str = r"
local cached = redis.call('GET', KEYS[1])
if cached then
  local ok, value = pcall(cjson.decode, cached)
  if not ok or not value['fingerprint'] then
    return redis.error_reply('invalid idempotency response record')
  end
  if value['fingerprint'] ~= ARGV[1] then return {'conflict', ''} end
  return {'replay', cached}
end

local active = redis.call('GET', KEYS[2])
if active then
  local ok, value = pcall(cjson.decode, active)
  if not ok or not value['fingerprint'] then
    return redis.error_reply('invalid idempotency lease record')
  end
  if value['fingerprint'] ~= ARGV[1] then return {'conflict', ''} end
  return {'in_progress', ''}
end

redis.call('SET', KEYS[2], ARGV[3], 'PX', ARGV[4])
return {'started', ARGV[2]}
";

#[cfg(feature = "redis")]
const REDIS_IDEMPOTENCY_COMPLETE_SCRIPT: &str = r"
local active = redis.call('GET', KEYS[2])
if not active then return 0 end
local ok, value = pcall(cjson.decode, active)
if not ok or value['fingerprint'] ~= ARGV[1] or value['token'] ~= ARGV[2] then return 0 end
redis.call('SET', KEYS[1], ARGV[3], 'PX', ARGV[4])
redis.call('DEL', KEYS[2])
return 1
";

#[cfg(feature = "redis")]
const REDIS_IDEMPOTENCY_ABORT_SCRIPT: &str = r"
local active = redis.call('GET', KEYS[1])
if not active then return 0 end
local ok, value = pcall(cjson.decode, active)
if not ok or value['fingerprint'] ~= ARGV[1] or value['token'] ~= ARGV[2] then return 0 end
return redis.call('DEL', KEYS[1])
";

#[cfg(feature = "redis")]
#[async_trait]
impl IdempotencyStore for RedisIdempotencyStore {
    async fn begin(
        &self,
        request: &IdempotencyRequest,
        _now_ms: u64,
    ) -> Result<IdempotencyBegin, PlatformError> {
        request.validate()?;
        let namespace = request.namespace();
        let fingerprint = request.fingerprint();
        let token = Uuid::new_v4().simple().to_string();
        let lease_state = serde_json::to_string(&RedisLeaseState {
            fingerprint: fingerprint.clone(),
            token: token.clone(),
        })
        .map_err(|_| PlatformError::Operation("idempotency lease serialization failed".into()))?;
        let (data_key, lock_key) = self.keys(&namespace);
        let mut connection = self.connection.lock().await;
        let (state, payload): (String, String) = redis::cmd("EVAL")
            .arg(REDIS_IDEMPOTENCY_BEGIN_SCRIPT)
            .arg(2)
            .arg(data_key)
            .arg(lock_key)
            .arg(&fingerprint)
            .arg(&token)
            .arg(lease_state)
            .arg(self.lock_ttl_ms)
            .query_async(&mut *connection)
            .await
            .map_err(|_| {
                PlatformError::ProviderUnavailable("Redis idempotency begin failed".into())
            })?;
        match state.as_str() {
            "started" => Ok(IdempotencyBegin::Started(IdempotencyLease {
                namespace,
                fingerprint,
                token: payload,
            })),
            "replay" => {
                let cached: RedisCachedResponse = serde_json::from_str(&payload).map_err(|_| {
                    PlatformError::Operation("invalid Redis idempotency response record".into())
                })?;
                if cached.fingerprint != fingerprint {
                    return Ok(IdempotencyBegin::Conflict);
                }
                Ok(IdempotencyBegin::Replay(cached.response))
            }
            "conflict" => Ok(IdempotencyBegin::Conflict),
            "in_progress" => Ok(IdempotencyBegin::InProgress),
            _ => Err(PlatformError::Operation(
                "Redis idempotency begin returned an invalid state".into(),
            )),
        }
    }

    async fn complete(
        &self,
        lease: &IdempotencyLease,
        response: IdempotencyResponse,
        _now_ms: u64,
    ) -> Result<(), PlatformError> {
        let payload = serde_json::to_string(&RedisCachedResponse {
            fingerprint: lease.fingerprint.clone(),
            response,
        })
        .map_err(|_| {
            PlatformError::Operation("idempotency response serialization failed".into())
        })?;
        let (data_key, lock_key) = self.keys(&lease.namespace);
        let mut connection = self.connection.lock().await;
        let stored: i64 = redis::cmd("EVAL")
            .arg(REDIS_IDEMPOTENCY_COMPLETE_SCRIPT)
            .arg(2)
            .arg(data_key)
            .arg(lock_key)
            .arg(&lease.fingerprint)
            .arg(&lease.token)
            .arg(payload)
            .arg(self.response_ttl_ms)
            .query_async(&mut *connection)
            .await
            .map_err(|_| {
                PlatformError::ProviderUnavailable("Redis idempotency completion failed".into())
            })?;
        if stored == 1 {
            Ok(())
        } else {
            Err(PlatformError::Conflict(
                "idempotency lease is missing, expired, or owned by another operation".into(),
            ))
        }
    }

    async fn abort(&self, lease: &IdempotencyLease) -> Result<(), PlatformError> {
        let (_, lock_key) = self.keys(&lease.namespace);
        let mut connection = self.connection.lock().await;
        let _: i64 = redis::cmd("EVAL")
            .arg(REDIS_IDEMPOTENCY_ABORT_SCRIPT)
            .arg(1)
            .arg(lock_key)
            .arg(&lease.fingerprint)
            .arg(&lease.token)
            .query_async(&mut *connection)
            .await
            .map_err(|_| {
                PlatformError::ProviderUnavailable("Redis idempotency abort failed".into())
            })?;
        Ok(())
    }
}

fn hex_digest(value: &[u8]) -> String {
    let digest = Sha256::digest(value);
    hex_prefix(&digest, digest.len())
}

fn hex_prefix(value: &[u8], bytes: usize) -> String {
    use std::fmt::Write;

    let mut encoded = String::with_capacity(bytes.saturating_mul(2));
    for byte in value.iter().take(bytes) {
        write!(&mut encoded, "{byte:02x}").expect("writing to String cannot fail");
    }
    encoded
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        versions: VersionFixture,
        content_types: ContentTypeFixture,
        entity_tags: Vec<EntityTagCase>,
        idempotency: IdempotencyFixture,
    }

    #[derive(Deserialize)]
    struct VersionFixture {
        current: String,
        supported: Vec<String>,
        cases: Vec<VersionCase>,
    }

    #[derive(Deserialize)]
    struct VersionCase {
        advertised: Option<String>,
        accepted: bool,
    }

    #[derive(Deserialize)]
    struct ContentTypeFixture {
        body_methods: Vec<String>,
        allowed: Vec<String>,
        exempt_prefixes: Vec<String>,
        cases: Vec<ContentTypeCase>,
    }

    #[derive(Deserialize)]
    struct ContentTypeCase {
        method: String,
        path: String,
        content_type: Option<String>,
        accepted: bool,
    }

    #[derive(Deserialize)]
    struct EntityTagCase {
        method: String,
        authenticated: bool,
        status: u16,
        cache_control: Option<String>,
        if_none_match: Option<String>,
        body: String,
        decision: String,
        entity_tag: Option<String>,
    }

    #[derive(Deserialize)]
    struct IdempotencyFixture {
        request: IdempotencyRequest,
        fingerprint: String,
    }

    #[cfg(feature = "redis")]
    #[derive(Deserialize)]
    struct RedisFixture {
        schema_version: u32,
        idempotency: RedisIdempotencyFixture,
    }

    #[cfg(feature = "redis")]
    #[derive(Deserialize)]
    struct RedisIdempotencyFixture {
        prefix: String,
        namespace: String,
        expected_data_key: String,
        expected_lock_key: String,
        response_ttl_ms: u64,
        lock_ttl_ms: u64,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!(
            "../../../contracts/http-runtime-behavior.json"
        ))
        .expect("valid HTTP runtime fixture")
    }

    #[cfg(feature = "redis")]
    fn redis_fixture() -> RedisFixture {
        serde_json::from_str(include_str!(
            "../../../contracts/redis-runtime-behavior.json"
        ))
        .expect("valid Redis runtime fixture")
    }

    #[tokio::test]
    async fn language_neutral_http_contract() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        let versions =
            ProtocolVersionPolicy::new(fixture.versions.current, fixture.versions.supported)
                .expect("versions");
        for case in fixture.versions.cases {
            assert_eq!(
                versions.negotiate(case.advertised.as_deref()) == ProtocolVersionDecision::Accepted,
                case.accepted
            );
        }

        let content_types = ContentTypePolicy {
            body_methods: fixture.content_types.body_methods.into_iter().collect(),
            allowed_media_types: fixture.content_types.allowed.into_iter().collect(),
            exempt_path_prefixes: fixture.content_types.exempt_prefixes,
        };
        content_types.validate().expect("content types");
        for case in fixture.content_types.cases {
            assert_eq!(
                content_types.evaluate(&case.method, &case.path, case.content_type.as_deref())
                    == ContentTypeDecision::Accepted,
                case.accepted
            );
        }

        for case in fixture.entity_tags {
            let decision = EntityTagPolicy::evaluate(
                &case.method,
                case.authenticated,
                case.status,
                case.cache_control.as_deref(),
                case.if_none_match.as_deref(),
                case.body.as_bytes(),
            );
            let (name, entity_tag) = match decision {
                EntityTagDecision::Bypass => ("bypass", None),
                EntityTagDecision::Attach { entity_tag } => ("attach", Some(entity_tag)),
                EntityTagDecision::NotModified { entity_tag } => ("not_modified", Some(entity_tag)),
            };
            assert_eq!(name, case.decision);
            assert_eq!(entity_tag.as_deref(), case.entity_tag.as_deref());
        }

        assert_eq!(
            fixture.idempotency.request.fingerprint(),
            fixture.idempotency.fingerprint
        );
    }

    #[tokio::test]
    async fn idempotency_store_replays_conflicts_and_recovers_expired_leases() {
        let store = InMemoryIdempotencyStore::new(1_000, 100).expect("store");
        let request = fixture().idempotency.request;
        let IdempotencyBegin::Started(lease) = store.begin(&request, 1).await.expect("begin")
        else {
            panic!("first request must start");
        };
        assert_eq!(
            store.begin(&request, 2).await.expect("repeat"),
            IdempotencyBegin::InProgress
        );
        let mut conflict = request.clone();
        conflict.body.push(b'!');
        assert_eq!(
            store.begin(&conflict, 3).await.expect("conflict"),
            IdempotencyBegin::Conflict
        );
        let response = IdempotencyResponse {
            status: 201,
            body: b"created".to_vec(),
            content_type: Some("application/json".into()),
            headers: BTreeMap::new(),
        };
        store
            .complete(&lease, response.clone(), 4)
            .await
            .expect("complete");
        assert_eq!(
            store.begin(&request, 5).await.expect("replay"),
            IdempotencyBegin::Replay(response)
        );

        let IdempotencyBegin::Started(recovered) =
            store.begin(&request, 1_005).await.expect("expired")
        else {
            panic!("expired response must allow a fresh operation");
        };
        store.abort(&recovered).await.expect("abort");
        assert!(matches!(
            store.begin(&request, 1_006).await.expect("restart"),
            IdempotencyBegin::Started(_)
        ));
    }

    #[cfg(feature = "redis")]
    #[tokio::test]
    async fn language_neutral_redis_idempotency_contract() {
        let fixture = redis_fixture();
        assert_eq!(fixture.schema_version, 1);
        let (data, lock) =
            redis_idempotency_keys(&fixture.idempotency.prefix, &fixture.idempotency.namespace);
        assert_eq!(data, fixture.idempotency.expected_data_key);
        assert_eq!(lock, fixture.idempotency.expected_lock_key);
        assert_eq!(fixture.idempotency.response_ttl_ms, 86_400_000);
        assert_eq!(fixture.idempotency.lock_ttl_ms, 300_000);
        assert!(REDIS_IDEMPOTENCY_BEGIN_SCRIPT.contains("in_progress"));
        assert!(REDIS_IDEMPOTENCY_COMPLETE_SCRIPT.contains("value['token']"));
        assert!(
            RedisIdempotencyStore::connect("", "idempotency", 1, 1)
                .await
                .is_err()
        );
    }
}
