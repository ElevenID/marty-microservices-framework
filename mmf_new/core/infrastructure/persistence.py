"""Read model store interfaces and implementations."""

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any


class ReadModelStore(ABC):
    """Abstract read model store interface."""

    @abstractmethod
    async def save(self, model_type: str, model_id: str, data: dict[str, Any]) -> None:
        """Save read model."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, model_type: str, model_id: str) -> dict[str, Any] | None:
        """Get read model by ID."""
        raise NotImplementedError

    @abstractmethod
    async def query(
        self,
        model_type: str,
        filters: dict[str, Any] | None = None,
        sort_by: str | None = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """Query read models."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, model_type: str, model_id: str) -> None:
        """Delete read model."""
        raise NotImplementedError

    @abstractmethod
    async def count(self, model_type: str, filters: dict[str, Any] | None = None) -> int:
        """Count read models."""
        raise NotImplementedError


class InMemoryReadModelStore(ReadModelStore):
    """In-memory read model store implementation."""

    def __init__(self):
        self._models: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def save(self, model_type: str, model_id: str, data: dict[str, Any]) -> None:
        """Save read model."""
        async with self._lock:
            self._models[model_type][model_id] = data.copy()

    async def get(self, model_type: str, model_id: str) -> dict[str, Any] | None:
        """Get read model by ID."""
        async with self._lock:
            return self._models[model_type].get(model_id)

    async def query(
        self,
        model_type: str,
        filters: dict[str, Any] | None = None,
        sort_by: str | None = None,
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """Query read models."""
        async with self._lock:
            models = list(self._models[model_type].values())

            # Apply filters
            if filters:
                filtered_models = []
                for model in models:
                    if self._matches_filters(model, filters):
                        filtered_models.append(model)
                models = filtered_models

            # Apply sorting
            if sort_by:
                reverse = sort_order.lower() == "desc"
                models.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)

            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            return models[start_idx:end_idx]

    async def delete(self, model_type: str, model_id: str) -> None:
        """Delete read model."""
        async with self._lock:
            if model_id in self._models[model_type]:
                del self._models[model_type][model_id]

    async def count(self, model_type: str, filters: dict[str, Any] | None = None) -> int:
        """Count read models."""
        async with self._lock:
            models = self._models[model_type].values()

            if not filters:
                return len(models)

            count = 0
            for model in models:
                if self._matches_filters(model, filters):
                    count += 1

            return count

    def _matches_filters(self, model: dict[str, Any], filters: dict[str, Any]) -> bool:
        """Check if model matches filters."""
        for key, value in filters.items():
            if key not in model:
                return False

            if isinstance(value, dict):
                # Handle complex filters like {"$gt": 100}
                for op, op_value in value.items():
                    if not self._apply_filter_operation(model[key], op, op_value):
                        return False
            # Simple equality filter
            elif model[key] != value:
                return False

        return True

    def _apply_filter_operation(self, field_value: Any, operation: str, op_value: Any) -> bool:
        """Apply filter operation."""
        if operation == "$eq":
            return field_value == op_value
        if operation == "$ne":
            return field_value != op_value
        if operation == "$gt":
            return field_value > op_value
        if operation == "$gte":
            return field_value >= op_value
        if operation == "$lt":
            return field_value < op_value
        if operation == "$lte":
            return field_value <= op_value
        if operation == "$in":
            return field_value in op_value
        if operation == "$nin":
            return field_value not in op_value
        return False
