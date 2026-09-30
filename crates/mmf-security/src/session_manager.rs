//! Canonical session orchestration and native in-memory/Redis provider adapters.

use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use async_trait::async_trait;
#[cfg(feature = "redis")]
use redis::AsyncCommands;
#[cfg(feature = "redis")]
use redis::aio::MultiplexedConnection;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::sync::Mutex;

use crate::managed_session::{ManagedSession, SessionSecurityContext, SessionTimeout};
use crate::session_configuration::SessionConfiguration;
use crate::session_events::{
    EventSeverity, ManagedSessionStore, SessionEvent, SessionEventDetails, SessionEventMetadata,
    SessionProviders,
};
use crate::{SecurityError, SessionEventType, SessionState};

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct SessionMetrics {
    pub total_sessions_created: u64,
    pub active_sessions: u64,
    pub expired_sessions: u64,
    pub terminated_sessions: u64,
    #[serde(default)]
    pub cleanup_events: BTreeMap<String, u64>,
    pub average_session_duration_ms: f64,
    pub peak_concurrent_sessions: u64,
    pub cleanup_operations: u64,
}

impl SessionMetrics {
    fn created(&mut self) {
        self.total_sessions_created = self.total_sessions_created.saturating_add(1);
        self.active_sessions = self.active_sessions.saturating_add(1);
        self.peak_concurrent_sessions = self.peak_concurrent_sessions.max(self.active_sessions);
    }

