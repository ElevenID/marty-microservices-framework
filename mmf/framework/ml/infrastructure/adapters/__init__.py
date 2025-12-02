"""
ML infrastructure adapters.
"""

from .feature_store import InMemoryFeatureStore
from .registry import InMemoryModelRegistry
from .serving import ModelServer

__all__ = [
    "InMemoryFeatureStore",
    "InMemoryModelRegistry",
    "ModelServer",
]
