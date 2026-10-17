//! Canonical reverse-proxy preparation, execution, and response normalization.

use std::{collections::BTreeMap, sync::Arc};

use mmf_resilience::{
    ExecutionError, ResilienceConfig, ResilienceManager, RetryConfig, RetryStrategy,
};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use tokio::sync::Mutex;
use uuid::Uuid;

use crate::{
    GatewayRequest, GatewayResponse, HttpMethod, LoadBalancer, LoadBalancingContext,
    LoadBalancingStrategy, PlatformError, RouteConfig, RouteTable, ServiceQuery, ServiceRegistry,
    UpstreamClient,
};

const MIP_CONTENT_TYPE: &str = "application/json";

/// Limits and resilience behavior shared by all MMF gateways.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct ProxyConfig {
    pub maximum_request_bytes: usize,
    pub maximum_response_bytes: usize,
    pub default_timeout_ms: u64,
    pub maximum_timeout_ms: u64,
    pub maximum_retries: u32,
    pub retry_base_delay_ms: u64,
    pub retry_max_delay_ms: u64,
    pub mip_version: String,
    pub load_balancing: LoadBalancingStrategy,
}

impl Default for ProxyConfig {
    fn default() -> Self {
        Self {
            maximum_request_bytes: 10 * 1024 * 1024,
            maximum_response_bytes: 10 * 1024 * 1024,
            default_timeout_ms: 30_000,
            maximum_timeout_ms: 30_000,
            maximum_retries: 2,
            retry_base_delay_ms: 500,
            retry_max_delay_ms: 4_000,
            mip_version: "0.4.1".into(),
            load_balancing: LoadBalancingStrategy::RoundRobin,
        }
    }
}

impl ProxyConfig {
    pub fn validate(&self) -> Result<(), PlatformError> {
        if self.maximum_request_bytes == 0
            || self.maximum_response_bytes == 0
            || self.default_timeout_ms == 0
            || self.maximum_timeout_ms == 0
            || self.default_timeout_ms > self.maximum_timeout_ms
            || self.retry_base_delay_ms == 0
            || self.retry_max_delay_ms < self.retry_base_delay_ms
            || self.mip_version.trim().is_empty()
        {
            return Err(PlatformError::InvalidConfiguration(
                "invalid reverse-proxy limits, timeouts, retries, or MIP version".into(),
            ));
        }
        Ok(())
    }
}

/// Identity values established at the gateway trust boundary.
#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct TrustedIdentityContext {
    pub user_id: Option<String>,
    pub user_email: Option<String>,
    pub user_domain: Option<String>,
    pub organization_id: Option<String>,
    pub api_key_id: Option<String>,
    #[serde(default)]
    pub api_key_scopes: Vec<String>,
    pub organization_plan: Option<String>,
    #[serde(default)]
    pub organization_permissions: Vec<String>,
    #[serde(default)]
    pub organization_roles: Vec<String>,
    pub required_permission: Option<String>,
}

/// Route-specific request changes made after authorization.
#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct ProxyOverrides {
    #[serde(default)]
    pub query: BTreeMap<String, Vec<String>>,
    /// Gateway-established query values that replace any client-controlled
    /// value with the same key after authorization.
    #[serde(default)]
    pub trusted_query: BTreeMap<String, Vec<String>>,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    pub body: Option<Vec<u8>>,
}

/// Execute matched routes through service discovery and the canonical resilience layer.
pub struct GatewayProxy {
    routes: RouteTable,
    registry: Arc<dyn ServiceRegistry>,
    upstream: Arc<dyn UpstreamClient>,
    balancer: Mutex<LoadBalancer>,
    config: ProxyConfig,
}

impl GatewayProxy {
    pub fn new(
        routes: RouteTable,
        registry: Arc<dyn ServiceRegistry>,
        upstream: Arc<dyn UpstreamClient>,
        config: ProxyConfig,
    ) -> Result<Self, PlatformError> {
        config.validate()?;
        Ok(Self {
            routes,
            registry,
            upstream,
            balancer: Mutex::new(LoadBalancer::default()),
            config,
        })
    }