    fn removed(&mut self, reason: &str, duration_ms: u64, expired: bool) {
        self.active_sessions = self.active_sessions.saturating_sub(1);
        if expired {
            self.expired_sessions = self.expired_sessions.saturating_add(1);
        } else {
            self.terminated_sessions = self.terminated_sessions.saturating_add(1);
        }
        *self.cleanup_events.entry(reason.into()).or_default() += 1;
        let completed = self
            .expired_sessions
            .saturating_add(self.terminated_sessions);
        if completed > 0 {
            let duration = f64::from(u32::try_from(duration_ms).unwrap_or(u32::MAX));
            let sample_count = f64::from(u32::try_from(completed).unwrap_or(u32::MAX));
            self.average_session_duration_ms +=
                (duration - self.average_session_duration_ms) / sample_count;
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct CreateSessionRequest {
    pub user_id: String,
    pub security_context: SessionSecurityContext,
    pub requested_timeout_ms: Option<u64>,
    pub auth_method: Option<String>,
    #[serde(default)]
    pub roles: BTreeSet<String>,
    #[serde(default)]
    pub permissions: BTreeSet<String>,
    #[serde(default)]
    pub attributes: BTreeMap<String, Value>,
}

pub struct SessionTokens {
    pub refresh_token: Option<String>,
    pub refresh_expires_at_ms: Option<u64>,
    pub id_token: Option<String>,
    pub access_token: Option<String>,
    pub access_expires_at_ms: Option<u64>,
    pub expires_at_ms: Option<u64>,
}

impl fmt::Debug for SessionTokens {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("SessionTokens")
            .field(
                "refresh_token",
                &self.refresh_token.as_ref().map(|_| "[REDACTED]"),
            )
            .field("refresh_expires_at_ms", &self.refresh_expires_at_ms)
            .field("id_token", &self.id_token.as_ref().map(|_| "[REDACTED]"))
            .field(
                "access_token",
                &self.access_token.as_ref().map(|_| "[REDACTED]"),
            )
            .field("access_expires_at_ms", &self.access_expires_at_ms)
            .field("expires_at_ms", &self.expires_at_ms)
            .finish()
    }
}

#[derive(Clone, Deserialize, Serialize)]
struct StoredSessionTokens {
    refresh_token: Option<String>,
    refresh_expires_at_ms: Option<u64>,
    id_token: Option<String>,
    access_token: Option<String>,
    access_expires_at_ms: Option<u64>,
    expires_at_ms: Option<u64>,
}

impl From<SessionTokens> for StoredSessionTokens {
    fn from(value: SessionTokens) -> Self {
        Self {
            refresh_token: value.refresh_token,
            refresh_expires_at_ms: value.refresh_expires_at_ms,
            id_token: value.id_token,
            access_token: value.access_token,
            access_expires_at_ms: value.access_expires_at_ms,
            expires_at_ms: value.expires_at_ms,
        }
    }
}

impl From<StoredSessionTokens> for SessionTokens {
    fn from(value: StoredSessionTokens) -> Self {
        Self {
            refresh_token: value.refresh_token,
            refresh_expires_at_ms: value.refresh_expires_at_ms,
            id_token: value.id_token,
            access_token: value.access_token,
            access_expires_at_ms: value.access_expires_at_ms,
            expires_at_ms: value.expires_at_ms,
        }
    }
}

#[async_trait]
pub trait SessionTokenVault: Send + Sync {
    async fn put(&self, session_id: &str, tokens: SessionTokens) -> Result<(), SecurityError>;
    async fn get(&self, session_id: &str) -> Result<Option<SessionTokens>, SecurityError>;
    async fn delete(&self, session_id: &str) -> Result<(), SecurityError>;

    async fn health_check(&self) -> Result<(), SecurityError> {
        Ok(())
    }
}

#[derive(Default)]
pub struct InMemoryManagedSessionStore {
    sessions: Mutex<BTreeMap<String, ManagedSession>>,
}

#[async_trait]
impl ManagedSessionStore for InMemoryManagedSessionStore {
    async fn create(&self, session: &ManagedSession) -> Result<(), SecurityError> {
        session.validate()?;
        let mut sessions = self.sessions.lock().await;
        if sessions.contains_key(&session.session_id) {
            return Err(SecurityError::SessionAlreadyExists);
        }
        sessions.insert(session.session_id.clone(), session.clone());
        Ok(())
    }

    async fn get(&self, session_id: &str) -> Result<Option<ManagedSession>, SecurityError> {
        Ok(self.sessions.lock().await.get(session_id).cloned())
    }

    async fn replace(&self, session: &ManagedSession) -> Result<(), SecurityError> {
        session.validate()?;
        let mut sessions = self.sessions.lock().await;
        if !sessions.contains_key(&session.session_id) {
            return Err(SecurityError::SessionNotFound);
        }
        sessions.insert(session.session_id.clone(), session.clone());
        Ok(())
    }

    async fn delete(&self, session_id: &str) -> Result<bool, SecurityError> {
        Ok(self.sessions.lock().await.remove(session_id).is_some())
    }

    async fn active_for_user(&self, user_id: &str) -> Result<Vec<ManagedSession>, SecurityError> {
        let mut sessions: Vec<_> = self
            .sessions
            .lock()
            .await
            .values()
            .filter(|session| session.user_id == user_id && session.state == SessionState::Active)
            .cloned()
            .collect();
        sessions.sort_by_key(|session| (session.created_at_ms, session.session_id.clone()));
        Ok(sessions)
    }

    async fn expired_before(
        &self,
        before_ms: u64,
        limit: usize,
    ) -> Result<Vec<ManagedSession>, SecurityError> {
        let mut sessions: Vec<_> = self
            .sessions
            .lock()
            .await
            .values()
            .filter(|session| session.is_expired_at(before_ms))
            .cloned()
            .collect();
        sessions.sort_by_key(|session| (session.expires_at_ms, session.session_id.clone()));
        sessions.truncate(limit);
        Ok(sessions)
    }
}

#[derive(Default)]
pub struct InMemorySessionTokenVault {
    tokens: Mutex<BTreeMap<String, StoredSessionTokens>>,
}

#[async_trait]
impl SessionTokenVault for InMemorySessionTokenVault {
    async fn put(&self, session_id: &str, tokens: SessionTokens) -> Result<(), SecurityError> {
        if session_id.trim().is_empty() {
            return Err(SecurityError::InvalidSessionState);
        }
        self.tokens
            .lock()
            .await
            .insert(session_id.into(), tokens.into());
        Ok(())
    }

    async fn get(&self, session_id: &str) -> Result<Option<SessionTokens>, SecurityError> {
        Ok(self
            .tokens
            .lock()
            .await
            .get(session_id)
            .cloned()
            .map(SessionTokens::from))
    }

    async fn delete(&self, session_id: &str) -> Result<(), SecurityError> {
        self.tokens.lock().await.remove(session_id);
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
#[cfg(feature = "redis")]
pub struct RedisSessionKeys {
    prefix: String,
}

#[cfg(feature = "redis")]
impl RedisSessionKeys {
    #[must_use]
    pub fn new(prefix: impl Into<String>) -> Self {
        Self {
            prefix: prefix.into(),
        }
    }

    #[must_use]
    pub fn session(&self, session_id: &str) -> String {
        format!("{}session:{session_id}", self.prefix)
    }

    #[must_use]
    pub fn user_sessions(&self, user_id: &str) -> String {
        format!("{}user_sessions:{user_id}", self.prefix)
    }

    #[must_use]
    pub fn tokens(&self, session_id: &str) -> String {
        format!("{}refresh_token:{session_id}", self.prefix)
    }
}

#[cfg(feature = "redis")]
pub struct RedisManagedSessionStore {
    connection: Mutex<MultiplexedConnection>,
    keys: RedisSessionKeys,
}

#[cfg(feature = "redis")]
impl RedisManagedSessionStore {
    pub async fn connect(
        redis_url: &str,
        key_prefix: impl Into<String>,
    ) -> Result<Self, SecurityError> {
        if redis_url.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "Redis session storage requires a connection URL".into(),
            ));
        }
        let client = redis::Client::open(redis_url)
            .map_err(|error| backend_error("configure Redis", error))?;
        let connection = client
            .get_multiplexed_async_connection()
            .await
            .map_err(|error| backend_error("connect to Redis", error))?;
        Ok(Self {
            connection: Mutex::new(connection),
            keys: RedisSessionKeys::new(key_prefix),
        })
    }

    async fn write_session(
        &self,
        session: &ManagedSession,
        only_if: &str,
    ) -> Result<bool, SecurityError> {
        session.validate()?;
        let payload = serde_json::to_string(session)
            .map_err(|error| SecurityError::InvalidConfiguration(error.to_string()))?;
        let ttl_ms = session.expires_at_ms.saturating_sub(now_ms()).max(1);
        let result: Option<String> = redis::cmd("SET")
            .arg(self.keys.session(&session.session_id))
            .arg(payload)
            .arg("PX")
            .arg(ttl_ms)
            .arg(only_if)
            .query_async(&mut *self.connection.lock().await)
            .await
            .map_err(|error| backend_error("write Redis session", error))?;
        Ok(result.is_some())
    }

    async fn scan_session_keys(&self) -> Result<Vec<String>, SecurityError> {
        let pattern = self.keys.session("*");
        let mut cursor = 0_u64;
        let mut keys = Vec::new();
        loop {
            let (next, mut page): (u64, Vec<String>) = redis::cmd("SCAN")
                .arg(cursor)
                .arg("MATCH")
                .arg(&pattern)
                .arg("COUNT")
                .arg(100)
                .query_async(&mut *self.connection.lock().await)
                .await
                .map_err(|error| backend_error("scan Redis sessions", error))?;
            keys.append(&mut page);
            cursor = next;
            if cursor == 0 {
                break;
            }
        }
        Ok(keys)
    }
}

#[cfg(feature = "redis")]
#[async_trait]
impl ManagedSessionStore for RedisManagedSessionStore {
    async fn create(&self, session: &ManagedSession) -> Result<(), SecurityError> {
        if !self.write_session(session, "NX").await? {
            return Err(SecurityError::SessionAlreadyExists);
        }
        let _: usize = self
            .connection
            .lock()
            .await
            .sadd(
                self.keys.user_sessions(&session.user_id),
                &session.session_id,
            )
            .await
            .map_err(|error| backend_error("index Redis session", error))?;
        Ok(())
    }

