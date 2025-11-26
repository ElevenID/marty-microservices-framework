"""
Model registry for ML models with versioning and metadata.
"""

import builtins
import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone

from marty_msf.framework.ml.models import MLModel, ModelStatus


class ModelRegistry:
    """Registry for ML models with versioning and metadata."""

    def __init__(self):
        """Initialize model registry."""
        self.models: builtins.dict[str, builtins.dict[str, MLModel]] = defaultdict(
            dict
        )  # name -> version -> model
        self.model_index: builtins.dict[str, MLModel] = {}  # model_id -> model

        # Model aliases (latest, production, etc.)
        self.aliases: builtins.dict[str, builtins.dict[str, str]] = defaultdict(
            dict
        )  # name -> alias -> version

        # Model lineage
        self.lineage: builtins.dict[str, builtins.list[str]] = defaultdict(
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

                logging.info(f"Registered model: {model.name} v{model.version}")
                return True

        except Exception as e:
            logging.exception(f"Failed to register model: {e}")
            return False

    def get_model(self, name: str, version: str = "latest") -> MLModel | None:
        """Get model by name and version."""
        with self._lock:
            if version == "latest":
                version = self.aliases[name].get("latest")
                if not version:
                    return None

            return self.models[name].get(version)

    def get_model_by_id(self, model_id: str) -> MLModel | None:
        """Get model by ID."""
        with self._lock:
            return self.model_index.get(model_id)

    def list_models(self, name: str | None = None) -> builtins.list[MLModel]:
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
                    logging.info(f"Set alias {alias} for {name} v{version}")
                    return True
                return False

        except Exception as e:
            logging.exception(f"Failed to set alias: {e}")
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

                    logging.info(f"Updated model {model_id} status to {status.value}")
                    return True
                return False

        except Exception as e:
            logging.exception(f"Failed to update model status: {e}")
            return False

    def add_lineage(self, parent_model_id: str, child_model_id: str):
        """Add model lineage relationship."""
        with self._lock:
            self.lineage[parent_model_id].append(child_model_id)

    def get_lineage(self, model_id: str) -> builtins.dict[str, builtins.list[str]]:
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

            return {"parent": parent, "children": children}
