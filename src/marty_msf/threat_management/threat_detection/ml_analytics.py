"""
Machine Learning-based Security Analytics for Marty Microservices Framework

Provides advanced machine learning capabilities for security analysis including:
- Anomaly detection with multiple ML algorithms
- Behavioral analysis and user profiling
- Threat classification and scoring
- Predictive security analytics
- Adaptive learning from security events
"""

import asyncio
import builtins
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, dict, list

import joblib
import numpy as np
from prometheus_client import Counter, Gauge, Histogram
from sklearn.cluster import DBSCAN
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# External dependencies (optional)
try:
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

try:
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False


@dataclass
class UserBehaviorProfile:
    """User behavior profile for anomaly detection"""

    user_id: str
    created_at: datetime
    updated_at: datetime

    # Access patterns
    typical_access_hours: builtins.list[int] = field(default_factory=list)
    typical_services: builtins.list[str] = field(default_factory=list)
    typical_endpoints: builtins.list[str] = field(default_factory=list)
    typical_ip_ranges: builtins.list[str] = field(default_factory=list)

    # Behavioral metrics
    avg_requests_per_hour: float = 0.0
    avg_session_duration: float = 0.0
    avg_response_time: float = 0.0

    # Risk factors
    failed_login_rate: float = 0.0
    privilege_escalation_attempts: int = 0
    unusual_access_count: int = 0

    # ML features
    feature_vector: builtins.list[float] = field(default_factory=list)
    anomaly_score: float = 0.0


@dataclass
class ServiceBehaviorProfile:
    """Service behavior profile for system anomaly detection"""

    service_name: str
    created_at: datetime
    updated_at: datetime

    # Performance metrics
    avg_response_time: float = 0.0
    avg_throughput: float = 0.0
    avg_error_rate: float = 0.0
    avg_cpu_usage: float = 0.0
    avg_memory_usage: float = 0.0

    # Traffic patterns
    typical_request_patterns: builtins.dict[str, float] = field(default_factory=dict)
    typical_user_agents: builtins.list[str] = field(default_factory=list)
    typical_source_countries: builtins.list[str] = field(default_factory=list)

    # Security metrics
    auth_failure_rate: float = 0.0
    suspicious_request_rate: float = 0.0
    malicious_ip_access_rate: float = 0.0

    # ML features
    feature_vector: builtins.list[float] = field(default_factory=list)
    anomaly_score: float = 0.0


@dataclass
class ThreatPrediction:
    """ML-based threat prediction"""

    prediction_id: str
    created_at: datetime
    threat_type: str
    confidence: float
    predicted_at: datetime
    features_used: builtins.list[str]
    model_version: str
    risk_score: float
    recommended_actions: builtins.list[str]