    async fn get(&self, session_id: &str) -> Result<Option<ManagedSession>, SecurityError> {
        let payload: Option<String> = self
            .connection
            .lock()
            .await
            .get(self.keys.session(session_id))
            .await
            .map_err(|error| backend_error("read Redis session", error))?;
        payload
            .map(|value| {
                let session: ManagedSession =
                    serde_json::from_str(&value).map_err(|_| SecurityError::InvalidSessionState)?;
                session.validate()?;
                Ok(session)
            })
            .transpose()
    }

    async fn replace(&self, session: &ManagedSession) -> Result<(), SecurityError> {
        if !self.write_session(session, "XX").await? {
            return Err(SecurityError::SessionNotFound);
        }
        Ok(())
    }

    async fn delete(&self, session_id: &str) -> Result<bool, SecurityError> {
        let Some(session) = ManagedSessionStore::get(self, session_id).await? else {
            return Ok(false);
        };
        let mut connection = self.connection.lock().await;
        let deleted: usize = connection
            .del(self.keys.session(session_id))
            .await
            .map_err(|error| backend_error("delete Redis session", error))?;
        let _: usize = connection
            .srem(self.keys.user_sessions(&session.user_id), session_id)
            .await
            .map_err(|error| backend_error("remove Redis session index", error))?;
        let _: usize = connection
            .del(self.keys.tokens(session_id))
            .await
            .map_err(|error| backend_error("delete Redis session tokens", error))?;
        Ok(deleted > 0)
    }

    async fn active_for_user(&self, user_id: &str) -> Result<Vec<ManagedSession>, SecurityError> {
        let key = self.keys.user_sessions(user_id);
        let ids: Vec<String> = self
            .connection
            .lock()
            .await
            .smembers(&key)
            .await
            .map_err(|error| backend_error("read Redis session index", error))?;
        let mut sessions = Vec::new();
        for id in ids {
            match ManagedSessionStore::get(self, &id).await? {
                Some(session) if session.state == SessionState::Active => sessions.push(session),
                _ => {
                    let _: usize = self
                        .connection
                        .lock()
                        .await
                        .srem(&key, &id)
                        .await
                        .map_err(|error| backend_error("clean Redis session index", error))?;
                }
            }
        }
        sessions.sort_by_key(|session| (session.created_at_ms, session.session_id.clone()));
        Ok(sessions)
    }

    async fn expired_before(
        &self,
        before_ms: u64,
        limit: usize,
    ) -> Result<Vec<ManagedSession>, SecurityError> {
        let mut expired = Vec::new();
        for key in self.scan_session_keys().await? {
            let session_id = key.rsplit(':').next().unwrap_or_default();
            if let Some(session) = ManagedSessionStore::get(self, session_id).await?
                && session.is_expired_at(before_ms)
            {
                expired.push(session);
            }
        }
        expired.sort_by_key(|session| (session.expires_at_ms, session.session_id.clone()));
        expired.truncate(limit);
        Ok(expired)
    }

    async fn health_check(&self) -> Result<(), SecurityError> {
        let response: String = redis::cmd("PING")
            .query_async(&mut *self.connection.lock().await)
            .await
            .map_err(|error| backend_error("ping Redis", error))?;
        if response == "PONG" {
            Ok(())
        } else {
            Err(SecurityError::ProviderUnavailable(
                "Redis returned an invalid health response".into(),
            ))
        }
    }
}

#[cfg(feature = "redis")]
#[async_trait]
impl SessionTokenVault for RedisManagedSessionStore {
    async fn put(&self, session_id: &str, tokens: SessionTokens) -> Result<(), SecurityError> {
        let stored: StoredSessionTokens = tokens.into();
        let expiry = stored
            .refresh_expires_at_ms
            .into_iter()
            .chain(stored.access_expires_at_ms)
            .chain(stored.expires_at_ms)
            .max()
            .ok_or_else(|| {
                SecurityError::InvalidConfiguration(
                    "session tokens require at least one expiration".into(),
                )
            })?;
        let payload = serde_json::to_string(&stored)
            .map_err(|error| SecurityError::InvalidConfiguration(error.to_string()))?;
        let _: String = redis::cmd("SET")
            .arg(self.keys.tokens(session_id))
            .arg(payload)
            .arg("PX")
            .arg(expiry.saturating_sub(now_ms()).max(1))
            .query_async(&mut *self.connection.lock().await)
            .await
            .map_err(|error| backend_error("write Redis session tokens", error))?;
        Ok(())
    }

    async fn get(&self, session_id: &str) -> Result<Option<SessionTokens>, SecurityError> {
        let payload: Option<String> = self
            .connection
            .lock()
            .await
            .get(self.keys.tokens(session_id))
            .await
            .map_err(|error| backend_error("read Redis session tokens", error))?;
        payload
            .map(|value| {
                serde_json::from_str::<StoredSessionTokens>(&value)
                    .map(SessionTokens::from)
                    .map_err(|_| SecurityError::InvalidSessionState)
            })
            .transpose()
    }

    async fn delete(&self, session_id: &str) -> Result<(), SecurityError> {
        let _: usize = self
            .connection
            .lock()
            .await
            .del(self.keys.tokens(session_id))
            .await
            .map_err(|error| backend_error("delete Redis session tokens", error))?;
        Ok(())
    }

