use std::collections::{BTreeMap, VecDeque};
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
#[cfg(feature = "redis")]
use redis::aio::MultiplexedConnection;
use serde::{Deserialize, Serialize};
#[cfg(feature = "redis")]
use tokio::sync::Mutex as AsyncMutex;
#[cfg(feature = "redis")]
use uuid::Uuid;

use crate::{DistributedRateLimiter, SecurityError};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RateLimitStrategy {
    TokenBucket,
    SlidingWindow,
    FixedWindow,
    LeakyBucket,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RateLimitScope {
    Global,
    PerUser,
    PerIp,
    PerEndpoint,
    PerService,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RateLimitRule {
    pub name: String,
    pub scope: RateLimitScope,
    pub strategy: RateLimitStrategy,
    pub limit: u64,
    pub window_ms: u64,
    #[serde(default)]
    pub burst_size: u64,
    #[serde(default = "enabled")]
    pub enabled: bool,
}

const fn enabled() -> bool {
    true
}

impl RateLimitRule {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.name.trim().is_empty() || self.limit == 0 || self.window_ms == 0 {
            return Err(SecurityError::InvalidRateLimitRule(self.name.clone()));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct RateLimitQuota {
    pub user_id: Option<String>,
    pub ip_address: Option<String>,
    pub endpoint: Option<String>,
    pub service: Option<String>,
    pub custom_key: Option<String>,
}

impl RateLimitQuota {
    #[must_use]
    pub fn cache_key(&self, rule: &RateLimitRule) -> String {
        let scope = match rule.scope {
            RateLimitScope::PerUser => self.user_id.as_ref().map(|value| format!("user:{value}")),
            RateLimitScope::PerIp => self.ip_address.as_ref().map(|value| format!("ip:{value}")),
            RateLimitScope::PerEndpoint => self
                .endpoint
                .as_ref()
                .map(|value| format!("endpoint:{value}")),
            RateLimitScope::PerService => self
                .service
                .as_ref()
                .map(|value| format!("service:{value}")),
            RateLimitScope::Global => Some("global".to_owned()),
        }
        .or_else(|| self.custom_key.clone())
        .unwrap_or_else(|| "unknown".to_owned());
        format!("rate_limit:{}:{scope}", rule.name)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RateLimitResult {
    pub allowed: bool,
    pub rule_name: String,
    pub current_count: u64,
    pub limit: u64,
    pub remaining: u64,
    pub reset_at_ms: u64,
    pub retry_after_ms: u64,
}

#[derive(Clone, Debug)]
enum WindowState {
    Fixed { started_at_ms: u64, count: u64 },
    Sliding { requests: VecDeque<u64> },
    Token { tokens: f64, updated_at_ms: u64 },
    Leaky { level: f64, updated_at_ms: u64 },
}

#[derive(Clone, Debug, Default)]
pub struct InMemoryRateLimiter {
    windows: Arc<Mutex<BTreeMap<String, WindowState>>>,
}

impl InMemoryRateLimiter {
    pub fn check(
        &self,
        rule: &RateLimitRule,
        quota: &RateLimitQuota,
        now_ms: u64,
    ) -> Result<RateLimitResult, SecurityError> {
        rule.validate()?;
        if !rule.enabled {
            return Ok(result(rule, true, 0, rule.limit, now_ms, 0));
        }
        let key = quota.cache_key(rule);
        let mut windows = self
            .windows
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let state = windows
            .entry(key)
            .or_insert_with(|| initial_state(rule, now_ms));
        Ok(match state {
            WindowState::Fixed {
                started_at_ms,
                count,
            } => check_fixed(rule, now_ms, started_at_ms, count),
            WindowState::Sliding { requests } => check_sliding(rule, now_ms, requests),
            WindowState::Token {
                tokens,
                updated_at_ms,
            } => check_token(rule, now_ms, tokens, updated_at_ms),
            WindowState::Leaky {
                level,
                updated_at_ms,
            } => check_leaky(rule, now_ms, level, updated_at_ms),
        })
    }
}

#[async_trait]
impl DistributedRateLimiter for InMemoryRateLimiter {
    async fn check(
        &self,
        rule: &RateLimitRule,
        quota: &RateLimitQuota,
        now_ms: u64,
    ) -> Result<RateLimitResult, SecurityError> {
        InMemoryRateLimiter::check(self, rule, quota, now_ms)
    }
}

/// Atomic Redis implementation of every canonical rate-limit strategy.
#[cfg(feature = "redis")]
pub struct RedisRateLimiter {
    connection: AsyncMutex<MultiplexedConnection>,
    key_prefix: String,
}

#[cfg(feature = "redis")]
impl RedisRateLimiter {
    pub async fn connect(
        redis_url: &str,
        key_prefix: impl Into<String>,
    ) -> Result<Self, SecurityError> {
        if redis_url.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "Redis rate limiter URL is required".into(),
            ));
        }
        let client = redis::Client::open(redis_url).map_err(|_| {
            SecurityError::ProviderUnavailable("Redis rate limiter URL is invalid".into())
        })?;
        let connection = client
            .get_multiplexed_async_connection()
            .await
            .map_err(|_| {
                SecurityError::ProviderUnavailable("Redis rate limiter connection failed".into())
            })?;
        Self::from_connection(connection, key_prefix)
    }

    pub fn from_connection(
        connection: MultiplexedConnection,
        key_prefix: impl Into<String>,
    ) -> Result<Self, SecurityError> {
        let key_prefix = key_prefix.into();
        if key_prefix.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "Redis rate limiter key prefix is required".into(),
            ));
        }
        Ok(Self {
            connection: AsyncMutex::new(connection),
            key_prefix,
        })
    }

    pub async fn health_check(&self) -> Result<(), SecurityError> {
        let mut connection = self.connection.lock().await;
        let response: String = redis::cmd("PING")
            .query_async(&mut *connection)
            .await
            .map_err(|_| {
                SecurityError::ProviderUnavailable("Redis rate limiter health check failed".into())
            })?;
        if response == "PONG" {
            Ok(())
        } else {
            Err(SecurityError::ProviderUnavailable(
                "Redis rate limiter health check returned an invalid response".into(),
            ))
        }
    }

    fn key(&self, rule: &RateLimitRule, quota: &RateLimitQuota) -> String {
        redis_rate_limit_key(&self.key_prefix, rule, quota)
    }
}

