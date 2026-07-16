"""
Marty Microservices Framework - Machine Learning Module.

This module provides a hexagonal architecture implementation of ML components
including Feature Store, Model Registry, and Model Serving.
"""

from .domain import (
    ABTestExperiment,
    ExperimentStatus,
    Feature,
    FeatureGroup,
    FeatureStorePort,
    FeatureType,
    MLModel,
    ModelFramework,
    ModelMetrics,
    ModelPrediction,
    ModelRegistryPort,
    ModelServingPort,
    ModelStatus,
    ModelType,
)
from .infrastructure import InMemoryFeatureStore, InMemoryModelRegistry, ModelServer

__all__ = [
    # Domain Entities
    "MLModel",
    "Feature",
    "FeatureGroup",
    "ModelPrediction",
    "ABTestExperiment",
    "ModelMetrics",
    # Domain Value Objects
    "ModelType",
    "ModelFramework",
    "ModelStatus",
    "ExperimentStatus",
    "FeatureType",
    # Domain Ports
    "FeatureStorePort",
    "ModelRegistryPort",
    "ModelServingPort",
    # Infrastructure Adapters
    "InMemoryFeatureStore",
    "InMemoryModelRegistry",
    "ModelServer",
]