    async fn health_check(&self) -> Result<(), SecurityError> {
        ManagedSessionStore::health_check(self).await
    }
}

pub struct SessionManager {
    configuration: SessionConfiguration,
    providers: SessionProviders,
    tokens: Arc<dyn SessionTokenVault>,
    metrics: Mutex<SessionMetrics>,
}

impl SessionManager {
    pub fn new(
        configuration: SessionConfiguration,
        providers: SessionProviders,
        tokens: Option<Arc<dyn SessionTokenVault>>,
    ) -> Result<Self, SecurityError> {
        providers.validate(&configuration)?;
        let tokens = tokens.ok_or_else(|| {
            SecurityError::RequiredProvidersUnavailable(vec!["session_token_vault"])
        })?;
        Ok(Self {
            configuration,
            providers,
            tokens,
            metrics: Mutex::new(SessionMetrics::default()),
        })
    }

    fn store(&self) -> Result<&Arc<dyn ManagedSessionStore>, SecurityError> {
        self.providers.store.as_ref().ok_or_else(|| {
            SecurityError::RequiredProvidersUnavailable(vec!["managed_session_store"])
        })
    }

    pub async fn create_session_at(
        &self,
        request: CreateSessionRequest,
        now_ms: u64,
    ) -> Result<ManagedSession, SecurityError> {
        if request.user_id.trim().is_empty() {
            return Err(SecurityError::InvalidIdentity(
                "session user ID cannot be empty".into(),
            ));
        }
        self.validate_context(&request.security_context)?;
        let policy = &self.configuration.timeout_policy;
        let idle_timeout_ms = request
            .requested_timeout_ms
            .unwrap_or(policy.default_timeout_ms)
            .min(policy.max_timeout_ms)
            .min(policy.absolute_timeout_ms.saturating_sub(1));
        if idle_timeout_ms == 0 {
            return Err(SecurityError::InvalidConfiguration(
                "session timeout must be positive".into(),
            ));
        }
        self.enforce_user_limit(&request.user_id, now_ms).await?;
        let mut session = ManagedSession::create_at(
            request.user_id,
            request.security_context,
            SessionTimeout {
                idle_timeout_ms,
                absolute_timeout_ms: policy.absolute_timeout_ms,
                extend_on_activity: policy.extend_on_activity,
            },
            request.auth_method,
            request.roles,
            request.permissions,
            now_ms,
        )?;
        for (key, value) in request.attributes {
            session.set_data(key, value, now_ms);
        }
        self.store()?.create(&session).await?;
        self.publish(SessionEvent::created(
            &session.session_id,
            &session.user_id,
            now_ms,
        ))
        .await?;
        self.metrics.lock().await.created();
        Ok(session)
    }

    pub async fn create_session(
        &self,
        request: CreateSessionRequest,
    ) -> Result<ManagedSession, SecurityError> {
        self.create_session_at(request, now_ms()).await
    }

    pub async fn get_session_at(
        &self,
        session_id: &str,
        now_ms: u64,
    ) -> Result<Option<ManagedSession>, SecurityError> {
        let Some(mut session) = self.store()?.get(session_id).await? else {
            return Ok(None);
        };
        session.validate()?;
        if session.is_expired_at(now_ms) {
            session.state = SessionState::Expired;
            self.remove_session(session, "timeout", now_ms, true)
                .await?;
            return Ok(None);
        }
        Ok(Some(session))
    }

    pub async fn get_session(
        &self,
        session_id: &str,
    ) -> Result<Option<ManagedSession>, SecurityError> {
        self.get_session_at(session_id, now_ms()).await
    }

    pub async fn access_session_at(
        &self,
        session_id: &str,
        context: &SessionSecurityContext,
        action: &str,
        now_ms: u64,
    ) -> Result<ManagedSession, SecurityError> {
        let mut session = self
            .get_session_at(session_id, now_ms)
            .await?
            .ok_or(SecurityError::SessionNotFound)?;
        self.validate_context(context)?;
        self.validate_context_match(&session.security_context, context)?;
        session.access_at(None, action, now_ms)?;
        self.store()?.replace(&session).await?;
        self.publish(SessionEvent::accessed(
            &session.session_id,
            &session.user_id,
            action,
            now_ms,
        ))
        .await?;
        Ok(session)
    }

    pub async fn access_session(
        &self,
        session_id: &str,
        context: &SessionSecurityContext,
        action: &str,
    ) -> Result<ManagedSession, SecurityError> {
        self.access_session_at(session_id, context, action, now_ms())
            .await
    }

    pub async fn update_session(&self, session: &ManagedSession) -> Result<(), SecurityError> {
        session.validate()?;
        if !session.is_active_at(now_ms()) {
            return Err(SecurityError::InvalidSessionState);
        }
        self.store()?.replace(session).await
    }

    pub async fn extend_session_at(
        &self,
        session_id: &str,
        extension_ms: u64,
        now_ms: u64,
    ) -> Result<ManagedSession, SecurityError> {
        if extension_ms == 0 {
            return Err(SecurityError::InvalidConfiguration(
                "session extension must be positive".into(),
            ));
        }
        let mut session = self
            .get_session_at(session_id, now_ms)
            .await?
            .ok_or(SecurityError::SessionNotFound)?;
        let count = session
            .metadata
            .get("extension_count")
            .and_then(Value::as_u64)
            .unwrap_or(0);
        if count >= self.configuration.timeout_policy.max_extensions as u64 {
            return Err(SecurityError::SessionLimitExceeded);
        }
        session.expires_at_ms = now_ms.saturating_add(extension_ms).min(
            session
                .created_at_ms
                .saturating_add(session.timeout.absolute_timeout_ms),
        );
        if session.expires_at_ms <= now_ms {
            return Err(SecurityError::InvalidSessionState);
        }
        session.metadata.insert(
            "extension_count".into(),
            Value::from(count.saturating_add(1)),
        );
        self.store()?.replace(&session).await?;
        Ok(session)
    }

