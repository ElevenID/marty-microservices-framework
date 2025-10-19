"""
AI/ML Integration and Intelligent Services for Marty Microservices Framework

This module provides comprehensive AI/ML integration capabilities including model serving,
feature stores, A/B testing, automated deployment pipelines, and intelligent recommendations.

This is now a shim module that re-exports components from their dedicated packages.
For new code, prefer importing directly from the component packages.
"""

from marty_msf.framework.ml.feature_store.feature_store import FeatureStore

# Model types and data structures
from marty_msf.framework.ml.models import (
    ABTestExperiment,
    ExperimentStatus,
    Feature,
    FeatureGroup,
    FeatureType,
    MLModel,
    ModelFramework,
    ModelMetrics,
    ModelPrediction,
    ModelStatus,
    ModelType,
)

# Registry system
from marty_msf.framework.ml.registry.model_registry import ModelRegistry

# Model serving
from marty_msf.framework.ml.serving.model_server import ModelServer

# A/B Testing components
# TODO: Extract these from the original file
# from marty_msf.framework.ml.ab_testing.ab_test_manager import ABTestManager

# Traffic routing
# TODO: Extract these from the original file
# from marty_msf.framework.ml.routing.traffic_router import TrafficRouter

# Observability
# TODO: Extract these from the original file
# from marty_msf.framework.ml.observability.ml_observability import MLObservability


# Legacy compatibility - create_ml_platform function
def create_ml_platform():
    """Create complete ML platform."""

    model_registry = ModelRegistry()
    feature_store = FeatureStore()
    model_server = ModelServer(model_registry, feature_store)

    # TODO: Add these components when extracted
    # ab_test_manager = ABTestManager(model_server)
    # observability = MLObservability()

    return {
        "model_registry": model_registry,
        "feature_store": feature_store,
        "model_server": model_server,
        # TODO: Uncomment when extracted
        # "ab_test_manager": ab_test_manager,
        # "observability": observability,
    }


# Re-export commonly used classes for backward compatibility
__all__ = [
    # Enums
    "ModelType",
    "ModelFramework",
    "ModelStatus",
    "ExperimentStatus",
    "FeatureType",
    # Core models
    "MLModel",
    "Feature",
    "FeatureGroup",
    "ModelPrediction",
    "ABTestExperiment",
    "ModelMetrics",
    # Services
    "ModelRegistry",
    "FeatureStore",
    "ModelServer",
    # TODO: Add when extracted
    # "ABTestManager",
    # "TrafficRouter",
    # "MLObservability",
    # Factory function
    "create_ml_platform",
]