    pub async fn execute(
        &self,
        mut request: GatewayRequest,
        identity: &TrustedIdentityContext,
        overrides: &ProxyOverrides,
    ) -> Result<GatewayResponse, PlatformError> {
        let matched = self.routes.find(&request)?;
        request.route_params = matched.params;
        let prepared =
            prepare_upstream_request(request, &matched.route, identity, overrides, &self.config)?;
        let instances = self
            .registry
            .discover(&ServiceQuery {
                service_name: matched.route.upstream_service.clone(),
                healthy_only: true,
                ..ServiceQuery::default()
            })
            .await?;
        let instance = self.balancer.lock().await.select(
            &matched.route.upstream_service,
            self.config.load_balancing,
            &instances,
            &LoadBalancingContext {
                client_ip: prepared.client_ip.clone(),
                hash_key: Some(prepared.request_id.clone()),
                ..LoadBalancingContext::default()
            },
        )?;

        let retryable = retryable_method(prepared.method);
        let retries = matched.route.retries.min(self.config.maximum_retries);
        let timeout_ms = matched.route.timeout_ms.min(self.config.maximum_timeout_ms);
        let resilience = ResilienceManager::new(
            format!("gateway:{}", matched.route.name),
            ResilienceConfig {
                retry: RetryConfig {
                    max_attempts: if retryable {
                        retries.saturating_add(1)
                    } else {
                        1
                    },
                    base_delay_ms: self.config.retry_base_delay_ms,
                    max_delay_ms: self.config.retry_max_delay_ms,
                    strategy: RetryStrategy::Exponential,
                    backoff_multiplier: 2.0,
                    jitter: false,
                    jitter_factor: 0.0,
                },
                retry_enabled: retryable && retries > 0,
                circuit_breaker_enabled: false,
                bulkhead_enabled: false,
                timeout_enabled: true,
                timeout_ms,
                ..ResilienceConfig::default()
            },
        )
        .map_err(|error| PlatformError::InvalidConfiguration(error.to_string()))?;

        let upstream = Arc::clone(&self.upstream);
        let result = resilience
            .execute(
                || {
                    let upstream = Arc::clone(&upstream);
                    let instance = instance.clone();
                    let request = prepared.clone();
                    async move { upstream.send(&instance, request).await }
                },
                is_retryable_failure,
            )
            .await;
        match result {
            Ok(response) => normalize_upstream_response(response, &self.config),
            Err(ExecutionError::RetryExhausted { last_error, .. }) => {
                Ok(upstream_failure_response(&last_error, &self.config))
            }
            Err(ExecutionError::Operation(error)) => {
                Ok(upstream_failure_response(&error, &self.config))
            }
            Err(ExecutionError::Resilience(error)) => Ok(mip_error_response(
                504,
                "service_timeout",
                &format!("Service timeout: {error}"),
                None,
                &self.config.mip_version,
            )),
        }
    }
}

/// Strip client-controlled context and inject only gateway-established identity.
pub fn prepare_upstream_request(
    mut request: GatewayRequest,
    route: &RouteConfig,
    identity: &TrustedIdentityContext,
    overrides: &ProxyOverrides,
    config: &ProxyConfig,
) -> Result<GatewayRequest, PlatformError> {
    config.validate()?;
    if let Some(body) = &overrides.body {
        request.body = Some(body.clone());
    }
    if request
        .body
        .as_ref()
        .is_some_and(|body| body.len() > config.maximum_request_bytes)
    {
        return Err(PlatformError::Operation(format!(
            "request exceeds the {}-byte limit",
            config.maximum_request_bytes
        )));
    }
    request.query = trusted_query(
        merge_query(request.query, &overrides.query),
        &overrides.trusted_query,
    );
    request.headers = trusted_headers(request.headers, identity, overrides.body.is_some());
    for (name, value) in &overrides.headers {
        insert_header(&mut request.headers, name, value.clone());
    }
    if let Some(path) = &route.rewrite_path {
        request.path = rewrite_path(path, &request.route_params);
    }
    Ok(request)
}