#[cfg(feature = "redis")]
fn strategy_name(strategy: RateLimitStrategy) -> &'static str {
    match strategy {
        RateLimitStrategy::TokenBucket => "token_bucket",
        RateLimitStrategy::SlidingWindow => "sliding_window",
        RateLimitStrategy::FixedWindow => "fixed_window",
        RateLimitStrategy::LeakyBucket => "leaky_bucket",
    }
}

#[cfg(feature = "redis")]
fn redis_rate_limit_key(prefix: &str, rule: &RateLimitRule, quota: &RateLimitQuota) -> String {
    format!(
        "{}:{}:{}",
        prefix,
        strategy_name(rule.strategy),
        quota.cache_key(rule)
    )
}

#[cfg(feature = "redis")]
const REDIS_RATE_LIMIT_SCRIPT: &str = r"
local strategy = ARGV[1]
local now = tonumber(ARGV[2])
local window = tonumber(ARGV[3])
local limit = tonumber(ARGV[4])
local burst = tonumber(ARGV[5])
local capacity = limit + burst
local member = ARGV[6]
local allowed = 0
local current = 0
local remaining = 0
local reset = now + window
local retry = 0

if strategy == 'sliding_window' then
  redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
  current = redis.call('ZCARD', KEYS[1])
  if current < capacity then
    redis.call('ZADD', KEYS[1], now, member)
    current = current + 1
    allowed = 1
  end
  redis.call('PEXPIRE', KEYS[1], window + 1000)
  remaining = math.max(0, capacity - current)
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  if #oldest >= 2 then reset = tonumber(oldest[2]) + window end
  if allowed == 0 then retry = math.max(0, reset - now) end
elseif strategy == 'fixed_window' then
  local started = tonumber(redis.call('HGET', KEYS[1], 'started') or now)
  current = tonumber(redis.call('HGET', KEYS[1], 'count') or 0)
  if now - started >= window then
    started = now
    current = 0
  end
  if current < capacity then
    current = current + 1
    allowed = 1
  end
  redis.call('HSET', KEYS[1], 'started', started, 'count', current)
  redis.call('PEXPIRE', KEYS[1], window + 1000)
  remaining = math.max(0, capacity - current)
  reset = started + window
  if allowed == 0 then retry = math.max(0, reset - now) end
elseif strategy == 'token_bucket' then
  local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens') or capacity)
  local updated = tonumber(redis.call('HGET', KEYS[1], 'updated') or now)
  tokens = math.min(capacity, tokens + math.max(0, now - updated) * limit / window)
  if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
  end
  remaining = math.max(0, math.floor(tokens))
  current = math.max(0, capacity - remaining)
  retry = allowed == 1 and 0 or math.ceil(window / limit)
  reset = now + retry
  redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated', now)
  redis.call('PEXPIRE', KEYS[1], window + 1000)
