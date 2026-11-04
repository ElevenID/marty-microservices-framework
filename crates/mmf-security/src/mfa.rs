//! Native multi-factor authentication domain and orchestration.
//!
//! The service owns RFC 6238 TOTP, challenge/device lifecycle, one-use backup
//! codes, replay prevention, and rate limiting. Network delivery and hardware,
//! push, and voice verification remain explicit provider ports and fail closed
//! when no provider is configured.

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::sync::Arc;

use async_trait::async_trait;
use hmac::{Hmac, KeyInit, Mac};
use mmf_core::constant_time_secret_eq;
use rand::RngExt as _;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha1::Sha1;
use sha2::{Digest, Sha256, Sha512};
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::SecurityError;
use crate::uri::percent_encode_component;

type HmacSha1 = Hmac<Sha1>;
type HmacSha256 = Hmac<Sha256>;
type HmacSha512 = Hmac<Sha512>;

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MfaMethod {
    Totp,
    Sms,
    Email,
    Push,
    #[serde(rename = "backup")]
    BackupCodes,
    HardwareToken,
    Voice,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MfaChallengeStatus {
    Pending,
    Verified,
    Failed,
    Expired,
    Cancelled,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MfaChallenge {
    pub challenge_id: String,
    pub user_id: String,
    pub method: MfaMethod,
    pub status: MfaChallengeStatus,
    pub created_at_ms: u64,
    pub expires_at_ms: u64,
    pub attempt_count: u32,
    pub max_attempts: u32,
    #[serde(default)]
    pub challenge_data: BTreeMap<String, Value>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl MfaChallenge {
    pub fn new_at(
        user_id: impl Into<String>,
        method: MfaMethod,
        now_ms: u64,
        lifetime_ms: u64,
        max_attempts: u32,
    ) -> Result<Self, SecurityError> {
        let user_id = user_id.into();
        if user_id.trim().is_empty() || lifetime_ms == 0 || max_attempts == 0 {
            return Err(SecurityError::InvalidConfiguration(
                "MFA challenge requires a user, positive lifetime, and positive attempt limit"
                    .into(),
            ));
        }
        Ok(Self {
            challenge_id: format!("mfa_{}", Uuid::new_v4().simple()),
            user_id,
            method,
            status: MfaChallengeStatus::Pending,
            created_at_ms: now_ms,
            expires_at_ms: now_ms.saturating_add(lifetime_ms),
            attempt_count: 0,
            max_attempts,
            challenge_data: BTreeMap::new(),
            metadata: BTreeMap::new(),
        })
    }

    #[must_use]
    pub const fn is_expired_at(&self, now_ms: u64) -> bool {
        now_ms >= self.expires_at_ms
    }

    #[must_use]
    pub const fn can_attempt_at(&self, now_ms: u64) -> bool {
        matches!(self.status, MfaChallengeStatus::Pending)
            && self.attempt_count < self.max_attempts
            && !self.is_expired_at(now_ms)
    }

    pub fn record_failure(&mut self) {
        self.attempt_count = self.attempt_count.saturating_add(1);
        if self.attempt_count >= self.max_attempts {
            self.status = MfaChallengeStatus::Failed;
        }
    }

    pub fn verify(&mut self) -> Result<(), SecurityError> {
        if self.status != MfaChallengeStatus::Pending {
            return Err(SecurityError::Conflict(
                "only pending MFA challenges can be verified".into(),
            ));
        }
        self.status = MfaChallengeStatus::Verified;
        Ok(())
    }

    pub fn cancel(&mut self) -> Result<(), SecurityError> {
        if self.status != MfaChallengeStatus::Pending {
            return Err(SecurityError::Conflict(
                "only pending MFA challenges can be cancelled".into(),
            ));
        }
        self.status = MfaChallengeStatus::Cancelled;
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MfaDeviceType {
    TotpApp,
    SmsPhone,
    Email,
    HardwareToken,
    VoicePhone,
    PushDevice,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MfaDeviceStatus {
    Pending,
    Active,
    Inactive,
    Compromised,
    Revoked,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MfaDevice {
    pub device_id: String,
    pub user_id: String,
    pub device_type: MfaDeviceType,
    pub device_name: String,
    pub status: MfaDeviceStatus,
    pub created_at_ms: u64,
    pub last_used_at_ms: Option<u64>,
    pub verified_at_ms: Option<u64>,
    pub use_count: u64,
    #[serde(default)]
    pub device_data: BTreeMap<String, Value>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl MfaDevice {
    pub fn new_at(
        user_id: impl Into<String>,
        device_type: MfaDeviceType,
        device_name: impl Into<String>,
        now_ms: u64,
    ) -> Result<Self, SecurityError> {
        let user_id = user_id.into();
        let device_name = device_name.into();
        if user_id.trim().is_empty() || device_name.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "MFA device requires a user and display name".into(),
            ));
        }
        Ok(Self {
            device_id: format!("mfa_device_{}", Uuid::new_v4().simple()),
            user_id,
            device_type,
            device_name: device_name.trim().into(),
            status: MfaDeviceStatus::Pending,
            created_at_ms: now_ms,
            last_used_at_ms: None,
            verified_at_ms: None,
            use_count: 0,
            device_data: BTreeMap::new(),
            metadata: BTreeMap::new(),
        })
    }

    #[must_use]
    pub const fn is_verified(&self) -> bool {
        self.verified_at_ms.is_some()
    }

    #[must_use]
    pub const fn can_be_used(&self) -> bool {
        matches!(self.status, MfaDeviceStatus::Active) && self.is_verified()
    }

    pub fn mark_verified_at(&mut self, now_ms: u64) -> Result<(), SecurityError> {
        if self.status != MfaDeviceStatus::Pending {
            return Err(SecurityError::Conflict(
                "only pending MFA devices can be verified".into(),
            ));
        }
        self.status = MfaDeviceStatus::Active;
        self.verified_at_ms = Some(now_ms);
        Ok(())
    }

    pub fn mark_used_at(&mut self, now_ms: u64) -> Result<(), SecurityError> {
        if !self.can_be_used() {
            return Err(SecurityError::Unauthorized(
                "inactive MFA device cannot be used".into(),
            ));
        }
        self.last_used_at_ms = Some(now_ms);
        self.use_count = self.use_count.saturating_add(1);
        Ok(())
    }

    pub fn rename(&mut self, name: impl Into<String>) -> Result<(), SecurityError> {
        let name = name.into();
        if name.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "MFA device name cannot be empty".into(),
            ));
        }
        self.device_name = name.trim().into();
        Ok(())
    }

    pub fn set_status(&mut self, status: MfaDeviceStatus) -> Result<(), SecurityError> {
        if status == MfaDeviceStatus::Active && !self.is_verified() {
            return Err(SecurityError::Conflict(
                "unverified MFA device cannot be activated".into(),
            ));
        }
        if self.status == MfaDeviceStatus::Revoked && status != MfaDeviceStatus::Revoked {
            return Err(SecurityError::Conflict(
                "revoked MFA device cannot be reactivated".into(),
            ));
        }
        self.status = status;
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MfaVerification {
    pub challenge_id: String,
    pub device_id: Option<String>,
    pub verification_code: Option<String>,
    pub backup_code: Option<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
    pub timestamp_ms: u64,
}

impl MfaVerification {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.challenge_id.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "MFA challenge id is required".into(),
            ));
        }
        match (&self.verification_code, &self.backup_code) {
            (Some(code), None) if !code.is_empty() && self.device_id.is_some() => Ok(()),
            (None, Some(code)) if !code.is_empty() => Ok(()),
            (Some(_), Some(_)) => Err(SecurityError::InvalidConfiguration(
                "verification and backup codes are mutually exclusive".into(),
            )),
            _ => Err(SecurityError::InvalidConfiguration(
                "MFA verification requires a code and device, or a backup code".into(),
            )),
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MfaVerificationResult {
    Success,
    InvalidCode,
    Expired,
    DeviceInactive,
    TooManyAttempts,
    UnknownChallenge,
    UnknownDevice,
    MethodMismatch,
    SystemError,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MfaVerificationResponse {
    pub challenge_id: String,
    pub result: MfaVerificationResult,
    pub success: bool,
    pub error_message: Option<String>,
    pub remaining_attempts: Option<u32>,
    pub device_id: Option<String>,
    pub verified_at_ms: u64,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl MfaVerificationResponse {
    fn success(challenge_id: String, device_id: Option<String>, now_ms: u64) -> Self {
        Self {
            challenge_id,
            result: MfaVerificationResult::Success,
            success: true,
            error_message: None,
            remaining_attempts: None,
            device_id,
            verified_at_ms: now_ms,
            metadata: BTreeMap::new(),
        }
    }

    fn failure(
        challenge_id: String,
        result: MfaVerificationResult,
        message: impl Into<String>,
        remaining_attempts: Option<u32>,
        device_id: Option<String>,
        now_ms: u64,
    ) -> Self {
        Self {
            challenge_id,
            result,
            success: false,
            error_message: Some(message.into()),
            remaining_attempts,
            device_id,
            verified_at_ms: now_ms,
            metadata: BTreeMap::new(),
        }
    }

    #[must_use]
    pub const fn is_retriable(&self) -> bool {
        matches!(
            self.result,
            MfaVerificationResult::InvalidCode | MfaVerificationResult::SystemError
        )
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum TotpAlgorithm {
    Sha1,
    Sha256,
    Sha512,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct TotpConfig {
    pub issuer: String,
    pub period_seconds: u64,
    pub digits: u32,
    pub algorithm: TotpAlgorithm,
    pub window: u32,
    pub max_devices_per_user: usize,
    pub challenge_lifetime_ms: u64,
    pub backup_codes_count: usize,
    pub rate_limit_window_ms: u64,
    pub max_attempts_per_window: usize,
}

impl Default for TotpConfig {
    fn default() -> Self {
        Self {
            issuer: "MMF Identity Service".into(),
            period_seconds: 30,
            digits: 6,
            algorithm: TotpAlgorithm::Sha1,
            window: 1,
            max_devices_per_user: 5,
            challenge_lifetime_ms: 300_000,
            backup_codes_count: 8,
            rate_limit_window_ms: 60_000,
            max_attempts_per_window: 5,
        }
    }
}

impl TotpConfig {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.issuer.trim().is_empty()
            || self.period_seconds == 0
            || !(6..=10).contains(&self.digits)
            || self.max_devices_per_user == 0
            || self.challenge_lifetime_ms == 0
            || self.backup_codes_count == 0
            || self.rate_limit_window_ms == 0
            || self.max_attempts_per_window == 0
        {
            return Err(SecurityError::InvalidConfiguration(
                "invalid TOTP configuration".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct DeliveredCodeConfig {
    pub code_length: usize,
    pub challenge_lifetime_ms: u64,
    pub max_devices_per_user: usize,
    pub max_attempts: u32,
}

impl DeliveredCodeConfig {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if !(4..=12).contains(&self.code_length)
            || self.challenge_lifetime_ms == 0
            || self.max_devices_per_user == 0
            || self.max_attempts == 0
        {
            return Err(SecurityError::InvalidConfiguration(
                "invalid delivered-code MFA configuration".into(),
            ));
        }
        Ok(())
    }
}

impl Default for DeliveredCodeConfig {
    fn default() -> Self {
        Self {
            code_length: 6,
            challenge_lifetime_ms: 300_000,
            max_devices_per_user: 3,
            max_attempts: 3,
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct MfaConfig {
    pub totp: TotpConfig,
    pub sms: DeliveredCodeConfig,
    pub email: DeliveredCodeConfig,
}

impl Default for MfaConfig {
    fn default() -> Self {
        Self {
            totp: TotpConfig::default(),
            sms: DeliveredCodeConfig::default(),
            email: DeliveredCodeConfig {
                code_length: 8,
                challenge_lifetime_ms: 600_000,
                ..DeliveredCodeConfig::default()
            },
        }
    }
}

impl MfaConfig {
    pub fn validate(&self) -> Result<(), SecurityError> {
        self.totp.validate()?;
        self.sms.validate()?;
        self.email.validate()
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct AuthenticationContext {
    pub ip_address: Option<String>,
    pub user_agent: Option<String>,
    pub session_id: Option<String>,
    pub correlation_id: Option<String>,
    #[serde(default)]
    pub attributes: BTreeMap<String, Value>,
}

#[async_trait]
pub trait CodeDeliveryProvider: Send + Sync {
    async fn deliver(
        &self,
        method: MfaMethod,
        destination: &str,
        code: &str,
        context: Option<&AuthenticationContext>,
    ) -> Result<(), SecurityError>;
}

#[async_trait]
pub trait ExternalMfaMethodProvider: Send + Sync {
    async fn create_challenge(
        &self,
        user_id: &str,
        method: MfaMethod,
        now_ms: u64,
        metadata: &BTreeMap<String, Value>,
    ) -> Result<MfaChallenge, SecurityError>;

    async fn verify_challenge(
        &self,
        verification: &MfaVerification,
        now_ms: u64,
    ) -> Result<MfaVerificationResponse, SecurityError>;

    async fn register_device(
        &self,
        user_id: &str,
        device_type: MfaDeviceType,
        device_name: &str,
        device_data: &BTreeMap<String, Value>,
        now_ms: u64,
    ) -> Result<MfaDevice, SecurityError>;
}

#[async_trait]
pub trait MfaProvider: Send + Sync {
    fn supported_methods(&self) -> BTreeSet<MfaMethod>;
    fn supported_device_types(&self) -> BTreeSet<MfaDeviceType>;

    async fn create_challenge(
        &self,
        user_id: &str,
        method: MfaMethod,
        device_id: Option<&str>,
        metadata: BTreeMap<String, Value>,
        now_ms: u64,
        context: Option<&AuthenticationContext>,
    ) -> Result<MfaChallenge, SecurityError>;

    async fn verify_challenge(
        &self,
        verification: &MfaVerification,
        now_ms: u64,
    ) -> Result<MfaVerificationResponse, SecurityError>;

    async fn register_device(
        &self,
        user_id: &str,
        device_type: MfaDeviceType,
        device_name: &str,
        device_data: BTreeMap<String, Value>,
        now_ms: u64,
        context: Option<&AuthenticationContext>,
    ) -> Result<MfaDevice, SecurityError>;

    async fn verify_device(
        &self,
        device_id: &str,
        verification_code: &str,
        now_ms: u64,
    ) -> Result<MfaDevice, SecurityError>;

    async fn get_user_devices(&self, user_id: &str, include_inactive: bool) -> Vec<MfaDevice>;
    async fn get_device(&self, device_id: &str) -> Result<MfaDevice, SecurityError>;
    async fn update_device(
        &self,
        device_id: &str,
        device_name: Option<&str>,
        status: Option<MfaDeviceStatus>,
    ) -> Result<MfaDevice, SecurityError>;
    async fn revoke_device(&self, device_id: &str) -> Result<bool, SecurityError>;
    async fn generate_backup_codes(
        &self,
        user_id: &str,
        count: Option<usize>,
    ) -> Result<Vec<String>, SecurityError>;
    async fn verify_backup_code(&self, user_id: &str, backup_code: &str) -> bool;
    async fn get_challenge(&self, challenge_id: &str) -> Result<MfaChallenge, SecurityError>;
    async fn cleanup_expired_challenges(&self, now_ms: u64) -> usize;
}

#[derive(Default)]
struct MfaState {
    devices: BTreeMap<String, MfaDevice>,
    challenges: BTreeMap<String, MfaChallenge>,
    challenge_code_hashes: BTreeMap<String, Vec<u8>>,
    backup_code_hashes: BTreeMap<String, BTreeSet<Vec<u8>>>,
    used_totp_codes: BTreeMap<String, VecDeque<(u64, String)>>,
    attempts: BTreeMap<String, VecDeque<u64>>,
}

pub struct NativeMfaService {
    config: MfaConfig,
    delivery: Option<Arc<dyn CodeDeliveryProvider>>,
    external: BTreeMap<MfaMethod, Arc<dyn ExternalMfaMethodProvider>>,
    state: RwLock<MfaState>,
}

impl NativeMfaService {
    pub fn new(
        config: MfaConfig,
        delivery: Option<Arc<dyn CodeDeliveryProvider>>,
        external: BTreeMap<MfaMethod, Arc<dyn ExternalMfaMethodProvider>>,
    ) -> Result<Self, SecurityError> {
        config.validate()?;
        Ok(Self {
            config,
            delivery,
            external,
            state: RwLock::new(MfaState::default()),
        })
    }

    #[must_use]
    pub fn supported_methods(&self) -> BTreeSet<MfaMethod> {
        let mut methods = BTreeSet::from([MfaMethod::Totp, MfaMethod::BackupCodes]);
        if self.delivery.is_some() {
            methods.extend([MfaMethod::Sms, MfaMethod::Email]);
        }
        methods.extend(self.external.keys().copied());
        methods
    }

    #[must_use]
    pub fn supported_device_types(&self) -> BTreeSet<MfaDeviceType> {
        let mut types = BTreeSet::from([MfaDeviceType::TotpApp]);
        if self.delivery.is_some() {
            types.extend([MfaDeviceType::SmsPhone, MfaDeviceType::Email]);
        }
        for method in self.external.keys() {
            match method {
                MfaMethod::Push => {
                    types.insert(MfaDeviceType::PushDevice);
                }
                MfaMethod::HardwareToken => {
                    types.insert(MfaDeviceType::HardwareToken);
                }
                MfaMethod::Voice => {
                    types.insert(MfaDeviceType::VoicePhone);
                }
                _ => {}
            }
        }
        types
    }

    pub async fn register_device(
        &self,
        user_id: &str,
        device_type: MfaDeviceType,
        device_name: &str,
        mut device_data: BTreeMap<String, Value>,
        now_ms: u64,
        context: Option<&AuthenticationContext>,
    ) -> Result<MfaDevice, SecurityError> {
        if let Some(method) = external_method_for_device(device_type) {
            let provider = self.external.get(&method).ok_or_else(|| {
                SecurityError::ProviderUnavailable(format!("{method:?} MFA provider"))
            })?;
            return provider
                .register_device(user_id, device_type, device_name, &device_data, now_ms)
                .await;
        }

        let (limit, enrollment_code) = match device_type {
            MfaDeviceType::TotpApp => {
                device_data
                    .entry("secret".into())
                    .or_insert_with(|| Value::String(generate_totp_secret()));
                device_data.insert(
                    "algorithm".into(),
                    Value::String(format!("{:?}", self.config.totp.algorithm).to_uppercase()),
                );
                device_data.insert("period".into(), self.config.totp.period_seconds.into());
                device_data.insert("digits".into(), self.config.totp.digits.into());
                (self.config.totp.max_devices_per_user, None)
            }
            MfaDeviceType::SmsPhone => (
                self.config.sms.max_devices_per_user,
                Some(generate_numeric_code(self.config.sms.code_length)),
            ),
            MfaDeviceType::Email => (
                self.config.email.max_devices_per_user,
                Some(generate_numeric_code(self.config.email.code_length)),
            ),
            _ => unreachable!("external device types returned above"),
        };

        let existing = self
            .state
            .read()
            .await
            .devices
            .values()
            .filter(|device| device.user_id == user_id && device.device_type == device_type)
            .count();
        if existing >= limit {
            return Err(SecurityError::Conflict(format!(
                "user reached the {limit} device limit"
            )));
        }

        let destination = if enrollment_code.is_some() {
            let destination = device_destination(device_type, &device_data)?;
            let valid = match device_type {
                MfaDeviceType::SmsPhone => validate_phone_number(destination),
                MfaDeviceType::Email => validate_email_address(destination),
                _ => true,
            };
            if !valid {
                return Err(SecurityError::InvalidConfiguration(
                    "invalid MFA delivery destination".into(),
                ));
            }
            Some(destination.to_owned())
        } else {
            None
        };
        let mut device = MfaDevice::new_at(user_id, device_type, device_name, now_ms)?;
        device.device_data = device_data;
        if let (Some(code), Some(destination)) = (&enrollment_code, destination.as_deref()) {
            self.delivery
                .as_ref()
                .ok_or_else(|| SecurityError::ProviderUnavailable("MFA code delivery".into()))?
                .deliver(method_for_device(device_type), destination, code, context)
                .await?;
            device.device_data.insert(
                "enrollment_code_hash".into(),
                Value::String(hex(&hash_code(code))),
            );
        }
        self.state
            .write()
            .await
            .devices
            .insert(device.device_id.clone(), device.clone());
        Ok(device)
    }

    pub async fn verify_device(
        &self,
        device_id: &str,
        verification_code: &str,
        now_ms: u64,
    ) -> Result<MfaDevice, SecurityError> {
        let mut state = self.state.write().await;
        let device = state
            .devices
            .get_mut(device_id)
            .ok_or_else(|| SecurityError::NotFound(format!("MFA device {device_id}")))?;
        if device.status != MfaDeviceStatus::Pending {
            return Err(SecurityError::Conflict(
                "MFA device is not pending verification".into(),
            ));
        }
        let valid = match device.device_type {
            MfaDeviceType::TotpApp => {
                let secret = string_field(&device.device_data, "secret")?;
                verify_totp_at(&self.config.totp, secret, verification_code, now_ms)?
            }
            MfaDeviceType::SmsPhone | MfaDeviceType::Email => {
                let expected = string_field(&device.device_data, "enrollment_code_hash")?;
                constant_time_secret_eq(
                    expected.as_bytes(),
                    hex(&hash_code(verification_code)).as_bytes(),
                )
            }
            _ => {
                return Err(SecurityError::ProviderUnavailable(
                    "external MFA device verification must use its native provider".into(),
                ));
            }
        };
        if !valid {
            return Err(SecurityError::Unauthorized(
                "invalid MFA device verification code".into(),
            ));
        }
        device.device_data.remove("enrollment_code_hash");
        device.mark_verified_at(now_ms)?;
        Ok(device.clone())
    }

    pub async fn create_challenge(
        &self,
        user_id: &str,
        method: MfaMethod,
        device_id: Option<&str>,
        metadata: BTreeMap<String, Value>,
        now_ms: u64,
        context: Option<&AuthenticationContext>,
    ) -> Result<MfaChallenge, SecurityError> {
        if matches!(
            method,
            MfaMethod::Push | MfaMethod::HardwareToken | MfaMethod::Voice
        ) {
            let provider = self.external.get(&method).ok_or_else(|| {
                SecurityError::ProviderUnavailable(format!("{method:?} MFA provider"))
            })?;
            return provider
                .create_challenge(user_id, method, now_ms, &metadata)
                .await;
        }

        let (lifetime, max_attempts) = match method {
            MfaMethod::Totp | MfaMethod::BackupCodes => (self.config.totp.challenge_lifetime_ms, 3),
            MfaMethod::Sms => (
                self.config.sms.challenge_lifetime_ms,
                self.config.sms.max_attempts,
            ),
            MfaMethod::Email => (
                self.config.email.challenge_lifetime_ms,
                self.config.email.max_attempts,
            ),
            _ => unreachable!("external methods returned above"),
        };
        let mut challenge = MfaChallenge::new_at(user_id, method, now_ms, lifetime, max_attempts)?;
        challenge.metadata = metadata;
        if let Some(device_id) = device_id {
            challenge
                .challenge_data
                .insert("device_id".into(), Value::String(device_id.into()));
        }

        let mut generated_code = None;
        let mut destination: Option<String> = None;
        if matches!(method, MfaMethod::Totp | MfaMethod::Sms | MfaMethod::Email) {
            let device_id = device_id.ok_or_else(|| {
                SecurityError::InvalidConfiguration(format!(
                    "{method:?} challenge requires an MFA device"
                ))
            })?;
            let state = self.state.read().await;
            let device = state
                .devices
                .get(device_id)
                .ok_or_else(|| SecurityError::NotFound(format!("MFA device {device_id}")))?;
            if device.user_id != user_id || !device.can_be_used() {
                return Err(SecurityError::Unauthorized(
                    "MFA device is inactive or belongs to another user".into(),
                ));
            }
            if method_for_device(device.device_type) != method {
                return Err(SecurityError::InvalidConfiguration(
                    "MFA method does not match device type".into(),
                ));
            }
            if matches!(method, MfaMethod::Sms | MfaMethod::Email) {
                let config = if method == MfaMethod::Sms {
                    &self.config.sms
                } else {
                    &self.config.email
                };
                generated_code = Some(generate_numeric_code(config.code_length));
                destination =
                    Some(device_destination(device.device_type, &device.device_data)?.to_owned());
            }
        }

        if let (Some(code), Some(destination)) = (&generated_code, destination.as_deref()) {
            self.delivery
                .as_ref()
                .ok_or_else(|| SecurityError::ProviderUnavailable("MFA code delivery".into()))?
                .deliver(method, destination, code, context)
                .await?;
        }
        let mut state = self.state.write().await;
        if let Some(code) = generated_code {
            state
                .challenge_code_hashes
                .insert(challenge.challenge_id.clone(), hash_code(&code));
        }
        state
            .challenges
            .insert(challenge.challenge_id.clone(), challenge.clone());
        Ok(challenge)
    }

    pub async fn verify_challenge(
        &self,
        verification: &MfaVerification,
        now_ms: u64,
    ) -> Result<MfaVerificationResponse, SecurityError> {
        verification.validate()?;
        let method = self
            .state
            .read()
            .await
            .challenges
            .get(&verification.challenge_id)
            .map(|challenge| challenge.method);
        if let Some(method @ (MfaMethod::Push | MfaMethod::HardwareToken | MfaMethod::Voice)) =
            method
        {
            let provider = self.external.get(&method).ok_or_else(|| {
                SecurityError::ProviderUnavailable(format!("{method:?} MFA provider"))
            })?;
            return provider.verify_challenge(verification, now_ms).await;
        }

        let mut state = self.state.write().await;
        let Some(mut challenge) = state.challenges.remove(&verification.challenge_id) else {
            return Ok(MfaVerificationResponse::failure(
                verification.challenge_id.clone(),
                MfaVerificationResult::UnknownChallenge,
                "MFA challenge was not found",
                None,
                verification.device_id.clone(),
                now_ms,
            ));
        };
        let response = self.verify_locked(&mut state, &mut challenge, verification, now_ms)?;
        state
            .challenges
            .insert(challenge.challenge_id.clone(), challenge);
        Ok(response)
    }

    fn verify_locked(
        &self,
        state: &mut MfaState,
        challenge: &mut MfaChallenge,
        verification: &MfaVerification,
        now_ms: u64,
    ) -> Result<MfaVerificationResponse, SecurityError> {
        if challenge.is_expired_at(now_ms) {
            challenge.status = MfaChallengeStatus::Expired;
            return Ok(MfaVerificationResponse::failure(
                challenge.challenge_id.clone(),
                MfaVerificationResult::Expired,
                "MFA challenge expired",
                None,
                verification.device_id.clone(),
                now_ms,
            ));
        }
        if !challenge.can_attempt_at(now_ms) {
            return Ok(MfaVerificationResponse::failure(
                challenge.challenge_id.clone(),
                MfaVerificationResult::TooManyAttempts,
                "MFA challenge cannot be attempted",
                Some(0),
                verification.device_id.clone(),
                now_ms,
            ));
        }

        let valid = if let Some(backup_code) = &verification.backup_code {
            if challenge.method != MfaMethod::BackupCodes && challenge.method != MfaMethod::Totp {
                return Ok(method_mismatch(challenge, verification, now_ms));
            }
            consume_backup_code(state, &challenge.user_id, backup_code)
        } else {
            let device_id = verification.device_id.as_deref().ok_or_else(|| {
                SecurityError::InvalidConfiguration("MFA device id is required".into())
            })?;
            let Some(device) = state.devices.get(device_id).cloned() else {
                return Ok(MfaVerificationResponse::failure(
                    challenge.challenge_id.clone(),
                    MfaVerificationResult::UnknownDevice,
                    "MFA device was not found",
                    None,
                    Some(device_id.into()),
                    now_ms,
                ));
            };
            if !device.can_be_used() {
                return Ok(MfaVerificationResponse::failure(
                    challenge.challenge_id.clone(),
                    MfaVerificationResult::DeviceInactive,
                    "MFA device is inactive",
                    None,
                    Some(device_id.into()),
                    now_ms,
                ));
            }
            if method_for_device(device.device_type) != challenge.method {
                return Ok(method_mismatch(challenge, verification, now_ms));
            }
            let code = verification
                .verification_code
                .as_deref()
                .unwrap_or_default();
            if challenge.method == MfaMethod::Totp
                && enforce_rate_limit(state, &challenge.user_id, &self.config.totp, now_ms).is_err()
            {
                return Ok(MfaVerificationResponse::failure(
                    challenge.challenge_id.clone(),
                    MfaVerificationResult::TooManyAttempts,
                    "MFA verification rate limit exceeded",
                    Some(0),
                    Some(device_id.into()),
                    now_ms,
                ));
            }
            match challenge.method {
                MfaMethod::Totp => {
                    let secret = string_field(&device.device_data, "secret")?;
                    let valid = verify_totp_at(&self.config.totp, secret, code, now_ms)?;
                    if valid && totp_was_used(state, device_id, code, now_ms, &self.config.totp) {
                        false
                    } else {
                        valid
                    }
                }
                MfaMethod::Sms | MfaMethod::Email => state
                    .challenge_code_hashes
                    .get(&challenge.challenge_id)
                    .is_some_and(|expected| constant_time_secret_eq(expected, &hash_code(code))),
                _ => false,
            }
        };

        finish_verification(state, challenge, verification, now_ms, valid)
    }

    pub async fn get_device(&self, device_id: &str) -> Result<MfaDevice, SecurityError> {
        self.state
            .read()
            .await
            .devices
            .get(device_id)
            .cloned()
            .ok_or_else(|| SecurityError::NotFound(format!("MFA device {device_id}")))
    }

    pub async fn get_user_devices(&self, user_id: &str, include_inactive: bool) -> Vec<MfaDevice> {
        self.state
            .read()
            .await
            .devices
            .values()
            .filter(|device| {
                device.user_id == user_id && (include_inactive || device.can_be_used())
            })
            .cloned()
            .collect()
    }

    pub async fn update_device(
        &self,
        device_id: &str,
        device_name: Option<&str>,
        status: Option<MfaDeviceStatus>,
    ) -> Result<MfaDevice, SecurityError> {
        let mut state = self.state.write().await;
        let device = state
            .devices
            .get_mut(device_id)
            .ok_or_else(|| SecurityError::NotFound(format!("MFA device {device_id}")))?;
        if let Some(device_name) = device_name {
            device.rename(device_name)?;
        }
        if let Some(status) = status {
            device.set_status(status)?;
        }
        Ok(device.clone())
    }

    pub async fn revoke_device(&self, device_id: &str) -> Result<bool, SecurityError> {
        let mut state = self.state.write().await;
        let device = state
            .devices
            .get_mut(device_id)
            .ok_or_else(|| SecurityError::NotFound(format!("MFA device {device_id}")))?;
        device.set_status(MfaDeviceStatus::Revoked)?;
        state.used_totp_codes.remove(device_id);
        Ok(true)
    }

    pub async fn generate_backup_codes(
        &self,
        user_id: &str,
        count: Option<usize>,
    ) -> Result<Vec<String>, SecurityError> {
        if user_id.trim().is_empty() {
            return Err(SecurityError::InvalidConfiguration(
                "backup codes require a user".into(),
            ));
        }
        let count = count.unwrap_or(self.config.totp.backup_codes_count);
        if count == 0 || count > 100 {
            return Err(SecurityError::InvalidConfiguration(
                "backup code count must be between 1 and 100".into(),
            ));
        }
        let codes: Vec<_> = (0..count).map(|_| generate_backup_code()).collect();
        let hashes = codes.iter().map(|code| hash_code(code)).collect();
        self.state
            .write()
            .await
            .backup_code_hashes
            .insert(user_id.into(), hashes);
        Ok(codes)
    }

    pub async fn verify_backup_code(&self, user_id: &str, backup_code: &str) -> bool {
        let mut state = self.state.write().await;
        consume_backup_code(&mut state, user_id, backup_code)
    }

    pub async fn get_challenge(&self, challenge_id: &str) -> Result<MfaChallenge, SecurityError> {
        self.state
            .read()
            .await
            .challenges
            .get(challenge_id)
            .cloned()
            .ok_or_else(|| SecurityError::NotFound(format!("MFA challenge {challenge_id}")))
    }

    pub async fn cleanup_expired_challenges(&self, now_ms: u64) -> usize {
        let mut state = self.state.write().await;
        let expired: Vec<_> = state
            .challenges
            .iter()
            .filter(|(_, challenge)| challenge.is_expired_at(now_ms))
            .map(|(id, _)| id.clone())
            .collect();
        for id in &expired {
            state.challenges.remove(id);
            state.challenge_code_hashes.remove(id);
        }
        expired.len()
    }

    #[must_use]
    pub fn totp_setup_uri(&self, secret: &str, user_identifier: &str) -> String {
        let issuer = percent_encode_component(&self.config.totp.issuer);
        let user = percent_encode_component(user_identifier);
        format!(
            "otpauth://totp/{issuer}:{user}?secret={secret}&issuer={issuer}&algorithm={algorithm:?}&digits={digits}&period={period}",
            algorithm = self.config.totp.algorithm,
            digits = self.config.totp.digits,
            period = self.config.totp.period_seconds
        )
    }
}

#[async_trait]
impl MfaProvider for NativeMfaService {
    fn supported_methods(&self) -> BTreeSet<MfaMethod> {
        Self::supported_methods(self)
    }

    fn supported_device_types(&self) -> BTreeSet<MfaDeviceType> {
        Self::supported_device_types(self)
    }

    async fn create_challenge(
        &self,
        user_id: &str,
        method: MfaMethod,
        device_id: Option<&str>,
        metadata: BTreeMap<String, Value>,
        now_ms: u64,
        context: Option<&AuthenticationContext>,
    ) -> Result<MfaChallenge, SecurityError> {
        Self::create_challenge(self, user_id, method, device_id, metadata, now_ms, context).await
    }

    async fn verify_challenge(
        &self,
        verification: &MfaVerification,
        now_ms: u64,
    ) -> Result<MfaVerificationResponse, SecurityError> {
        Self::verify_challenge(self, verification, now_ms).await
    }

    async fn register_device(
        &self,
        user_id: &str,
        device_type: MfaDeviceType,
        device_name: &str,
        device_data: BTreeMap<String, Value>,
        now_ms: u64,
        context: Option<&AuthenticationContext>,
    ) -> Result<MfaDevice, SecurityError> {
        Self::register_device(
            self,
            user_id,
            device_type,
            device_name,
            device_data,
            now_ms,
            context,
        )
        .await
    }

    async fn verify_device(
        &self,
        device_id: &str,
        verification_code: &str,
        now_ms: u64,
    ) -> Result<MfaDevice, SecurityError> {
        Self::verify_device(self, device_id, verification_code, now_ms).await
    }

    async fn get_user_devices(&self, user_id: &str, include_inactive: bool) -> Vec<MfaDevice> {
        Self::get_user_devices(self, user_id, include_inactive).await
    }

    async fn get_device(&self, device_id: &str) -> Result<MfaDevice, SecurityError> {
        Self::get_device(self, device_id).await
    }

    async fn update_device(
        &self,
        device_id: &str,
        device_name: Option<&str>,
        status: Option<MfaDeviceStatus>,
    ) -> Result<MfaDevice, SecurityError> {
        Self::update_device(self, device_id, device_name, status).await
    }

    async fn revoke_device(&self, device_id: &str) -> Result<bool, SecurityError> {
        Self::revoke_device(self, device_id).await
    }

    async fn generate_backup_codes(
        &self,
        user_id: &str,
        count: Option<usize>,
    ) -> Result<Vec<String>, SecurityError> {
        Self::generate_backup_codes(self, user_id, count).await
    }

    async fn verify_backup_code(&self, user_id: &str, backup_code: &str) -> bool {
        Self::verify_backup_code(self, user_id, backup_code).await
    }

    async fn get_challenge(&self, challenge_id: &str) -> Result<MfaChallenge, SecurityError> {
        Self::get_challenge(self, challenge_id).await
    }

    async fn cleanup_expired_challenges(&self, now_ms: u64) -> usize {
        Self::cleanup_expired_challenges(self, now_ms).await
    }
}

fn external_method_for_device(device_type: MfaDeviceType) -> Option<MfaMethod> {
    match device_type {
        MfaDeviceType::HardwareToken => Some(MfaMethod::HardwareToken),
        MfaDeviceType::VoicePhone => Some(MfaMethod::Voice),
        MfaDeviceType::PushDevice => Some(MfaMethod::Push),
        _ => None,
    }
}

const fn method_for_device(device_type: MfaDeviceType) -> MfaMethod {
    match device_type {
        MfaDeviceType::TotpApp => MfaMethod::Totp,
        MfaDeviceType::SmsPhone => MfaMethod::Sms,
        MfaDeviceType::Email => MfaMethod::Email,
        MfaDeviceType::HardwareToken => MfaMethod::HardwareToken,
        MfaDeviceType::VoicePhone => MfaMethod::Voice,
        MfaDeviceType::PushDevice => MfaMethod::Push,
    }
}

fn device_destination(
    device_type: MfaDeviceType,
    data: &BTreeMap<String, Value>,
) -> Result<&str, SecurityError> {
    match device_type {
        MfaDeviceType::SmsPhone => string_field(data, "phone_number"),
        MfaDeviceType::Email => string_field(data, "email_address"),
        _ => Err(SecurityError::InvalidConfiguration(
            "device type has no code-delivery destination".into(),
        )),
    }
}

fn string_field<'a>(
    values: &'a BTreeMap<String, Value>,
    name: &str,
) -> Result<&'a str, SecurityError> {
    values
        .get(name)
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| SecurityError::InvalidConfiguration(format!("MFA device requires {name}")))
}

fn method_mismatch(
    challenge: &MfaChallenge,
    verification: &MfaVerification,
    now_ms: u64,
) -> MfaVerificationResponse {
    MfaVerificationResponse::failure(
        challenge.challenge_id.clone(),
        MfaVerificationResult::MethodMismatch,
        "verification method does not match MFA challenge",
        None,
        verification.device_id.clone(),
        now_ms,
    )
}

fn finish_verification(
    state: &mut MfaState,
    challenge: &mut MfaChallenge,
    verification: &MfaVerification,
    now_ms: u64,
    valid: bool,
) -> Result<MfaVerificationResponse, SecurityError> {
    if valid {
        challenge.verify()?;
        state.challenge_code_hashes.remove(&challenge.challenge_id);
        if let Some(device_id) = &verification.device_id
            && let Some(device) = state.devices.get_mut(device_id)
        {
            device.mark_used_at(now_ms)?;
        }
        Ok(MfaVerificationResponse::success(
            challenge.challenge_id.clone(),
            verification.device_id.clone(),
            now_ms,
        ))
    } else {
        challenge.record_failure();
        let remaining = challenge
            .max_attempts
            .saturating_sub(challenge.attempt_count);
        Ok(MfaVerificationResponse::failure(
            challenge.challenge_id.clone(),
            MfaVerificationResult::InvalidCode,
            "invalid MFA verification code",
            Some(remaining),
            verification.device_id.clone(),
            now_ms,
        ))
    }
}

fn enforce_rate_limit(
    state: &mut MfaState,
    user_id: &str,
    config: &TotpConfig,
    now_ms: u64,
) -> Result<(), SecurityError> {
    let attempts = state.attempts.entry(user_id.into()).or_default();
    while attempts
        .front()
        .is_some_and(|attempt| attempt.saturating_add(config.rate_limit_window_ms) < now_ms)
    {
        attempts.pop_front();
    }
    if attempts.len() >= config.max_attempts_per_window {
        return Err(SecurityError::Unauthorized(
            "MFA verification rate limit exceeded".into(),
        ));
    }
    attempts.push_back(now_ms);
    Ok(())
}

fn totp_was_used(
    state: &mut MfaState,
    device_id: &str,
    code: &str,
    now_ms: u64,
    config: &TotpConfig,
) -> bool {
    let retention_ms = config
        .period_seconds
        .saturating_mul(u64::from(config.window).saturating_add(2))
        .saturating_mul(1_000);
    let used = state.used_totp_codes.entry(device_id.into()).or_default();
    while used
        .front()
        .is_some_and(|(used_at, _)| used_at.saturating_add(retention_ms) < now_ms)
    {
        used.pop_front();
    }
    if used.iter().any(|(_, used_code)| used_code == code) {
        true
    } else {
        used.push_back((now_ms, code.into()));
        false
    }
}

fn consume_backup_code(state: &mut MfaState, user_id: &str, code: &str) -> bool {
    let candidate = hash_code(code);
    state
        .backup_code_hashes
        .get_mut(user_id)
        .is_some_and(|codes| codes.remove(&candidate))
}

#[must_use]
pub fn generate_numeric_code(length: usize) -> String {
    let mut rng = rand::rng();
    (0..length)
        .map(|_| char::from(b'0' + rng.random_range(0..10)))
        .collect()
}

#[must_use]
pub fn generate_backup_code() -> String {
    const ALPHABET: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    let mut rng = rand::rng();
    let raw: String = (0..8)
        .map(|_| char::from(ALPHABET[rng.random_range(0..ALPHABET.len())]))
        .collect();
    format!("{}-{}", &raw[..4], &raw[4..])
}

#[must_use]
pub fn generate_totp_secret() -> String {
    let mut bytes = [0_u8; 20];
    rand::rng().fill(&mut bytes);
    base32_encode(&bytes)
}

pub fn verify_totp_at(
    config: &TotpConfig,
    secret: &str,
    code: &str,
    now_ms: u64,
) -> Result<bool, SecurityError> {
    config.validate()?;
    if code.len() != config.digits as usize || !code.bytes().all(|byte| byte.is_ascii_digit()) {
        return Ok(false);
    }
    let counter = now_ms / 1_000 / config.period_seconds;
    for offset in -(i64::from(config.window))..=i64::from(config.window) {
        let candidate_counter = counter.saturating_add_signed(offset);
        let expected = generate_totp(config, secret, candidate_counter)?;
        if constant_time_secret_eq(expected.as_bytes(), code.as_bytes()) {
            return Ok(true);
        }
    }
    Ok(false)
}

pub fn generate_totp(
    config: &TotpConfig,
    secret: &str,
    counter: u64,
) -> Result<String, SecurityError> {
    config.validate()?;
    let secret = base32_decode(secret)?;
    let counter = counter.to_be_bytes();
    let digest = match config.algorithm {
        TotpAlgorithm::Sha1 => {
            let mut mac = HmacSha1::new_from_slice(&secret)
                .map_err(|_| SecurityError::InvalidConfiguration("invalid TOTP secret".into()))?;
            mac.update(&counter);
            mac.finalize().into_bytes().to_vec()
        }
        TotpAlgorithm::Sha256 => {
            let mut mac = HmacSha256::new_from_slice(&secret)
                .map_err(|_| SecurityError::InvalidConfiguration("invalid TOTP secret".into()))?;
            mac.update(&counter);
            mac.finalize().into_bytes().to_vec()
        }
        TotpAlgorithm::Sha512 => {
            let mut mac = HmacSha512::new_from_slice(&secret)
                .map_err(|_| SecurityError::InvalidConfiguration("invalid TOTP secret".into()))?;
            mac.update(&counter);
            mac.finalize().into_bytes().to_vec()
        }
    };
    let offset = usize::from(digest[digest.len() - 1] & 0x0f);
    let binary = u32::from_be_bytes([
        digest[offset],
        digest[offset + 1],
        digest[offset + 2],
        digest[offset + 3],
    ]) & 0x7fff_ffff;
    let modulus = 10_u32
        .checked_pow(config.digits)
        .ok_or_else(|| SecurityError::InvalidConfiguration("TOTP digits overflow".into()))?;
    Ok(format!(
        "{value:0width$}",
        value = binary % modulus,
        width = config.digits as usize
    ))
}

#[must_use]
pub fn validate_phone_number(value: &str) -> bool {
    let bytes = value.as_bytes();
    (3..=16).contains(&bytes.len())
        && bytes.first() == Some(&b'+')
        && matches!(bytes.get(1), Some(b'1'..=b'9'))
        && bytes[2..].iter().all(u8::is_ascii_digit)
}

#[must_use]
pub fn validate_email_address(value: &str) -> bool {
    let Some((local, domain)) = value.split_once('@') else {
        return false;
    };
    !local.is_empty()
        && !domain.is_empty()
        && !local.contains(char::is_whitespace)
        && !domain.contains(char::is_whitespace)
        && domain
            .rsplit_once('.')
            .is_some_and(|(host, suffix)| !host.is_empty() && suffix.len() >= 2)
}

fn hash_code(code: &str) -> Vec<u8> {
    Sha256::digest(code.as_bytes()).to_vec()
}

fn hex(bytes: &[u8]) -> String {
    const HEX: &[u8] = b"0123456789abcdef";
    let mut encoded = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        encoded.push(char::from(HEX[usize::from(byte >> 4)]));
        encoded.push(char::from(HEX[usize::from(byte & 0x0f)]));
    }
    encoded
}

fn base32_encode(bytes: &[u8]) -> String {
    const ALPHABET: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
    let mut output = String::new();
    let mut buffer = 0_u32;
    let mut bits = 0_u8;
    for byte in bytes {
        buffer = (buffer << 8) | u32::from(*byte);
        bits += 8;
        while bits >= 5 {
            bits -= 5;
            output.push(char::from(ALPHABET[((buffer >> bits) & 31) as usize]));
            buffer &= (1_u32 << bits).saturating_sub(1);
        }
    }
    if bits > 0 {
        output.push(char::from(ALPHABET[((buffer << (5 - bits)) & 31) as usize]));
    }
    output
}

fn base32_decode(value: &str) -> Result<Vec<u8>, SecurityError> {
    let mut output = Vec::new();
    let mut buffer = 0_u32;
    let mut bits = 0_u8;
    for byte in value.bytes().filter(|byte| *byte != b'=') {
        let upper = byte.to_ascii_uppercase();
        let decoded = match upper {
            b'A'..=b'Z' => upper - b'A',
            b'2'..=b'7' => upper - b'2' + 26,
            _ => {
                return Err(SecurityError::InvalidConfiguration(
                    "TOTP secret is not valid base32".into(),
                ));
            }
        };
        buffer = (buffer << 5) | u32::from(decoded);
        bits += 5;
        if bits >= 8 {
            bits -= 8;
            output.push(((buffer >> bits) & 0xff) as u8);
            buffer &= (1_u32 << bits).saturating_sub(1);
        }
    }
    if output.is_empty() {
        return Err(SecurityError::InvalidConfiguration(
            "TOTP secret cannot be empty".into(),
        ));
    }
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        totp_vectors: Vec<TotpVector>,
        challenge: ChallengeCase,
        delivery: DeliveryCase,
        setup: SetupCase,
    }

    #[derive(Deserialize)]
    struct TotpVector {
        algorithm: TotpAlgorithm,
        secret: String,
        counter: u64,
        expected: String,
    }

    #[derive(Deserialize)]
    struct ChallengeCase {
        created_at_ms: u64,
        lifetime_ms: u64,
        max_attempts: u32,
        active_at_ms: u64,
        expired_at_ms: u64,
    }

    #[derive(Deserialize)]
    struct DeliveryCase {
        phone_number: String,
        email_address: String,
        invalid_phone_number: String,
        invalid_email_address: String,
    }

    #[derive(Deserialize)]
    struct SetupCase {
        user_identifier: String,
        encoded_user_identifier: String,
        encoded_issuer: String,
    }

    fn fixture() -> Fixture {
        let fixture: Fixture = serde_json::from_str(include_str!(
            "../../../contracts/identity-mfa-behavior.json"
        ))
        .expect("valid language-neutral MFA fixture");
        assert_eq!(fixture.schema_version, 1);
        fixture
    }

    #[derive(Default)]
    struct RecordingDelivery(Mutex<Vec<(MfaMethod, String, String)>>);

    #[async_trait]
    impl CodeDeliveryProvider for RecordingDelivery {
        async fn deliver(
            &self,
            method: MfaMethod,
            destination: &str,
            code: &str,
            _context: Option<&AuthenticationContext>,
        ) -> Result<(), SecurityError> {
            self.0
                .lock()
                .expect("delivery mutex")
                .push((method, destination.into(), code.into()));
            Ok(())
        }
    }

    fn rfc_config(algorithm: TotpAlgorithm) -> TotpConfig {
        TotpConfig {
            digits: 8,
            algorithm,
            window: 0,
            ..TotpConfig::default()
        }
    }

    #[test]
    fn rfc_6238_sha_vectors() {
        for case in fixture().totp_vectors {
            assert_eq!(
                generate_totp(&rfc_config(case.algorithm), &case.secret, case.counter).unwrap(),
                case.expected
            );
        }
    }

    #[test]
    fn challenge_and_device_lifecycle_fail_closed() {
        let case = fixture().challenge;
        let mut challenge = MfaChallenge::new_at(
            "user",
            MfaMethod::Totp,
            case.created_at_ms,
            case.lifetime_ms,
            case.max_attempts,
        )
        .unwrap();
        assert!(challenge.can_attempt_at(case.active_at_ms));
        assert!(challenge.is_expired_at(case.expired_at_ms));
        challenge.record_failure();
        challenge.record_failure();
        assert_eq!(challenge.status, MfaChallengeStatus::Failed);
        assert!(!challenge.can_attempt_at(199));

        let mut device = MfaDevice::new_at("user", MfaDeviceType::TotpApp, "phone", 100).unwrap();
        assert!(device.set_status(MfaDeviceStatus::Active).is_err());
        device.mark_verified_at(101).unwrap();
        device.mark_used_at(102).unwrap();
        assert_eq!(device.use_count, 1);
        device.set_status(MfaDeviceStatus::Revoked).unwrap();
        assert!(device.set_status(MfaDeviceStatus::Active).is_err());
    }

    #[tokio::test]
    async fn delivered_codes_are_provider_backed_and_one_challenge_only() {
        let delivery = Arc::new(RecordingDelivery::default());
        let case = fixture().delivery;
        let service = NativeMfaService::new(
            MfaConfig::default(),
            Some(delivery.clone()),
            BTreeMap::new(),
        )
        .unwrap();
        let device = service
            .register_device(
                "user",
                MfaDeviceType::SmsPhone,
                "phone",
                BTreeMap::from([("phone_number".into(), Value::String(case.phone_number))]),
                1_000,
                None,
            )
            .await
            .unwrap();
        let enrollment_code = delivery.0.lock().unwrap()[0].2.clone();
        service
            .verify_device(&device.device_id, &enrollment_code, 1_001)
            .await
            .unwrap();
        let challenge = service
            .create_challenge(
                "user",
                MfaMethod::Sms,
                Some(&device.device_id),
                BTreeMap::new(),
                2_000,
                None,
            )
            .await
            .unwrap();
        let code = delivery.0.lock().unwrap()[1].2.clone();
        let verification = MfaVerification {
            challenge_id: challenge.challenge_id,
            device_id: Some(device.device_id),
            verification_code: Some(code),
            backup_code: None,
            metadata: BTreeMap::new(),
            timestamp_ms: 2_001,
        };
        assert!(
            service
                .verify_challenge(&verification, 2_001)
                .await
                .unwrap()
                .success
        );
        assert!(
            !service
                .verify_challenge(&verification, 2_002)
                .await
                .unwrap()
                .success
        );
    }

    #[tokio::test]
    async fn missing_delivery_and_external_providers_fail_closed() {
        let case = fixture().delivery;
        let service = NativeMfaService::new(MfaConfig::default(), None, BTreeMap::new()).unwrap();
        assert!(matches!(
            service
                .register_device(
                    "user",
                    MfaDeviceType::Email,
                    "email",
                    BTreeMap::from([("email_address".into(), Value::String(case.email_address))]),
                    1,
                    None,
                )
                .await,
            Err(SecurityError::ProviderUnavailable(_))
        ));
        assert!(matches!(
            service
                .create_challenge("user", MfaMethod::Push, None, BTreeMap::new(), 1, None)
                .await,
            Err(SecurityError::ProviderUnavailable(_))
        ));
    }

    #[tokio::test]
    async fn backup_codes_are_single_use() {
        let service = NativeMfaService::new(MfaConfig::default(), None, BTreeMap::new()).unwrap();
        let code = service
            .generate_backup_codes("user", Some(1))
            .await
            .unwrap()
            .remove(0);
        let first = service
            .create_challenge(
                "user",
                MfaMethod::BackupCodes,
                None,
                BTreeMap::new(),
                1,
                None,
            )
            .await
            .unwrap();
        let request = MfaVerification {
            challenge_id: first.challenge_id,
            device_id: None,
            verification_code: None,
            backup_code: Some(code.clone()),
            metadata: BTreeMap::new(),
            timestamp_ms: 2,
        };
        assert!(service.verify_challenge(&request, 2).await.unwrap().success);

        let second = service
            .create_challenge(
                "user",
                MfaMethod::BackupCodes,
                None,
                BTreeMap::new(),
                3,
                None,
            )
            .await
            .unwrap();
        let replay = MfaVerification {
            challenge_id: second.challenge_id,
            ..request
        };
        assert!(!service.verify_challenge(&replay, 4).await.unwrap().success);
    }

    #[tokio::test]
    async fn totp_window_replay_and_device_limit_are_enforced() {
        let mut config = MfaConfig::default();
        config.totp.digits = 8;
        config.totp.window = 1;
        config.totp.max_devices_per_user = 1;
        config.totp.max_attempts_per_window = 10;
        let service = NativeMfaService::new(config.clone(), None, BTreeMap::new()).unwrap();
        let secret = fixture().totp_vectors.remove(0).secret;
        let device = service
            .register_device(
                "user",
                MfaDeviceType::TotpApp,
                "authenticator",
                BTreeMap::from([("secret".into(), Value::String(secret.clone()))]),
                1,
                None,
            )
            .await
            .unwrap();
        assert!(matches!(
            service
                .register_device(
                    "user",
                    MfaDeviceType::TotpApp,
                    "second authenticator",
                    BTreeMap::new(),
                    2,
                    None,
                )
                .await,
            Err(SecurityError::Conflict(_))
        ));

        let code = generate_totp(&config.totp, &secret, 1).unwrap();
        service
            .verify_device(&device.device_id, &code, 59_000)
            .await
            .unwrap();
        assert!(verify_totp_at(&config.totp, &secret, &code, 89_000).unwrap());

        let challenge = service
            .create_challenge(
                "user",
                MfaMethod::Totp,
                Some(&device.device_id),
                BTreeMap::new(),
                59_000,
                None,
            )
            .await
            .unwrap();
        let request = MfaVerification {
            challenge_id: challenge.challenge_id,
            device_id: Some(device.device_id.clone()),
            verification_code: Some(code.clone()),
            backup_code: None,
            metadata: BTreeMap::new(),
            timestamp_ms: 59_001,
        };
        assert!(
            service
                .verify_challenge(&request, 59_001)
                .await
                .unwrap()
                .success
        );

        let replay_challenge = service
            .create_challenge(
                "user",
                MfaMethod::Totp,
                Some(&device.device_id),
                BTreeMap::new(),
                59_002,
                None,
            )
            .await
            .unwrap();
        let replay = MfaVerification {
            challenge_id: replay_challenge.challenge_id,
            ..request
        };
        assert_eq!(
            service
                .verify_challenge(&replay, 59_002)
                .await
                .unwrap()
                .result,
            MfaVerificationResult::InvalidCode
        );
    }

    #[tokio::test]
    async fn totp_rate_limit_is_enforced() {
        let mut limited_config = MfaConfig::default();
        limited_config.totp.digits = 8;
        limited_config.totp.window = 1;
        limited_config.totp.max_attempts_per_window = 1;
        let limited = NativeMfaService::new(limited_config, None, BTreeMap::new()).unwrap();
        let secret = fixture().totp_vectors.remove(0).secret;
        let code = generate_totp(&rfc_config(TotpAlgorithm::Sha1), &secret, 1).unwrap();
        let limited_device = limited
            .register_device(
                "limited-user",
                MfaDeviceType::TotpApp,
                "authenticator",
                BTreeMap::from([("secret".into(), Value::String(secret))]),
                1,
                None,
            )
            .await
            .unwrap();
        limited
            .verify_device(&limited_device.device_id, &code, 59_000)
            .await
            .unwrap();
        let first = limited
            .create_challenge(
                "limited-user",
                MfaMethod::Totp,
                Some(&limited_device.device_id),
                BTreeMap::new(),
                59_000,
                None,
            )
            .await
            .unwrap();
        let invalid = MfaVerification {
            challenge_id: first.challenge_id,
            device_id: Some(limited_device.device_id.clone()),
            verification_code: Some("00000000".into()),
            backup_code: None,
            metadata: BTreeMap::new(),
            timestamp_ms: 59_001,
        };
        assert_eq!(
            limited
                .verify_challenge(&invalid, 59_001)
                .await
                .unwrap()
                .result,
            MfaVerificationResult::InvalidCode
        );
        let second = limited
            .create_challenge(
                "limited-user",
                MfaMethod::Totp,
                Some(&limited_device.device_id),
                BTreeMap::new(),
                59_002,
                None,
            )
            .await
            .unwrap();
        let rate_limited = MfaVerification {
            challenge_id: second.challenge_id,
            ..invalid
        };
        assert_eq!(
            limited
                .verify_challenge(&rate_limited, 59_002)
                .await
                .unwrap()
                .result,
            MfaVerificationResult::TooManyAttempts
        );
    }

    #[tokio::test]
    async fn expired_challenges_are_removed_with_secret_material() {
        let service = NativeMfaService::new(MfaConfig::default(), None, BTreeMap::new()).unwrap();
        service
            .create_challenge(
                "user",
                MfaMethod::BackupCodes,
                None,
                BTreeMap::new(),
                1,
                None,
            )
            .await
            .unwrap();
        assert_eq!(service.cleanup_expired_challenges(600_000).await, 1);
        assert_eq!(service.cleanup_expired_challenges(600_001).await, 0);
    }

    #[test]
    fn delivery_destination_validation_matches_behavior_contract() {
        let case = fixture().delivery;
        assert!(validate_phone_number(&case.phone_number));
        assert!(!validate_phone_number(&case.invalid_phone_number));
        assert!(validate_email_address(&case.email_address));
        assert!(!validate_email_address(&case.invalid_email_address));
    }

    #[test]
    fn native_service_implements_the_canonical_provider_port() {
        let provider: Arc<dyn MfaProvider> =
            Arc::new(NativeMfaService::new(MfaConfig::default(), None, BTreeMap::new()).unwrap());
        assert_eq!(
            provider.supported_methods(),
            BTreeSet::from([MfaMethod::Totp, MfaMethod::BackupCodes])
        );
        assert_eq!(
            provider.supported_device_types(),
            BTreeSet::from([MfaDeviceType::TotpApp])
        );
    }

    #[test]
    fn setup_uri_is_encoded_and_secret_generation_is_base32() {
        let case = fixture().setup;
        let service = NativeMfaService::new(MfaConfig::default(), None, BTreeMap::new()).unwrap();
        let secret = generate_totp_secret();
        assert_eq!(base32_decode(&secret).unwrap().len(), 20);
        let uri = service.totp_setup_uri(&secret, &case.user_identifier);
        assert!(uri.contains(&case.encoded_user_identifier));
        assert!(uri.contains(&case.encoded_issuer));
    }

    #[test]
    fn setup_uri_keeps_issuer_and_user_inside_their_components() {
        let mut config = MfaConfig::default();
        config.totp.issuer = "Café +/Issuer".into();
        let service = NativeMfaService::new(config, None, BTreeMap::new()).unwrap();
        assert_eq!(
            service.totp_setup_uri("JBSWY3DPEHPK3PXP", "a:b@example.test?x=1&y=%\n"),
            "otpauth://totp/Caf%C3%A9%20%2B%2FIssuer:a%3Ab%40example.test%3Fx%3D1%26y%3D%25%0A?secret=JBSWY3DPEHPK3PXP&issuer=Caf%C3%A9%20%2B%2FIssuer&algorithm=Sha1&digits=6&period=30"
        );
    }
}