#[must_use]
pub fn merge_query(
    mut incoming: BTreeMap<String, Vec<String>>,
    injected: &BTreeMap<String, Vec<String>>,
) -> BTreeMap<String, Vec<String>> {
    for (key, values) in injected {
        incoming
            .entry(key.clone())
            .or_insert_with(|| values.clone());
    }
    incoming
}

#[must_use]
pub fn trusted_query(
    mut incoming: BTreeMap<String, Vec<String>>,
    trusted: &BTreeMap<String, Vec<String>>,
) -> BTreeMap<String, Vec<String>> {
    for (key, values) in trusted {
        incoming.insert(key.clone(), values.clone());
    }
    incoming
}

#[must_use]
pub const fn retryable_method(method: HttpMethod) -> bool {
    matches!(
        method,
        HttpMethod::Get
            | HttpMethod::Head
            | HttpMethod::Options
            | HttpMethod::Put
            | HttpMethod::Delete
    )
}

#[must_use]
pub fn trusted_headers(
    incoming: BTreeMap<String, String>,
    identity: &TrustedIdentityContext,
    body_overridden: bool,
) -> BTreeMap<String, String> {
    let forwarded_host = header(&incoming, "x-forwarded-host")
        .or_else(|| header(&incoming, "host"))
        .map(ToOwned::to_owned);
    let mut headers = incoming
        .into_iter()
        .filter(|(name, _)| !excluded_request_header(name, body_overridden))
        .collect::<BTreeMap<_, _>>();
    if let Some(value) = forwarded_host {
        insert_header(&mut headers, "X-Forwarded-Host", value);
    }
    insert_optional(&mut headers, "X-User-Id", identity.user_id.as_deref());
    insert_optional(&mut headers, "X-User-Email", identity.user_email.as_deref());
    insert_optional(
        &mut headers,
        "X-User-Domain",
        identity.user_domain.as_deref(),
    );
    insert_optional(
        &mut headers,
        "X-Organization-ID",
        identity.organization_id.as_deref(),
    );
    insert_optional(&mut headers, "X-Api-Key-Id", identity.api_key_id.as_deref());
    insert_ordered_list(&mut headers, "X-Api-Key-Scopes", &identity.api_key_scopes);
    insert_optional(
        &mut headers,
        "X-Org-Plan",
        identity.organization_plan.as_deref(),
    );
    insert_list(
        &mut headers,
        "X-Org-Permissions",
        &identity.organization_permissions,
    );
    insert_list(&mut headers, "X-Org-Roles", &identity.organization_roles);
    insert_optional(
        &mut headers,
        "X-Required-Permission",
        identity.required_permission.as_deref(),
    );
    headers
}

pub fn normalize_upstream_response(
    mut response: GatewayResponse,
    config: &ProxyConfig,
) -> Result<GatewayResponse, PlatformError> {
    config.validate()?;
    if response
        .body
        .as_ref()
        .is_some_and(|body| body.len() > config.maximum_response_bytes)
    {
        return Ok(mip_error_response(
            502,
            "response_too_large",
            "Downstream response exceeded size limit",
            None,
            &config.mip_version,
        ));
    }
    sanitize_response_headers(&mut response.headers);
    if response.status_code >= 400 {
        return Ok(normalize_error_response(response, &config.mip_version));
    }
    Ok(response)
}

