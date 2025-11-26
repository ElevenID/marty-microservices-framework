import builtins
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

class ContractType(Enum):
    """Types of contracts supported."""
    HTTP_API = "http_api"
    MESSAGE_QUEUE = "message_queue"
    GRPC = "grpc"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    DATABASE = "database"

class VerificationLevel(Enum):
    """Contract verification levels."""
    STRICT = "strict"
    PERMISSIVE = "permissive"
    SCHEMA_ONLY = "schema_only"

@dataclass
class ContractRequest:
    """HTTP request specification for contract."""
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, Any] = field(default_factory=dict)
    body: Any | None = None
    content_type: str = "application/json"

@dataclass
class ContractResponse:
    """HTTP response specification for contract."""
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: Any | None = None
    schema: dict[str, Any] | None = None
    content_type: str = "application/json"

@dataclass
class ContractInteraction:
    """Single interaction in a contract."""
    description: str
    request: ContractRequest
    response: ContractResponse
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class Contract:
    """Service contract definition."""
    consumer: str
    provider: str
    version: str
    contract_type: ContractType
    interactions: list[ContractInteraction] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert contract to dictionary."""
        return {
            "consumer": self.consumer,
            "provider": self.provider,
            "version": self.version,
            "contract_type": self.contract_type.value,
            "interactions": [
                {
                    "description": interaction.description,
                    "request": {
                        "method": interaction.request.method,
                        "path": interaction.request.path,
                        "headers": interaction.request.headers,
                        "query_params": interaction.request.query_params,
                        "body": interaction.request.body,
                        "content_type": interaction.request.content_type,
                    },
                    "response": {
                        "status_code": interaction.response.status_code,
                        "headers": interaction.response.headers,
                        "body": interaction.response.body,
                        "schema": interaction.response.schema,
                        "content_type": interaction.response.content_type,
                    },
                    "metadata": interaction.metadata,
                }
                for interaction in self.interactions
            ],
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
