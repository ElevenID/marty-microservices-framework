"""
Domain ports for ML components.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from .entities import Feature, FeatureGroup, MLModel, ModelPrediction, ModelStatus


class FeatureStorePort(ABC):
    """Abstract interface for feature store implementations."""

    @abstractmethod
    def register_feature(self, feature: Feature) -> bool:
        """Register a feature."""

    @abstractmethod
    def register_feature_group(self, feature_group: FeatureGroup) -> bool:
        """Register a feature group."""

    @abstractmethod
    def get_online_features(self, entity_id: str, feature_names: list[str]) -> dict[str, Any]:
        """Get online features for an entity."""

    @abstractmethod
    def set_online_features(self, entity_id: str, features: dict[str, Any]) -> bool:
        """Set online features for an entity."""

    @abstractmethod
    def get_offline_features(
        self,
        feature_names: list[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get offline features for training."""

    @abstractmethod
    def add_offline_features(self, entity_id: str, features: dict[str, Any]) -> bool:
        """Add offline features for an entity."""

    @abstractmethod
    def compute_feature_statistics(self, feature_name: str) -> dict[str, Any]:
        """Compute statistics for a feature."""

    @abstractmethod
    def validate_features(self, entity_id: str, features: dict[str, Any]) -> dict[str, list[str]]:
        """Validate features against registered schema."""


class ModelRegistryPort(ABC):
    """Abstract interface for model registry."""

    @abstractmethod
    def register_model(self, model: MLModel) -> bool:
        """Register a new model."""

    @abstractmethod
    def get_model(self, name: str, version: str = "latest") -> MLModel | None:
        """Get model by name and version."""

    @abstractmethod
    def get_model_by_id(self, model_id: str) -> MLModel | None:
        """Get model by ID."""

    @abstractmethod
    def list_models(self, name: str | None = None) -> list[MLModel]:
        """List models."""

    @abstractmethod
    def set_alias(self, name: str, alias: str, version: str) -> bool:
        """Set alias for model version."""

    @abstractmethod
    def update_model_status(self, model_id: str, status: ModelStatus) -> bool:
        """Update model status."""

    @abstractmethod
    def add_lineage(self, parent_model_id: str, child_model_id: str) -> None:
        """Add model lineage relationship."""

    @abstractmethod
    def get_lineage(self, model_id: str) -> dict[str, list[str]]:
        """Get model lineage."""


class ModelServingPort(ABC):
    """Abstract interface for model serving."""

    @abstractmethod
    async def load_model(self, model_id: str) -> bool:
        """Load model into memory."""

    @abstractmethod
    async def unload_model(self, model_id: str) -> bool:
        """Unload model from memory."""

    @abstractmethod
    async def predict(
        self, model_id: str, input_data: dict[str, Any], use_cache: bool = True
    ) -> ModelPrediction | None:
        """Make prediction using model."""

    @abstractmethod
    def get_serving_status(self) -> dict[str, Any]:
        """Get overall serving status."""
