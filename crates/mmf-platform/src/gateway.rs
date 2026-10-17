use std::collections::{BTreeMap, BTreeSet};

use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;

use crate::PlatformError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum HttpMethod {
    Get,
    Post,
    Put,
    Delete,
    Patch,
    Head,
    Options,
    Trace,
    Connect,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthenticationType {
    None,
    ApiKey,
    BearerToken,
    Jwt,
    OAuth2,
    BasicAuth,
    MutualTls,
    Custom,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RouteMatchType {
    Exact,
    Prefix,
    Regex,
    Wildcard,
    Template,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct GatewayRequest {
    pub method: HttpMethod,
    pub path: String,
    #[serde(default)]
    pub query: BTreeMap<String, Vec<String>>,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    pub body: Option<Vec<u8>>,
    pub client_ip: Option<String>,
    pub request_id: String,
    pub timestamp_ms: u64,
    #[serde(default)]
    pub route_params: BTreeMap<String, String>,
    #[serde(default)]
    pub context: BTreeMap<String, Value>,
}

impl GatewayRequest {
    #[must_use]
    pub fn new(method: HttpMethod, path: impl Into<String>, timestamp_ms: u64) -> Self {
        Self {
            method,
            path: path.into(),
            query: BTreeMap::new(),
            headers: BTreeMap::new(),
            body: None,
            client_ip: None,
            request_id: Uuid::new_v4().to_string(),
            timestamp_ms,
            route_params: BTreeMap::new(),
            context: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn header(&self, name: &str) -> Option<&str> {
        self.headers
            .iter()
            .find(|(key, _)| key.eq_ignore_ascii_case(name))
            .map(|(_, value)| value.as_str())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct GatewayResponse {
    pub status_code: u16,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    /// Separate Set-Cookie fields; HTTP forbids combining them into one value.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub set_cookies: Vec<String>,
    pub body: Option<Vec<u8>>,
    pub response_time_ms: Option<u64>,
    pub upstream_service: Option<String>,
}

impl GatewayResponse {
    pub fn set_json(&mut self, value: &Value) -> Result<(), PlatformError> {
        let body = serde_json::to_vec(value)
            .map_err(|error| PlatformError::Operation(error.to_string()))?;
        self.headers
            .insert("Content-Type".into(), "application/json".into());
        self.headers
            .insert("Content-Length".into(), body.len().to_string());
        self.body = Some(body);
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RouteConfig {
    pub name: String,
    pub pattern: String,
    pub match_type: RouteMatchType,
    pub upstream_service: String,
    #[serde(default)]
    pub methods: BTreeSet<HttpMethod>,
    pub host: Option<String>,
    #[serde(default)]
    pub required_headers: BTreeMap<String, String>,
    pub rewrite_path: Option<String>,
    pub timeout_ms: u64,
    pub retries: u32,
    pub auth_required: bool,
    pub authentication_type: AuthenticationType,
    pub priority: i32,
    #[serde(default)]
    pub tags: BTreeSet<String>,
}

impl RouteConfig {
    pub fn validate(&self) -> Result<(), PlatformError> {
        if self.name.trim().is_empty()
            || self.pattern.trim().is_empty()
            || self.upstream_service.trim().is_empty()
        {
            return Err(PlatformError::InvalidConfiguration(
                "route name, pattern, and upstream service are required".into(),
            ));
        }
        if self.methods.is_empty() || self.timeout_ms == 0 {
            return Err(PlatformError::InvalidConfiguration(
                "route methods and a nonzero timeout are required".into(),
            ));
        }
        if self.auth_required && self.authentication_type == AuthenticationType::None {
            return Err(PlatformError::InvalidConfiguration(
                "authenticated routes require an authentication type".into(),
            ));
        }
        if self.match_type == RouteMatchType::Regex {
            Regex::new(&self.pattern)
                .map_err(|error| PlatformError::InvalidConfiguration(error.to_string()))?;
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RouteMatch {
    pub route: RouteConfig,
    pub params: BTreeMap<String, String>,
}

#[derive(Default)]
pub struct RouteTable {
    routes: Vec<RouteConfig>,
}

impl RouteTable {
    pub fn add(&mut self, route: RouteConfig) -> Result<(), PlatformError> {
        route.validate()?;
        self.routes.retain(|item| item.name != route.name);
        self.routes.push(route);
        self.routes.sort_by(|left, right| {
            right
                .priority
                .cmp(&left.priority)
                .then(left.name.cmp(&right.name))
        });
        Ok(())
    }

    pub fn remove(&mut self, name: &str) -> bool {
        let before = self.routes.len();
        self.routes.retain(|route| route.name != name);
        before != self.routes.len()
    }

    pub fn find(&self, request: &GatewayRequest) -> Result<RouteMatch, PlatformError> {
        self.routes
            .iter()
            .filter(|route| route.methods.contains(&request.method))
            .filter(|route| {
                route.host.as_ref().is_none_or(|host| {
                    request
                        .header("host")
                        .is_some_and(|actual| actual.eq_ignore_ascii_case(host))
                })
            })
            .filter(|route| {
                route
                    .required_headers
                    .iter()
                    .all(|(key, value)| request.header(key).is_some_and(|actual| actual == value))
            })
            .find_map(|route| {
                match_path(route.match_type, &route.pattern, &request.path)
                    .ok()
                    .flatten()
                    .map(|params| RouteMatch {
                        route: route.clone(),
                        params,
                    })
            })
            .ok_or_else(|| PlatformError::RouteNotFound {
                method: format!("{:?}", request.method).to_ascii_uppercase(),
                path: request.path.clone(),
            })
    }

    #[must_use]
    pub fn routes(&self) -> &[RouteConfig] {
        &self.routes
    }
}

pub fn match_path(
    match_type: RouteMatchType,
    pattern: &str,
    path: &str,
) -> Result<Option<BTreeMap<String, String>>, PlatformError> {
    match match_type {
        RouteMatchType::Exact => Ok((pattern == path).then(BTreeMap::new)),
        RouteMatchType::Prefix => Ok(path.starts_with(pattern).then(|| {
            let remainder = path[pattern.len()..].trim_start_matches('/');
            if remainder.is_empty() {
                BTreeMap::new()
            } else {
                BTreeMap::from([("*".into(), remainder.into())])
            }
        })),
        RouteMatchType::Wildcard => Ok(wildcard_matches(pattern, path)
            .then(|| BTreeMap::from([("wildcard".into(), path.into())]))),
        RouteMatchType::Template => template_match(pattern, path),
        RouteMatchType::Regex => {
            let expression = Regex::new(pattern)
                .map_err(|error| PlatformError::InvalidConfiguration(error.to_string()))?;
            let Some(captures) = expression.captures(path) else {
                return Ok(None);
            };
            let params = expression
                .capture_names()
                .flatten()
                .filter_map(|name| {
                    captures
                        .name(name)
                        .map(|value| (name.into(), value.as_str().into()))
                })
                .collect();
            Ok(Some(params))
        }
    }
}

fn template_match(
    pattern: &str,
    path: &str,
) -> Result<Option<BTreeMap<String, String>>, PlatformError> {
    let pattern_parts: Vec<_> = pattern.trim_matches('/').split('/').collect();
    let path_parts: Vec<_> = path.trim_matches('/').split('/').collect();
    let mut params = BTreeMap::new();
    for (index, expected) in pattern_parts.iter().enumerate() {
        if expected.starts_with('{') && expected.ends_with('}') {
            let parameter = &expected[1..expected.len() - 1];
            if let Some(name) = parameter.strip_suffix(":path") {
                if name.is_empty() || index + 1 != pattern_parts.len() {
                    return Err(PlatformError::InvalidConfiguration(
                        "catch-all template parameters must be named and terminal".into(),
                    ));
                }
                params.insert(
                    name.into(),
                    path_parts.get(index..).unwrap_or_default().join("/"),
                );
                return Ok(Some(params));
            }
            let name = parameter;
            if name.is_empty() {
                return Err(PlatformError::InvalidConfiguration(
                    "template parameter name must not be empty".into(),
                ));
            }
            if name.contains(':') {
                return Err(PlatformError::InvalidConfiguration(
                    "unsupported template parameter converter".into(),
                ));
            }
            let Some(actual) = path_parts.get(index) else {
                return Ok(None);
            };
            params.insert(name.into(), (*actual).into());
        } else if path_parts
            .get(index)
            .is_none_or(|actual| expected != actual)
        {
            return Ok(None);
        }
    }
    Ok((pattern_parts.len() == path_parts.len()).then_some(params))
}

pub use mmf_core::wildcard_matches;