class SecurityMLAnalyzer:
    """
    Machine Learning Security Analytics Engine

    Features:
    - Isolation Forest for anomaly detection
    - DBSCAN for clustering unusual behaviors
    - Random Forest for threat classification
    - Behavioral profiling and learning
    - Predictive security analytics
    """

    def __init__(self, model_update_interval: int = 3600):
        self.model_update_interval = model_update_interval

        # User and service profiles
        self.user_profiles: builtins.dict[str, UserBehaviorProfile] = {}
        self.service_profiles: builtins.dict[str, ServiceBehaviorProfile] = {}

        # ML Models
        self.anomaly_detector = None
        self.threat_classifier = None
        self.behavior_clusterer = None
        self.scaler = StandardScaler() if ML_AVAILABLE else None

        # Training data
        self.training_data: builtins.list[builtins.dict[str, Any]] = []
        self.feature_names: builtins.list[str] = []

        # Model performance tracking
        self.model_accuracy = 0.0
        self.last_model_update = datetime.now()

        # Security event history for learning
        self.security_events: deque = deque(maxlen=100000)

        # Initialize ML models if available
        if ML_AVAILABLE:
            self._initialize_models()

        # Metrics
        if METRICS_AVAILABLE:
            self.ml_predictions = Counter(
                "marty_ml_security_predictions_total",
                "ML security predictions",
                ["prediction_type", "confidence_level"],
            )
            self.anomaly_detections = Counter(
                "marty_ml_anomaly_detections_total",
                "ML anomaly detections",
                ["entity_type", "anomaly_type"],
            )
            self.model_accuracy_gauge = Gauge("marty_ml_model_accuracy", "ML model accuracy")

    def _initialize_models(self):
        """Initialize ML models"""
        if not ML_AVAILABLE:
            print("ML libraries not available, using fallback methods")
            return

        # Anomaly detection model
        self.anomaly_detector = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100,  # Expect 10% anomalies
        )

        # Threat classification model
        self.threat_classifier = RandomForestClassifier(
            n_estimators=100, random_state=42, max_depth=10
        )

        # Behavior clustering model
        self.behavior_clusterer = DBSCAN(eps=0.5, min_samples=5)

        # Define feature names
        self.feature_names = [
            "hour_of_day",
            "day_of_week",
            "requests_per_hour",
            "unique_endpoints",
            "failed_logins",
            "response_time_avg",
            "payload_size_avg",
            "geographic_risk",
            "service_tier_risk",
            "user_privilege_level",
            "session_duration",
            "ip_reputation",
        ]

        print("Initialized ML models for security analytics")

    async def analyze_user_behavior(
        self, user_id: str, recent_events: builtins.list[builtins.dict[str, Any]]
    ) -> UserBehaviorProfile:
        """Analyze user behavior and update profile"""

        # Get or create user profile
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserBehaviorProfile(
                user_id=user_id, created_at=datetime.now(), updated_at=datetime.now()
            )

        profile = self.user_profiles[user_id]

        if not recent_events:
            return profile

        # Update access patterns
        access_hours = [
            datetime.fromisoformat(event.get("timestamp", datetime.now().isoformat())).hour
            for event in recent_events
            if "timestamp" in event
        ]
        if access_hours:
            profile.typical_access_hours = list(set(access_hours))

        services = [event.get("service_name", "") for event in recent_events]
        profile.typical_services = list(set(filter(None, services)))

        endpoints = [event.get("endpoint", "") for event in recent_events]
        profile.typical_endpoints = list(set(filter(None, endpoints)))

        # Calculate behavioral metrics
        if recent_events:
            profile.avg_requests_per_hour = len(recent_events) / max(
                1,
                len(
                    {
                        datetime.fromisoformat(
                            event.get("timestamp", datetime.now().isoformat())
                        ).hour
                        for event in recent_events
                        if "timestamp" in event
                    }
                ),
            )

            response_times = [
                event.get("response_time", 0)
                for event in recent_events
                if event.get("response_time")
            ]
            if response_times:
                profile.avg_response_time = statistics.mean(response_times)

            # Calculate risk factors
            failed_logins = sum(
                1 for event in recent_events if event.get("event_type") == "authentication_failure"
            )
            profile.failed_login_rate = failed_logins / len(recent_events) if recent_events else 0.0

            admin_accesses = sum(
                1 for event in recent_events if "admin" in event.get("endpoint", "").lower()
            )
            profile.privilege_escalation_attempts = admin_accesses

        # Generate feature vector for ML
        profile.feature_vector = self._extract_user_features(profile, recent_events)

        # Calculate anomaly score
        if ML_AVAILABLE and self.anomaly_detector and profile.feature_vector:
            try:
                features = np.array(profile.feature_vector).reshape(1, -1)
                if hasattr(self.anomaly_detector, "decision_function"):
                    anomaly_score = self.anomaly_detector.decision_function(features)[0]
                    # Convert to 0-1 range where higher is more anomalous
                    profile.anomaly_score = max(0, min(1, (0.5 - anomaly_score) / 0.5))
                else:
                    profile.anomaly_score = 0.5  # Default when model not trained
            except Exception as e:
                print(f"Error calculating user anomaly score: {e}")
                profile.anomaly_score = 0.0
        else:
            # Fallback anomaly detection
            profile.anomaly_score = self._calculate_user_anomaly_score_fallback(profile)

        profile.updated_at = datetime.now()

        # Update metrics
        if METRICS_AVAILABLE and profile.anomaly_score > 0.7:
            self.anomaly_detections.labels(entity_type="user", anomaly_type="behavioral").inc()

        return profile

    def _extract_user_features(
        self,
        profile: UserBehaviorProfile,
        recent_events: builtins.list[builtins.dict[str, Any]],
    ) -> builtins.list[float]:
        """Extract ML features from user behavior"""

        if not recent_events:
            return [0.0] * len(self.feature_names)

        features = []

        # Hour of day (average)
        hours = [
            datetime.fromisoformat(event.get("timestamp", datetime.now().isoformat())).hour
            for event in recent_events
            if "timestamp" in event
        ]
        avg_hour = statistics.mean(hours) if hours else 12.0
        features.append(avg_hour / 24.0)  # Normalize to 0-1

        # Day of week (most common)
        days = [
            datetime.fromisoformat(event.get("timestamp", datetime.now().isoformat())).weekday()
            for event in recent_events
            if "timestamp" in event
        ]
        most_common_day = statistics.mode(days) if days else 0
        features.append(most_common_day / 7.0)  # Normalize to 0-1

        # Requests per hour
        features.append(min(1.0, profile.avg_requests_per_hour / 100.0))  # Cap at 100 req/hour

        # Unique endpoints accessed
        unique_endpoints = len({event.get("endpoint", "") for event in recent_events})
        features.append(min(1.0, unique_endpoints / 50.0))  # Cap at 50 endpoints

        # Failed login rate
        features.append(profile.failed_login_rate)

        # Average response time (normalized)
        features.append(min(1.0, profile.avg_response_time / 5000.0))  # Cap at 5 seconds

        # Average payload size
        payload_sizes = [len(str(event.get("request_body", ""))) for event in recent_events]
        avg_payload = statistics.mean(payload_sizes) if payload_sizes else 0
        features.append(min(1.0, avg_payload / 10000.0))  # Cap at 10KB

        # Geographic risk (simplified)
        external_ips = [
            event.get("source_ip", "")
            for event in recent_events
            if not event.get("source_ip", "").startswith(("192.168", "10.", "172."))
        ]
        geo_risk = len(external_ips) / len(recent_events) if recent_events else 0.0
        features.append(geo_risk)

        # Service tier risk
        critical_services = sum(
            1
            for event in recent_events
            if any(x in event.get("service_name", "").lower() for x in ["payment", "auth", "admin"])
        )
        service_risk = critical_services / len(recent_events) if recent_events else 0.0
        features.append(service_risk)

        # User privilege level (inferred)
        admin_actions = sum(
            1 for event in recent_events if "admin" in event.get("endpoint", "").lower()
        )
        privilege_level = min(1.0, admin_actions / max(1, len(recent_events)))
        features.append(privilege_level)

        # Session duration (estimated)
        if len(recent_events) > 1:
            timestamps = [
                datetime.fromisoformat(event.get("timestamp", datetime.now().isoformat()))
                for event in recent_events
                if "timestamp" in event
            ]
            if len(timestamps) > 1:
                session_duration = (max(timestamps) - min(timestamps)).total_seconds()
                features.append(min(1.0, session_duration / 3600.0))  # Cap at 1 hour
            else:
                features.append(0.5)  # Default
        else:
            features.append(0.5)  # Default

        # IP reputation (simplified)
        unique_ips = len({event.get("source_ip", "") for event in recent_events})
        ip_reputation = min(1.0, unique_ips / 10.0) if unique_ips > 1 else 0.1
        features.append(ip_reputation)

        return features

    def _calculate_user_anomaly_score_fallback(self, profile: UserBehaviorProfile) -> float:
        """Fallback anomaly calculation when ML not available"""

        score = 0.0

        # High failed login rate
        if profile.failed_login_rate > 0.3:
            score += 0.4

        # Unusual privilege escalation
        if profile.privilege_escalation_attempts > 5:
            score += 0.3

        # Very high request rate
        if profile.avg_requests_per_hour > 100:
            score += 0.2

        # Slow response times (might indicate probing)
        if profile.avg_response_time > 2000:
            score += 0.1

        return min(1.0, score)

    async def analyze_service_behavior(
        self, service_name: str, recent_metrics: builtins.list[builtins.dict[str, Any]]
    ) -> ServiceBehaviorProfile:
        """Analyze service behavior and update profile"""

        # Get or create service profile
        if service_name not in self.service_profiles:
            self.service_profiles[service_name] = ServiceBehaviorProfile(
                service_name=service_name,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

        profile = self.service_profiles[service_name]

        if not recent_metrics:
            return profile

        # Update performance metrics
        response_times = [
            m.get("response_time", 0) for m in recent_metrics if m.get("response_time")
        ]
        if response_times:
            profile.avg_response_time = statistics.mean(response_times)

        throughput_values = [m.get("throughput", 0) for m in recent_metrics if m.get("throughput")]
        if throughput_values:
            profile.avg_throughput = statistics.mean(throughput_values)

        error_rates = [m.get("error_rate", 0) for m in recent_metrics if m.get("error_rate")]
        if error_rates:
            profile.avg_error_rate = statistics.mean(error_rates)

        # Update security metrics
        auth_failures = sum(
            1 for m in recent_metrics if m.get("event_type") == "authentication_failure"
        )
        profile.auth_failure_rate = auth_failures / len(recent_metrics) if recent_metrics else 0.0

        suspicious_requests = sum(
            1 for m in recent_metrics if "suspicious" in m.get("event_type", "")
        )
        profile.suspicious_request_rate = (
            suspicious_requests / len(recent_metrics) if recent_metrics else 0.0
        )

        # Generate feature vector
        profile.feature_vector = self._extract_service_features(profile, recent_metrics)

        # Calculate anomaly score
        if ML_AVAILABLE and self.anomaly_detector and profile.feature_vector:
            try:
                features = np.array(profile.feature_vector).reshape(1, -1)
                if hasattr(self.anomaly_detector, "decision_function"):
                    anomaly_score = self.anomaly_detector.decision_function(features)[0]
                    profile.anomaly_score = max(0, min(1, (0.5 - anomaly_score) / 0.5))
                else:
                    profile.anomaly_score = 0.5
            except Exception as e:
                print(f"Error calculating service anomaly score: {e}")
                profile.anomaly_score = 0.0
        else:
            profile.anomaly_score = self._calculate_service_anomaly_score_fallback(profile)

        profile.updated_at = datetime.now()

        # Update metrics
        if METRICS_AVAILABLE and profile.anomaly_score > 0.7:
            self.anomaly_detections.labels(entity_type="service", anomaly_type="performance").inc()

        return profile

    def _extract_service_features(
        self,
        profile: ServiceBehaviorProfile,
        recent_metrics: builtins.list[builtins.dict[str, Any]],
    ) -> builtins.list[float]:
        """Extract ML features from service behavior"""

        features = []

        # Average response time (normalized)
        features.append(min(1.0, profile.avg_response_time / 5000.0))

        # Average throughput (normalized)
        features.append(min(1.0, profile.avg_throughput / 1000.0))

        # Error rate
        features.append(profile.avg_error_rate)

        # Authentication failure rate
        features.append(profile.auth_failure_rate)

        # Suspicious request rate
        features.append(profile.suspicious_request_rate)

        # Request pattern diversity
        endpoints = [m.get("endpoint", "") for m in recent_metrics]
        unique_endpoints = len(set(endpoints))
        pattern_diversity = min(1.0, unique_endpoints / 100.0)
        features.append(pattern_diversity)

        # Time pattern (current hour normalized)
        current_hour = datetime.now().hour
        features.append(current_hour / 24.0)

        # Service criticality (inferred from name)
        critical_keywords = ["payment", "auth", "user", "admin", "core"]
        criticality = (
            1.0
            if any(keyword in profile.service_name.lower() for keyword in critical_keywords)
            else 0.5
        )
        features.append(criticality)

        return features

    def _calculate_service_anomaly_score_fallback(self, profile: ServiceBehaviorProfile) -> float:
        """Fallback service anomaly calculation"""

        score = 0.0

        # High error rate
        if profile.avg_error_rate > 0.05:  # 5% error rate
            score += 0.4

        # High auth failure rate
        if profile.auth_failure_rate > 0.1:
            score += 0.3

        # High suspicious request rate
        if profile.suspicious_request_rate > 0.05:
            score += 0.2

        # Very slow response times
        if profile.avg_response_time > 3000:  # 3 seconds
            score += 0.1

        return min(1.0, score)

    async def predict_threat(self, event_data: builtins.dict[str, Any]) -> ThreatPrediction | None:
        """Predict threat likelihood using ML models"""

        if not ML_AVAILABLE or not self.threat_classifier:
            return self._predict_threat_fallback(event_data)

        try:
            # Extract features for prediction
            features = self._extract_prediction_features(event_data)

            if not features:
                return None

            # Make prediction
            features_array = np.array(features).reshape(1, -1)

            # Check if model is trained
            if not hasattr(self.threat_classifier, "classes_"):
                return self._predict_threat_fallback(event_data)

            # Get prediction probabilities
            probabilities = self.threat_classifier.predict_proba(features_array)[0]
            classes = self.threat_classifier.classes_

            # Find highest probability threat
            max_prob_idx = np.argmax(probabilities)
            threat_type = classes[max_prob_idx]
            confidence = probabilities[max_prob_idx]

            # Only return prediction if confidence is high enough
            if confidence < 0.6:
                return None

            prediction = ThreatPrediction(
                prediction_id=f"pred_{int(time.time())}",
                created_at=datetime.now(),
                threat_type=threat_type,
                confidence=confidence,
                predicted_at=datetime.now() + timedelta(minutes=30),  # Predict 30 min ahead
                features_used=self.feature_names,
                model_version="1.0",
                risk_score=confidence,
                recommended_actions=self._get_threat_recommendations(threat_type),
            )

            # Update metrics
            if METRICS_AVAILABLE:
                confidence_level = "high" if confidence > 0.8 else "medium"
                self.ml_predictions.labels(
                    prediction_type=threat_type, confidence_level=confidence_level
                ).inc()

            return prediction

        except Exception as e:
            print(f"Error in ML threat prediction: {e}")
            return self._predict_threat_fallback(event_data)

    def _extract_prediction_features(
        self, event_data: builtins.dict[str, Any]
    ) -> builtins.list[float]:
        """Extract features for threat prediction"""

        features = []

        # Time-based features
        timestamp = event_data.get("timestamp")
        if timestamp:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp)
            else:
                dt = timestamp
            features.append(dt.hour / 24.0)
            features.append(dt.weekday() / 7.0)
        else:
            features.extend([0.5, 0.5])  # Default values

        # Request characteristics
        features.append(min(1.0, len(str(event_data.get("request_body", ""))) / 10000.0))
        features.append(len(set(event_data.get("endpoint", "").split("/"))) / 10.0)

        # Security indicators
        failed_auth = 1.0 if event_data.get("event_type") == "authentication_failure" else 0.0
        features.append(failed_auth)

        response_time = event_data.get("response_time", 0)
        features.append(min(1.0, response_time / 5000.0))

        # Payload analysis
        payload = str(event_data.get("request_body", "")) + str(
            event_data.get("request_params", "")
        )
        sql_indicators = len(
            [p for p in ["SELECT", "UNION", "DROP", "INSERT"] if p in payload.upper()]
        )
        features.append(min(1.0, sql_indicators / 4.0))

        # Geographic risk
        source_ip = event_data.get("source_ip", "")
        is_external = 0.0 if source_ip.startswith(("192.168", "10.", "172.")) else 1.0
        features.append(is_external)

        # Service criticality
        service_name = event_data.get("service_name", "").lower()
        critical_services = ["payment", "auth", "user", "admin"]
        criticality = 1.0 if any(cs in service_name for cs in critical_services) else 0.5
        features.append(criticality)

        # User privilege (inferred)
        endpoint = event_data.get("endpoint", "").lower()
        admin_access = 1.0 if "admin" in endpoint or "management" in endpoint else 0.0
        features.append(admin_access)

        # Error indicators
        error_rate = event_data.get("error_rate", 0.0)
        features.append(error_rate)

        # IP reputation (simplified)
        known_good_ips = ["192.168.", "10.", "172.16.", "172.17.", "172.18."]
        ip_reputation = (
            0.1 if any(source_ip.startswith(prefix) for prefix in known_good_ips) else 0.8
        )
        features.append(ip_reputation)

        return features

    def _predict_threat_fallback(
        self, event_data: builtins.dict[str, Any]
    ) -> ThreatPrediction | None:
        """Fallback threat prediction without ML"""

        risk_score = 0.0
        threat_type = "unknown"

        # Check for SQL injection patterns
        payload = str(event_data.get("request_body", "")) + str(
            event_data.get("request_params", "")
        )
        if any(pattern in payload.upper() for pattern in ["SELECT", "UNION", "DROP", "; DROP"]):
            threat_type = "injection_attack"
            risk_score = 0.9

        # Check for authentication attacks
        elif event_data.get("event_type") == "authentication_failure":
            threat_type = "brute_force"
            risk_score = 0.7

        # Check for admin access
        elif "admin" in event_data.get("endpoint", "").lower():
            threat_type = "privilege_escalation"
            risk_score = 0.6

        # Check for external access to sensitive services
        elif not event_data.get("source_ip", "").startswith(("192.168", "10.", "172.")) and any(
            service in event_data.get("service_name", "").lower()
            for service in ["payment", "user", "auth"]
        ):
            threat_type = "unauthorized_access"
            risk_score = 0.5

        if risk_score > 0.5:
            return ThreatPrediction(
                prediction_id=f"pred_fallback_{int(time.time())}",
                created_at=datetime.now(),
                threat_type=threat_type,
                confidence=risk_score,
                predicted_at=datetime.now() + timedelta(minutes=15),
                features_used=["fallback_rules"],
                model_version="fallback",
                risk_score=risk_score,
                recommended_actions=self._get_threat_recommendations(threat_type),
            )

        return None

    def _get_threat_recommendations(self, threat_type: str) -> builtins.list[str]:
        """Get recommended actions for threat type"""

        recommendations = {
            "injection_attack": [
                "Block suspicious requests immediately",
                "Review and strengthen input validation",
                "Check database integrity",
                "Alert security team",
            ],
            "brute_force": [
                "Implement IP-based rate limiting",
                "Require multi-factor authentication",
                "Monitor authentication patterns",
                "Consider account lockout policies",
            ],
            "privilege_escalation": [
                "Audit user permissions immediately",
                "Review access control policies",
                "Monitor privileged account activities",
                "Implement additional authorization checks",
            ],
            "unauthorized_access": [
                "Verify user authorization",
                "Check access logs for patterns",
                "Consider geo-blocking if appropriate",
                "Enhance authentication requirements",
            ],
            "data_exfiltration": [
                "Monitor data transfer patterns",
                "Implement data loss prevention",
                "Review user access rights",
                "Consider encryption at rest",
            ],
        }

        return recommendations.get(
            threat_type, ["Monitor situation closely", "Alert security team"]
        )

    async def train_models(self, training_events: builtins.list[builtins.dict[str, Any]]) -> bool:
        """Train ML models with security event data"""

        if not ML_AVAILABLE:
            print("ML libraries not available for training")
            return False

        try:
            # Prepare training data
            features = []
            labels = []

            for event in training_events:
                event_features = self._extract_prediction_features(event)
                if event_features:
                    features.append(event_features)
                    # Use threat category as label
                    labels.append(event.get("threat_category", "normal"))

            if len(features) < 10:
                print("Insufficient training data")
                return False

            features_array = np.array(features)

            # Train anomaly detector
            self.anomaly_detector.fit(features_array)

            # Train threat classifier if we have labels
            if len(set(labels)) > 1:  # Need at least 2 different labels
                self.threat_classifier.fit(features_array, labels)

                # Calculate accuracy with cross-validation
                if len(features) > 20:
                    X_train, X_test, y_train, y_test = train_test_split(
                        features_array, labels, test_size=0.2, random_state=42
                    )
                    self.threat_classifier.fit(X_train, y_train)
                    self.model_accuracy = self.threat_classifier.score(X_test, y_test)

                    # Update metrics
                    if METRICS_AVAILABLE:
                        self.model_accuracy_gauge.set(self.model_accuracy)

            self.last_model_update = datetime.now()
            print(
                f"Trained ML models with {len(features)} samples, accuracy: {self.model_accuracy:.3f}"
            )
            return True

        except Exception as e:
            print(f"Error training ML models: {e}")
            return False

    def get_user_risk_summary(self) -> builtins.dict[str, Any]:
        """Get summary of user risk profiles"""

        if not self.user_profiles:
            return {"total_users": 0, "high_risk_users": 0}

        high_risk_users = [
            profile for profile in self.user_profiles.values() if profile.anomaly_score > 0.7
        ]

        avg_anomaly_score = statistics.mean(
            [profile.anomaly_score for profile in self.user_profiles.values()]
        )

        return {
            "total_users": len(self.user_profiles),
            "high_risk_users": len(high_risk_users),
            "avg_anomaly_score": avg_anomaly_score,
            "high_risk_user_ids": [profile.user_id for profile in high_risk_users],
        }

    def get_service_risk_summary(self) -> builtins.dict[str, Any]:
        """Get summary of service risk profiles"""

        if not self.service_profiles:
            return {"total_services": 0, "high_risk_services": 0}

        high_risk_services = [
            profile for profile in self.service_profiles.values() if profile.anomaly_score > 0.7
        ]

        avg_anomaly_score = statistics.mean(
            [profile.anomaly_score for profile in self.service_profiles.values()]
        )

        return {
            "total_services": len(self.service_profiles),
            "high_risk_services": len(high_risk_services),
            "avg_anomaly_score": avg_anomaly_score,
            "high_risk_service_names": [profile.service_name for profile in high_risk_services],
        }

    def get_ml_model_status(self) -> builtins.dict[str, Any]:
        """Get ML model status and performance"""

        return {
            "ml_available": ML_AVAILABLE,
            "models_trained": self.anomaly_detector is not None
            and hasattr(self.anomaly_detector, "estimators_"),
            "model_accuracy": self.model_accuracy,
            "last_model_update": self.last_model_update.isoformat(),
            "training_data_size": len(self.training_data),
            "feature_count": len(self.feature_names),
            "user_profiles": len(self.user_profiles),
            "service_profiles": len(self.service_profiles),
        }


