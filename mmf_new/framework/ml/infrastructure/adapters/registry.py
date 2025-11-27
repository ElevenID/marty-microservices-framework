"""
Model registry implementation.
"""

import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone

from ...domain.entities import MLModel
from ...domain.ports import ModelRegistryPort
from ...domain.value_objects import ModelStatus


class InMemoryModelRegistry(ModelRegistryPort):
    """In-memory implementation of ModelRegistryPort."""

    def __init__(self):
        """Initialize model registry."""
        self.models: dict[str, dict[str, MLModel]] = defaultdict(dict)  # name -> version -> model
        self.model_index: dict[str, MLModel] = {}  # model_id -> model

        # Model aliases (latest, production, etc.)
        self.aliases: dict[str, dict[str, str]] = defaultdict(dict)  # name -> alias -> version

        # Model lineage
        self.lineage: dict[str, list[str]] = defaultdict(
            list
        )  # parent_model_id -> [child_model_ids]

        # Thread safety
        self._lock = threading.RLock()

    def register_model(self, model: MLModel) -> bool:
        """Register a new model."""
        try:
            with self._lock:
                self.models[model.name][model.version] = model
                self.model_index[model.model_id] = model

                # Set as latest version
                self.aliases[model.name]["latest"] = model.version

                logging.info("Registered model: %s v%s", model.name, model.version)
                return True

        except Exception as e:
            logging.exception("Failed to register model: %s", e)
            return False

    def get_model(self, name: str, version: str = "latest") -> MLModel | None:
        """Get model by name and version."""
        with self._lock:
            if version == "latest":
                latest_version = self.aliases[name].get("latest")
                if not latest_version:
                    return None
                version = latest_version

            return self.models[name].get(version)

    def get_model_by_id(self, model_id: str) -> MLModel | None:
        """Get model by ID."""
        with self._lock:
            return self.model_index.get(model_id)

    def list_models(self, name: str | None = None) -> list[MLModel]:
        """List models."""
        with self._lock:
            if name:
                return list(self.models[name].values())
            return list(self.model_index.values())

    def set_alias(self, name: str, alias: str, version: str) -> bool:
        """Set alias for model version."""
        try:
            with self._lock:
                if name in self.models and version in self.models[name]:
                    self.aliases[name][alias] = version
                    logging.info("Set alias %s for %s v%s", alias, name, version)
                    return True
                return False

        except Exception as e:
            logging.exception("Failed to set alias: %s", e)
            return False

    def update_model_status(self, model_id: str, status: ModelStatus) -> bool:
        """Update model status."""
        try:
            with self._lock:
                model = self.model_index.get(model_id)
                if model:
                    model.status = status
                    model.updated_at = datetime.now(timezone.utc)

                    if status == ModelStatus.DEPLOYED:
                        model.deployed_at = datetime.now(timezone.utc)

                    logging.info("Updated model %s status to %s", model_id, status.value)
                    return True
                return False

        except Exception as e:
            logging.exception("Failed to update model status: %s", e)
            return False

    def add_lineage(self, parent_model_id: str, child_model_id: str) -> None:
        """Add model lineage relationship."""
        with self._lock:
            self.lineage[parent_model_id].append(child_model_id)

    def get_lineage(self, model_id: str) -> dict[str, list[str]]:
        """Get model lineage."""
        with self._lock:
            # Find children
            children = self.lineage.get(model_id, [])

            # Find parent
            parent = None
            for parent_id, child_ids in self.lineage.items():
                if model_id in child_ids:
                    parent = parent_id
                    break

            # Ensure parent is a list of strings if found, or empty list
            parent_list = [parent] if parent else []

            return {"parent": parent_list, "children": children}
