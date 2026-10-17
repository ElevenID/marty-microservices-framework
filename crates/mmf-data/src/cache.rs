use std::collections::{BTreeMap, BTreeSet};
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use redis::FromRedisValue;
use redis::aio::MultiplexedConnection;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::sync::Mutex as AsyncMutex;

use crate::DataError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CacheBackend {
    Memory,
    Redis,
    Memcached,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CachePattern {
    CacheAside,
    WriteThrough,
    WriteBehind,
    RefreshAhead,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SerializationFormat {
    Json,
    String,
    Bytes,
    /// Read compatibility only. Native MMF never decodes executable pickle.
    Pickle,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
pub struct CacheConfig {
    pub backend: CacheBackend,
    pub host: String,
    pub port: u16,
    pub url: Option<String>,
    pub database: u32,
    pub secret_reference: Option<String>,
    pub max_connections: usize,
    pub default_ttl_seconds: u64,
    pub serialization: SerializationFormat,
    pub compression_enabled: bool,
    pub key_prefix: String,
    pub namespace: String,
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            backend: CacheBackend::Memory,
            host: "localhost".into(),
            port: 6_379,
            url: None,
            database: 0,
            secret_reference: None,
            max_connections: 100,
            default_ttl_seconds: 3_600,
            serialization: SerializationFormat::Json,
            compression_enabled: true,
            key_prefix: String::new(),
            namespace: "default".into(),
        }
    }
}

impl CacheConfig {
    pub fn validate(&self, production: bool) -> Result<(), DataError> {
        if self.namespace.trim().is_empty() || self.max_connections == 0 {
            return Err(DataError::InvalidConfiguration(
                "cache namespace and positive connection limit are required".into(),
            ));
        }
        if self.serialization == SerializationFormat::Pickle {
            return Err(DataError::InvalidConfiguration(
                "native MMF does not deserialize executable pickle".into(),
            ));
        }
        if production && self.backend != CacheBackend::Memory {
            let url = self.url.as_deref().ok_or_else(|| {
                DataError::ProviderUnavailable("production cache URL is required".into())
            })?;
            if self.backend == CacheBackend::Redis {
                let client = redis::Client::open(url).map_err(|_| {
                    DataError::InvalidConfiguration("production Redis URL is invalid".into())
                })?;
                let permitted = match client.get_connection_info().addr() {
                    redis::ConnectionAddr::TcpTls {
                        insecure: false, ..
                    } => true,
                    redis::ConnectionAddr::Unix(path) => cfg!(unix) && path.is_absolute(),
                    _ => false,
                };
                if !permitted {
                    return Err(DataError::InvalidConfiguration(
                        "production Redis requires verified TLS or a local Unix socket".into(),
                    ));
                }
            }
        }
        Ok(())
    }

    #[must_use]
    pub fn key(&self, key: &str) -> String {
        if self.key_prefix.is_empty() {
            format!("{}:{key}", self.namespace)
        } else {
            format!("{}:{}:{key}", self.namespace, self.key_prefix)
        }
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct CacheStats {
    pub hits: u64,
    pub misses: u64,
    pub sets: u64,
    pub deletes: u64,
    pub errors: u64,
    pub total_size: u64,
}

impl CacheStats {
    #[must_use]
    pub fn hit_rate(&self) -> f64 {
        let total = self.hits.saturating_add(self.misses);
        if total == 0 {
            0.0
        } else {
            #[allow(clippy::cast_precision_loss)]
            let hits = self.hits as f64;
            #[allow(clippy::cast_precision_loss)]
            let total = total as f64;
            hits / total
        }
    }
}

pub struct CacheSerializer {
    format: SerializationFormat,
}

impl CacheSerializer {
    pub fn new(format: SerializationFormat) -> Result<Self, DataError> {
        if format == SerializationFormat::Pickle {
            return Err(DataError::InvalidConfiguration(
                "pickle is not a supported native serialization format".into(),
            ));
        }
        Ok(Self { format })
    }

    pub fn serialize(&self, value: &Value) -> Result<Vec<u8>, DataError> {
        match self.format {
            SerializationFormat::Json => serde_json::to_vec(value)
                .map_err(|error| DataError::Serialization(error.to_string())),
            SerializationFormat::String => value
                .as_str()
                .map(|value| value.as_bytes().to_vec())
                .ok_or_else(|| DataError::Serialization("string value required".into())),
            SerializationFormat::Bytes => value
                .as_array()
                .ok_or_else(|| DataError::Serialization("byte array required".into()))?
                .iter()
                .map(|item| {
                    item.as_u64()
                        .and_then(|byte| u8::try_from(byte).ok())
                        .ok_or_else(|| DataError::Serialization("invalid byte".into()))
                })
                .collect(),
            SerializationFormat::Pickle => Err(DataError::Serialization(
                "pickle is never decoded by native MMF".into(),
            )),
        }
    }

    pub fn deserialize(&self, data: &[u8]) -> Result<Value, DataError> {
        match self.format {
            SerializationFormat::Json => serde_json::from_slice(data)
                .map_err(|error| DataError::Serialization(error.to_string())),
            SerializationFormat::String => String::from_utf8(data.to_vec())
                .map(Value::String)
                .map_err(|error| DataError::Serialization(error.to_string())),
            SerializationFormat::Bytes => Ok(Value::Array(
                data.iter().map(|byte| Value::from(*byte)).collect(),
            )),
            SerializationFormat::Pickle => Err(DataError::Serialization(
                "pickle is never decoded by native MMF".into(),
            )),
        }
    }
}

#[async_trait]
pub trait CacheStore: Send + Sync {
    async fn get(&self, key: &str, now_ms: u64) -> Result<Option<Vec<u8>>, DataError>;
    /// Atomically read and remove a value. This is the canonical primitive for
    /// one-time state, challenges, and replay-resistant handoffs.
    async fn take(&self, key: &str, now_ms: u64) -> Result<Option<Vec<u8>>, DataError>;
    async fn set(
        &self,
        key: &str,
        value: Vec<u8>,
        ttl_seconds: Option<u64>,
        now_ms: u64,
    ) -> Result<bool, DataError>;
    /// Atomically create a value only when the key does not already exist.
    /// Expired entries do not block acquisition. This is the canonical lease,
    /// idempotency-claim, and distributed single-winner primitive.
    async fn set_if_absent(
        &self,
        key: &str,
        value: Vec<u8>,
        ttl_seconds: Option<u64>,
        now_ms: u64,
    ) -> Result<bool, DataError>;
    async fn delete(&self, key: &str) -> Result<bool, DataError>;
    async fn exists(&self, key: &str, now_ms: u64) -> Result<bool, DataError>;
    async fn clear(&self) -> Result<(), DataError>;
    async fn stats(&self) -> Result<CacheStats, DataError>;
    async fn sadd(&self, key: &str, members: Vec<Vec<u8>>, now_ms: u64)
    -> Result<usize, DataError>;
    async fn srem(&self, key: &str, members: Vec<Vec<u8>>, now_ms: u64)
    -> Result<usize, DataError>;
    async fn smembers(&self, key: &str, now_ms: u64) -> Result<Vec<Vec<u8>>, DataError>;
    async fn zadd(&self, key: &str, members: BTreeMap<Vec<u8>, f64>) -> Result<usize, DataError>;
    async fn zrevrangebyscore(
        &self,
        key: &str,
        max_score: f64,
        min_score: f64,
        start: usize,
        limit: Option<usize>,
    ) -> Result<Vec<Vec<u8>>, DataError>;
    async fn zcount(&self, key: &str, min_score: f64, max_score: f64) -> Result<usize, DataError>;
    async fn zremrangebyscore(
        &self,
        key: &str,
        min_score: f64,
        max_score: f64,
    ) -> Result<usize, DataError>;
    async fn zcard(&self, key: &str) -> Result<usize, DataError>;
    async fn zremrangebyrank(
        &self,
        key: &str,
        min_rank: usize,
        max_rank: usize,
    ) -> Result<usize, DataError>;
    async fn expire(&self, key: &str, ttl_seconds: u64, now_ms: u64) -> Result<bool, DataError>;
    async fn keys(&self, pattern: &str, now_ms: u64) -> Result<Vec<String>, DataError>;
}

/// Production Redis implementation of the canonical MMF cache contract.
///
/// Every operation is constrained to the configured namespace and key prefix.
/// Namespace clearing and key enumeration use `SCAN`; this adapter never issues
/// a database-wide `KEYS` or `FLUSHDB` command.
#[derive(Clone)]
pub struct RedisCache {
    connection: Arc<AsyncMutex<MultiplexedConnection>>,
    config: CacheConfig,
    stats: Arc<Mutex<CacheStats>>,
}

impl RedisCache {
    /// Connect to Redis and verify that the backend is responsive.
    pub async fn connect(config: CacheConfig, production: bool) -> Result<Self, DataError> {
        config.validate(production)?;
        if config.backend != CacheBackend::Redis {
            return Err(DataError::InvalidConfiguration(
                "Redis cache requires the redis backend".into(),
            ));
        }
        let redis_url = config.url.clone().unwrap_or_else(|| {
            format!(
                "redis://{}:{}/{}",
                config.host, config.port, config.database
            )
        });
        let client = redis::Client::open(redis_url)
            .map_err(|error| DataError::InvalidConfiguration(error.to_string()))?;
        if matches!(
            client.get_connection_info().addr(),
            redis::ConnectionAddr::TcpTls { .. }
        ) && rustls::crypto::CryptoProvider::get_default().is_none()
            && rustls::crypto::ring::default_provider()
                .install_default()
                .is_err()
            && rustls::crypto::CryptoProvider::get_default().is_none()
        {
            return Err(DataError::ProviderUnavailable(
                "Redis TLS crypto provider could not be installed".into(),
            ));
        }
        let connection = client
            .get_multiplexed_async_connection()
            .await
            .map_err(|error| DataError::ProviderUnavailable(error.to_string()))?;
        let cache = Self::from_connection(config, connection)?;
        let response: String = cache.command(&mut redis::cmd("PING")).await?;
        if response != "PONG" {
            return Err(DataError::ProviderUnavailable(
                "Redis health check returned an unexpected response".into(),
            ));
        }
        Ok(cache)
    }

    /// Construct an adapter from an established Redis connection.
    pub fn from_connection(
        config: CacheConfig,
        connection: MultiplexedConnection,
    ) -> Result<Self, DataError> {
        config.validate(false)?;
        if config.backend != CacheBackend::Redis {
            return Err(DataError::InvalidConfiguration(
                "Redis cache requires the redis backend".into(),
            ));
        }
        Ok(Self {
            connection: Arc::new(AsyncMutex::new(connection)),
            config,
            stats: Arc::new(Mutex::new(CacheStats::default())),
        })
    }

    /// Create another namespaced cache view over the same Redis connection.
    ///
    /// This lets one service isolate several cache families without opening a
    /// connection per family. Each view has independent process-local metrics.
    pub fn with_key_space(
        &self,
        namespace: impl Into<String>,
        key_prefix: impl Into<String>,
    ) -> Result<Self, DataError> {
        let mut config = self.config.clone();
        config.namespace = namespace.into();
        config.key_prefix = key_prefix.into();
        config.validate(false)?;
        Ok(Self {
            connection: Arc::clone(&self.connection),
            config,
            stats: Arc::new(Mutex::new(CacheStats::default())),
        })
    }

    fn namespaced_key(&self, key: &str) -> Result<String, DataError> {
        if key.trim().is_empty() {
            return Err(DataError::InvalidQuery("cache key is required".into()));
        }
        Ok(self.config.key(key))
    }

    fn namespace_prefix(&self) -> String {
        self.config.key("")
    }

    fn lock_stats(&self) -> std::sync::MutexGuard<'_, CacheStats> {
        self.stats
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }

    async fn command<T>(&self, command: &mut redis::Cmd) -> Result<T, DataError>
    where
        T: FromRedisValue,
    {
        let result = command
            .query_async(&mut *self.connection.lock().await)
            .await;
        result.map_err(|error| {
            let mut stats = self.lock_stats();
            stats.errors = stats.errors.saturating_add(1);
            DataError::Operation(error.to_string())
        })
    }

    async fn scan_namespaced_keys(&self, pattern: &str) -> Result<Vec<String>, DataError> {
        if pattern.is_empty() {
            return Err(DataError::InvalidQuery(
                "cache key pattern is required".into(),
            ));
        }
        let prefix = self.namespace_prefix();
        let match_pattern = format!("{prefix}{pattern}");
        let mut cursor = 0_u64;
        let mut keys = Vec::new();
        loop {
            let (next, mut page): (u64, Vec<String>) = self
                .command(
                    redis::cmd("SCAN")
                        .arg(cursor)
                        .arg("MATCH")
                        .arg(&match_pattern)
                        .arg("COUNT")
                        .arg(200_u16),
                )
                .await?;
            keys.append(&mut page);
            if next == 0 {
                break;
            }
            cursor = next;
        }
        keys.sort();
        keys.dedup();
        Ok(keys)
    }
}

#[async_trait]
impl CacheStore for RedisCache {
    async fn get(&self, key: &str, _now_ms: u64) -> Result<Option<Vec<u8>>, DataError> {
        let value: Option<Vec<u8>> = self
            .command(redis::cmd("GET").arg(self.namespaced_key(key)?))
            .await?;
        let mut stats = self.lock_stats();
        if value.is_some() {
            stats.hits = stats.hits.saturating_add(1);
        } else {
            stats.misses = stats.misses.saturating_add(1);
        }
        Ok(value)
    }

    async fn take(&self, key: &str, _now_ms: u64) -> Result<Option<Vec<u8>>, DataError> {
        let value: Option<Vec<u8>> = self
            .command(redis::cmd("GETDEL").arg(self.namespaced_key(key)?))
            .await?;
        let mut stats = self.lock_stats();
        if let Some(value) = &value {
            stats.hits = stats.hits.saturating_add(1);
            stats.deletes = stats.deletes.saturating_add(1);
            stats.total_size = stats.total_size.saturating_sub(value.len() as u64);
        } else {
            stats.misses = stats.misses.saturating_add(1);
        }
        Ok(value)
    }

    async fn set(
        &self,
        key: &str,
        value: Vec<u8>,
        ttl_seconds: Option<u64>,
        _now_ms: u64,
    ) -> Result<bool, DataError> {
        let key = self.namespaced_key(key)?;
        let ttl_seconds = ttl_seconds.unwrap_or_default();
        let previous_size: usize = self
            .command(
                redis::cmd("EVAL")
                    .arg(
                        "local size = 0; local kind = redis.call('TYPE', KEYS[1]); \
                         if kind.ok == 'string' then size = redis.call('STRLEN', KEYS[1]); end; \
                         if tonumber(ARGV[2]) > 0 then \
                           redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2]); \
                         else redis.call('SET', KEYS[1], ARGV[1]); end; return size",
                    )
                    .arg(1_u8)
                    .arg(&key)
                    .arg(&value)
                    .arg(ttl_seconds),
            )
            .await?;
        let mut stats = self.lock_stats();
        stats.sets = stats.sets.saturating_add(1);
        stats.total_size = stats
            .total_size
            .saturating_sub(previous_size as u64)
            .saturating_add(value.len() as u64);
        Ok(true)
    }

    async fn set_if_absent(
        &self,
        key: &str,
        value: Vec<u8>,
        ttl_seconds: Option<u64>,
        _now_ms: u64,
    ) -> Result<bool, DataError> {
        let key = self.namespaced_key(key)?;
        let mut command = redis::cmd("SET");
        command.arg(&key).arg(&value).arg("NX");
        if let Some(ttl_seconds) = ttl_seconds.filter(|ttl| *ttl > 0) {
            command.arg("EX").arg(ttl_seconds);
        }
        let result: Option<String> = self.command(&mut command).await?;
        let inserted = result.is_some();
        if inserted {
            let mut stats = self.lock_stats();
            stats.sets = stats.sets.saturating_add(1);
            stats.total_size = stats.total_size.saturating_add(value.len() as u64);
        }
        Ok(inserted)
    }

    async fn delete(&self, key: &str) -> Result<bool, DataError> {
        let key = self.namespaced_key(key)?;
        let (deleted, previous_size): (usize, usize) = self
            .command(
                redis::cmd("EVAL")
                    .arg(
                        "local size = 0; local kind = redis.call('TYPE', KEYS[1]); \
                         if kind.ok == 'string' then size = redis.call('STRLEN', KEYS[1]); end; \
                         return {redis.call('DEL', KEYS[1]), size}",
                    )
                    .arg(1_u8)
                    .arg(key),
            )
            .await?;
        if deleted > 0 {
            let mut stats = self.lock_stats();
            stats.deletes = stats.deletes.saturating_add(1);
            stats.total_size = stats.total_size.saturating_sub(previous_size as u64);
        }
        Ok(deleted > 0)
    }

    async fn exists(&self, key: &str, _now_ms: u64) -> Result<bool, DataError> {
        let count: usize = self
            .command(redis::cmd("EXISTS").arg(self.namespaced_key(key)?))
            .await?;
        Ok(count > 0)
    }

    async fn clear(&self) -> Result<(), DataError> {
        let keys = self.scan_namespaced_keys("*").await?;
        for page in keys.chunks(200) {
            let _: usize = self.command(redis::cmd("DEL").arg(page)).await?;
        }
        self.lock_stats().total_size = 0;
        Ok(())
    }

    async fn stats(&self) -> Result<CacheStats, DataError> {
        Ok(self.lock_stats().clone())
    }

    async fn sadd(
        &self,
        key: &str,
        members: Vec<Vec<u8>>,
        _now_ms: u64,
    ) -> Result<usize, DataError> {
        if members.is_empty() {
            return Ok(0);
        }
        self.command(
            redis::cmd("SADD")
                .arg(self.namespaced_key(key)?)
                .arg(members),
        )
        .await
    }

    async fn srem(
        &self,
        key: &str,
        members: Vec<Vec<u8>>,
        _now_ms: u64,
    ) -> Result<usize, DataError> {
        if members.is_empty() {
            return Ok(0);
        }
        self.command(
            redis::cmd("SREM")
                .arg(self.namespaced_key(key)?)
                .arg(members),
        )
        .await
    }

    async fn smembers(&self, key: &str, _now_ms: u64) -> Result<Vec<Vec<u8>>, DataError> {
        let mut members: Vec<Vec<u8>> = self
            .command(redis::cmd("SMEMBERS").arg(self.namespaced_key(key)?))
            .await?;
        members.sort();
        Ok(members)
    }

    async fn zadd(&self, key: &str, members: BTreeMap<Vec<u8>, f64>) -> Result<usize, DataError> {
        if members.values().any(|score| !score.is_finite()) {
            return Err(DataError::InvalidQuery(
                "sorted-set score must be finite".into(),
            ));
        }
        if members.is_empty() {
            return Ok(0);
        }
        let mut command = redis::cmd("ZADD");
        command.arg(self.namespaced_key(key)?);
        for (member, score) in members {
            command.arg(score).arg(member);
        }
        self.command(&mut command).await
    }

    async fn zrevrangebyscore(
        &self,
        key: &str,
        max_score: f64,
        min_score: f64,
        start: usize,
        limit: Option<usize>,
    ) -> Result<Vec<Vec<u8>>, DataError> {
        validate_range(min_score, max_score)?;
        let mut command = redis::cmd("ZREVRANGEBYSCORE");
        command
            .arg(self.namespaced_key(key)?)
            .arg(max_score)
            .arg(min_score);
        if let Some(limit) = limit {
            command.arg("LIMIT").arg(start).arg(limit);
        } else if start > 0 {
            command.arg("LIMIT").arg(start).arg(i64::MAX);
        }
        self.command(&mut command).await
    }

    async fn zcount(&self, key: &str, min_score: f64, max_score: f64) -> Result<usize, DataError> {
        validate_range(min_score, max_score)?;
        self.command(
            redis::cmd("ZCOUNT")
                .arg(self.namespaced_key(key)?)
                .arg(min_score)
                .arg(max_score),
        )
        .await
    }

    async fn zremrangebyscore(
        &self,
        key: &str,
        min_score: f64,
        max_score: f64,
    ) -> Result<usize, DataError> {
        validate_range(min_score, max_score)?;
        self.command(
            redis::cmd("ZREMRANGEBYSCORE")
                .arg(self.namespaced_key(key)?)
                .arg(min_score)
                .arg(max_score),
        )
        .await
    }

    async fn zcard(&self, key: &str) -> Result<usize, DataError> {
        self.command(redis::cmd("ZCARD").arg(self.namespaced_key(key)?))
            .await
    }

    async fn zremrangebyrank(
        &self,
        key: &str,
        min_rank: usize,
        max_rank: usize,
    ) -> Result<usize, DataError> {
        if min_rank > max_rank {
            return Err(DataError::InvalidQuery(
                "invalid sorted-set rank range".into(),
            ));
        }
        self.command(
            redis::cmd("ZREMRANGEBYRANK")
                .arg(self.namespaced_key(key)?)
                .arg(min_rank)
                .arg(max_rank),
        )
        .await
    }

    async fn expire(&self, key: &str, ttl_seconds: u64, _now_ms: u64) -> Result<bool, DataError> {
        self.command(
            redis::cmd("EXPIRE")
                .arg(self.namespaced_key(key)?)
                .arg(ttl_seconds),
        )
        .await
    }

    async fn keys(&self, pattern: &str, _now_ms: u64) -> Result<Vec<String>, DataError> {
        let prefix = self.namespace_prefix();
        Ok(self
            .scan_namespaced_keys(pattern)
            .await?
            .into_iter()
            .filter_map(|key| key.strip_prefix(&prefix).map(str::to_owned))
            .collect())
    }
}

#[derive(Clone, Debug)]
struct Entry {
    value: Vec<u8>,
    expires_at_ms: Option<u64>,
}

#[derive(Default)]
struct MemoryState {
    entries: BTreeMap<String, Entry>,
    sets: BTreeMap<String, BTreeSet<Vec<u8>>>,
    sorted_sets: BTreeMap<String, BTreeMap<Vec<u8>, f64>>,
    collection_expiry_ms: BTreeMap<String, u64>,
    stats: CacheStats,
}

#[derive(Clone, Default)]
pub struct MemoryCache {
    state: Arc<Mutex<MemoryState>>,
}

impl MemoryCache {
    fn purge(state: &mut MemoryState, key: &str, now_ms: u64) {
        if state
            .entries
            .get(key)
            .and_then(|entry| entry.expires_at_ms)
            .is_some_and(|expires| expires <= now_ms)
            && let Some(entry) = state.entries.remove(key)
        {
            state.stats.total_size = state
                .stats
                .total_size
                .saturating_sub(entry.value.len() as u64);
        }
        if state
            .collection_expiry_ms
            .get(key)
            .is_some_and(|expires| *expires <= now_ms)
        {
            state.collection_expiry_ms.remove(key);
            state.sets.remove(key);
            state.sorted_sets.remove(key);
        }
    }

    fn lock(&self) -> std::sync::MutexGuard<'_, MemoryState> {
        self.state
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }
}

#[async_trait]
impl CacheStore for MemoryCache {
    async fn get(&self, key: &str, now_ms: u64) -> Result<Option<Vec<u8>>, DataError> {
        let mut state = self.lock();
        Self::purge(&mut state, key, now_ms);
        let value = state.entries.get(key).map(|entry| entry.value.clone());
        if value.is_some() {
            state.stats.hits = state.stats.hits.saturating_add(1);
        } else {
            state.stats.misses = state.stats.misses.saturating_add(1);
        }
        Ok(value)
    }

    async fn take(&self, key: &str, now_ms: u64) -> Result<Option<Vec<u8>>, DataError> {
        let mut state = self.lock();
        Self::purge(&mut state, key, now_ms);
        let value = state.entries.remove(key).map(|entry| entry.value);
        if let Some(value) = &value {
            state.stats.hits = state.stats.hits.saturating_add(1);
            state.stats.deletes = state.stats.deletes.saturating_add(1);
            state.stats.total_size = state.stats.total_size.saturating_sub(value.len() as u64);
        } else {
            state.stats.misses = state.stats.misses.saturating_add(1);
        }
        Ok(value)
    }

    async fn set(
        &self,
        key: &str,
        value: Vec<u8>,
        ttl_seconds: Option<u64>,
        now_ms: u64,
    ) -> Result<bool, DataError> {
        if key.is_empty() {
            return Err(DataError::InvalidQuery("cache key is required".into()));
        }
        let expires_at_ms = ttl_seconds.map(|ttl| now_ms.saturating_add(ttl.saturating_mul(1_000)));
        let mut state = self.lock();
        if let Some(previous) = state.entries.insert(
            key.into(),
            Entry {
                value: value.clone(),
                expires_at_ms,
            },
        ) {
            state.stats.total_size = state
                .stats
                .total_size
                .saturating_sub(previous.value.len() as u64);
        }
        state.stats.total_size = state.stats.total_size.saturating_add(value.len() as u64);
        state.stats.sets = state.stats.sets.saturating_add(1);
        Ok(true)
    }

    async fn set_if_absent(
        &self,
        key: &str,
        value: Vec<u8>,
        ttl_seconds: Option<u64>,
        now_ms: u64,
    ) -> Result<bool, DataError> {
        if key.is_empty() {
            return Err(DataError::InvalidQuery("cache key is required".into()));
        }
        let expires_at_ms = ttl_seconds.map(|ttl| now_ms.saturating_add(ttl.saturating_mul(1_000)));
        let mut state = self.lock();
        Self::purge(&mut state, key, now_ms);
        if state.entries.contains_key(key)
            || state.sets.contains_key(key)
            || state.sorted_sets.contains_key(key)
        {
            return Ok(false);
        }
        state.entries.insert(
            key.into(),
            Entry {
                value: value.clone(),
                expires_at_ms,
            },
        );
        state.stats.total_size = state.stats.total_size.saturating_add(value.len() as u64);
        state.stats.sets = state.stats.sets.saturating_add(1);
        Ok(true)
    }

    async fn delete(&self, key: &str) -> Result<bool, DataError> {
        let mut state = self.lock();
        let removed = state.entries.remove(key);
        if let Some(entry) = &removed {
            state.stats.total_size = state
                .stats
                .total_size
                .saturating_sub(entry.value.len() as u64);
            state.stats.deletes = state.stats.deletes.saturating_add(1);
        }
        let removed_set = state.sets.remove(key).is_some();
        let removed_sorted_set = state.sorted_sets.remove(key).is_some();
        state.collection_expiry_ms.remove(key);
        Ok(removed.is_some() || removed_set || removed_sorted_set)
    }

    async fn exists(&self, key: &str, now_ms: u64) -> Result<bool, DataError> {
        let mut state = self.lock();
        Self::purge(&mut state, key, now_ms);
        Ok(state.entries.contains_key(key)
            || state.sets.contains_key(key)
            || state.sorted_sets.contains_key(key))
    }

    async fn clear(&self) -> Result<(), DataError> {
        let mut state = self.lock();
        state.entries.clear();
        state.sets.clear();
        state.sorted_sets.clear();
        state.collection_expiry_ms.clear();
        state.stats.total_size = 0;
        Ok(())
    }

    async fn stats(&self) -> Result<CacheStats, DataError> {
        Ok(self.lock().stats.clone())
    }

    async fn sadd(
        &self,
        key: &str,
        members: Vec<Vec<u8>>,
        now_ms: u64,
    ) -> Result<usize, DataError> {
        if key.is_empty() {
            return Err(DataError::InvalidQuery("cache key is required".into()));
        }
        let mut state = self.lock();
        Self::purge(&mut state, key, now_ms);
        let set = state.sets.entry(key.to_owned()).or_default();
        Ok(members
            .into_iter()
            .map(|member| usize::from(set.insert(member)))
            .sum())
    }

    async fn srem(
        &self,
        key: &str,
        members: Vec<Vec<u8>>,
        now_ms: u64,
    ) -> Result<usize, DataError> {
        let mut state = self.lock();
        Self::purge(&mut state, key, now_ms);
        let Some(set) = state.sets.get_mut(key) else {
            return Ok(0);
        };
        let removed = members
            .into_iter()
            .map(|member| usize::from(set.remove(&member)))
            .sum();
        if set.is_empty() {
            state.sets.remove(key);
            state.collection_expiry_ms.remove(key);
        }
        Ok(removed)
    }

    async fn smembers(&self, key: &str, now_ms: u64) -> Result<Vec<Vec<u8>>, DataError> {
        let mut state = self.lock();
        Self::purge(&mut state, key, now_ms);
        Ok(state
            .sets
            .get(key)
            .map_or_else(Vec::new, |set| set.iter().cloned().collect()))
    }

    async fn zadd(&self, key: &str, members: BTreeMap<Vec<u8>, f64>) -> Result<usize, DataError> {
        if members.values().any(|score| !score.is_finite()) {
            return Err(DataError::InvalidQuery(
                "sorted-set score must be finite".into(),
            ));
        }
        let mut state = self.lock();
        let set = state.sorted_sets.entry(key.into()).or_default();
        let mut added = 0;
        for (member, score) in members {
            added += usize::from(set.insert(member, score).is_none());
        }
        Ok(added)
    }

    async fn zrevrangebyscore(
        &self,
        key: &str,
        max_score: f64,
        min_score: f64,
        start: usize,
        limit: Option<usize>,
    ) -> Result<Vec<Vec<u8>>, DataError> {
        validate_range(min_score, max_score)?;
        let state = self.lock();
        let mut values = state
            .sorted_sets
            .get(key)
            .into_iter()
            .flat_map(|set| set.iter())
            .filter(|(_, score)| **score >= min_score && **score <= max_score)
            .map(|(member, score)| (member.clone(), *score))
            .collect::<Vec<_>>();
        values.sort_by(|left, right| {
            right
                .1
                .total_cmp(&left.1)
                .then_with(|| left.0.cmp(&right.0))
        });
        Ok(values
            .into_iter()
            .skip(start)
            .take(limit.unwrap_or(usize::MAX))
            .map(|(member, _)| member)
            .collect())
    }

    async fn zcount(&self, key: &str, min_score: f64, max_score: f64) -> Result<usize, DataError> {
        validate_range(min_score, max_score)?;
        Ok(self.lock().sorted_sets.get(key).map_or(0, |set| {
            set.values()
                .filter(|score| **score >= min_score && **score <= max_score)
                .count()
        }))
    }

    async fn zremrangebyscore(
        &self,
        key: &str,
        min_score: f64,
        max_score: f64,
    ) -> Result<usize, DataError> {
        validate_range(min_score, max_score)?;
        let mut state = self.lock();
        let Some(set) = state.sorted_sets.get_mut(key) else {
            return Ok(0);
        };
        let before = set.len();
        set.retain(|_, score| *score < min_score || *score > max_score);
        Ok(before - set.len())
    }

    async fn zcard(&self, key: &str) -> Result<usize, DataError> {
        Ok(self.lock().sorted_sets.get(key).map_or(0, BTreeMap::len))
    }

    async fn zremrangebyrank(
        &self,
        key: &str,
        min_rank: usize,
        max_rank: usize,
    ) -> Result<usize, DataError> {
        if min_rank > max_rank {
            return Err(DataError::InvalidQuery(
                "invalid sorted-set rank range".into(),
            ));
        }
        let mut state = self.lock();
        let Some(set) = state.sorted_sets.get_mut(key) else {
            return Ok(0);
        };
        let mut ranked = set
            .iter()
            .map(|(member, score)| (member.clone(), *score))
            .collect::<Vec<_>>();
        ranked.sort_by(|left, right| {
            left.1
                .total_cmp(&right.1)
                .then_with(|| left.0.cmp(&right.0))
        });
        let members = ranked
            .into_iter()
            .skip(min_rank)
            .take(max_rank.saturating_sub(min_rank).saturating_add(1))
            .map(|(member, _)| member)
            .collect::<Vec<_>>();
        for member in &members {
            set.remove(member);
        }
        Ok(members.len())
    }

    async fn expire(&self, key: &str, ttl_seconds: u64, now_ms: u64) -> Result<bool, DataError> {
        let mut state = self.lock();
        let expires_at_ms = now_ms.saturating_add(ttl_seconds.saturating_mul(1_000));
        if let Some(entry) = state.entries.get_mut(key) {
            entry.expires_at_ms = Some(expires_at_ms);
            return Ok(true);
        }
        if state.sets.contains_key(key) || state.sorted_sets.contains_key(key) {
            state
                .collection_expiry_ms
                .insert(key.to_owned(), expires_at_ms);
            return Ok(true);
        }
        Ok(false)
    }

    async fn keys(&self, pattern: &str, now_ms: u64) -> Result<Vec<String>, DataError> {
        let mut state = self.lock();
        let keys = state.entries.keys().cloned().collect::<Vec<_>>();
        for key in &keys {
            Self::purge(&mut state, key, now_ms);
        }
        Ok(state
            .entries
            .keys()
            .chain(state.sets.keys())
            .chain(state.sorted_sets.keys())
            .filter(|key| glob_matches(pattern, key))
            .cloned()
            .collect())
    }
}

fn validate_range(minimum: f64, maximum: f64) -> Result<(), DataError> {
    if !minimum.is_finite() || !maximum.is_finite() || minimum > maximum {
        return Err(DataError::InvalidQuery(
            "invalid sorted-set score range".into(),
        ));
    }
    Ok(())
}

fn glob_matches(pattern: &str, value: &str) -> bool {
    if pattern == "*" {
        return true;
    }
    let segments = pattern.split('*').collect::<Vec<_>>();
    let mut remainder = value;
    for (index, segment) in segments.iter().enumerate() {
        if segment.is_empty() {
            continue;
        }
        let Some(position) = remainder.find(segment) else {
            return false;
        };
        if index == 0 && !pattern.starts_with('*') && position != 0 {
            return false;
        }
        remainder = &remainder[position + segment.len()..];
    }
    pattern.ends_with('*') || remainder.is_empty()
}
