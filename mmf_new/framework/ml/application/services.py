"""
Application services for ML components.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from mmf_new.framework.ml.domain.entities import MLModel, ModelStatus, ModelType, ModelFramework
from mmf_new.framework.ml.domain.ports import FeatureStorePort


class ModelTrainingService:
    """Service for managing model training operations."""

    def __init__(self, feature_store: FeatureStorePort):
        self.feature_store = feature_store

    async def start_training(
        self,
        name: str,
        model_type: ModelType,
        framework: ModelFramework,
        feature_names: list[str],
        training_params: dict[str, Any],
    ) -> MLModel:
        """
        Start a model training job.

        Args:
            name: Name of the model
            model_type: Type of model (classification, regression, etc.)
            framework: Framework to use (sklearn, pytorch, etc.)
            feature_names: List of features to use for training
            training_params: Hyperparameters and other training configuration

        Returns:
            The created MLModel instance in TRAINING status
        """
        # 1. Validate features exist
        # In a real implementation, we might check if features are available in the store
        # self.feature_store.validate_features(...)

        # 2. Create model entity
        model_id = str(uuid4())
        model = MLModel(
            model_id=model_id,
            name=name,
            version="v1",  # Simplified versioning
            model_type=model_type,
            framework=framework,
            status=ModelStatus.TRAINING,
            hyperparameters=training_params,
            metadata={
                "feature_names": feature_names,
                "started_at": datetime.utcnow().isoformat(),
            },
        )

        # 3. Trigger training (this would likely involve an infrastructure adapter for a job queue)
        # For now, we just return the entity representing the started job
        
        return model

    async def complete_training(
        self,
        model: MLModel,
        metrics: dict[str, float],
        model_artifact: bytes,
    ) -> MLModel:
        """
        Complete a training job and update model status.

        Args:
            model: The model entity
            metrics: Training metrics (accuracy, etc.)
            model_artifact: The serialized model

        Returns:
            Updated MLModel in READY status
        """
        model.status = ModelStatus.READY
        model.model_data = model_artifact
        model.accuracy = metrics.get("accuracy")
        model.precision = metrics.get("precision")
        model.recall = metrics.get("recall")
        model.f1_score = metrics.get("f1_score")
        model.training_duration = metrics.get("duration")
        
        return model
