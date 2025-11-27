"""
Feature store for ML feature management.
"""

import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np
from marty_msf.framework.ml.models import Feature, FeatureGroup, FeatureType

from .interface import FeatureStoreInterface


class FeatureStore(FeatureStoreInterface):
    """Feature store for ML feature management."""

    def __init__(self):
        """Initialize feature store."""
        self.features: dict[str, Feature] = {}
        self.feature_groups: dict[str, FeatureGroup] = {}

        # Feature data storage (in-memory for demo)
        self.online_store: dict[str, dict[str, Any]] = {}  # entity_id -> features
        self.offline_store: dict[str, list[dict[str, Any]]] = defaultdict(list)

        # Feature statistics
        self.feature_stats: dict[str, dict[str, Any]] = {}

        # Thread safety
        self._lock = threading.RLock()

    def register_feature(self, feature: Feature) -> bool:
        """Register a feature."""
        try:
            with self._lock:
                self.features[feature.feature_id] = feature
                logging.info("Registered feature: %s", feature.name)
                return True

        except Exception as e:
            logging.exception("Failed to register feature: %s", e)
            return False

    def register_feature_group(self, feature_group: FeatureGroup) -> bool:
        """Register a feature group."""
        try:
            with self._lock:
                self.feature_groups[feature_group.group_id] = feature_group
                logging.info("Registered feature group: %s", feature_group.name)
                return True

        except Exception as e:
            logging.exception("Failed to register feature group: %s", e)
            return False

    def get_online_features(self, entity_id: str, feature_names: list[str]) -> dict[str, Any]:
        """Get online features for an entity."""
        with self._lock:
            entity_features = self.online_store.get(entity_id, {})

            result = {}
            for feature_name in feature_names:
                result[feature_name] = entity_features.get(feature_name)

            return result

    def set_online_features(self, entity_id: str, features: dict[str, Any]) -> bool:
        """Set online features for an entity."""
        try:
            with self._lock:
                if entity_id not in self.online_store:
                    self.online_store[entity_id] = {}

                self.online_store[entity_id].update(features)
                return True

        except Exception as e:
            logging.exception("Failed to set online features: %s", e)
            return False

    def get_offline_features(
        self,
        feature_names: list[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get offline features for training."""
        with self._lock:
            result = []

            for entity_id, feature_history in self.offline_store.items():
                for feature_record in feature_history:
                    # Apply time filters
                    record_time = feature_record.get("timestamp")
                    if start_time and record_time and record_time < start_time:
                        continue
                    if end_time and record_time and record_time > end_time:
                        continue

                    # Extract requested features
                    filtered_record = {"entity_id": entity_id}
                    for feature_name in feature_names:
                        if feature_name in feature_record:
                            filtered_record[feature_name] = feature_record[feature_name]

                    result.append(filtered_record)

            return result

    def add_offline_features(self, entity_id: str, features: dict[str, Any]) -> bool:
        """Add offline features for an entity."""
        try:
            with self._lock:
                features["timestamp"] = datetime.now(timezone.utc)
                self.offline_store[entity_id].append(features)
                return True

        except Exception as e:
            logging.exception("Failed to add offline features: %s", e)
            return False

    def compute_feature_statistics(self, feature_name: str) -> dict[str, Any]:
        """Compute statistics for a feature."""
        with self._lock:
            values = []

            # Collect values from online store
            for entity_features in self.online_store.values():
                if feature_name in entity_features:
                    value = entity_features[feature_name]
                    if value is not None:
                        values.append(value)

            # Collect values from offline store
            for feature_history in self.offline_store.values():
                for feature_record in feature_history:
                    if feature_name in feature_record:
                        value = feature_record[feature_name]
                        if value is not None:
                            values.append(value)

            if not values:
                return {}

            # Compute statistics
            stats = {
                "count": len(values),
                "unique_count": len(set(values)),
                "null_count": 0,  # Already filtered out nulls
            }

            # Numerical statistics
            if all(isinstance(v, int | float) for v in values):
                stats.update(
                    {
                        "mean": np.mean(values),
                        "std": np.std(values),
                        "min": np.min(values),
                        "max": np.max(values),
                        "median": np.median(values),
                        "percentile_25": np.percentile(values, 25),
                        "percentile_75": np.percentile(values, 75),
                    }
                )

            self.feature_stats[feature_name] = stats
            return stats

    def validate_features(self, entity_id: str, features: dict[str, Any]) -> dict[str, list[str]]:
        """Validate features against registered schema."""
        validation_errors = defaultdict(list)

        for feature_name, value in features.items():
            feature = self.features.get(feature_name)

            if not feature:
                validation_errors[feature_name].append("Feature not registered")
                continue

            # Required validation
            if feature.required and value is None:
                validation_errors[feature_name].append("Required feature is null")
                continue

            if value is None:
                continue  # Skip other validations for null values

            # Type validation
            if feature.feature_type == FeatureType.NUMERICAL and not isinstance(value, int | float):
                validation_errors[feature_name].append("Expected numerical value")

            # Range validation
            if (
                feature.min_value is not None
                and isinstance(value, int | float)
                and value < feature.min_value
            ):
                validation_errors[feature_name].append(f"Value below minimum: {feature.min_value}")

            if (
                feature.max_value is not None
                and isinstance(value, int | float)
                and value > feature.max_value
            ):
                validation_errors[feature_name].append(f"Value above maximum: {feature.max_value}")

            # Allowed values validation
            if feature.allowed_values and value not in feature.allowed_values:
                validation_errors[feature_name].append(
                    f"Value not in allowed list: {feature.allowed_values}"
                )

        return dict(validation_errors)
