use std::collections::BTreeMap;
use std::time::{SystemTime, UNIX_EPOCH};

use mmf_data::{CacheBackend, CacheConfig, CacheStore, RedisCache};

fn redis_config(url: String, namespace: String) -> CacheConfig {
    CacheConfig {
        backend: CacheBackend::Redis,
        url: Some(url),
        namespace,
        key_prefix: "acceptance".into(),
        ..CacheConfig::default()
    }
}

async fn assert_atomic_and_set_contract(cache: &RedisCache) {
    cache
        .set("one-time", b"challenge".to_vec(), Some(60), 0)
        .await
        .expect("set one-time value");
    assert_eq!(
        cache.take("one-time", 0).await.expect("take value"),
        Some(b"challenge".to_vec())
    );
    assert_eq!(cache.take("one-time", 0).await.expect("replay take"), None);
    assert!(
        cache
            .set_if_absent("lease", b"first".to_vec(), Some(30), 0)
            .await
            .expect("first lease")
    );
    assert!(
        !cache
            .set_if_absent("lease", b"second".to_vec(), Some(30), 0)
            .await
            .expect("contended lease")
    );
    assert_eq!(
        cache.get("lease", 0).await.expect("lease read"),
        Some(b"first".to_vec())
    );
    assert_eq!(
        cache
            .sadd(
                "sessions",
                vec![b"session-2".to_vec(), b"session-1".to_vec()],
                0,
            )
            .await
            .expect("add set members"),
        2
    );
    assert_eq!(
        cache.smembers("sessions", 0).await.expect("set members"),
        [b"session-1".to_vec(), b"session-2".to_vec()]
    );
    assert_eq!(
        cache
            .srem("sessions", vec![b"session-1".to_vec()], 0)
            .await
            .expect("remove set member"),
        1
    );
    assert!(cache.delete("sessions").await.expect("delete set"));
}

#[test]
fn redis_configuration_is_namespaced_and_fail_closed() {
    let config = redis_config("redis://localhost:6379/0".into(), "organization".into());
    assert_eq!(
        config.key("member:tenant:user"),
        "organization:acceptance:member:tenant:user"
    );
    assert!(config.validate(false).is_ok());
    assert!(config.validate(true).is_err());

    let tls_config = redis_config("rediss://redis.example.test/0".into(), "production".into());
    assert!(tls_config.validate(true).is_ok());

    let unix_config = redis_config(
        "unix:///run/marty-redis/redis.sock?db=2".into(),
        "production".into(),
    );
    assert_eq!(unix_config.validate(true).is_ok(), cfg!(unix));
    for unsafe_url in [
        "unix://remote.example/run/redis.sock",
        "redis://redis:6379/0",
        "rediss://redis.example.test/0#insecure",
    ] {
        assert!(
            redis_config(unsafe_url.into(), "production".into())
                .validate(true)
                .is_err(),
            "{unsafe_url}"
        );
    }
}

#[tokio::test]
async fn redis_tls_connect_installs_a_crypto_provider_before_dialing() {
    let config = redis_config("rediss://127.0.0.1:1/0".into(), "tls-provider".into());
    assert!(RedisCache::connect(config, true).await.is_err());
    assert!(rustls::crypto::CryptoProvider::get_default().is_some());
}

#[tokio::test]
async fn redis_backend_matches_the_canonical_cache_contract_when_available() {
    let Ok(url) = std::env::var("MMF_REDIS_TEST_URL") else {
        return;
    };
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock")
        .as_nanos();
    let namespace = format!("mmf-redis-acceptance-{}-{unique}", std::process::id());
    let production = url.starts_with("unix://") || url.starts_with("redis+unix://");
    let cache = RedisCache::connect(redis_config(url.clone(), namespace), production)
        .await
        .expect("connect primary namespace");
    let isolated = cache
        .with_key_space(format!("mmf-redis-isolated-{unique}"), "acceptance")
        .expect("derive isolated namespace");

    cache.clear().await.expect("clear primary namespace");
    isolated.clear().await.expect("clear isolated namespace");
    isolated
        .set("shared", b"isolated".to_vec(), None, 0)
        .await
        .expect("set isolated value");

    cache
        .set("shared", b"primary".to_vec(), None, 0)
        .await
        .expect("set primary value");
    assert_eq!(
        cache.get("shared", 0).await.expect("get primary"),
        Some(b"primary".to_vec())
    );
    assert!(cache.exists("shared", 0).await.expect("primary exists"));
    assert_eq!(cache.keys("sha*", 0).await.expect("scan keys"), ["shared"]);

    cache
        .set("expiring", b"value".to_vec(), Some(1), 0)
        .await
        .expect("set expiring value");
    tokio::time::sleep(std::time::Duration::from_millis(1_100)).await;
    assert_eq!(cache.get("expiring", 0).await.expect("expired get"), None);

    cache
        .zadd(
            "scores",
            BTreeMap::from([(b"low".to_vec(), 1.0), (b"high".to_vec(), 3.0)]),
        )
        .await
        .expect("add sorted-set members");
    assert_eq!(cache.zcard("scores").await.expect("sorted-set size"), 2);
    assert_eq!(
        cache
            .zrevrangebyscore("scores", 3.0, 0.0, 0, None)
            .await
            .expect("sorted-set range"),
        [b"high".to_vec(), b"low".to_vec()]
    );
    assert_eq!(
        cache
            .zcount("scores", 0.0, 2.0)
            .await
            .expect("sorted-set count"),
        1
    );
    assert!(cache.expire("scores", 30, 0).await.expect("sorted-set TTL"));
    assert!(cache.delete("scores").await.expect("delete sorted set"));

    let stats = cache.stats().await.expect("cache stats");
    assert_eq!(stats.hits, 1);
    assert_eq!(stats.misses, 1);
    assert_eq!(stats.sets, 2);
    assert_eq!(stats.deletes, 1);
    assert_eq!(stats.errors, 0);

    assert_atomic_and_set_contract(&cache).await;

    cache.clear().await.expect("clear primary namespace");
    assert_eq!(
        isolated.get("shared", 0).await.expect("get isolated"),
        Some(b"isolated".to_vec())
    );
    isolated.clear().await.expect("clear isolated namespace");
}