fn normalize_error_response(response: GatewayResponse, mip_version: &str) -> GatewayResponse {
    let value = response
        .body
        .as_deref()
        .and_then(|body| serde_json::from_slice::<Value>(body).ok());
    let body = value.as_ref().and_then(Value::as_object);
    if body.is_some_and(complete_mip_error) {
        return response;
    }
    let detail = body.and_then(|value| value.get("detail"));
    let detail_object = detail.and_then(Value::as_object);
    let error = detail_object
        .and_then(|value| value.get("error"))
        .or_else(|| body.and_then(|value| value.get("error")))
        .and_then(Value::as_str)
        .unwrap_or("service_error");
    let description = detail_object
        .and_then(|value| value.get("message"))
        .and_then(Value::as_str)
        .or_else(|| detail.and_then(Value::as_str))
        .or_else(|| {
            body.and_then(|value| value.get("error_description"))
                .and_then(Value::as_str)
        })
        .unwrap_or("Downstream service request failed");
    let details = detail_object
        .map(|value| {
            Value::Object(
                value
                    .iter()
                    .filter(|(key, _)| !matches!(key.as_str(), "error" | "message"))
                    .map(|(key, value)| (key.clone(), value.clone()))
                    .collect(),
            )
        })
        .filter(|value| value.as_object().is_some_and(|map| !map.is_empty()))
        .or_else(|| body.and_then(|value| value.get("details")).cloned());
    mip_error_response(
        response.status_code,
        error,
        description,
        details,
        mip_version,
    )
}

#[must_use]
pub fn mip_error_response(
    status_code: u16,
    error: &str,
    description: &str,
    details: Option<Value>,
    mip_version: &str,
) -> GatewayResponse {
    let mut body = Map::from_iter([
        ("error".into(), Value::String(error.into())),
        (
            "error_description".into(),
            Value::String(description.into()),
        ),
        (
            "message_id".into(),
            Value::String(Uuid::new_v4().to_string()),
        ),
    ]);
    if let Some(details) = details {
        body.insert("details".into(), details);
    }
    let body = serde_json::to_vec(&Value::Object(body)).unwrap_or_default();
    GatewayResponse {
        status_code,
        headers: BTreeMap::from([
            ("Content-Type".into(), MIP_CONTENT_TYPE.into()),
            ("X-MIP-Version".into(), mip_version.into()),
        ]),
        set_cookies: Vec::new(),
        body: Some(body),
        response_time_ms: None,
        upstream_service: None,
    }
}

fn complete_mip_error(body: &Map<String, Value>) -> bool {
    ["error", "error_description"]
        .into_iter()
        .all(|key| body.get(key).and_then(Value::as_str).is_some())
        && body
            .get("message_id")
            .and_then(Value::as_str)
            .is_some_and(|value| !value.trim().is_empty())
}

fn excluded_request_header(name: &str, body_overridden: bool) -> bool {
    let name = name.to_ascii_lowercase();
    matches!(
        name.as_str(),
        "host"
            | "connection"
            | "keep-alive"
            | "transfer-encoding"
            | "x-user-id"
            | "x-user-email"
            | "x-user-domain"
            | "x-organization-id"
            | "x-api-key"
            | "x-api-key-id"
            | "x-api-key-scopes"
            | "x-org-plan"
            | "x-org-permissions"
            | "x-org-roles"
            | "x-required-permission"
    ) || (body_overridden && name == "content-length")
}

fn header<'a>(headers: &'a BTreeMap<String, String>, name: &str) -> Option<&'a str> {
    headers
        .iter()
        .find(|(key, _)| key.eq_ignore_ascii_case(name))
        .map(|(_, value)| value.as_str())
}

fn insert_header(headers: &mut BTreeMap<String, String>, name: &str, value: String) {
    headers.retain(|key, _| !key.eq_ignore_ascii_case(name));
    headers.insert(name.into(), value);
}

fn insert_optional(headers: &mut BTreeMap<String, String>, name: &str, value: Option<&str>) {
    if let Some(value) = value.filter(|value| !value.is_empty()) {
        insert_header(headers, name, value.into());
    }
}

fn insert_list(headers: &mut BTreeMap<String, String>, name: &str, values: &[String]) {
    if !values.is_empty() {
        let mut values = values.to_vec();
        values.sort();
        values.dedup();
        insert_header(headers, name, values.join(","));
    }
}

fn insert_ordered_list(headers: &mut BTreeMap<String, String>, name: &str, values: &[String]) {
    if !values.is_empty() {
        insert_header(headers, name, values.join(","));
    }
}

fn sanitize_response_headers(headers: &mut BTreeMap<String, String>) {
    headers.retain(|name, _| {
        !matches!(
            name.to_ascii_lowercase().as_str(),
            "content-encoding" | "transfer-encoding" | "content-length"
        )
    });
}