    pub async fn extend_session(
        &self,
        session_id: &str,
        extension_ms: u64,
    ) -> Result<ManagedSession, SecurityError> {
        self.extend_session_at(session_id, extension_ms, now_ms())
            .await
    }

    pub async fn terminate_session_at(
        &self,
        session_id: &str,
        reason: &str,
        now_ms: u64,
    ) -> Result<bool, SecurityError> {
        let Some(mut session) = self.store()?.get(session_id).await? else {
            return Ok(false);
        };
        session.terminate_at(reason, now_ms);
        self.remove_session(session, reason, now_ms, false).await?;
        Ok(true)
    }

    pub async fn terminate_session(
        &self,
        session_id: &str,
        reason: &str,
    ) -> Result<bool, SecurityError> {
        self.terminate_session_at(session_id, reason, now_ms())
            .await
    }

    pub async fn terminate_user_sessions_at(
        &self,
        user_id: &str,
        except_session_id: Option<&str>,
        reason: &str,
        now_ms: u64,
    ) -> Result<usize, SecurityError> {
        let sessions = self.store()?.active_for_user(user_id).await?;
        let mut terminated = 0;
        for session in sessions {
            if except_session_id == Some(session.session_id.as_str()) {
                continue;
            }
            if self
                .terminate_session_at(&session.session_id, reason, now_ms)
                .await?
            {
                terminated += 1;
            }
        }
        Ok(terminated)
    }

    pub async fn terminate_user_sessions(
        &self,
        user_id: &str,
        except_session_id: Option<&str>,
        reason: &str,
    ) -> Result<usize, SecurityError> {
        self.terminate_user_sessions_at(user_id, except_session_id, reason, now_ms())
            .await
    }

    pub async fn user_sessions_at(
        &self,
        user_id: &str,
        now_ms: u64,
    ) -> Result<Vec<ManagedSession>, SecurityError> {
        let sessions = self.store()?.active_for_user(user_id).await?;
        let mut active = Vec::new();
        for session in sessions {
            if session.is_active_at(now_ms) {
                active.push(session);
            } else {
                self.remove_session(session, "timeout", now_ms, true)
                    .await?;
            }
        }
        Ok(active)
    }

    pub async fn user_sessions(&self, user_id: &str) -> Result<Vec<ManagedSession>, SecurityError> {
        self.user_sessions_at(user_id, now_ms()).await
    }

    pub async fn cleanup_expired_at(
        &self,
        now_ms: u64,
        limit: usize,
    ) -> Result<usize, SecurityError> {
        if limit == 0 {
            return Err(SecurityError::InvalidConfiguration(
                "session cleanup limit must be positive".into(),
            ));
        }
        let sessions = self.store()?.expired_before(now_ms, limit).await?;
        let count = sessions.len();
        for session in sessions {
            self.remove_session(session, "timeout", now_ms, true)
                .await?;
        }
        let mut metrics = self.metrics.lock().await;
        metrics.cleanup_operations = metrics.cleanup_operations.saturating_add(1);
        Ok(count)
    }

    pub async fn cleanup_expired(&self) -> Result<usize, SecurityError> {
        self.cleanup_expired_at(now_ms(), self.configuration.cleanup.batch_size)
            .await
    }

    pub async fn put_tokens(
        &self,
        session_id: &str,
        tokens: SessionTokens,
    ) -> Result<(), SecurityError> {
        self.put_tokens_at(session_id, tokens, now_ms()).await
    }

    pub async fn put_tokens_at(
        &self,
        session_id: &str,
        tokens: SessionTokens,
        now_ms: u64,
    ) -> Result<(), SecurityError> {
        let session = self
            .store()?
            .get(session_id)
            .await?
            .ok_or(SecurityError::SessionNotFound)?;
        let mut tokens = tokens;
        if tokens.expires_at_ms.is_none() {
            tokens.expires_at_ms = Some(session.expires_at_ms);
        }
        let expirations = [
            tokens.refresh_expires_at_ms,
            tokens.access_expires_at_ms,
            tokens.expires_at_ms,
        ];
        if expirations
            .into_iter()
            .flatten()
            .all(|expiry| expiry <= now_ms)
        {
            return Err(SecurityError::InvalidConfiguration(
                "session tokens require a future expiration".into(),
            ));
        }
        for token in [
            tokens.refresh_token.as_deref(),
            tokens.id_token.as_deref(),
            tokens.access_token.as_deref(),
        ]
        .into_iter()
        .flatten()
        {
            if token.trim().is_empty() {
                return Err(SecurityError::InvalidConfiguration(
                    "session token cannot be empty".into(),
                ));
            }
        }
        self.tokens.put(session_id, tokens).await
    }

    pub async fn tokens(&self, session_id: &str) -> Result<Option<SessionTokens>, SecurityError> {
        self.tokens_at(session_id, now_ms()).await
    }

    pub async fn tokens_at(
        &self,
        session_id: &str,
        now_ms: u64,
    ) -> Result<Option<SessionTokens>, SecurityError> {
        if self.store()?.get(session_id).await?.is_none() {
            return Ok(None);
        }
        let Some(mut tokens) = self.tokens.get(session_id).await? else {
            return Ok(None);
        };
        if tokens
            .refresh_expires_at_ms
            .is_some_and(|expiry| expiry <= now_ms)
        {
            tokens.refresh_token = None;
            tokens.refresh_expires_at_ms = None;
        }
        if tokens
            .access_expires_at_ms
            .is_some_and(|expiry| expiry <= now_ms)
        {
            tokens.access_token = None;
            tokens.access_expires_at_ms = None;
        }
        if tokens.refresh_token.is_none()
            && tokens.id_token.is_none()
            && tokens.access_token.is_none()
        {
            self.tokens.delete(session_id).await?;
            return Ok(None);
        }
        Ok(Some(tokens))
    }

