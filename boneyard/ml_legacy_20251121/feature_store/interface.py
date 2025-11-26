"""
Feature store interface definition.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from marty_msf.framework.ml.models import Feature, FeatureGroup


class FeatureStoreInterface(ABC):
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
