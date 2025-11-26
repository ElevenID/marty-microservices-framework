"""
Core data models for ML components in the Marty Microservices Framework.
"""

import builtins
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from marty_msf.framework.ml.models.enums import (
    ExperimentStatus,
    FeatureType,
    ModelFramework,
    ModelStatus,
    ModelType,
)


@dataclass
class MLModel:
    """ML model definition."""

    model_id: str
    name: str
    version: str
    model_type: ModelType
    framework: ModelFramework
    status: ModelStatus = ModelStatus.TRAINING

    # Model artifacts
    model_path: str | None = None
    model_data: bytes | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    # Performance metrics
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    mse: float | None = None
    mae: float | None = None
    r2_score: float | None = None
    custom_metrics: builtins.dict[str, float] = field(default_factory=dict)

    # Training information
    training_data_size: int | None = None
    training_duration: float | None = None
    hyperparameters: builtins.dict[str, Any] = field(default_factory=dict)

    # Deployment information
    endpoint_url: str | None = None
    cpu_requirement: float = 1.0
    memory_requirement: int = 1024  # MB
    gpu_requirement: bool = False

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deployed_at: datetime | None = None


@dataclass
class Feature:
    """Feature definition for ML models."""

    feature_id: str
    name: str
    feature_type: FeatureType
    description: str = ""

    # Feature metadata
    source_table: str | None = None
    source_column: str | None = None
    transformation: str | None = None

    # Validation rules
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: builtins.list[Any] | None = None
    required: bool = True

    # Statistics
    mean: float | None = None
    std: float | None = None
    null_count: int | None = None
    unique_count: int | None = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class FeatureGroup:
    """Group of related features."""

    group_id: str
    name: str
    description: str
    features: builtins.list[Feature] = field(default_factory=list)
    online_enabled: bool = True
    offline_enabled: bool = True

    # Storage configuration
    online_store: str | None = None
    offline_store: str | None = None

    # Update frequency
    update_frequency: str = "daily"  # daily, hourly, real-time

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ModelPrediction:
    """Model prediction result."""

    prediction_id: str
    model_id: str
    input_features: builtins.dict[str, Any]
    prediction: Any
    confidence: float | None = None
    probabilities: builtins.dict[str, float] | None = None
    latency_ms: float | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ABTestExperiment:
    """A/B testing experiment definition."""

    experiment_id: str
    name: str
    description: str
    control_model_id: str
    treatment_model_ids: builtins.list[str]
    traffic_split: builtins.dict[str, float]  # model_id -> percentage
    primary_metric: str
    status: ExperimentStatus = ExperimentStatus.DRAFT

    # Target metrics
    secondary_metrics: builtins.list[str] = field(default_factory=list)

    # Experiment parameters
    min_sample_size: int = 1000
    max_duration_days: int = 30
    significance_level: float = 0.05
    power: float = 0.8

    # Results
    results: builtins.dict[str, Any] = field(default_factory=dict)
    winner_model_id: str | None = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    ended_at: datetime | None = None


@dataclass
class ModelMetrics:
    """Model performance metrics."""

    model_id: str
    timestamp: datetime

    # Performance metrics
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0

    # Resource metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    gpu_usage: float = 0.0

    # Business metrics
    prediction_accuracy: float | None = None
    user_satisfaction: float | None = None
    revenue_impact: float | None = None