    pub async fn update_access_token_at(
        &self,
        session_id: &str,
        access_token: String,
        expires_in_ms: u64,
        now_ms: u64,
    ) -> Result<(), SecurityError> {
        if expires_in_ms == 0 || access_token.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "access token and expiration must be present".into(),
            ));
        }
        let mut tokens = self
            .tokens_at(session_id, now_ms)
            .await?
            .ok_or_else(|| SecurityError::NotFound("session token bundle".into()))?;
        tokens.access_token = Some(access_token);
        tokens.access_expires_at_ms = Some(now_ms.saturating_add(expires_in_ms));
        self.put_tokens_at(session_id, tokens, now_ms).await
    }

    pub async fn should_refresh_access_token_at(
        &self,
        session_id: &str,
        threshold_ms: u64,
        now_ms: u64,
    ) -> Result<bool, SecurityError> {
        Ok(self
            .tokens_at(session_id, now_ms)
            .await?
            .and_then(|tokens| tokens.access_expires_at_ms)
            .is_some_and(|expiry| expiry <= now_ms.saturating_add(threshold_ms)))
    }

    pub async fn metrics(&self) -> SessionMetrics {
        self.metrics.lock().await.clone()
    }

    pub async fn health_check(&self) -> Result<(), SecurityError> {
        self.store()?.health_check().await?;
        self.tokens.health_check().await
    }

    async fn enforce_user_limit(&self, user_id: &str, now_ms: u64) -> Result<(), SecurityError> {
        let max = self.configuration.protection_policy.max_concurrent_sessions;
        let sessions = self.user_sessions_at(user_id, now_ms).await?;
        let remove = sessions.len().saturating_sub(max.saturating_sub(1));
        for session in sessions.into_iter().take(remove) {
            self.terminate_session_at(&session.session_id, "concurrent_session_limit", now_ms)
                .await?;
        }
        Ok(())
    }

    async fn remove_session(
        &self,
        session: ManagedSession,
        reason: &str,
        now_ms: u64,
        expired: bool,
    ) -> Result<(), SecurityError> {
        self.store()?.delete(&session.session_id).await?;
        self.tokens.delete(&session.session_id).await?;
        let event = if expired {
            SessionEvent::expired(&session.session_id, &session.user_id, reason, now_ms)
        } else {
            SessionEvent::create_at(
                &session.session_id,
                &session.user_id,
                SessionEventType::SessionTerminated,
                Some(reason.into()),
                EventSeverity::Medium,
                SessionEventMetadata::default(),
                SessionEventDetails::None,
                now_ms,
            )
        };
        self.publish(event).await?;
        self.metrics.lock().await.removed(
            reason,
            now_ms.saturating_sub(session.created_at_ms),
            expired,
        );
        Ok(())
    }

    async fn publish(&self, event: SessionEvent) -> Result<(), SecurityError> {
        if let Some(events) = &self.providers.events {
            events.publish(&event).await?;
        }
        if let Some(analytics) = &self.providers.analytics {
            analytics.record(&event).await?;
        }
        Ok(())
    }

    fn validate_context(&self, context: &SessionSecurityContext) -> Result<(), SecurityError> {
        context.validate()?;
        if self
            .configuration
            .protection_policy
            .require_secure_connection
            && !context.secure_connection
        {
            return Err(SecurityError::Unauthorized(
                "secure transport is required for sessions".into(),
            ));
        }
        Ok(())
    }

    fn validate_context_match(
        &self,
        expected: &SessionSecurityContext,
        actual: &SessionSecurityContext,
    ) -> Result<(), SecurityError> {
        let protection = &self.configuration.protection_policy;
        if protection.validate_ip_address
            && !protection.allow_ip_changes
            && expected.ip_address != actual.ip_address
        {
            return Err(SecurityError::Unauthorized(
                "session security context mismatch".into(),
            ));
        }
        if protection.validate_user_agent
            && !protection.allow_user_agent_changes
            && expected.user_agent != actual.user_agent
        {
            return Err(SecurityError::Unauthorized(
                "session security context mismatch".into(),
            ));
        }
        if protection.session_fingerprinting
            && expected.client_fingerprint.is_some()
            && expected.client_fingerprint != actual.client_fingerprint
        {
            return Err(SecurityError::Unauthorized(
                "session security context mismatch".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct SessionRequestContext {
    pub session_id: Option<String>,
    #[serde(default)]
    pub cookies: BTreeMap<String, String>,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    pub security_context: Option<SessionSecurityContext>,
    pub action: String,
    pub require_session: bool,
    pub now_ms: u64,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SessionRequestErrorCode {
    SessionRequired,
    SessionInvalid,
    SessionContextMismatch,
    BackendUnavailable,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SessionRequestError {
    pub code: SessionRequestErrorCode,
    pub message: String,
}

impl SessionManager {
    pub async fn resolve_request(
        &self,
        request: &SessionRequestContext,
        cookie_name: &str,
        header_name: &str,
    ) -> Result<Option<ManagedSession>, SessionRequestError> {
        if !self.configuration.enable_session_management {
            return Ok(None);
        }
        let session_id = request
            .session_id
            .as_deref()
            .or_else(|| request.cookies.get(cookie_name).map(String::as_str))
            .or_else(|| request.headers.get(header_name).map(String::as_str));
        let Some(session_id) = session_id else {
            return if request.require_session {
                Err(SessionRequestError {
                    code: SessionRequestErrorCode::SessionRequired,
                    message: "session is required".into(),
                })
            } else {
                Ok(None)
            };
        };
        let Some(context) = request.security_context.as_ref() else {
            return Err(SessionRequestError {
                code: SessionRequestErrorCode::SessionContextMismatch,
                message: "session security context is required".into(),
            });
        };
        match self
            .access_session_at(session_id, context, &request.action, request.now_ms)
            .await
        {
            Ok(session) => Ok(Some(session)),
            Err(SecurityError::SessionNotFound | SecurityError::InvalidSessionState) => {
                Err(SessionRequestError {
                    code: SessionRequestErrorCode::SessionInvalid,
                    message: "session is invalid or expired".into(),
                })
            }
            Err(SecurityError::Unauthorized(message)) => Err(SessionRequestError {
                code: SessionRequestErrorCode::SessionContextMismatch,
                message,
            }),
            Err(error) => Err(SessionRequestError {
                code: SessionRequestErrorCode::BackendUnavailable,
                message: error.to_string(),
            }),
        }
    }
}

#[cfg(feature = "redis")]
fn backend_error(operation: &str, error: impl fmt::Display) -> SecurityError {
    SecurityError::ProviderUnavailable(format!("failed to {operation}: {error}"))
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
    use super::*;

    fn fixture() -> Value {
        serde_json::from_str(include_str!(
            "../../../contracts/session-platform-behavior.json"
        ))
        .expect("valid session platform behavior fixture")
    }

    fn configuration(max_sessions: usize) -> SessionConfiguration {
        let mut configuration = SessionConfiguration::development().expect("development");
        configuration.protection_policy.max_concurrent_sessions = max_sessions;
        configuration.protection_policy.require_secure_connection = true;
        configuration.protection_policy.validate_ip_address = true;
        configuration.protection_policy.allow_ip_changes = false;
        configuration.protection_policy.validate_user_agent = true;
        configuration.protection_policy.allow_user_agent_changes = false;
        configuration.propagate_session_events = false;
        configuration.enable_session_analytics = false;
        configuration.cleanup.archive_old_sessions = false;
        configuration
    }

    fn context(ip_address: &str, user_agent: &str, now_ms: u64) -> SessionSecurityContext {
        SessionSecurityContext {
            ip_address: ip_address.into(),
            user_agent: Some(user_agent.into()),
            secure_connection: true,
            client_fingerprint: Some("fixture-device".into()),
            location_info: BTreeMap::new(),
            created_at_ms: now_ms,
        }
    }

    fn request(fixture: &Value, created_at_ms: u64) -> CreateSessionRequest {
        let case = &fixture["manager"];
        CreateSessionRequest {
            user_id: case["user_id"].as_str().expect("user ID").into(),
            security_context: context(
                fixture["middleware"]["ip_address"].as_str().expect("IP"),
                fixture["middleware"]["user_agent"]
                    .as_str()
                    .expect("user agent"),
                created_at_ms,
            ),
            requested_timeout_ms: Some(case["idle_timeout_ms"].as_u64().expect("timeout")),
            auth_method: Some("oidc".into()),
            roles: [case["role"].as_str().expect("role").into()]
                .into_iter()
                .collect(),
            permissions: [case["permission"].as_str().expect("permission").into()]
                .into_iter()
                .collect(),
            attributes: BTreeMap::from([(
                case["attribute"].as_str().expect("attribute").into(),
                case["attribute_value"].clone(),
            )]),
        }
    }

    fn manager(
        max_sessions: usize,
    ) -> (
        SessionManager,
        Arc<InMemoryManagedSessionStore>,
        Arc<InMemorySessionTokenVault>,
    ) {
        let store = Arc::new(InMemoryManagedSessionStore::default());
        let tokens = Arc::new(InMemorySessionTokenVault::default());
        let manager = SessionManager::new(
            configuration(max_sessions),
            SessionProviders {
                store: Some(store.clone()),
                ..SessionProviders::default()
            },
            Some(tokens.clone()),
        )
        .expect("manager");
        (manager, store, tokens)
    }

    #[tokio::test]
    #[allow(clippy::too_many_lines)]
    async fn manager_preserves_lifecycle_limits_tokens_metrics_and_cleanup_behavior() {
        let fixture = fixture();
        let case = &fixture["manager"];
        let created = case["created_at_ms"].as_array().expect("creation times");
        let (manager, _, _) = manager(
            usize::try_from(case["max_concurrent_sessions"].as_u64().expect("limit"))
                .expect("usize limit"),
        );
        let first = manager
            .create_session_at(
                request(&fixture, created[0].as_u64().expect("first")),
                1_000,
            )
            .await
            .expect("first session");
        manager
            .put_tokens_at(
                &first.session_id,
                SessionTokens {
                    refresh_token: Some(
                        fixture["tokens"]["refresh_token"]
                            .as_str()
                            .expect("refresh token")
                            .into(),
                    ),
                    refresh_expires_at_ms: fixture["tokens"]["refresh_expires_at_ms"].as_u64(),
                    id_token: Some(
                        fixture["tokens"]["id_token"]
                            .as_str()
                            .expect("ID token")
                            .into(),
                    ),
                    access_token: Some(
                        fixture["tokens"]["access_token"]
                            .as_str()
                            .expect("access token")
                            .into(),
                    ),
                    access_expires_at_ms: fixture["tokens"]["access_expires_at_ms"].as_u64(),
                    expires_at_ms: None,
                },
                1_000,
            )
            .await
            .expect("store tokens");
        let second = manager
            .create_session_at(request(&fixture, 2_000), 2_000)
            .await
            .expect("second session");
        let third = manager
            .create_session_at(request(&fixture, 3_000), 3_000)
            .await
            .expect("third session");
        assert!(
            manager
                .get_session_at(&first.session_id, 3_000)
                .await
                .expect("get")
                .is_none()
        );
        assert!(
            manager
                .tokens_at(&first.session_id, 3_000)
                .await
                .expect("tokens")
                .is_none()
        );
        let active = manager
            .user_sessions_at(case["user_id"].as_str().expect("user"), 3_000)
            .await
            .expect("active sessions");
        assert_eq!(
            active.len(),
            usize::try_from(
                case["expected_active_after_limit"]
                    .as_u64()
                    .expect("active count"),
            )
            .expect("usize active count")
        );
        let accessed = manager
            .access_session_at(
                &second.session_id,
                &request(&fixture, 2_000).security_context,
                "request",
                case["accessed_at_ms"].as_u64().expect("accessed"),
            )
            .await
            .expect("access session");
        assert_eq!(accessed.expires_at_ms, case["expected_extended_expiry_ms"]);
        assert!(accessed.has_role(case["role"].as_str().expect("role")));
        assert!(accessed.has_permission(case["permission"].as_str().expect("permission")));
        assert_eq!(
            accessed
                .data
                .get(case["attribute"].as_str().expect("attribute")),
            Some(&case["attribute_value"])
        );
        let terminated = manager
            .terminate_user_sessions_at(
                case["user_id"].as_str().expect("user"),
                Some(&third.session_id),
                case["terminate_reason"].as_str().expect("reason"),
                700_000,
            )
            .await
            .expect("terminate sessions");
        assert_eq!(terminated, 1);
        let mut expiring = request(&fixture, 800_000);
        expiring.user_id = case["other_user_id"].as_str().expect("other user").into();
        expiring.requested_timeout_ms = Some(1);
        manager
            .create_session_at(expiring, 800_000)
            .await
            .expect("expiring session");
        assert_eq!(
            manager
                .cleanup_expired_at(800_001, 100)
                .await
                .expect("cleanup"),
            1
        );
        let metrics = manager.metrics().await;
        assert_eq!(metrics.total_sessions_created, 4);
        assert_eq!(metrics.active_sessions, 1);
        assert_eq!(metrics.terminated_sessions, 2);
        assert_eq!(metrics.expired_sessions, 1);
        assert_eq!(metrics.cleanup_operations, 1);
    }

    #[tokio::test]
    async fn request_enforcement_and_token_refresh_fail_closed() {
        let fixture = fixture();
        let case = &fixture["middleware"];
        let (manager, _, _) = manager(2);
        let session = manager
            .create_session_at(request(&fixture, 1_000), 1_000)
            .await
            .expect("session");
        manager
            .put_tokens_at(
                &session.session_id,
                SessionTokens {
                    refresh_token: Some("refresh".into()),
                    refresh_expires_at_ms: Some(10_000_000),
                    id_token: Some("id".into()),
                    access_token: Some("access".into()),
                    access_expires_at_ms: Some(3_601_000),
                    expires_at_ms: None,
                },
                1_000,
            )
            .await
            .expect("tokens");
        assert!(
            manager
                .should_refresh_access_token_at(&session.session_id, 300_000, 3_301_000)
                .await
                .expect("refresh decision")
        );
        let request_context = SessionRequestContext {
            cookies: BTreeMap::from([(
                case["cookie_name"].as_str().expect("cookie").into(),
                session.session_id.clone(),
            )]),
            security_context: Some(request(&fixture, 1_000).security_context),
            action: "request".into(),
            require_session: true,
            now_ms: 2_000,
            ..SessionRequestContext::default()
        };
        let resolved = manager
            .resolve_request(
                &request_context,
                case["cookie_name"].as_str().expect("cookie"),
                case["header_name"].as_str().expect("header"),
            )
            .await
            .expect("resolve")
            .expect("session");
        assert_eq!(resolved.user_id, fixture["manager"]["user_id"]);
        let missing = manager
            .resolve_request(
                &SessionRequestContext {
                    require_session: true,
                    action: "request".into(),
                    now_ms: 2_000,
                    ..SessionRequestContext::default()
                },
                "session_id",
                "x-session-id",
            )
            .await
            .expect_err("missing session must fail");
        assert_eq!(missing.code, SessionRequestErrorCode::SessionRequired);
        let mut mismatch = request_context;
        mismatch.security_context = Some(context(
            case["other_ip_address"].as_str().expect("other IP"),
            case["user_agent"].as_str().expect("user agent"),
            2_000,
        ));
        let mismatch = manager
            .resolve_request(&mismatch, "session_id", "x-session-id")
            .await
            .expect_err("context mismatch must fail");
        assert_eq!(
            mismatch.code,
            SessionRequestErrorCode::SessionContextMismatch
        );
    }

    #[test]
    #[cfg(feature = "redis")]
    fn redis_keys_match_the_shared_contract() {
        let fixture = fixture();
        let keys =
            RedisSessionKeys::new(fixture["redis"]["key_prefix"].as_str().expect("key prefix"));
        assert_eq!(keys.session("session-123"), fixture["redis"]["session_key"]);
        assert_eq!(
            keys.user_sessions("user-123"),
            fixture["redis"]["user_sessions_key"]
        );
        assert_eq!(
            keys.tokens("session-123"),
            fixture["redis"]["refresh_token_key"]
        );
    }

    #[test]
    fn secret_debugging_redacts_tokens() {
        let tokens = SessionTokens {
            refresh_token: Some("top-secret".into()),
            refresh_expires_at_ms: Some(10_000),
            id_token: None,
            access_token: None,
            access_expires_at_ms: None,
            expires_at_ms: Some(10_000),
        };
        assert!(!format!("{tokens:?}").contains("top-secret"));
    }

    #[test]
    fn missing_native_providers_and_invalid_inputs_fail_closed() {
        let configuration = configuration(2);
        assert!(
            SessionManager::new(
                configuration.clone(),
                SessionProviders::default(),
                Some(Arc::new(InMemorySessionTokenVault::default())),
            )
            .is_err()
        );
        assert!(
            SessionManager::new(
                configuration,
                SessionProviders {
                    store: Some(Arc::new(InMemoryManagedSessionStore::default())),
                    ..SessionProviders::default()
                },
                None,
            )
            .is_err()
        );
    }
}
