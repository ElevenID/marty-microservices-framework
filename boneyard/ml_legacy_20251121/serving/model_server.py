"""
Model serving infrastructure for the Marty Microservices Framework.
"""

import builtins
import hashlib
import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

from marty_msf.framework.ml.models import (
    ModelFramework,
    ModelMetrics,
    ModelPrediction,
    ModelStatus,
)


class ModelServer:
    """Model serving infrastructure."""

    def __init__(self, model_registry, feature_store):
        """Initialize model server."""
        self.model_registry = model_registry
        self.feature_store = feature_store

        # Loaded models cache
        self.loaded_models: builtins.dict[str, Any] = {}

        # Prediction cache
        self.prediction_cache: builtins.dict[str, ModelPrediction] = {}

        # Performance tracking
        self.model_metrics: builtins.dict[str, builtins.list[ModelMetrics]] = defaultdict(list)

        # Thread safety
        self._lock = threading.RLock()

    async def load_model(self, model_id: str) -> bool:
        """Load model into memory."""
        try:
            model = self.model_registry.get_model_by_id(model_id)
            if not model:
                return False

            with self._lock:
                # Simulate model loading
                if model.framework == ModelFramework.SKLEARN:
                    # Load sklearn model
                    if model.model_path:
                        # In practice: model_obj = joblib.load(model.model_path)
                        model_obj = {"type": "sklearn", "path": model.model_path}
                    else:
                        # In practice: model_obj = pickle.loads(model.model_data)
                        model_obj = {"type": "sklearn", "data": "serialized_model"}

                elif model.framework == ModelFramework.TENSORFLOW:
                    # Load TensorFlow model
                    model_obj = {"type": "tensorflow", "path": model.model_path}

                else:
                    # Generic model loading
                    model_obj = {"type": "generic", "framework": model.framework.value}

                self.loaded_models[model_id] = model_obj

                # Update model status
                self.model_registry.update_model_status(model_id, ModelStatus.SERVING)

                logging.info("Loaded model: %s", model_id)
                return True

        except Exception as e:
            logging.exception("Failed to load model %s: %s", model_id, e)
            return False

    async def unload_model(self, model_id: str) -> bool:
        """Unload model from memory."""
        try:
            with self._lock:
                if model_id in self.loaded_models:
                    del self.loaded_models[model_id]

                    # Update model status
                    self.model_registry.update_model_status(model_id, ModelStatus.READY)

                    logging.info("Unloaded model: %s", model_id)
                    return True
                return False

        except Exception as e:
            logging.exception("Failed to unload model %s: %s", model_id, e)
            return False

    async def predict(
        self, model_id: str, input_data: builtins.dict[str, Any], use_cache: bool = True
    ) -> ModelPrediction | None:
        """Make prediction using model."""
        start_time = time.time()

        try:
            # Check cache first
            if use_cache:
                cache_key = self._generate_cache_key(model_id, input_data)
                cached_prediction = self.prediction_cache.get(cache_key)

                if cached_prediction:
                    return cached_prediction

            # Load model if not loaded
            if model_id not in self.loaded_models:
                success = await self.load_model(model_id)
                if not success:
                    return None

            self.model_registry.get_model_by_id(model_id)
            model_obj = self.loaded_models[model_id]

            # Prepare features
            features = await self._prepare_features(model_id, input_data)

            # Make prediction
            prediction_result = await self._make_prediction(model_obj, features)

            # Create prediction object
            prediction = ModelPrediction(
                prediction_id=str(uuid.uuid4()),
                model_id=model_id,
                input_features=features,
                prediction=prediction_result["prediction"],
                confidence=prediction_result.get("confidence"),
                probabilities=prediction_result.get("probabilities"),
                latency_ms=(time.time() - start_time) * 1000,
            )

            # Cache prediction
            if use_cache:
                cache_key = self._generate_cache_key(model_id, input_data)
                self.prediction_cache[cache_key] = prediction

            # Update metrics
            self._update_model_metrics(model_id, prediction.latency_ms, success=True)

            return prediction

        except Exception as e:
            self._update_model_metrics(model_id, (time.time() - start_time) * 1000, success=False)
            logging.exception("Prediction error for model %s: %s", model_id, e)
            return None

    async def _prepare_features(
        self, model_id: str, input_data: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Prepare features for prediction."""
        # Get feature names from model metadata
        model = self.model_registry.get_model_by_id(model_id)
        required_features = model.metadata.get("required_features", [])

        features = {}

        for feature_name in required_features:
            if feature_name in input_data:
                features[feature_name] = input_data[feature_name]
            else:
                # Try to get from feature store
                entity_id = input_data.get("entity_id")
                if entity_id:
                    feature_value = self.feature_store.get_online_features(
                        entity_id, [feature_name]
                    ).get(feature_name)

                    if feature_value is not None:
                        features[feature_name] = feature_value

        return features

    async def _make_prediction(
        self, model_obj: Any, features: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Make prediction using loaded model."""
        # Simulate prediction based on model type
        framework = model_obj.get("type", "generic")

        if framework == "sklearn":
            # Simulate sklearn prediction
            # In practice: prediction = model_obj.predict([list(features.values())])[0]
            prediction = np.random.random()
            confidence = np.random.random()

            return {"prediction": prediction, "confidence": confidence}

        if framework == "tensorflow":
            # Simulate TensorFlow prediction
            prediction = np.random.random(10)  # Multi-class prediction
            probabilities = {f"class_{i}": float(pred) for i, pred in enumerate(prediction)}

            return {
                "prediction": int(np.argmax(prediction)),
                "probabilities": probabilities,
                "confidence": float(np.max(prediction)),
            }

        # Generic prediction
        return {"prediction": np.random.random(), "confidence": np.random.random()}

    def _generate_cache_key(self, model_id: str, input_data: builtins.dict[str, Any]) -> str:
        """Generate cache key for prediction."""
        # Create deterministic hash of model_id and input_data
        cache_input = {"model_id": model_id, "input_data": input_data}

        cache_string = json.dumps(cache_input, sort_keys=True)
        return hashlib.sha256(cache_string.encode()).hexdigest()[:16]

    def _update_model_metrics(self, model_id: str, latency_ms: float, success: bool):
        """Update model performance metrics."""
        with self._lock:
            # Get current metrics or create new
            current_metrics = self.model_metrics[model_id]

            if not current_metrics or len(current_metrics) == 0:
                metrics = ModelMetrics(model_id=model_id, timestamp=datetime.now(timezone.utc))
                self.model_metrics[model_id].append(metrics)
            else:
                metrics = current_metrics[-1]

                # Create new metrics if current one is too old (> 1 minute)
                if (datetime.now(timezone.utc) - metrics.timestamp).total_seconds() > 60:
                    metrics = ModelMetrics(model_id=model_id, timestamp=datetime.now(timezone.utc))
                    self.model_metrics[model_id].append(metrics)

            # Update metrics
            metrics.request_count += 1

            if success:
                metrics.success_count += 1
            else:
                metrics.error_count += 1

            # Update latency (moving average)
            if metrics.request_count == 1:
                metrics.avg_latency = latency_ms
            else:
                metrics.avg_latency = (
                    metrics.avg_latency * (metrics.request_count - 1) + latency_ms
                ) / metrics.request_count

            # Update percentiles (simplified)
            metrics.p95_latency = max(metrics.p95_latency, latency_ms)
            metrics.p99_latency = max(metrics.p99_latency, latency_ms)

    def get_model_metrics(self, model_id: str) -> builtins.list[ModelMetrics]:
        """Get performance metrics for a model."""
        with self._lock:
            return self.model_metrics.get(model_id, [])

    def get_serving_status(self) -> builtins.dict[str, Any]:
        """Get overall serving status."""
        with self._lock:
            total_models = len(self.loaded_models)
            total_requests = sum(
                sum(m.request_count for m in metrics) for metrics in self.model_metrics.values()
            )

            return {
                "loaded_models": total_models,
                "total_requests": total_requests,
                "cache_size": len(self.prediction_cache),
                "loaded_model_ids": list(self.loaded_models.keys()),
            }
