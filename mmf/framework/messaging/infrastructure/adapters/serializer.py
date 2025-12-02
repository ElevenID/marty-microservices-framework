from __future__ import annotations

import json
from typing import Any

from mmf.framework.messaging.domain.models import MessagingError
from mmf.framework.messaging.domain.ports import IMessageSerializer


class JSONMessageSerializer(IMessageSerializer):
    """JSON message serializer implementation."""

    def serialize(self, data: Any) -> bytes:
        """Serialize data to JSON bytes."""
        try:
            return json.dumps(data, default=str).encode("utf-8")
        except (TypeError, ValueError) as e:
            raise MessagingError(f"Failed to serialize data: {e}") from e

    def deserialize(self, data: bytes) -> Any:
        """Deserialize JSON bytes to data."""
        try:
            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise MessagingError(f"Failed to deserialize data: {e}") from e

    def get_content_type(self) -> str:
        """Get content type for JSON."""
        return "application/json"