elseif strategy == 'leaky_bucket' then
  local level = tonumber(redis.call('HGET', KEYS[1], 'level') or 0)
  local updated = tonumber(redis.call('HGET', KEYS[1], 'updated') or now)
  level = math.max(0, level - math.max(0, now - updated) * limit / window)
  if level + 1 <= capacity then
    level = level + 1
    allowed = 1
  end
  current = math.ceil(level)
  remaining = math.max(0, capacity - current)
  retry = allowed == 1 and 0 or math.ceil(window / limit)
  reset = now + retry
  redis.call('HSET', KEYS[1], 'level', level, 'updated', now)
  redis.call('PEXPIRE', KEYS[1], window + 1000)
else
  return redis.error_reply('unsupported rate limit strategy')
end

return {allowed, current, remaining, reset, retry}
";

#[cfg(feature = "redis")]
#[async_trait]
impl DistributedRateLimiter for RedisRateLimiter {
    async fn check(
        &self,
        rule: &RateLimitRule,
        quota: &RateLimitQuota,
        now_ms: u64,
    ) -> Result<RateLimitResult, SecurityError> {
        rule.validate()?;
        if !rule.enabled {
            return Ok(result(rule, true, 0, rule.limit, now_ms, 0));
        }
        let strategy = strategy_name(rule.strategy);
        let key = self.key(rule, quota);
        let member = format!("{now_ms}:{}", Uuid::new_v4().simple());
        let mut connection = self.connection.lock().await;
        let (allowed, current_count, remaining, reset_at_ms, retry_after_ms): (
            i64,
            u64,
            u64,
            u64,
            u64,
        ) = redis::cmd("EVAL")
            .arg(REDIS_RATE_LIMIT_SCRIPT)
            .arg(1)
            .arg(key)
            .arg(strategy)
            .arg(now_ms)
            .arg(rule.window_ms)
            .arg(rule.limit)
            .arg(rule.burst_size)
            .arg(member)
            .query_async(&mut *connection)
            .await
            .map_err(|_| {
                SecurityError::ProviderUnavailable("Redis rate limit check failed".into())
            })?;
        Ok(RateLimitResult {
            allowed: allowed == 1,
            rule_name: rule.name.clone(),
            current_count,
            limit: rule.limit,
            remaining,
            reset_at_ms,
            retry_after_ms,
        })
    }
}

#[allow(clippy::cast_precision_loss)]
fn initial_state(rule: &RateLimitRule, now_ms: u64) -> WindowState {
    match rule.strategy {
        RateLimitStrategy::FixedWindow => WindowState::Fixed {
            started_at_ms: now_ms,
            count: 0,
        },
        RateLimitStrategy::SlidingWindow => WindowState::Sliding {
            requests: VecDeque::new(),
        },
        RateLimitStrategy::TokenBucket => WindowState::Token {
            tokens: (rule.limit + rule.burst_size) as f64,
            updated_at_ms: now_ms,
        },
        RateLimitStrategy::LeakyBucket => WindowState::Leaky {
            level: 0.0,
            updated_at_ms: now_ms,
        },
    }
}

fn check_fixed(
    rule: &RateLimitRule,
    now_ms: u64,
    started_at_ms: &mut u64,
    count: &mut u64,
) -> RateLimitResult {
    if now_ms.saturating_sub(*started_at_ms) >= rule.window_ms {
        *started_at_ms = now_ms;
        *count = 0;
    }
    let capacity = rule.limit.saturating_add(rule.burst_size);
    let allowed = *count < capacity;
    if allowed {
        *count = count.saturating_add(1);
    }
    let reset = started_at_ms.saturating_add(rule.window_ms);
    result(
        rule,
        allowed,
        *count,
        capacity.saturating_sub(*count),
        reset,
        if allowed {
            0
        } else {
            reset.saturating_sub(now_ms)
        },
    )
}

fn check_sliding(
    rule: &RateLimitRule,
    now_ms: u64,
    requests: &mut VecDeque<u64>,
) -> RateLimitResult {
    while requests
        .front()
        .is_some_and(|time| now_ms.saturating_sub(*time) >= rule.window_ms)
    {
        requests.pop_front();
    }
    let capacity = rule.limit.saturating_add(rule.burst_size);
    let allowed = u64::try_from(requests.len()).unwrap_or(u64::MAX) < capacity;
    if allowed {
        requests.push_back(now_ms);
    }
    let count = u64::try_from(requests.len()).unwrap_or(u64::MAX);
    let reset = requests
        .front()
        .copied()
        .unwrap_or(now_ms)
        .saturating_add(rule.window_ms);
    result(
        rule,
        allowed,
        count,
        capacity.saturating_sub(count),
        reset,
        if allowed {
            0
        } else {
            reset.saturating_sub(now_ms)
        },
    )
}

