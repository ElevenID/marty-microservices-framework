//! OAuth 2.0 authorization, client, token, and store behavior.

use std::collections::{BTreeMap, BTreeSet};

use async_trait::async_trait;
use base64::{Engine, engine::general_purpose::URL_SAFE_NO_PAD};
use mmf_core::constant_time_secret_eq;
use rand::RngExt as _;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::SecurityError;
use crate::uri::{percent_encode_component, valid_native_redirect_uri, valid_redirect_uri};

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum OAuth2Flow {
    AuthorizationCode,
    ClientCredentials,
    Implicit,
    #[serde(rename = "password")]
    ResourceOwnerPassword,
    DeviceCode,
    RefreshToken,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
pub enum OAuth2ResponseType {
    #[serde(rename = "code")]
    Code,
    #[serde(rename = "token")]
    Token,
    #[serde(rename = "id_token")]
    IdToken,
    #[serde(rename = "code id_token")]
    CodeIdToken,
    #[serde(rename = "code token")]
    CodeToken,
    #[serde(rename = "code token id_token")]
    CodeTokenIdToken,
}

impl OAuth2ResponseType {
    #[must_use]
    pub const fn requires_openid(self) -> bool {
        matches!(
            self,
            Self::IdToken | Self::CodeIdToken | Self::CodeTokenIdToken
        )
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
pub enum OAuth2Scope {
    #[serde(rename = "read")]
    Read,
    #[serde(rename = "write")]
    Write,
    #[serde(rename = "openid")]
    Openid,
    #[serde(rename = "profile")]
    Profile,
    #[serde(rename = "email")]
    Email,
    #[serde(rename = "address")]
    Address,
    #[serde(rename = "phone")]
    Phone,
    #[serde(rename = "offline_access")]
    OfflineAccess,
    #[serde(rename = "user:read")]
    UserRead,
    #[serde(rename = "user:write")]
    UserWrite,
    #[serde(rename = "admin")]
    Admin,
}

impl std::fmt::Display for OAuth2Scope {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(match self {
            Self::Read => "read",
            Self::Write => "write",
            Self::Openid => "openid",
            Self::Profile => "profile",
            Self::Email => "email",
            Self::Address => "address",
            Self::Phone => "phone",
            Self::OfflineAccess => "offline_access",
            Self::UserRead => "user:read",
            Self::UserWrite => "user:write",
            Self::Admin => "admin",
        })
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
pub enum OAuth2GrantType {
    #[serde(rename = "authorization_code")]
    AuthorizationCode,
    #[serde(rename = "client_credentials")]
    ClientCredentials,
    #[serde(rename = "refresh_token")]
    RefreshToken,
    #[serde(rename = "password")]
    Password,
    #[serde(rename = "implicit")]
    Implicit,
    #[serde(rename = "device_code")]
    DeviceCode,
    #[serde(rename = "urn:ietf:params:oauth:grant-type:jwt-bearer")]
    JwtBearer,
    #[serde(rename = "urn:ietf:params:oauth:grant-type:token-exchange")]
    TokenExchange,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum OAuth2ClientType {
    Public,
    Confidential,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum OAuth2ApplicationType {
    Web,
    Native,
    Spa,
    Service,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum OAuth2TokenEndpointAuthMethod {
    ClientSecretPost,
    ClientSecretBasic,
    ClientSecretJwt,
    PrivateKeyJwt,
    None,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OAuth2Client {
    pub client_id: String,
    #[serde(default, skip_serializing)]
    secret_digest: Option<Vec<u8>>,
    pub client_secret_reference: Option<String>,
    pub client_name: String,
    pub client_type: OAuth2ClientType,
    pub application_type: OAuth2ApplicationType,
    #[serde(default)]
    pub redirect_uris: BTreeSet<String>,
    #[serde(default)]
    pub allowed_scopes: BTreeSet<String>,
    #[serde(default)]
    pub allowed_grant_types: BTreeSet<OAuth2GrantType>,
    #[serde(default)]
    pub allowed_response_types: BTreeSet<OAuth2ResponseType>,
    pub token_endpoint_auth_method: OAuth2TokenEndpointAuthMethod,
    pub client_uri: Option<String>,
    pub logo_uri: Option<String>,
    pub tos_uri: Option<String>,
    pub policy_uri: Option<String>,
    pub require_pkce: bool,
    pub allow_refresh_tokens: bool,
    pub access_token_lifetime_ms: u64,
    pub refresh_token_lifetime_ms: u64,
    pub authorization_code_lifetime_ms: u64,
    pub created_at_ms: u64,
    pub updated_at_ms: u64,
    pub enabled: bool,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct IssuedOAuth2Client {
    pub client: OAuth2Client,
    pub client_secret: Option<String>,
}

impl OAuth2Client {
    pub fn confidential(
        client_id: impl Into<String>,
        client_name: impl Into<String>,
        secret: &str,
        secret_reference: Option<String>,
        redirect_uris: BTreeSet<String>,
        now_ms: u64,
    ) -> Result<Self, SecurityError> {
        if secret.is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "confidential OAuth2 clients require a secret".into(),
            ));
        }
        let mut client = Self::defaults(
            client_id,
            client_name,
            OAuth2ClientType::Confidential,
            OAuth2ApplicationType::Web,
            now_ms,
        );
        client.secret_digest = Some(hash_secret(secret));
        client.client_secret_reference = secret_reference;
        client.redirect_uris = redirect_uris;
        client.validate()?;
        Ok(client)
    }

    pub fn public(
        client_id: impl Into<String>,
        client_name: impl Into<String>,
        application_type: OAuth2ApplicationType,
        redirect_uris: BTreeSet<String>,
        now_ms: u64,
    ) -> Result<Self, SecurityError> {
        let mut client = Self::defaults(
            client_id,
            client_name,
            OAuth2ClientType::Public,
            application_type,
            now_ms,
        );
        client.token_endpoint_auth_method = OAuth2TokenEndpointAuthMethod::None;
        client.require_pkce = true;
        client.redirect_uris = redirect_uris;
        client.validate()?;
        Ok(client)
    }

    pub fn web(
        client_name: impl Into<String>,
        redirect_uris: BTreeSet<String>,
        allowed_scopes: BTreeSet<String>,
        now_ms: u64,
    ) -> Result<IssuedOAuth2Client, SecurityError> {
        let secret = generate_client_secret();
        let mut client = Self::confidential(
            generate_client_id(),
            client_name,
            &secret,
            None,
            redirect_uris,
            now_ms,
        )?;
        client.allowed_scopes = default_oidc_scopes(allowed_scopes);
        client.validate()?;
        Ok(IssuedOAuth2Client {
            client,
            client_secret: Some(secret),
        })
    }

    pub fn spa(
        client_name: impl Into<String>,
        redirect_uris: BTreeSet<String>,
        allowed_scopes: BTreeSet<String>,
        now_ms: u64,
    ) -> Result<IssuedOAuth2Client, SecurityError> {
        Self::public_application(
            client_name,
            OAuth2ApplicationType::Spa,
            redirect_uris,
            allowed_scopes,
            now_ms,
        )
    }

    pub fn native(
        client_name: impl Into<String>,
        redirect_uris: BTreeSet<String>,
        allowed_scopes: BTreeSet<String>,
        now_ms: u64,
    ) -> Result<IssuedOAuth2Client, SecurityError> {
        Self::public_application(
            client_name,
            OAuth2ApplicationType::Native,
            redirect_uris,
            allowed_scopes,
            now_ms,
        )
    }

    pub fn service(
        client_name: impl Into<String>,
        allowed_scopes: BTreeSet<String>,
        now_ms: u64,
    ) -> Result<IssuedOAuth2Client, SecurityError> {
        let secret = generate_client_secret();
        let mut client = Self::defaults(
            generate_client_id(),
            client_name,
            OAuth2ClientType::Confidential,
            OAuth2ApplicationType::Service,
            now_ms,
        );
        client.secret_digest = Some(hash_secret(&secret));
        client.allowed_scopes = if allowed_scopes.is_empty() {
            BTreeSet::from(["read".into(), "write".into()])
        } else {
            allowed_scopes
        };
        client.allowed_grant_types = BTreeSet::from([OAuth2GrantType::ClientCredentials]);
        client.allowed_response_types.clear();
        client.allow_refresh_tokens = false;
        client.validate()?;
        Ok(IssuedOAuth2Client {
            client,
            client_secret: Some(secret),
        })
    }

    fn public_application(
        client_name: impl Into<String>,
        application_type: OAuth2ApplicationType,
        redirect_uris: BTreeSet<String>,
        allowed_scopes: BTreeSet<String>,
        now_ms: u64,
    ) -> Result<IssuedOAuth2Client, SecurityError> {
        let mut client = Self::public(
            generate_client_id(),
            client_name,
            application_type,
            redirect_uris,
            now_ms,
        )?;
        client.allowed_scopes = default_oidc_scopes(allowed_scopes);
        client.validate()?;
        Ok(IssuedOAuth2Client {
            client,
            client_secret: None,
        })
    }

    fn defaults(
        client_id: impl Into<String>,
        client_name: impl Into<String>,
        client_type: OAuth2ClientType,
        application_type: OAuth2ApplicationType,
        now_ms: u64,
    ) -> Self {
        Self {
            client_id: client_id.into(),
            secret_digest: None,
            client_secret_reference: None,
            client_name: client_name.into(),
            client_type,
            application_type,
            redirect_uris: BTreeSet::new(),
            allowed_scopes: BTreeSet::new(),
            allowed_grant_types: BTreeSet::from([OAuth2GrantType::AuthorizationCode]),
            allowed_response_types: BTreeSet::from([OAuth2ResponseType::Code]),
            token_endpoint_auth_method: OAuth2TokenEndpointAuthMethod::ClientSecretBasic,
            client_uri: None,
            logo_uri: None,
            tos_uri: None,
            policy_uri: None,
            require_pkce: false,
            allow_refresh_tokens: true,
            access_token_lifetime_ms: 3_600_000,
            refresh_token_lifetime_ms: 2_592_000_000,
            authorization_code_lifetime_ms: 600_000,
            created_at_ms: now_ms,
            updated_at_ms: now_ms,
            enabled: true,
            metadata: BTreeMap::new(),
        }
    }

    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.client_id.trim().is_empty() || self.client_name.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "OAuth2 client id and name are required".into(),
            ));
        }
        if self.client_type == OAuth2ClientType::Confidential && self.secret_digest.is_none() {
            return Err(SecurityError::ProviderUnavailable(
                "confidential OAuth2 client secret".into(),
            ));
        }
        if self.client_type == OAuth2ClientType::Public && self.secret_digest.is_some() {
            return Err(SecurityError::InvalidConfiguration(
                "public OAuth2 clients cannot store a secret".into(),
            ));
        }
        if self
            .allowed_grant_types
            .contains(&OAuth2GrantType::AuthorizationCode)
            && self.redirect_uris.is_empty()
        {
            return Err(SecurityError::InvalidConfiguration(
                "authorization-code clients require a redirect URI".into(),
            ));
        }
        if self.redirect_uris.iter().any(|uri| {
            if self.application_type == OAuth2ApplicationType::Native {
                !valid_native_redirect_uri(uri)
            } else {
                !valid_redirect_uri(uri)
            }
        }) {
            return Err(SecurityError::InvalidConfiguration(
                "OAuth2 redirect URIs require HTTPS except loopback clients".into(),
            ));
        }
        if matches!(
            self.application_type,
            OAuth2ApplicationType::Spa | OAuth2ApplicationType::Native
        ) && (self.client_type != OAuth2ClientType::Public || !self.require_pkce)
        {
            return Err(SecurityError::InvalidConfiguration(
                "SPA clients must be public and require PKCE".into(),
            ));
        }
        if self.access_token_lifetime_ms == 0
            || self.refresh_token_lifetime_ms == 0
            || self.authorization_code_lifetime_ms == 0
        {
            return Err(SecurityError::InvalidConfiguration(
                "OAuth2 token lifetimes must be positive".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn verify_client_secret(&self, secret: &str) -> bool {
        if self.client_type == OAuth2ClientType::Public {
            return true;
        }
        self.secret_digest.as_deref().is_some_and(|expected| {
            let candidate = hash_secret(secret);
            // Restored clients can carry a malformed digest. Preserve the
            // previous length rejection before the shared comparator scans it.
            expected.len() == candidate.len() && constant_time_secret_eq(expected, &candidate)
        })
    }

    #[must_use]
    pub fn allows_redirect_uri(&self, uri: &str) -> bool {
        self.enabled && self.redirect_uris.contains(uri)
    }

    #[must_use]
    pub fn allows_scopes(&self, scopes: &BTreeSet<String>) -> bool {
        self.enabled && scopes.is_subset(&self.allowed_scopes)
    }

    #[must_use]
    pub fn allows_scope(&self, scope: &str) -> bool {
        self.enabled && self.allowed_scopes.contains(scope)
    }

    #[must_use]
    pub const fn can_use_pkce(&self) -> bool {
        true
    }

    #[must_use]
    pub const fn requires_pkce(&self) -> bool {
        self.require_pkce
    }

    #[must_use]
    pub const fn can_use_refresh_tokens(&self) -> bool {
        self.allow_refresh_tokens
    }

    #[must_use]
    pub fn allows_grant_type(&self, grant_type: OAuth2GrantType) -> bool {
        self.enabled && self.allowed_grant_types.contains(&grant_type)
    }

    #[must_use]
    pub fn allows_response_type(&self, response_type: OAuth2ResponseType) -> bool {
        self.enabled && self.allowed_response_types.contains(&response_type)
    }

    pub fn replace_redirect_uris(
        &mut self,
        redirect_uris: BTreeSet<String>,
        now_ms: u64,
    ) -> Result<(), SecurityError> {
        let previous = std::mem::replace(&mut self.redirect_uris, redirect_uris);
        if let Err(error) = self.validate() {
            self.redirect_uris = previous;
            return Err(error);
        }
        self.updated_at_ms = now_ms;
        Ok(())
    }

    pub fn replace_scopes(&mut self, scopes: BTreeSet<String>, now_ms: u64) {
        self.allowed_scopes = scopes;
        self.updated_at_ms = now_ms;
    }

    pub fn rotate_secret(&mut self, secret: &str, now_ms: u64) -> Result<(), SecurityError> {
        if self.client_type != OAuth2ClientType::Confidential || secret.is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "only confidential clients can rotate non-empty secrets".into(),
            ));
        }
        self.secret_digest = Some(hash_secret(secret));
        self.updated_at_ms = now_ms;
        Ok(())
    }

    pub fn rotate_generated_secret(&mut self, now_ms: u64) -> Result<String, SecurityError> {
        let secret = generate_client_secret();
        self.rotate_secret(&secret, now_ms)?;
        Ok(secret)
    }

    pub fn deactivate(&mut self, now_ms: u64) {
        self.enabled = false;
        self.updated_at_ms = now_ms;
    }

    pub fn activate(&mut self, now_ms: u64) {
        self.enabled = true;
        self.updated_at_ms = now_ms;
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OAuth2ClientRegistration {
    pub client_name: String,
    pub application_type: OAuth2ApplicationType,
    #[serde(default)]
    pub redirect_uris: BTreeSet<String>,
    #[serde(default)]
    pub allowed_scopes: BTreeSet<String>,
    pub client_uri: Option<String>,
    pub logo_uri: Option<String>,
    pub tos_uri: Option<String>,
    pub policy_uri: Option<String>,
    pub require_pkce: bool,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl OAuth2ClientRegistration {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.client_name.trim().is_empty()
            || (self.application_type != OAuth2ApplicationType::Service
                && self.redirect_uris.is_empty())
        {
            return Err(SecurityError::InvalidConfiguration(
                "invalid OAuth2 client registration".into(),
            ));
        }
        if self.redirect_uris.iter().any(|uri| {
            if self.application_type == OAuth2ApplicationType::Native {
                !valid_native_redirect_uri(uri)
            } else {
                !valid_redirect_uri(uri)
            }
        }) {
            return Err(SecurityError::InvalidConfiguration(
                "OAuth2 redirect URIs require HTTPS except loopback clients".into(),
            ));
        }
        Ok(())
    }

    pub fn register(&self, now_ms: u64) -> Result<IssuedOAuth2Client, SecurityError> {
        self.validate()?;
        let mut issued = match self.application_type {
            OAuth2ApplicationType::Web => OAuth2Client::web(
                &self.client_name,
                self.redirect_uris.clone(),
                self.allowed_scopes.clone(),
                now_ms,
            )?,
            OAuth2ApplicationType::Spa => OAuth2Client::spa(
                &self.client_name,
                self.redirect_uris.clone(),
                self.allowed_scopes.clone(),
                now_ms,
            )?,
            OAuth2ApplicationType::Native => OAuth2Client::native(
                &self.client_name,
                self.redirect_uris.clone(),
                self.allowed_scopes.clone(),
                now_ms,
            )?,
            OAuth2ApplicationType::Service => {
                OAuth2Client::service(&self.client_name, self.allowed_scopes.clone(), now_ms)?
            }
        };
        issued.client.client_uri.clone_from(&self.client_uri);
        issued.client.logo_uri.clone_from(&self.logo_uri);
        issued.client.tos_uri.clone_from(&self.tos_uri);
        issued.client.policy_uri.clone_from(&self.policy_uri);
        issued.client.metadata.clone_from(&self.metadata);
        issued.client.require_pkce |= self.require_pkce;
        issued.client.validate()?;
        Ok(issued)
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OAuth2AuthorizationRequest {
    pub client_id: String,
    pub redirect_uri: String,
    pub response_type: OAuth2ResponseType,
    #[serde(default)]
    pub scopes: BTreeSet<String>,
    pub state: Option<String>,
    pub code_challenge: Option<String>,
    pub code_challenge_method: Option<PkceMethod>,
    pub nonce: Option<String>,
    pub request_id: String,
    pub created_at_ms: u64,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl OAuth2AuthorizationRequest {
    pub fn from_query_params(
        params: &BTreeMap<String, String>,
        now_ms: u64,
    ) -> Result<Self, SecurityError> {
        let response_type =
            parse_response_type(params.get("response_type").map_or("code", String::as_str))?;
        let scopes = params
            .get("scope")
            .map_or("", String::as_str)
            .split_whitespace()
            .map(str::to_owned)
            .collect();
        let code_challenge_method = params
            .get("code_challenge_method")
            .map(|value| match value.as_str() {
                "plain" => Ok(PkceMethod::Plain),
                "S256" => Ok(PkceMethod::S256),
                _ => Err(SecurityError::InvalidConfiguration(
                    "unsupported PKCE challenge method".into(),
                )),
            })
            .transpose()?;
        let request = Self {
            client_id: required_param(params, "client_id")?.to_owned(),
            redirect_uri: required_param(params, "redirect_uri")?.to_owned(),
            response_type,
            scopes,
            state: params.get("state").cloned(),
            code_challenge: params.get("code_challenge").cloned(),
            code_challenge_method,
            nonce: params.get("nonce").cloned(),
            request_id: Uuid::new_v4().to_string(),
            created_at_ms: now_ms,
            metadata: BTreeMap::from([(
                "original_params".into(),
                serde_json::to_value(params).unwrap_or(Value::Null),
            )]),
        };
        request.validate()?;
        Ok(request)
    }

    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.client_id.trim().is_empty()
            || !valid_native_redirect_uri(&self.redirect_uri)
            || self.request_id.trim().is_empty()
        {
            return Err(SecurityError::InvalidConfiguration(
                "invalid OAuth2 authorization request".into(),
            ));
        }
        if self.code_challenge.is_some() != self.code_challenge_method.is_some() {
            return Err(SecurityError::InvalidConfiguration(
                "PKCE challenge and method must be supplied together".into(),
            ));
        }
        if self
            .code_challenge
            .as_deref()
            .is_some_and(|challenge| !valid_pkce_value(challenge))
        {
            return Err(SecurityError::InvalidConfiguration(
                "PKCE challenge must contain 43 to 128 unreserved characters".into(),
            ));
        }
        if self.response_type.requires_openid() && !self.scopes.contains("openid") {
            return Err(SecurityError::InvalidConfiguration(
                "OIDC response types require the openid scope".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn has_scope(&self, scope: &str) -> bool {
        self.scopes.contains(scope)
    }

    #[must_use]
    pub const fn is_pkce_request(&self) -> bool {
        self.code_challenge.is_some()
    }

    #[must_use]
    pub fn is_oidc_request(&self) -> bool {
        self.scopes.contains("openid")
    }

    #[must_use]
    pub fn scope_string(&self) -> String {
        self.scopes.iter().cloned().collect::<Vec<_>>().join(" ")
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub enum PkceMethod {
    #[serde(rename = "plain")]
    Plain,
    #[serde(rename = "S256")]
    S256,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct AuthorizationCode {
    pub code_id: String,
    pub code: String,
    pub client_id: String,
    pub user_id: String,
    pub redirect_uri: String,
    pub scopes: BTreeSet<String>,
    pub state: Option<String>,
    pub code_challenge: Option<String>,
    pub code_challenge_method: Option<PkceMethod>,
    pub nonce: Option<String>,
    pub created_at_ms: u64,
    pub expires_at_ms: u64,
    pub consumed_at_ms: Option<u64>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl AuthorizationCode {
    pub fn new(
        request: &OAuth2AuthorizationRequest,
        user_id: impl Into<String>,
        lifetime_ms: u64,
    ) -> Result<Self, SecurityError> {
        request.validate()?;
        let user_id = user_id.into();
        if user_id.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "authorization code user id is required".into(),
            ));
        }
        if lifetime_ms == 0 {
            return Err(SecurityError::InvalidConfiguration(
                "authorization code lifetime must be positive".into(),
            ));
        }
        let mut metadata = request.metadata.clone();
        metadata.insert(
            "request_id".into(),
            Value::String(request.request_id.clone()),
        );
        Ok(Self {
            code_id: Uuid::new_v4().to_string(),
            code: random_token(32),
            client_id: request.client_id.clone(),
            user_id,
            redirect_uri: request.redirect_uri.clone(),
            scopes: request.scopes.clone(),
            state: request.state.clone(),
            code_challenge: request.code_challenge.clone(),
            code_challenge_method: request.code_challenge_method,
            nonce: request.nonce.clone(),
            created_at_ms: request.created_at_ms,
            expires_at_ms: request.created_at_ms.saturating_add(lifetime_ms),
            consumed_at_ms: None,
            metadata,
        })
    }

    #[must_use]
    pub const fn is_expired_at(&self, now_ms: u64) -> bool {
        now_ms >= self.expires_at_ms
    }

    #[must_use]
    pub const fn can_be_used_at(&self, now_ms: u64) -> bool {
        self.consumed_at_ms.is_none() && !self.is_expired_at(now_ms)
    }

    pub fn consume(
        &mut self,
        client_id: &str,
        redirect_uri: &str,
        verifier: Option<&str>,
        now_ms: u64,
    ) -> Result<(), SecurityError> {
        if !self.can_be_used_at(now_ms) {
            return Err(SecurityError::Unauthorized(
                "authorization code is expired or already consumed".into(),
            ));
        }
        if self.client_id != client_id || self.redirect_uri != redirect_uri {
            return Err(SecurityError::Unauthorized(
                "authorization code binding mismatch".into(),
            ));
        }
        if !verify_pkce(
            self.code_challenge.as_deref(),
            self.code_challenge_method,
            verifier,
        ) {
            return Err(SecurityError::Unauthorized(
                "authorization code PKCE verification failed".into(),
            ));
        }
        self.consumed_at_ms = Some(now_ms);
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OAuth2AuthorizationResponse {
    pub redirect_uri: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub code: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub access_token: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub token_type: Option<OAuth2TokenType>,
    #[serde(rename = "expires_in", skip_serializing_if = "Option::is_none")]
    pub expires_in_seconds: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub state: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_uri: Option<String>,
}

impl OAuth2AuthorizationResponse {
    #[must_use]
    pub fn success(
        redirect_uri: impl Into<String>,
        code: impl Into<String>,
        state: Option<String>,
    ) -> Self {
        Self {
            redirect_uri: redirect_uri.into(),
            code: Some(code.into()),
            access_token: None,
            token_type: None,
            expires_in_seconds: None,
            state,
            error: None,
            error_description: None,
            error_uri: None,
        }
    }

    #[must_use]
    pub fn failure(
        redirect_uri: impl Into<String>,
        error: impl Into<String>,
        error_description: Option<String>,
        error_uri: Option<String>,
        state: Option<String>,
    ) -> Self {
        Self {
            redirect_uri: redirect_uri.into(),
            code: None,
            access_token: None,
            token_type: None,
            expires_in_seconds: None,
            state,
            error: Some(error.into()),
            error_description,
            error_uri,
        }
    }

    #[must_use]
    pub fn is_success(&self) -> bool {
        self.error.is_none() && (self.code.is_some() || self.access_token.is_some())
    }

    pub fn redirect_url(&self) -> Result<String, SecurityError> {
        if !valid_native_redirect_uri(&self.redirect_uri) {
            return Err(SecurityError::InvalidConfiguration(
                "invalid OAuth2 response redirect URI".into(),
            ));
        }
        let mut params = Vec::new();
        for (key, value) in [
            ("code", self.code.as_deref()),
            ("access_token", self.access_token.as_deref()),
            ("state", self.state.as_deref()),
            ("error", self.error.as_deref()),
            ("error_description", self.error_description.as_deref()),
            ("error_uri", self.error_uri.as_deref()),
        ] {
            if let Some(value) = value {
                params.push(format!(
                    "{}={}",
                    percent_encode_component(key),
                    percent_encode_component(value)
                ));
            }
        }
        if let Some(token_type) = self.token_type {
            params.push(format!("token_type={token_type}"));
        }
        if let Some(expires) = self.expires_in_seconds {
            params.push(format!("expires_in={expires}"));
        }
        if params.is_empty() {
            return Ok(self.redirect_uri.clone());
        }
        let separator = if self.redirect_uri.contains('?') {
            '&'
        } else {
            '?'
        };
        Ok(format!(
            "{}{separator}{}",
            self.redirect_uri,
            params.join("&")
        ))
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub enum OAuth2TokenType {
    #[serde(rename = "Bearer")]
    Bearer,
    #[serde(rename = "MAC")]
    Mac,
}

impl std::fmt::Display for OAuth2TokenType {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(match self {
            Self::Bearer => "Bearer",
            Self::Mac => "MAC",
        })
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OAuth2AccessToken {
    pub token_id: String,
    #[serde(skip_serializing)]
    pub access_token: String,
    pub token_type: OAuth2TokenType,
    pub client_id: String,
    pub user_id: Option<String>,
    #[serde(default)]
    pub scopes: BTreeSet<String>,
    pub expires_at_ms: u64,
    pub created_at_ms: u64,
    pub revoked_at_ms: Option<u64>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl OAuth2AccessToken {
    #[must_use]
    pub fn issue(
        client_id: impl Into<String>,
        user_id: Option<String>,
        scopes: BTreeSet<String>,
        now_ms: u64,
        lifetime_ms: u64,
    ) -> Self {
        Self {
            token_id: Uuid::new_v4().to_string(),
            access_token: random_token(32),
            token_type: OAuth2TokenType::Bearer,
            client_id: client_id.into(),
            user_id,
            scopes,
            expires_at_ms: now_ms.saturating_add(lifetime_ms),
            created_at_ms: now_ms,
            revoked_at_ms: None,
            metadata: BTreeMap::new(),
        }
    }

    #[must_use]
    pub const fn is_active_at(&self, now_ms: u64) -> bool {
        self.revoked_at_ms.is_none() && now_ms < self.expires_at_ms
    }

    #[must_use]
    pub const fn is_expired_at(&self, now_ms: u64) -> bool {
        now_ms >= self.expires_at_ms
    }

    #[must_use]
    pub const fn is_revoked(&self) -> bool {
        self.revoked_at_ms.is_some()
    }

    #[must_use]
    pub fn has_scope(&self, scope: &str) -> bool {
        self.scopes.contains(scope)
    }

    #[must_use]
    pub fn has_any_scopes(&self, scopes: &BTreeSet<String>) -> bool {
        !self.scopes.is_disjoint(scopes)
    }

    #[must_use]
    pub fn has_all_scopes(&self, scopes: &BTreeSet<String>) -> bool {
        scopes.is_subset(&self.scopes)
    }

    #[must_use]
    pub fn scope_string(&self) -> String {
        self.scopes.iter().cloned().collect::<Vec<_>>().join(" ")
    }

    #[must_use]
    pub fn time_to_expiry_ms(&self, now_ms: u64) -> u64 {
        self.expires_at_ms.saturating_sub(now_ms)
    }

    #[must_use]
    pub fn expires_in_seconds(&self, now_ms: u64) -> u64 {
        self.time_to_expiry_ms(now_ms) / 1_000
    }

    pub fn revoke(&mut self, now_ms: u64) -> bool {
        if self.revoked_at_ms.is_some() {
            false
        } else {
            self.revoked_at_ms = Some(now_ms);
            true
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OAuth2RefreshToken {
    pub token_id: String,
    #[serde(skip_serializing)]
    pub refresh_token: String,
    pub access_token_id: String,
    pub client_id: String,
    pub user_id: Option<String>,
    #[serde(default)]
    pub scopes: BTreeSet<String>,
    pub expires_at_ms: u64,
    pub created_at_ms: u64,
    pub used_at_ms: Option<u64>,
    pub revoked_at_ms: Option<u64>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl OAuth2RefreshToken {
    #[must_use]
    pub fn issue(access_token: &OAuth2AccessToken, now_ms: u64, lifetime_ms: u64) -> Self {
        Self {
            token_id: Uuid::new_v4().to_string(),
            refresh_token: random_token(32),
            access_token_id: access_token.token_id.clone(),
            client_id: access_token.client_id.clone(),
            user_id: access_token.user_id.clone(),
            scopes: access_token.scopes.clone(),
            expires_at_ms: now_ms.saturating_add(lifetime_ms),
            created_at_ms: now_ms,
            used_at_ms: None,
            revoked_at_ms: None,
            metadata: BTreeMap::new(),
        }
    }

    #[must_use]
    pub const fn can_be_used_at(&self, now_ms: u64) -> bool {
        self.used_at_ms.is_none() && self.revoked_at_ms.is_none() && now_ms < self.expires_at_ms
    }

    #[must_use]
    pub const fn is_expired_at(&self, now_ms: u64) -> bool {
        now_ms >= self.expires_at_ms
    }

    #[must_use]
    pub const fn is_used(&self) -> bool {
        self.used_at_ms.is_some()
    }

    #[must_use]
    pub const fn is_revoked(&self) -> bool {
        self.revoked_at_ms.is_some()
    }

    #[must_use]
    pub fn scope_string(&self) -> String {
        self.scopes.iter().cloned().collect::<Vec<_>>().join(" ")
    }

    pub fn consume(&mut self, now_ms: u64) -> Result<(), SecurityError> {
        if !self.can_be_used_at(now_ms) {
            return Err(SecurityError::Unauthorized(
                "refresh token is expired, revoked, or already used".into(),
            ));
        }
        self.used_at_ms = Some(now_ms);
        Ok(())
    }

    pub fn revoke(&mut self, now_ms: u64) -> bool {
        if self.revoked_at_ms.is_some() {
            false
        } else {
            self.revoked_at_ms = Some(now_ms);
            true
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OAuth2TokenRequest {
    pub grant_type: OAuth2GrantType,
    pub client_id: String,
    #[serde(skip_serializing)]
    pub client_secret: Option<String>,
    #[serde(skip_serializing)]
    pub code: Option<String>,
    pub redirect_uri: Option<String>,
    #[serde(skip_serializing)]
    pub code_verifier: Option<String>,
    #[serde(skip_serializing)]
    pub refresh_token: Option<String>,
    pub scope: Option<String>,
    pub username: Option<String>,
    #[serde(skip_serializing)]
    pub password: Option<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl OAuth2TokenRequest {
    #[must_use]
    pub fn authorization_code(
        client_id: impl Into<String>,
        code: impl Into<String>,
        redirect_uri: impl Into<String>,
        client_secret: Option<String>,
        code_verifier: Option<String>,
    ) -> Self {
        Self::empty(OAuth2GrantType::AuthorizationCode, client_id, client_secret).with_code(
            code.into(),
            redirect_uri.into(),
            code_verifier,
        )
    }

    #[must_use]
    pub fn refresh(
        client_id: impl Into<String>,
        refresh_token: impl Into<String>,
        client_secret: Option<String>,
        scope: Option<String>,
    ) -> Self {
        let mut request = Self::empty(OAuth2GrantType::RefreshToken, client_id, client_secret);
        request.refresh_token = Some(refresh_token.into());
        request.scope = scope;
        request
    }

    #[must_use]
    pub fn client_credentials(
        client_id: impl Into<String>,
        client_secret: impl Into<String>,
        scope: Option<String>,
    ) -> Self {
        let mut request = Self::empty(
            OAuth2GrantType::ClientCredentials,
            client_id,
            Some(client_secret.into()),
        );
        request.scope = scope;
        request
    }

    fn empty(
        grant_type: OAuth2GrantType,
        client_id: impl Into<String>,
        client_secret: Option<String>,
    ) -> Self {
        Self {
            grant_type,
            client_id: client_id.into(),
            client_secret,
            code: None,
            redirect_uri: None,
            code_verifier: None,
            refresh_token: None,
            scope: None,
            username: None,
            password: None,
            metadata: BTreeMap::new(),
        }
    }

    fn with_code(
        mut self,
        code: String,
        redirect_uri: String,
        code_verifier: Option<String>,
    ) -> Self {
        self.code = Some(code);
        self.redirect_uri = Some(redirect_uri);
        self.code_verifier = code_verifier;
        self
    }

    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.client_id.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "OAuth2 token request requires client id".into(),
            ));
        }
        let valid = match self.grant_type {
            OAuth2GrantType::AuthorizationCode => {
                self.code.is_some() && self.redirect_uri.is_some()
            }
            OAuth2GrantType::RefreshToken => self.refresh_token.is_some(),
            OAuth2GrantType::ClientCredentials => true,
            OAuth2GrantType::Password => self.username.is_some() && self.password.is_some(),
            OAuth2GrantType::JwtBearer
            | OAuth2GrantType::DeviceCode
            | OAuth2GrantType::TokenExchange => self.code.is_some(),
            OAuth2GrantType::Implicit => false,
        };
        if valid {
            Ok(())
        } else {
            Err(SecurityError::InvalidConfiguration(
                "OAuth2 grant request is missing required parameters".into(),
            ))
        }
    }

    #[must_use]
    pub fn requested_scopes(&self) -> BTreeSet<String> {
        self.scope
            .as_deref()
            .unwrap_or_default()
            .split_whitespace()
            .map(str::to_owned)
            .collect()
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OAuth2TokenResponse {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub access_token: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub token_type: Option<OAuth2TokenType>,
    #[serde(rename = "expires_in", skip_serializing_if = "Option::is_none")]
    pub expires_in_seconds: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub refresh_token: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scope: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id_token: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_uri: Option<String>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub metadata: BTreeMap<String, Value>,
}

impl OAuth2TokenResponse {
    #[must_use]
    pub fn success(
        access_token: impl Into<String>,
        expires_in_seconds: Option<u64>,
        refresh_token: Option<String>,
        scope: Option<String>,
        id_token: Option<String>,
    ) -> Self {
        Self {
            access_token: Some(access_token.into()),
            token_type: Some(OAuth2TokenType::Bearer),
            expires_in_seconds,
            refresh_token,
            scope,
            id_token,
            error: None,
            error_description: None,
            error_uri: None,
            metadata: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn failure(
        error: impl Into<String>,
        error_description: Option<String>,
        error_uri: Option<String>,
    ) -> Self {
        Self {
            access_token: None,
            token_type: None,
            expires_in_seconds: None,
            refresh_token: None,
            scope: None,
            id_token: None,
            error: Some(error.into()),
            error_description,
            error_uri,
            metadata: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn is_success(&self) -> bool {
        self.error.is_none() && self.access_token.is_some()
    }

    pub fn to_value(&self) -> Result<Value, SecurityError> {
        serde_json::to_value(self).map_err(|_| {
            SecurityError::InvalidConfiguration("cannot serialize OAuth2 token response".into())
        })
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct OAuth2TokenIntrospection {
    pub active: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub client_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub username: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scope: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub token_type: Option<OAuth2TokenType>,
    #[serde(rename = "exp", skip_serializing_if = "Option::is_none")]
    pub exp_seconds: Option<u64>,
    #[serde(rename = "iat", skip_serializing_if = "Option::is_none")]
    pub iat_seconds: Option<u64>,
    #[serde(rename = "nbf", skip_serializing_if = "Option::is_none")]
    pub nbf_seconds: Option<u64>,
    #[serde(rename = "sub", skip_serializing_if = "Option::is_none")]
    pub subject: Option<String>,
    #[serde(rename = "aud", skip_serializing_if = "Option::is_none")]
    pub audience: Option<String>,
    #[serde(rename = "iss", skip_serializing_if = "Option::is_none")]
    pub issuer: Option<String>,
    #[serde(rename = "jti", skip_serializing_if = "Option::is_none")]
    pub token_id: Option<String>,
}

impl OAuth2TokenIntrospection {
    #[must_use]
    pub fn from_access_token(token: &OAuth2AccessToken, now_ms: u64) -> Self {
        if !token.is_active_at(now_ms) {
            return Self::default();
        }
        Self {
            active: true,
            client_id: Some(token.client_id.clone()),
            username: token.user_id.clone(),
            scope: Some(token.scope_string()),
            token_type: Some(token.token_type),
            exp_seconds: Some(token.expires_at_ms / 1_000),
            iat_seconds: Some(token.created_at_ms / 1_000),
            subject: token.user_id.clone(),
            token_id: Some(token.token_id.clone()),
            ..Self::default()
        }
    }

    pub fn to_value(&self) -> Result<Value, SecurityError> {
        serde_json::to_value(self).map_err(|_| {
            SecurityError::InvalidConfiguration("cannot serialize token introspection".into())
        })
    }
}

#[async_trait]
pub trait OAuth2ClientStore: Send + Sync {
    async fn save_client(&self, client: OAuth2Client) -> Result<(), SecurityError>;
    async fn client(&self, client_id: &str) -> Result<Option<OAuth2Client>, SecurityError>;
    async fn clients_by_name(&self, client_name: &str) -> Result<Vec<OAuth2Client>, SecurityError>;
    async fn replace_client(&self, client: OAuth2Client) -> Result<(), SecurityError>;
    async fn delete_client(&self, client_id: &str) -> Result<bool, SecurityError>;
    async fn list_clients(
        &self,
        offset: usize,
        limit: usize,
    ) -> Result<Vec<OAuth2Client>, SecurityError>;
    async fn list_active_clients(
        &self,
        offset: usize,
        limit: usize,
    ) -> Result<Vec<OAuth2Client>, SecurityError>;
    async fn client_exists(&self, client_id: &str) -> Result<bool, SecurityError>;
    async fn register_client(
        &self,
        registration: &OAuth2ClientRegistration,
        now_ms: u64,
    ) -> Result<IssuedOAuth2Client, SecurityError>;
    async fn set_client_active(
        &self,
        client_id: &str,
        active: bool,
        now_ms: u64,
    ) -> Result<bool, SecurityError>;
    async fn regenerate_client_secret(
        &self,
        client_id: &str,
        now_ms: u64,
    ) -> Result<Option<String>, SecurityError>;
}

#[async_trait]
pub trait OAuth2AuthorizationStore: Send + Sync {
    async fn save_authorization(&self, code: AuthorizationCode) -> Result<(), SecurityError>;
    async fn authorization(&self, code: &str) -> Result<Option<AuthorizationCode>, SecurityError>;
    async fn authorization_by_id(
        &self,
        authorization_id: &str,
    ) -> Result<Option<AuthorizationCode>, SecurityError>;
    async fn replace_authorization(&self, code: AuthorizationCode) -> Result<(), SecurityError>;
    async fn consume_authorization(
        &self,
        code: &str,
        client_id: &str,
        redirect_uri: &str,
        verifier: Option<&str>,
        now_ms: u64,
    ) -> Result<bool, SecurityError>;
    async fn delete_authorization(&self, authorization_id: &str) -> Result<bool, SecurityError>;
    async fn authorizations_for_user(
        &self,
        user_id: &str,
        client_id: Option<&str>,
        active_only: bool,
        now_ms: u64,
    ) -> Result<Vec<AuthorizationCode>, SecurityError>;
    async fn authorizations_for_client(
        &self,
        client_id: &str,
        active_only: bool,
        now_ms: u64,
    ) -> Result<Vec<AuthorizationCode>, SecurityError>;
    async fn cleanup_authorizations(&self, now_ms: u64) -> Result<usize, SecurityError>;
    async fn revoke_authorizations_for_user(
        &self,
        user_id: &str,
        client_id: Option<&str>,
    ) -> Result<usize, SecurityError>;
    async fn revoke_authorizations_for_client(
        &self,
        client_id: &str,
    ) -> Result<usize, SecurityError>;
}

#[async_trait]
pub trait OAuth2TokenStore: Send + Sync {
    async fn save_access_token(&self, token: OAuth2AccessToken) -> Result<(), SecurityError>;
    async fn save_refresh_token(&self, token: OAuth2RefreshToken) -> Result<(), SecurityError>;
    async fn access_token(&self, token: &str) -> Result<Option<OAuth2AccessToken>, SecurityError>;
    async fn refresh_token(&self, token: &str)
    -> Result<Option<OAuth2RefreshToken>, SecurityError>;
    async fn access_token_by_id(
        &self,
        token_id: &str,
    ) -> Result<Option<OAuth2AccessToken>, SecurityError>;
    async fn refresh_token_by_id(
        &self,
        token_id: &str,
    ) -> Result<Option<OAuth2RefreshToken>, SecurityError>;
    async fn replace_access_token(&self, token: OAuth2AccessToken) -> Result<(), SecurityError>;
    async fn replace_refresh_token(&self, token: OAuth2RefreshToken) -> Result<(), SecurityError>;
    async fn revoke_access_token(&self, token: &str, now_ms: u64) -> Result<bool, SecurityError>;
    async fn revoke_refresh_token(&self, token: &str, now_ms: u64) -> Result<bool, SecurityError>;
    async fn revoke_for_user(
        &self,
        user_id: &str,
        client_id: Option<&str>,
        now_ms: u64,
    ) -> Result<usize, SecurityError>;
    async fn revoke_for_client(&self, client_id: &str, now_ms: u64)
    -> Result<usize, SecurityError>;
    async fn access_tokens_for_user(
        &self,
        user_id: &str,
        client_id: Option<&str>,
        active_only: bool,
        now_ms: u64,
    ) -> Result<Vec<OAuth2AccessToken>, SecurityError>;
    async fn access_tokens_for_client(
        &self,
        client_id: &str,
        active_only: bool,
        now_ms: u64,
    ) -> Result<Vec<OAuth2AccessToken>, SecurityError>;
    async fn consume_refresh_token(&self, token: &str, now_ms: u64) -> Result<bool, SecurityError>;
    async fn cleanup_tokens(&self, now_ms: u64) -> Result<usize, SecurityError>;
}

#[derive(Default)]
pub struct InMemoryOAuth2Store {
    clients: RwLock<BTreeMap<String, OAuth2Client>>,
    authorizations: RwLock<BTreeMap<String, AuthorizationCode>>,
    access_tokens: RwLock<BTreeMap<String, OAuth2AccessToken>>,
    refresh_tokens: RwLock<BTreeMap<String, OAuth2RefreshToken>>,
}

#[async_trait]
impl OAuth2ClientStore for InMemoryOAuth2Store {
    async fn save_client(&self, client: OAuth2Client) -> Result<(), SecurityError> {
        client.validate()?;
        self.clients
            .write()
            .await
            .insert(client.client_id.clone(), client);
        Ok(())
    }

    async fn client(&self, client_id: &str) -> Result<Option<OAuth2Client>, SecurityError> {
        Ok(self.clients.read().await.get(client_id).cloned())
    }

    async fn clients_by_name(&self, client_name: &str) -> Result<Vec<OAuth2Client>, SecurityError> {
        Ok(self
            .clients
            .read()
            .await
            .values()
            .filter(|client| client.client_name == client_name)
            .cloned()
            .collect())
    }

    async fn replace_client(&self, client: OAuth2Client) -> Result<(), SecurityError> {
        client.validate()?;
        let mut clients = self.clients.write().await;
        if !clients.contains_key(&client.client_id) {
            return Err(SecurityError::NotFound("OAuth2 client".into()));
        }
        clients.insert(client.client_id.clone(), client);
        Ok(())
    }

    async fn delete_client(&self, client_id: &str) -> Result<bool, SecurityError> {
        Ok(self.clients.write().await.remove(client_id).is_some())
    }

    async fn list_clients(
        &self,
        offset: usize,
        limit: usize,
    ) -> Result<Vec<OAuth2Client>, SecurityError> {
        Ok(self
            .clients
            .read()
            .await
            .values()
            .skip(offset)
            .take(limit.min(1_000))
            .cloned()
            .collect())
    }

    async fn list_active_clients(
        &self,
        offset: usize,
        limit: usize,
    ) -> Result<Vec<OAuth2Client>, SecurityError> {
        Ok(self
            .clients
            .read()
            .await
            .values()
            .filter(|client| client.enabled)
            .skip(offset)
            .take(limit.min(1_000))
            .cloned()
            .collect())
    }

    async fn client_exists(&self, client_id: &str) -> Result<bool, SecurityError> {
        Ok(self.clients.read().await.contains_key(client_id))
    }

    async fn register_client(
        &self,
        registration: &OAuth2ClientRegistration,
        now_ms: u64,
    ) -> Result<IssuedOAuth2Client, SecurityError> {
        let issued = registration.register(now_ms)?;
        self.save_client(issued.client.clone()).await?;
        Ok(issued)
    }

    async fn set_client_active(
        &self,
        client_id: &str,
        active: bool,
        now_ms: u64,
    ) -> Result<bool, SecurityError> {
        let mut clients = self.clients.write().await;
        let Some(client) = clients.get_mut(client_id) else {
            return Ok(false);
        };
        if active {
            client.activate(now_ms);
        } else {
            client.deactivate(now_ms);
        }
        Ok(true)
    }

    async fn regenerate_client_secret(
        &self,
        client_id: &str,
        now_ms: u64,
    ) -> Result<Option<String>, SecurityError> {
        let mut clients = self.clients.write().await;
        clients
            .get_mut(client_id)
            .map(|client| client.rotate_generated_secret(now_ms))
            .transpose()
    }
}

#[async_trait]
impl OAuth2AuthorizationStore for InMemoryOAuth2Store {
    async fn save_authorization(&self, code: AuthorizationCode) -> Result<(), SecurityError> {
        let mut records = self.authorizations.write().await;
        if records.contains_key(&code.code) {
            return Err(SecurityError::Conflict(
                "authorization code already exists".into(),
            ));
        }
        records.insert(code.code.clone(), code);
        Ok(())
    }

    async fn authorization(&self, code: &str) -> Result<Option<AuthorizationCode>, SecurityError> {
        Ok(self.authorizations.read().await.get(code).cloned())
    }

    async fn authorization_by_id(
        &self,
        authorization_id: &str,
    ) -> Result<Option<AuthorizationCode>, SecurityError> {
        Ok(self
            .authorizations
            .read()
            .await
            .values()
            .find(|authorization| authorization.code_id == authorization_id)
            .cloned())
    }

    async fn replace_authorization(&self, code: AuthorizationCode) -> Result<(), SecurityError> {
        let mut records = self.authorizations.write().await;
        if !records.contains_key(&code.code) {
            return Err(SecurityError::NotFound("authorization code".into()));
        }
        records.insert(code.code.clone(), code);
        Ok(())
    }

    async fn consume_authorization(
        &self,
        code: &str,
        client_id: &str,
        redirect_uri: &str,
        verifier: Option<&str>,
        now_ms: u64,
    ) -> Result<bool, SecurityError> {
        let mut records = self.authorizations.write().await;
        let Some(authorization) = records.get_mut(code) else {
            return Ok(false);
        };
        authorization.consume(client_id, redirect_uri, verifier, now_ms)?;
        Ok(true)
    }

    async fn delete_authorization(&self, authorization_id: &str) -> Result<bool, SecurityError> {
        let mut records = self.authorizations.write().await;
        let code = records.iter().find_map(|(code, authorization)| {
            (authorization.code_id == authorization_id).then(|| code.clone())
        });
        Ok(code.is_some_and(|code| records.remove(&code).is_some()))
    }

    async fn authorizations_for_user(
        &self,
        user_id: &str,
        client_id: Option<&str>,
        active_only: bool,
        now_ms: u64,
    ) -> Result<Vec<AuthorizationCode>, SecurityError> {
        Ok(self
            .authorizations
            .read()
            .await
            .values()
            .filter(|authorization| {
                authorization.user_id == user_id
                    && client_id.is_none_or(|client| authorization.client_id == client)
                    && (!active_only || authorization.can_be_used_at(now_ms))
            })
            .cloned()
            .collect())
    }

    async fn authorizations_for_client(
        &self,
        client_id: &str,
        active_only: bool,
        now_ms: u64,
    ) -> Result<Vec<AuthorizationCode>, SecurityError> {
        Ok(self
            .authorizations
            .read()
            .await
            .values()
            .filter(|authorization| {
                authorization.client_id == client_id
                    && (!active_only || authorization.can_be_used_at(now_ms))
            })
            .cloned()
            .collect())
    }

    async fn cleanup_authorizations(&self, now_ms: u64) -> Result<usize, SecurityError> {
        let mut records = self.authorizations.write().await;
        let before = records.len();
        records.retain(|_, code| code.can_be_used_at(now_ms));
        Ok(before - records.len())
    }

    async fn revoke_authorizations_for_user(
        &self,
        user_id: &str,
        client_id: Option<&str>,
    ) -> Result<usize, SecurityError> {
        let mut records = self.authorizations.write().await;
        let before = records.len();
        records.retain(|_, authorization| {
            authorization.user_id != user_id
                || client_id.is_some_and(|client| authorization.client_id != client)
        });
        Ok(before - records.len())
    }

    async fn revoke_authorizations_for_client(
        &self,
        client_id: &str,
    ) -> Result<usize, SecurityError> {
        let mut records = self.authorizations.write().await;
        let before = records.len();
        records.retain(|_, authorization| authorization.client_id != client_id);
        Ok(before - records.len())
    }
}

#[async_trait]
impl OAuth2TokenStore for InMemoryOAuth2Store {
    async fn save_access_token(&self, token: OAuth2AccessToken) -> Result<(), SecurityError> {
        self.access_tokens
            .write()
            .await
            .insert(token.access_token.clone(), token);
        Ok(())
    }

    async fn save_refresh_token(&self, token: OAuth2RefreshToken) -> Result<(), SecurityError> {
        self.refresh_tokens
            .write()
            .await
            .insert(token.refresh_token.clone(), token);
        Ok(())
    }

    async fn access_token(&self, token: &str) -> Result<Option<OAuth2AccessToken>, SecurityError> {
        Ok(self.access_tokens.read().await.get(token).cloned())
    }

    async fn refresh_token(
        &self,
        token: &str,
    ) -> Result<Option<OAuth2RefreshToken>, SecurityError> {
        Ok(self.refresh_tokens.read().await.get(token).cloned())
    }

    async fn access_token_by_id(
        &self,
        token_id: &str,
    ) -> Result<Option<OAuth2AccessToken>, SecurityError> {
        Ok(self
            .access_tokens
            .read()
            .await
            .values()
            .find(|token| token.token_id == token_id)
            .cloned())
    }

    async fn refresh_token_by_id(
        &self,
        token_id: &str,
    ) -> Result<Option<OAuth2RefreshToken>, SecurityError> {
        Ok(self
            .refresh_tokens
            .read()
            .await
            .values()
            .find(|token| token.token_id == token_id)
            .cloned())
    }

    async fn replace_access_token(&self, token: OAuth2AccessToken) -> Result<(), SecurityError> {
        let mut records = self.access_tokens.write().await;
        if !records.contains_key(&token.access_token) {
            return Err(SecurityError::NotFound("access token".into()));
        }
        records.insert(token.access_token.clone(), token);
        Ok(())
    }

    async fn replace_refresh_token(&self, token: OAuth2RefreshToken) -> Result<(), SecurityError> {
        let mut records = self.refresh_tokens.write().await;
        if !records.contains_key(&token.refresh_token) {
            return Err(SecurityError::NotFound("refresh token".into()));
        }
        records.insert(token.refresh_token.clone(), token);
        Ok(())
    }

    async fn revoke_access_token(&self, token: &str, now_ms: u64) -> Result<bool, SecurityError> {
        Ok(self
            .access_tokens
            .write()
            .await
            .get_mut(token)
            .is_some_and(|token| token.revoke(now_ms)))
    }

    async fn revoke_refresh_token(&self, token: &str, now_ms: u64) -> Result<bool, SecurityError> {
        Ok(self
            .refresh_tokens
            .write()
            .await
            .get_mut(token)
            .is_some_and(|token| token.revoke(now_ms)))
    }

    async fn revoke_for_user(
        &self,
        user_id: &str,
        client_id: Option<&str>,
        now_ms: u64,
    ) -> Result<usize, SecurityError> {
        let mut access = self.access_tokens.write().await;
        let mut refresh = self.refresh_tokens.write().await;
        let access_count = revoke_tokens(
            &mut access,
            |token| {
                token.user_id.as_deref() == Some(user_id)
                    && client_id.is_none_or(|client| token.client_id == client)
            },
            now_ms,
        );
        let refresh_count = revoke_refresh_tokens(
            &mut refresh,
            |token| {
                token.user_id.as_deref() == Some(user_id)
                    && client_id.is_none_or(|client| token.client_id == client)
            },
            now_ms,
        );
        Ok(access_count + refresh_count)
    }

    async fn revoke_for_client(
        &self,
        client_id: &str,
        now_ms: u64,
    ) -> Result<usize, SecurityError> {
        let mut access = self.access_tokens.write().await;
        let mut refresh = self.refresh_tokens.write().await;
        let access_count = revoke_tokens(&mut access, |token| token.client_id == client_id, now_ms);
        let refresh_count =
            revoke_refresh_tokens(&mut refresh, |token| token.client_id == client_id, now_ms);
        Ok(access_count + refresh_count)
    }

    async fn access_tokens_for_user(
        &self,
        user_id: &str,
        client_id: Option<&str>,
        active_only: bool,
        now_ms: u64,
    ) -> Result<Vec<OAuth2AccessToken>, SecurityError> {
        Ok(self
            .access_tokens
            .read()
            .await
            .values()
            .filter(|token| {
                token.user_id.as_deref() == Some(user_id)
                    && client_id.is_none_or(|client| token.client_id == client)
                    && (!active_only || token.is_active_at(now_ms))
            })
            .cloned()
            .collect())
    }

    async fn access_tokens_for_client(
        &self,
        client_id: &str,
        active_only: bool,
        now_ms: u64,
    ) -> Result<Vec<OAuth2AccessToken>, SecurityError> {
        Ok(self
            .access_tokens
            .read()
            .await
            .values()
            .filter(|token| {
                token.client_id == client_id && (!active_only || token.is_active_at(now_ms))
            })
            .cloned()
            .collect())
    }

    async fn consume_refresh_token(&self, token: &str, now_ms: u64) -> Result<bool, SecurityError> {
        let mut records = self.refresh_tokens.write().await;
        let Some(token) = records.get_mut(token) else {
            return Ok(false);
        };
        token.consume(now_ms)?;
        Ok(true)
    }

    async fn cleanup_tokens(&self, now_ms: u64) -> Result<usize, SecurityError> {
        let mut access = self.access_tokens.write().await;
        let mut refresh = self.refresh_tokens.write().await;
        let before = access.len() + refresh.len();
        access.retain(|_, token| token.is_active_at(now_ms));
        refresh.retain(|_, token| token.can_be_used_at(now_ms));
        Ok(before - access.len() - refresh.len())
    }
}

fn revoke_tokens(
    tokens: &mut BTreeMap<String, OAuth2AccessToken>,
    predicate: impl Fn(&OAuth2AccessToken) -> bool,
    now_ms: u64,
) -> usize {
    let mut count = 0;
    for token in tokens.values_mut().filter(|token| predicate(token)) {
        count += usize::from(token.revoke(now_ms));
    }
    count
}

fn revoke_refresh_tokens(
    tokens: &mut BTreeMap<String, OAuth2RefreshToken>,
    predicate: impl Fn(&OAuth2RefreshToken) -> bool,
    now_ms: u64,
) -> usize {
    let mut count = 0;
    for token in tokens.values_mut().filter(|token| predicate(token)) {
        count += usize::from(token.revoke(now_ms));
    }
    count
}

#[async_trait]
pub trait OAuth2Provider: Send + Sync {
    async fn authorize(
        &self,
        request: &OAuth2AuthorizationRequest,
        user_id: &str,
        approved_scopes: Option<&BTreeSet<String>>,
    ) -> Result<OAuth2AuthorizationResponse, SecurityError>;
    async fn exchange_code(
        &self,
        request: &OAuth2TokenRequest,
        now_ms: u64,
    ) -> Result<OAuth2TokenResponse, SecurityError>;
    async fn refresh_tokens(
        &self,
        request: &OAuth2TokenRequest,
        now_ms: u64,
    ) -> Result<OAuth2TokenResponse, SecurityError>;
    async fn client_credentials(
        &self,
        request: &OAuth2TokenRequest,
        now_ms: u64,
    ) -> Result<OAuth2TokenResponse, SecurityError>;
    async fn introspect(
        &self,
        token: &str,
        client_id: Option<&str>,
        now_ms: u64,
    ) -> Result<OAuth2TokenIntrospection, SecurityError>;
    async fn revoke(
        &self,
        token: &str,
        client_id: &str,
        client_secret: Option<&str>,
        now_ms: u64,
    ) -> Result<bool, SecurityError>;
    async fn validate_access_token(
        &self,
        token: &str,
        required_scopes: Option<&BTreeSet<String>>,
        now_ms: u64,
    ) -> Result<Option<OAuth2AccessToken>, SecurityError>;
    async fn authorization(
        &self,
        authorization_code: &str,
    ) -> Result<Option<AuthorizationCode>, SecurityError>;
    async fn access_token(&self, token: &str) -> Result<Option<OAuth2AccessToken>, SecurityError>;
    async fn refresh_token(&self, token: &str)
    -> Result<Option<OAuth2RefreshToken>, SecurityError>;
}

#[must_use]
pub fn generate_code_challenge(verifier: &str) -> String {
    URL_SAFE_NO_PAD.encode(Sha256::digest(verifier.as_bytes()))
}

pub fn generate_code_verifier(length: usize) -> Result<String, SecurityError> {
    const ALPHABET: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
    if !(43..=128).contains(&length) {
        return Err(SecurityError::InvalidConfiguration(
            "PKCE verifier length must be between 43 and 128".into(),
        ));
    }
    let mut rng = rand::rng();
    Ok((0..length)
        .map(|_| char::from(ALPHABET[rng.random_range(0..ALPHABET.len())]))
        .collect())
}

#[must_use]
pub fn generate_client_id() -> String {
    random_token(32)
}

#[must_use]
pub fn generate_client_secret() -> String {
    random_token(64)
}

#[must_use]
pub fn generate_authorization_code() -> String {
    random_token(32)
}

#[must_use]
pub fn generate_state() -> String {
    random_token(16)
}

#[must_use]
pub fn generate_access_token() -> String {
    random_token(32)
}

#[must_use]
pub fn generate_refresh_token() -> String {
    random_token(32)
}

#[must_use]
pub fn verify_pkce(
    challenge: Option<&str>,
    method: Option<PkceMethod>,
    verifier: Option<&str>,
) -> bool {
    // The shared comparator scans the longer input. Keep impossible challenge
    // lengths on the existing early-rejection path before comparing secrets.
    match (challenge, method, verifier) {
        (None, None, _) => true,
        (Some(challenge), Some(PkceMethod::Plain), Some(verifier)) => {
            valid_pkce_value(verifier)
                && challenge.len() == verifier.len()
                && constant_time_secret_eq(challenge.as_bytes(), verifier.as_bytes())
        }
        (Some(challenge), Some(PkceMethod::S256), Some(verifier)) => {
            valid_pkce_value(verifier)
                && challenge.len() == 43
                && constant_time_secret_eq(
                    challenge.as_bytes(),
                    generate_code_challenge(verifier).as_bytes(),
                )
        }
        _ => false,
    }
}

fn default_oidc_scopes(scopes: BTreeSet<String>) -> BTreeSet<String> {
    if scopes.is_empty() {
        BTreeSet::from(["openid".into(), "profile".into(), "email".into()])
    } else {
        scopes
    }
}

fn valid_pkce_value(value: &str) -> bool {
    (43..=128).contains(&value.len())
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'.' | b'_' | b'~'))
}

fn required_param<'a>(
    params: &'a BTreeMap<String, String>,
    name: &str,
) -> Result<&'a str, SecurityError> {
    params
        .get(name)
        .map(String::as_str)
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| {
            SecurityError::InvalidConfiguration(format!("OAuth2 request is missing {name}"))
        })
}

fn parse_response_type(value: &str) -> Result<OAuth2ResponseType, SecurityError> {
    match value {
        "code" => Ok(OAuth2ResponseType::Code),
        "token" => Ok(OAuth2ResponseType::Token),
        "id_token" => Ok(OAuth2ResponseType::IdToken),
        "code id_token" => Ok(OAuth2ResponseType::CodeIdToken),
        "code token" => Ok(OAuth2ResponseType::CodeToken),
        "code token id_token" | "code id_token token" => Ok(OAuth2ResponseType::CodeTokenIdToken),
        _ => Err(SecurityError::InvalidConfiguration(
            "unsupported OAuth2 response type".into(),
        )),
    }
}

fn hash_secret(secret: &str) -> Vec<u8> {
    Sha256::digest(secret.as_bytes()).to_vec()
}

fn random_token(bytes: usize) -> String {
    let mut value = vec![0_u8; bytes];
    rand::rng().fill(value.as_mut_slice());
    URL_SAFE_NO_PAD.encode(value)
}

#[cfg(test)]
mod tests {
    #[test]
    fn redirects_encode_components_without_changing_query_or_rejection_policy() {
        for (redirect, separator) in [
            ("https://client.example/callback", "?"),
            ("https://client.example/callback?existing=1", "&"),
            ("com.example.app://callback", "?"),
        ] {
            let response = super::OAuth2AuthorizationResponse::success(
                redirect,
                "code +/%",
                Some("café&next=#\n".into()),
            );
            assert_eq!(
                response.redirect_url().unwrap(),
                format!(
                    "{redirect}{separator}code=code%20%2B%2F%25&state=caf%C3%A9%26next%3D%23%0A"
                )
            );
        }
        let response = super::OAuth2AuthorizationResponse::failure(
            "https://client.example/callback",
            "access_denied",
            Some("no + access".into()),
            Some("https://issuer.example/help?q=a&b=1".into()),
            Some(String::new()),
        );
        assert_eq!(
            response.redirect_url().unwrap(),
            "https://client.example/callback?state=&error=access_denied&error_description=no%20%2B%20access&error_uri=https%3A%2F%2Fissuer.example%2Fhelp%3Fq%3Da%26b%3D1"
        );
        for redirect in [
            "javascript://callback",
            "https://client.example/callback#fragment",
        ] {
            assert!(
                super::OAuth2AuthorizationResponse::success(redirect, "code", None)
                    .redirect_url()
                    .is_err()
            );
        }
    }

    #[test]
    fn pkce_comparison_rejects_malformed_challenge_lengths() {
        let verifier = "v".repeat(43);
        let digest = super::generate_code_challenge(&verifier);
        assert!(super::verify_pkce(
            Some(&verifier),
            Some(super::PkceMethod::Plain),
            Some(&verifier)
        ));
        assert!(super::verify_pkce(
            Some(&digest),
            Some(super::PkceMethod::S256),
            Some(&verifier)
        ));
        for challenge in [
            String::new(),
            "x".repeat(42),
            "x".repeat(44),
            "x".repeat(129),
            "x".repeat(16_384),
        ] {
            assert!(!super::verify_pkce(
                Some(&challenge),
                Some(super::PkceMethod::Plain),
                Some(&verifier)
            ));
            assert!(!super::verify_pkce(
                Some(&challenge),
                Some(super::PkceMethod::S256),
                Some(&verifier)
            ));
        }
        let wrong = "x".repeat(43);
        assert!(!super::verify_pkce(
            Some(&wrong),
            Some(super::PkceMethod::Plain),
            Some(&verifier)
        ));
        assert!(!super::verify_pkce(
            Some(&wrong),
            Some(super::PkceMethod::S256),
            Some(&verifier)
        ));
        assert!(super::verify_pkce(None, None, Some(&verifier)));
        assert!(!super::verify_pkce(Some(&digest), None, Some(&verifier)));
        assert!(!super::verify_pkce(
            Some(&digest),
            Some(super::PkceMethod::S256),
            None
        ));
    }

    use super::*;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        client: ClientCase,
        pkce: PkceCase,
        authorization: AuthorizationCase,
        oauth_query: BTreeMap<String, String>,
        tokens: TokenCase,
    }

    #[derive(Deserialize)]
    struct ClientCase {
        client_id: String,
        client_name: String,
        secret: String,
        redirect_uri: String,
        invalid_redirect_uri: String,
        malformed_redirect_uri: String,
        scopes: BTreeSet<String>,
        grant_types: BTreeSet<OAuth2GrantType>,
        response_types: BTreeSet<OAuth2ResponseType>,
        require_pkce: bool,
    }

    #[derive(Deserialize)]
    struct PkceCase {
        verifier: String,
        s256_challenge: String,
        plain_challenge: String,
    }

    #[derive(Deserialize)]
    struct AuthorizationCase {
        created_at_ms: u64,
        lifetime_ms: u64,
        consume_at_ms: u64,
        expired_at_ms: u64,
        state: String,
        nonce: String,
    }

    #[derive(Deserialize)]
    struct TokenCase {
        created_at_ms: u64,
        access_lifetime_ms: u64,
        refresh_lifetime_ms: u64,
        active_at_ms: u64,
        expired_at_ms: u64,
        scope: String,
    }

    fn fixture() -> Fixture {
        let fixture: Fixture = serde_json::from_str(include_str!(
            "../../../contracts/identity-oauth-oidc-behavior.json"
        ))
        .expect("valid OAuth/OIDC behavior fixture");
        assert_eq!(fixture.schema_version, 1);
        fixture
    }

    fn client(case: &ClientCase) -> OAuth2Client {
        let mut client = OAuth2Client::confidential(
            &case.client_id,
            &case.client_name,
            &case.secret,
            Some(format!("secret://identity/{}", case.client_id)),
            BTreeSet::from([case.redirect_uri.clone()]),
            1,
        )
        .unwrap();
        client.allowed_scopes.clone_from(&case.scopes);
        client.allowed_grant_types.clone_from(&case.grant_types);
        client
            .allowed_response_types
            .clone_from(&case.response_types);
        client.require_pkce = case.require_pkce;
        client.validate().unwrap();
        client
    }

    fn authorization_request(fixture: &Fixture) -> OAuth2AuthorizationRequest {
        OAuth2AuthorizationRequest {
            client_id: fixture.client.client_id.clone(),
            redirect_uri: fixture.client.redirect_uri.clone(),
            response_type: OAuth2ResponseType::Code,
            scopes: fixture.client.scopes.clone(),
            state: Some(fixture.authorization.state.clone()),
            code_challenge: Some(fixture.pkce.s256_challenge.clone()),
            code_challenge_method: Some(PkceMethod::S256),
            nonce: Some(fixture.authorization.nonce.clone()),
            request_id: "request-1".into(),
            created_at_ms: fixture.authorization.created_at_ms,
            metadata: BTreeMap::new(),
        }
    }

    #[test]
    fn restored_client_digests_preserve_secret_verification_boundaries() {
        let fixture = fixture();
        let original = client(&fixture.client);
        let mut stored = serde_json::to_value(&original).unwrap();
        assert!(stored.get("secret_digest").is_none());
        let digest = hash_secret(&fixture.client.secret);
        stored["secret_digest"] = serde_json::json!(digest);
        let restored: OAuth2Client = serde_json::from_value(stored.clone()).unwrap();
        assert!(restored.verify_client_secret(&fixture.client.secret));
        assert!(!restored.verify_client_secret("incorrect"));
        for index in [0, digest.len() / 2, digest.len() - 1] {
            let mut changed = digest.clone();
            changed[index] ^= 1;
            stored["secret_digest"] = serde_json::json!(changed);
            let restored: OAuth2Client = serde_json::from_value(stored.clone()).unwrap();
            assert!(!restored.verify_client_secret(&fixture.client.secret));
        }
        for length in [0, 1, 31, 33, 65_536] {
            stored["secret_digest"] = serde_json::json!(vec![0_u8; length]);
            let restored: OAuth2Client = serde_json::from_value(stored.clone()).unwrap();
            assert!(!restored.verify_client_secret(&fixture.client.secret));
            assert!(!restored.verify_client_secret(""));
        }
    }

    #[test]
    fn client_and_pkce_match_language_neutral_contract() {
        let fixture = fixture();
        let client = client(&fixture.client);
        assert!(client.verify_client_secret(&fixture.client.secret));
        assert!(!client.verify_client_secret("wrong-secret"));
        assert!(client.allows_redirect_uri(&fixture.client.redirect_uri));
        assert!(!client.allows_redirect_uri(&fixture.client.invalid_redirect_uri));
        assert!(client.allows_scopes(&fixture.client.scopes));
        assert_eq!(
            generate_code_challenge(&fixture.pkce.verifier),
            fixture.pkce.s256_challenge
        );
        assert!(verify_pkce(
            Some(&fixture.pkce.s256_challenge),
            Some(PkceMethod::S256),
            Some(&fixture.pkce.verifier)
        ));
        assert!(verify_pkce(
            Some(&fixture.pkce.plain_challenge),
            Some(PkceMethod::Plain),
            Some(&fixture.pkce.plain_challenge)
        ));
        assert!(verify_pkce(None, None, Some(&fixture.pkce.verifier)));
    }

    #[test]
    fn authorization_codes_are_bound_expiring_and_single_use() {
        let fixture = fixture();
        let request = authorization_request(&fixture);
        let mut code =
            AuthorizationCode::new(&request, "user-123", fixture.authorization.lifetime_ms)
                .unwrap();
        assert!(code.can_be_used_at(fixture.authorization.consume_at_ms));
        code.consume(
            &fixture.client.client_id,
            &fixture.client.redirect_uri,
            Some(&fixture.pkce.verifier),
            fixture.authorization.consume_at_ms,
        )
        .unwrap();
        assert!(
            code.consume(
                &fixture.client.client_id,
                &fixture.client.redirect_uri,
                Some(&fixture.pkce.verifier),
                fixture.authorization.consume_at_ms
            )
            .is_err()
        );

        let mut expired =
            AuthorizationCode::new(&request, "user-123", fixture.authorization.lifetime_ms)
                .unwrap();
        assert!(
            expired
                .consume(
                    &fixture.client.client_id,
                    &fixture.client.redirect_uri,
                    Some(&fixture.pkce.verifier),
                    fixture.authorization.expired_at_ms
                )
                .is_err()
        );
        let boundary =
            AuthorizationCode::new(&request, "user-123", fixture.authorization.lifetime_ms)
                .unwrap();
        assert!(
            boundary.is_expired_at(
                fixture
                    .authorization
                    .created_at_ms
                    .saturating_add(fixture.authorization.lifetime_ms)
            )
        );
    }

    #[test]
    fn query_parsing_client_profiles_and_response_building_preserve_behavior() {
        let fixture = fixture();
        let request = OAuth2AuthorizationRequest::from_query_params(
            &fixture.oauth_query,
            fixture.authorization.created_at_ms,
        )
        .unwrap();
        assert_eq!(request.client_id, fixture.client.client_id);
        assert_eq!(request.scopes, fixture.client.scopes);
        assert_eq!(request.code_challenge_method, Some(PkceMethod::S256));

        let spa = OAuth2Client::spa(
            "SPA",
            BTreeSet::from([fixture.client.redirect_uri.clone()]),
            BTreeSet::new(),
            1,
        )
        .unwrap();
        assert!(spa.client.requires_pkce());
        assert!(spa.client_secret.is_none());
        assert!(spa.client.verify_client_secret("unused"));
        let service = OAuth2Client::service("service", BTreeSet::new(), 1).unwrap();
        assert!(service.client.redirect_uris.is_empty());
        assert!(
            service
                .client
                .allows_grant_type(OAuth2GrantType::ClientCredentials)
        );
        assert!(!service.client.can_use_refresh_tokens());
        assert!(service.client_secret.is_some());

        let verifier = generate_code_verifier(128).unwrap();
        assert_eq!(verifier.len(), 128);
        assert!(generate_code_verifier(42).is_err());
        let response = OAuth2AuthorizationResponse::success(
            fixture.client.redirect_uri,
            "code with spaces",
            Some(fixture.authorization.state),
        );
        assert!(
            response
                .redirect_url()
                .unwrap()
                .contains("code=code%20with%20spaces")
        );
    }

    #[tokio::test]
    async fn token_lifecycle_and_stores_match_contract() {
        let fixture = fixture();
        let token = OAuth2AccessToken::issue(
            &fixture.client.client_id,
            Some("user-123".into()),
            fixture.client.scopes.clone(),
            fixture.tokens.created_at_ms,
            fixture.tokens.access_lifetime_ms,
        );
        assert!(token.is_active_at(fixture.tokens.active_at_ms));
        assert!(!token.is_active_at(fixture.tokens.expired_at_ms));
        assert_eq!(token.scope_string(), fixture.tokens.scope);
        let refresh = OAuth2RefreshToken::issue(
            &token,
            fixture.tokens.created_at_ms,
            fixture.tokens.refresh_lifetime_ms,
        );
        assert!(refresh.can_be_used_at(fixture.tokens.active_at_ms));

        let store = InMemoryOAuth2Store::default();
        store.save_client(client(&fixture.client)).await.unwrap();
        store.save_access_token(token.clone()).await.unwrap();
        store.save_refresh_token(refresh.clone()).await.unwrap();
        assert_eq!(
            store.access_token(&token.access_token).await.unwrap(),
            Some(token.clone())
        );
        let introspection =
            OAuth2TokenIntrospection::from_access_token(&token, fixture.tokens.active_at_ms);
        assert!(introspection.active);
        let introspection_value = introspection.to_value().unwrap();
        assert_eq!(
            introspection_value.get("sub"),
            Some(&Value::String("user-123".into()))
        );
        assert!(introspection_value.get("exp_seconds").is_none());
        assert_eq!(
            OAuth2TokenIntrospection::from_access_token(&token, fixture.tokens.expired_at_ms)
                .to_value()
                .unwrap(),
            serde_json::json!({"active": false})
        );
        let response = OAuth2TokenResponse::success(
            &token.access_token,
            Some(3_600),
            Some(refresh.refresh_token.clone()),
            Some(token.scope_string()),
            None,
        )
        .to_value()
        .unwrap();
        assert_eq!(response.get("expires_in"), Some(&Value::from(3_600)));
        assert!(response.get("expires_in_seconds").is_none());
        assert_eq!(
            store
                .revoke_for_user("user-123", None, fixture.tokens.active_at_ms)
                .await
                .unwrap(),
            2
        );
        assert!(
            !store
                .access_token(&token.access_token)
                .await
                .unwrap()
                .unwrap()
                .is_active_at(fixture.tokens.active_at_ms)
        );
        assert!(
            store
                .refresh_token_by_id(&refresh.token_id)
                .await
                .unwrap()
                .unwrap()
                .is_revoked()
        );
    }

    #[tokio::test]
    async fn complete_store_ports_preserve_registration_and_lifecycle_features() {
        let fixture = fixture();
        let store = InMemoryOAuth2Store::default();
        let registration = OAuth2ClientRegistration {
            client_name: fixture.client.client_name.clone(),
            application_type: OAuth2ApplicationType::Web,
            redirect_uris: BTreeSet::from([fixture.client.redirect_uri.clone()]),
            allowed_scopes: fixture.client.scopes.clone(),
            client_uri: None,
            logo_uri: None,
            tos_uri: None,
            policy_uri: None,
            require_pkce: true,
            metadata: BTreeMap::new(),
        };
        let issued = store.register_client(&registration, 1).await.unwrap();
        assert!(issued.client_secret.is_some());
        assert!(store.client_exists(&issued.client.client_id).await.unwrap());
        assert_eq!(
            store
                .clients_by_name(&fixture.client.client_name)
                .await
                .unwrap()
                .len(),
            1
        );
        assert!(
            store
                .set_client_active(&issued.client.client_id, false, 2)
                .await
                .unwrap()
        );
        assert!(store.list_active_clients(0, 100).await.unwrap().is_empty());
        let rotated = store
            .regenerate_client_secret(&issued.client.client_id, 3)
            .await
            .unwrap()
            .unwrap();
        assert!(
            store
                .client(&issued.client.client_id)
                .await
                .unwrap()
                .unwrap()
                .verify_client_secret(&rotated)
        );

        let request = authorization_request(&fixture);
        let authorization =
            AuthorizationCode::new(&request, "user-123", fixture.authorization.lifetime_ms)
                .unwrap();
        let authorization_id = authorization.code_id.clone();
        let code = authorization.code.clone();
        store.save_authorization(authorization).await.unwrap();
        assert!(
            store
                .consume_authorization(
                    &code,
                    &fixture.client.client_id,
                    &fixture.client.redirect_uri,
                    Some(&fixture.pkce.verifier),
                    fixture.authorization.consume_at_ms,
                )
                .await
                .unwrap()
        );
        assert!(
            store
                .authorization_by_id(&authorization_id)
                .await
                .unwrap()
                .unwrap()
                .consumed_at_ms
                .is_some()
        );
        assert!(store.delete_authorization(&authorization_id).await.unwrap());
    }

    #[test]
    fn malformed_clients_requests_and_redirects_fail_closed() {
        let fixture = fixture();
        let mut client = client(&fixture.client);
        assert!(
            client
                .replace_redirect_uris(
                    BTreeSet::from([fixture.client.malformed_redirect_uri.clone()]),
                    2,
                )
                .is_err()
        );
        let mut request = authorization_request(&fixture);
        request.code_challenge_method = None;
        assert!(request.validate().is_err());
        let response = OAuth2AuthorizationResponse {
            redirect_uri: "javascript:alert(1)".into(),
            code: Some("code".into()),
            access_token: None,
            token_type: None,
            expires_in_seconds: None,
            state: None,
            error: None,
            error_description: None,
            error_uri: None,
        };
        assert!(response.redirect_url().is_err());
        assert!(
            OAuth2AuthorizationResponse::success(
                "https://client.example/callback#fragment",
                "code",
                None,
            )
            .redirect_url()
            .is_err()
        );
    }
}
