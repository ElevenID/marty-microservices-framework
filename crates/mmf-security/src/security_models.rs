use std::collections::{BTreeMap, BTreeSet};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::SecurityError;
pub use mmf_security_contracts::{MeshType, MtlsMode, ServiceMeshManager, ServiceMeshPolicy};

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ThreatLevel {
    Informational,
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ThreatType {
    Injection,
    CrossSiteScripting,
    Intrusion,
    BruteForce,
    DenialOfService,
    Reconnaissance,
    Malware,
    DataLeak,
    Unknown,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SecurityEvent {
    pub event_id: String,
    pub event_type: String,
    pub timestamp_ms: u64,
    #[serde(default)]
    pub service_name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_ip: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_agent: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub endpoint: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub method: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub status_code: Option<u16>,
    pub severity: ThreatLevel,
    #[serde(default)]
    pub details: BTreeMap<String, Value>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ThreatDetectionResult {
    pub event_id: String,
    pub is_threat: bool,
    pub threat_score: f64,
    pub threat_level: ThreatLevel,
    #[serde(default)]
    pub detected_threats: BTreeSet<ThreatType>,
    #[serde(default)]
    pub risk_factors: Vec<String>,
    #[serde(default)]
    pub recommended_actions: Vec<String>,
    #[serde(default)]
    pub correlated_events: Vec<String>,
}

impl ThreatDetectionResult {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if !self.threat_score.is_finite() || !(0.0..=1.0).contains(&self.threat_score) {
            return Err(SecurityError::InvalidThreatScore);
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ThreatRule {
    pub id: String,
    pub threat_type: ThreatType,
    pub level: ThreatLevel,
    pub score: f64,
    pub patterns: Vec<String>,
    #[serde(default = "one")]
    pub minimum_matches: usize,
    #[serde(default = "enabled")]
    pub enabled: bool,
    #[serde(default)]
    pub recommended_actions: Vec<String>,
}

const fn one() -> usize {
    1
}

const fn enabled() -> bool {
    true
}

#[derive(Clone, Debug, Default)]
pub struct PatternThreatDetector {
    rules: Vec<ThreatRule>,
}

impl PatternThreatDetector {
    pub fn new(rules: Vec<ThreatRule>) -> Result<Self, SecurityError> {
        for rule in &rules {
            if rule.id.trim().is_empty()
                || rule.patterns.is_empty()
                || rule.minimum_matches == 0
                || !rule.score.is_finite()
                || !(0.0..=1.0).contains(&rule.score)
            {
                return Err(SecurityError::InvalidThreatRule(rule.id.clone()));
            }
        }
        Ok(Self { rules })
    }

    pub fn analyze(&self, event: &SecurityEvent) -> Result<ThreatDetectionResult, SecurityError> {
        let searchable = serde_json::to_string(event)
            .map_err(|error| SecurityError::ThreatDetection(error.to_string()))?
            .to_ascii_lowercase();
        let matched = self
            .rules
            .iter()
            .filter(|rule| rule.enabled)
            .filter(|rule| {
                rule.patterns
                    .iter()
                    .filter(|pattern| searchable.contains(&pattern.to_ascii_lowercase()))
                    .count()
                    >= rule.minimum_matches
            })
            .collect::<Vec<_>>();
        let threat_score = matched
            .iter()
            .map(|rule| rule.score)
            .fold(0.0_f64, f64::max);
        let threat_level = matched
            .iter()
            .map(|rule| rule.level)
            .max()
            .unwrap_or(ThreatLevel::Informational);
        let result = ThreatDetectionResult {
            event_id: event.event_id.clone(),
            is_threat: !matched.is_empty(),
            threat_score,
            threat_level,
            detected_threats: matched.iter().map(|rule| rule.threat_type).collect(),
            risk_factors: matched
                .iter()
                .map(|rule| format!("matched threat rule '{}'", rule.id))
                .collect(),
            recommended_actions: matched
                .iter()
                .flat_map(|rule| rule.recommended_actions.clone())
                .collect::<BTreeSet<_>>()
                .into_iter()
                .collect(),
            correlated_events: Vec::new(),
        };
        result.validate()?;
        Ok(result)
    }
}

#[async_trait]
pub trait ThreatDetector: Send + Sync {
    async fn analyze(&self, event: &SecurityEvent) -> Result<ThreatDetectionResult, SecurityError>;
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Vulnerability {
    pub id: String,
    pub component: String,
    pub title: String,
    pub severity: ThreatLevel,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub advisory_url: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub patched_version: Option<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

#[async_trait]
pub trait VulnerabilityScanner: Send + Sync {
    async fn scan(&self) -> Result<Vec<Vulnerability>, SecurityError>;
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct AuditEvent {
    pub event_id: String,
    pub event_type: String,
    pub timestamp_ms: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actor_id: Option<String>,
    pub action: String,
    pub resource: String,
    pub outcome: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub request_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_ip: Option<String>,
    #[serde(default)]
    pub details: BTreeMap<String, Value>,
}

#[async_trait]
pub trait Auditor: Send + Sync {
    async fn record(&self, event: AuditEvent) -> Result<(), SecurityError>;
}