# Example usage
async def main():
    """Example usage of ML security analyzer"""

    # Initialize analyzer
    analyzer = SecurityMLAnalyzer()

    # Simulate user behavior analysis
    user_events = [
        {
            "user_id": "user123",
            "timestamp": datetime.now().isoformat(),
            "service_name": "user-service",
            "endpoint": "/api/v1/profile",
            "event_type": "data_access",
            "response_time": 150,
            "source_ip": "192.168.1.100",
        },
        {
            "user_id": "user123",
            "timestamp": (datetime.now() + timedelta(minutes=5)).isoformat(),
            "service_name": "payment-service",
            "endpoint": "/api/v1/admin/payments",
            "event_type": "data_access",
            "response_time": 2500,
            "source_ip": "203.0.113.42",  # External IP
        },
    ]

    # Analyze user behavior
    user_profile = await analyzer.analyze_user_behavior("user123", user_events)
    print(f"User anomaly score: {user_profile.anomaly_score:.3f}")

    # Simulate threat prediction
    suspicious_event = {
        "timestamp": datetime.now().isoformat(),
        "source_ip": "198.51.100.42",
        "service_name": "user-service",
        "endpoint": "/api/v1/users",
        "event_type": "suspicious_request",
        "request_body": "SELECT * FROM users WHERE id = '1' OR '1'='1'",
        "response_time": 3000,
    }

    threat_prediction = await analyzer.predict_threat(suspicious_event)
    if threat_prediction:
        print(
            f"Threat prediction: {threat_prediction.threat_type} (confidence: {threat_prediction.confidence:.3f})"
        )
        print(f"Recommendations: {threat_prediction.recommended_actions}")

    # Get risk summaries
    user_summary = analyzer.get_user_risk_summary()
    service_summary = analyzer.get_service_risk_summary()
    model_status = analyzer.get_ml_model_status()

    print(f"\nUser Risk Summary: {user_summary}")
    print(f"Service Risk Summary: {service_summary}")
    print(f"ML Model Status: {model_status}")


if __name__ == "__main__":
    asyncio.run(main())