#[allow(clippy::cast_precision_loss)]
fn check_token(
    rule: &RateLimitRule,
    now_ms: u64,
    tokens: &mut f64,
    updated_at_ms: &mut u64,
) -> RateLimitResult {
    let capacity_units = rule.limit.saturating_add(rule.burst_size);
    let capacity = capacity_units as f64;
    let elapsed = now_ms.saturating_sub(*updated_at_ms) as f64;
    *tokens = (*tokens + elapsed * rule.limit as f64 / rule.window_ms as f64).min(capacity);
    *updated_at_ms = now_ms;
    let allowed = *tokens >= 1.0;
    if allowed {
        *tokens -= 1.0;
    }
    #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
    let remaining = tokens.floor().max(0.0) as u64;
    let retry_after = if allowed {
        0
    } else {
        rule.window_ms.div_ceil(rule.limit)
    };
    result(
        rule,
        allowed,
        capacity_units.saturating_sub(remaining),
        remaining,
        now_ms.saturating_add(retry_after),
        retry_after,
    )
}

#[allow(clippy::cast_precision_loss)]
fn check_leaky(
    rule: &RateLimitRule,
    now_ms: u64,
    level: &mut f64,
    updated_at_ms: &mut u64,
) -> RateLimitResult {
    let capacity_units = rule.limit.saturating_add(rule.burst_size);
    let capacity = capacity_units as f64;
    let elapsed = now_ms.saturating_sub(*updated_at_ms) as f64;
    *level = (*level - elapsed * rule.limit as f64 / rule.window_ms as f64).max(0.0);
    *updated_at_ms = now_ms;
    let allowed = *level + 1.0 <= capacity;
    if allowed {
        *level += 1.0;
    }
    #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
    let current = level.ceil() as u64;
    let retry_after = if allowed {
        0
    } else {
        rule.window_ms.div_ceil(rule.limit)
    };
    result(
        rule,
        allowed,
        current,
        capacity_units.saturating_sub(current),
        now_ms.saturating_add(retry_after),
        retry_after,
    )
}

fn result(
    rule: &RateLimitRule,
    allowed: bool,
    current_count: u64,
    remaining: u64,
    reset_at_ms: u64,
    retry_after_ms: u64,
) -> RateLimitResult {
    RateLimitResult {
        allowed,
        rule_name: rule.name.clone(),
        current_count,
        limit: rule.limit,
        remaining,
        reset_at_ms,
        retry_after_ms,
    }
}

#[cfg(all(test, feature = "redis"))]
mod redis_tests {
    use super::*;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        rate_limit: RedisFixture,
    }

    #[derive(Deserialize)]
    struct RedisFixture {
        prefix: String,
        rule_name: String,
        strategy: RateLimitStrategy,
        user_id: String,
        expected_key: String,
        supported_strategies: Vec<String>,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!(
            "../../../contracts/redis-runtime-behavior.json"
        ))
        .expect("valid Redis runtime fixture")
    }

    #[test]
    fn language_neutral_redis_rate_limit_contract() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        assert_eq!(
            fixture.rate_limit.supported_strategies,
            [
                RateLimitStrategy::TokenBucket,
                RateLimitStrategy::SlidingWindow,
                RateLimitStrategy::FixedWindow,
                RateLimitStrategy::LeakyBucket,
            ]
            .map(strategy_name)
        );
        let rule = RateLimitRule {
            name: fixture.rate_limit.rule_name,
            scope: RateLimitScope::PerUser,
            strategy: fixture.rate_limit.strategy,
            limit: 120,
            window_ms: 60_000,
            burst_size: 0,
            enabled: true,
        };
        let quota = RateLimitQuota {
            user_id: Some(fixture.rate_limit.user_id),
            ..RateLimitQuota::default()
        };
        assert_eq!(
            redis_rate_limit_key(&fixture.rate_limit.prefix, &rule, &quota),
            fixture.rate_limit.expected_key
        );
        assert!(REDIS_RATE_LIMIT_SCRIPT.contains("redis.call('ZADD'"));
        assert!(REDIS_RATE_LIMIT_SCRIPT.contains("redis.call('HSET'"));
    }

    #[tokio::test]
    async fn empty_redis_rate_limit_configuration_fails_before_io() {
        assert!(RedisRateLimiter::connect("", "mip:rl").await.is_err());
    }
}