fn rewrite_path(template: &str, params: &BTreeMap<String, String>) -> String {
    params
        .iter()
        .fold(template.to_owned(), |path, (key, value)| {
            path.replace(&format!("{{{key}}}"), value)
        })
}

fn is_retryable_failure(error: &PlatformError) -> bool {
    matches!(
        error,
        PlatformError::UpstreamTimeout(_) | PlatformError::UpstreamTransport(_)
    )
}

fn upstream_failure_response(error: &PlatformError, config: &ProxyConfig) -> GatewayResponse {
    match error {
        PlatformError::UpstreamTimeout(_) => mip_error_response(
            504,
            "service_timeout",
            "Service timeout",
            None,
            &config.mip_version,
        ),
        _ => mip_error_response(
            503,
            "service_unavailable",
            "Service unavailable",
            None,
            &config.mip_version,
        ),
    }
}

#[cfg(test)]
mod tests {
    use std::{
        collections::BTreeSet,
        sync::atomic::{AtomicU32, Ordering},
    };

    use async_trait::async_trait;

    use super::*;
    use crate::{
        AuthenticationType, EndpointProtocol, HealthStatus, RouteMatchType, ServiceEndpoint,
        ServiceInstance,
    };

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        retryable_methods: Vec<HttpMethod>,
        non_retryable_methods: Vec<HttpMethod>,
        query_merge: QueryFixture,
        trusted_query: QueryFixture,
        trusted_headers: HeaderFixture,
        errors: Vec<ErrorFixture>,
        limits: LimitsFixture,
    }

    #[derive(Deserialize)]
    struct QueryFixture {
        incoming: BTreeMap<String, Vec<String>>,
        injected: BTreeMap<String, Vec<String>>,
        expected: BTreeMap<String, Vec<String>>,
    }

    #[derive(Deserialize)]
    struct HeaderFixture {
        incoming: BTreeMap<String, String>,
        identity: TrustedIdentityContext,
        expected_present: BTreeMap<String, String>,
        expected_absent: Vec<String>,
    }

    #[derive(Deserialize)]
    struct ErrorFixture {
        name: String,
        status: u16,
        body: Option<Value>,
        raw_body: Option<String>,
        expected_error: String,
        expected_description: String,
        passthrough: bool,
    }

    #[derive(Deserialize)]
    struct LimitsFixture {
        maximum_response_bytes: usize,
        default_timeout_ms: u64,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!(
            "../../../contracts/gateway-runtime-behavior.json"
        ))
        .expect("valid gateway runtime fixture")
    }

    fn response(case: &ErrorFixture) -> GatewayResponse {
        let body = case
            .body
            .as_ref()
            .map(|value| serde_json::to_vec(value).expect("body"))
            .or_else(|| {
                case.raw_body
                    .as_ref()
                    .map(|value| value.as_bytes().to_vec())
            });
        GatewayResponse {
            status_code: case.status,
            headers: BTreeMap::from([
                ("Content-Length".into(), "999".into()),
                ("X-Upstream".into(), "test".into()),
            ]),
            set_cookies: Vec::new(),
            body,
            response_time_ms: None,
            upstream_service: Some("test".into()),
        }
    }

    #[test]
    fn language_neutral_request_contract() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        for method in fixture.retryable_methods {
            assert!(retryable_method(method));
        }
        for method in fixture.non_retryable_methods {
            assert!(!retryable_method(method));
        }
        assert_eq!(
            merge_query(fixture.query_merge.incoming, &fixture.query_merge.injected),
            fixture.query_merge.expected
        );
        assert_eq!(
            trusted_query(
                fixture.trusted_query.incoming,
                &fixture.trusted_query.injected
            ),
            fixture.trusted_query.expected
        );
        let headers = trusted_headers(
            fixture.trusted_headers.incoming,
            &fixture.trusted_headers.identity,
            false,
        );
        for (name, expected) in fixture.trusted_headers.expected_present {
            assert_eq!(header(&headers, &name), Some(expected.as_str()));
        }
        for name in fixture.trusted_headers.expected_absent {
            assert!(header(&headers, &name).is_none());
        }
    }

    #[test]
    fn language_neutral_error_contract() {
        let config = ProxyConfig::default();
        for case in fixture().errors {
            let original = response(&case);
            let normalized = normalize_upstream_response(original.clone(), &config)
                .expect("normalized response");
            let body: Value =
                serde_json::from_slice(normalized.body.as_deref().expect("normalized body"))
                    .expect("JSON body");
            assert_eq!(body["error"], case.expected_error, "{}", case.name);
            assert_eq!(
                body["error_description"], case.expected_description,
                "{}",
                case.name
            );
            assert!(header(&normalized.headers, "content-length").is_none());
            if case.passthrough {
                assert_eq!(header(&normalized.headers, "x-upstream"), Some("test"));
                assert_eq!(
                    normalized.status_code, original.status_code,
                    "{}",
                    case.name
                );
                assert_eq!(normalized.body, original.body, "{}", case.name);
            } else {
                assert!(header(&normalized.headers, "x-upstream").is_none());
                assert!(
                    body["message_id"]
                        .as_str()
                        .is_some_and(|value| !value.is_empty()),
                    "{}",
                    case.name
                );
            }
        }
    }

    #[test]
    fn redirects_preserve_individual_session_cookies() {
        let response = GatewayResponse {
            status_code: 302,
            headers: BTreeMap::from([
                ("location".into(), "/console".into()),
                ("content-length".into(), "999".into()),
            ]),
            set_cookies: vec![
                "sessionId=synthetic; Path=/; Secure".into(),
                "marty_impersonation_handoff=; Max-Age=0; Path=/; Secure".into(),
            ],
            body: None,
            response_time_ms: None,
            upstream_service: Some("auth".into()),
        };
        let normalized = normalize_upstream_response(response, &ProxyConfig::default()).unwrap();
        assert_eq!(normalized.status_code, 302);
        assert_eq!(
            normalized.headers.get("location").map(String::as_str),
            Some("/console")
        );
        assert!(!normalized.headers.contains_key("content-length"));
        assert_eq!(normalized.set_cookies.len(), 2);
        assert!(normalized.set_cookies[0].starts_with("sessionId="));
        assert!(normalized.set_cookies[1].starts_with("marty_impersonation_handoff="));

        let prior_wire = r#"{"status_code":200,"headers":{},"body":null,"response_time_ms":null,"upstream_service":null}"#;
        let decoded: GatewayResponse = serde_json::from_str(prior_wire).unwrap();
        assert!(decoded.set_cookies.is_empty());
    }

    #[test]
    fn response_limits_fail_closed() {
        let fixture = fixture();
        let config = ProxyConfig {
            maximum_response_bytes: fixture.limits.maximum_response_bytes,
            default_timeout_ms: fixture.limits.default_timeout_ms,
            ..ProxyConfig::default()
        };
        let response = GatewayResponse {
            status_code: 200,
            headers: BTreeMap::new(),
            set_cookies: Vec::new(),
            body: Some(vec![0; config.maximum_response_bytes + 1]),
            response_time_ms: None,
            upstream_service: None,
        };
        let normalized = normalize_upstream_response(response, &config).expect("normalized");
        assert_eq!(normalized.status_code, 502);
        let body: Value =
            serde_json::from_slice(normalized.body.as_deref().expect("body")).expect("JSON");
        assert_eq!(body["error"], "response_too_large");
    }

    struct TestRegistry {
        instance: ServiceInstance,
    }

    #[async_trait]
    impl ServiceRegistry for TestRegistry {
        async fn register(&self, _instance: &ServiceInstance) -> Result<(), PlatformError> {
            Ok(())
        }

        async fn deregister(
            &self,
            _service: &str,
            _instance_id: &str,
        ) -> Result<bool, PlatformError> {
            Ok(false)
        }

        async fn discover(
            &self,
            query: &ServiceQuery,
        ) -> Result<Vec<ServiceInstance>, PlatformError> {
            if query.service_name == self.instance.service_name {
                Ok(vec![self.instance.clone()])
            } else {
                Ok(Vec::new())
            }
        }

        async fn heartbeat(
            &self,
            _service: &str,
            _instance_id: &str,
            _now_ms: u64,
        ) -> Result<(), PlatformError> {
            Ok(())
        }

        async fn healthy(&self) -> Result<bool, PlatformError> {
            Ok(true)
        }
    }

    struct TestUpstream {
        failures: u32,
        calls: AtomicU32,
    }

    #[async_trait]
    impl UpstreamClient for TestUpstream {
        async fn send(
            &self,
            _instance: &ServiceInstance,
            _request: GatewayRequest,
        ) -> Result<GatewayResponse, PlatformError> {
            let call = self.calls.fetch_add(1, Ordering::SeqCst);
            if call < self.failures {
                return Err(PlatformError::UpstreamTransport("connection reset".into()));
            }
            Ok(GatewayResponse {
                status_code: 200,
                headers: BTreeMap::new(),
                set_cookies: Vec::new(),
                body: Some(br#"{"ok":true}"#.to_vec()),
                response_time_ms: Some(1),
                upstream_service: Some("documents".into()),
            })
        }
    }

    fn test_proxy(method: HttpMethod, failures: u32) -> (GatewayProxy, Arc<TestUpstream>) {
        let mut instance = ServiceInstance::new(
            "documents",
            ServiceEndpoint {
                host: "127.0.0.1".into(),
                port: 8080,
                protocol: EndpointProtocol::Http,
                path: String::new(),
                verify_tls: true,
                connect_timeout_ms: 1_000,
                read_timeout_ms: 1_000,
            },
            0,
        )
        .expect("instance");
        instance.update_health(HealthStatus::Healthy, 0);
        let registry = Arc::new(TestRegistry { instance });
        let upstream = Arc::new(TestUpstream {
            failures,
            calls: AtomicU32::new(0),
        });
        let mut routes = RouteTable::default();
        routes
            .add(RouteConfig {
                name: "documents".into(),
                pattern: "/documents/{id}".into(),
                match_type: RouteMatchType::Template,
                upstream_service: "documents".into(),
                methods: BTreeSet::from([method]),
                host: None,
                required_headers: BTreeMap::new(),
                rewrite_path: Some("/v1/documents/{id}".into()),
                timeout_ms: 1_000,
                retries: 2,
                auth_required: true,
                authentication_type: AuthenticationType::Jwt,
                priority: 1,
                tags: BTreeSet::new(),
            })
            .expect("route");
        let proxy = GatewayProxy::new(
            routes,
            registry,
            upstream.clone(),
            ProxyConfig {
                retry_base_delay_ms: 1,
                retry_max_delay_ms: 1,
                ..ProxyConfig::default()
            },
        )
        .expect("proxy");
        (proxy, upstream)
    }

    #[tokio::test]
    async fn proxy_discovers_rewrites_and_retries_idempotent_requests() {
        let (proxy, upstream) = test_proxy(HttpMethod::Get, 2);
        let response = proxy
            .execute(
                GatewayRequest::new(HttpMethod::Get, "/documents/doc-1", 0),
                &TrustedIdentityContext::default(),
                &ProxyOverrides::default(),
            )
            .await
            .expect("response");
        assert_eq!(response.status_code, 200);
        assert_eq!(upstream.calls.load(Ordering::SeqCst), 3);
    }

    #[tokio::test]
    async fn proxy_does_not_retry_non_idempotent_requests() {
        let (proxy, upstream) = test_proxy(HttpMethod::Post, 1);
        let response = proxy
            .execute(
                GatewayRequest::new(HttpMethod::Post, "/documents/doc-1", 0),
                &TrustedIdentityContext::default(),
                &ProxyOverrides::default(),
            )
            .await
            .expect("fail-closed response");
        assert_eq!(response.status_code, 503);
        assert_eq!(upstream.calls.load(Ordering::SeqCst), 1);
    }
}
