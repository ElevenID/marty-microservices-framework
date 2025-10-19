"""
Message Serialization Framework

Provides comprehensive message serialization and deserialization support
for various formats including JSON, Pickle, Protocol Buffers, and Avro.
"""

import builtins
import datetime
import gzip
import io
import json
import logging
import pickle
import warnings
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import avro.io
import avro.schema
import msgpack

logger = logging.getLogger(__name__)


class RestrictedUnpickler(pickle.Unpickler):
    """Restricted unpickler that only allows safe types to prevent code execution."""

    SAFE_BUILTINS = {
        "str",
        "int",
        "float",
        "bool",
        "list",
        "tuple",
        "dict",
        "set",
        "frozenset",
        "bytes",
        "bytearray",
        "complex",
        "type",
        "slice",
        "range",
    }

    def find_class(self, module, name):
        # Only allow safe built-in types and specific allowed modules
        if module == "builtins" and name in self.SAFE_BUILTINS:
            return getattr(builtins, name)
        # Allow datetime objects which are commonly serialized in messages
        if module == "datetime" and name in {"datetime", "date", "time", "timedelta"}:

            return getattr(datetime, name)
        # Block everything else
        raise pickle.UnpicklingError(f"Forbidden class {module}.{name}")


class SerializationFormat(Enum):
    """Supported serialization formats."""

    JSON = "json"
    PICKLE = "pickle"
    PROTOBUF = "protobuf"
    AVRO = "avro"
    MSGPACK = "msgpack"


class CompressionType(Enum):
    """Supported compression types."""

    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"
    LZ4 = "lz4"


class SerializationError(Exception):
    """Exception raised during serialization/deserialization."""

    def __init__(self, message: str, format_type: str, original_error: Exception | None = None):
        super().__init__(message)
        self.format_type = format_type
        self.original_error = original_error


@dataclass
class SerializationConfig:
    """Configuration for message serialization."""

    format: SerializationFormat = SerializationFormat.JSON
    compression: CompressionType = CompressionType.NONE
    compression_level: int = 6
    encoding: str = "utf-8"

    # JSON specific
    json_ensure_ascii: bool = False
    json_sort_keys: bool = False
    json_indent: int | None = None

    # Pickle specific
    pickle_protocol: int = pickle.HIGHEST_PROTOCOL

    # Protobuf specific
    protobuf_message_type: builtins.type | None = None

    # Custom serialization hooks
    custom_encoder: Any | None = None
    custom_decoder: Any | None = None


class MessageSerializer(ABC):
    """Abstract base class for message serializers."""

    def __init__(self, config: SerializationConfig | None = None):
        self.config = config or SerializationConfig()

    @abstractmethod
    def serialize(self, data: Any) -> bytes:
        """Serialize data to bytes."""

    @abstractmethod
    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to data."""

    def compress(self, data: bytes) -> bytes:
        """Compress serialized data."""
        if self.config.compression == CompressionType.NONE:
            return data
        if self.config.compression == CompressionType.GZIP:
            return gzip.compress(data, compresslevel=self.config.compression_level)
        if self.config.compression == CompressionType.ZLIB:
            return zlib.compress(data, level=self.config.compression_level)
        raise SerializationError(
            f"Unsupported compression type: {self.config.compression}",
            self.config.format.value,
        )

    def decompress(self, data: bytes) -> bytes:
        """Decompress data."""
        if self.config.compression == CompressionType.NONE:
            return data
        if self.config.compression == CompressionType.GZIP:
            return gzip.decompress(data)
        if self.config.compression == CompressionType.ZLIB:
            return zlib.decompress(data)
        raise SerializationError(
            f"Unsupported compression type: {self.config.compression}",
            self.config.format.value,
        )

    def get_content_type(self) -> str:
        """Get content type for this serializer."""
        content_types = {
            SerializationFormat.JSON: "application/json",
            SerializationFormat.PICKLE: "application/octet-stream",
            SerializationFormat.PROTOBUF: "application/x-protobuf",
            SerializationFormat.AVRO: "application/avro",
            SerializationFormat.MSGPACK: "application/msgpack",
        }
        return content_types.get(self.config.format, "application/octet-stream")


class JSONSerializer(MessageSerializer):
    """JSON message serializer."""

    def __init__(self, config: SerializationConfig | None = None):
        super().__init__(config)
        if self.config.format != SerializationFormat.JSON:
            self.config.format = SerializationFormat.JSON

    def serialize(self, data: Any) -> bytes:
        """Serialize data to JSON bytes."""
        try:
            json_str = json.dumps(
                data,
                ensure_ascii=self.config.json_ensure_ascii,
                sort_keys=self.config.json_sort_keys,
                indent=self.config.json_indent,
                cls=self.config.custom_encoder,
            )

            json_bytes = json_str.encode(self.config.encoding)
            return self.compress(json_bytes)

        except Exception as e:
            raise SerializationError(f"Failed to serialize to JSON: {e!s}", "json", e)

    def deserialize(self, data: bytes) -> Any:
        """Deserialize JSON bytes to data."""
        try:
            decompressed = self.decompress(data)
            json_str = decompressed.decode(self.config.encoding)

            return json.loads(json_str, cls=self.config.custom_decoder)

        except Exception as e:
            raise SerializationError(f"Failed to deserialize from JSON: {e!s}", "json", e)


class PickleSerializer(MessageSerializer):
    """Pickle message serializer."""

    def __init__(self, config: SerializationConfig | None = None):
        super().__init__(config)
        if self.config.format != SerializationFormat.PICKLE:
            self.config.format = SerializationFormat.PICKLE

    def serialize(self, data: Any) -> bytes:
        """Serialize data to pickle bytes."""
        try:
            pickle_bytes = pickle.dumps(data, protocol=self.config.pickle_protocol)
            return self.compress(pickle_bytes)

        except Exception as e:
            raise SerializationError(f"Failed to serialize to pickle: {e!s}", "pickle", e)

    def deserialize(self, data: bytes) -> Any:
        """Deserialize pickle bytes to data."""
        try:
            decompressed = self.decompress(data)

            # Security: Use restricted unpickler to prevent arbitrary code execution
            warnings.warn(
                "Pickle deserialization is potentially unsafe. Consider using JSON or Protocol Buffers for better security.",
                UserWarning,
                stacklevel=2,
            )
            return RestrictedUnpickler(io.BytesIO(decompressed)).load()

        except Exception as e:
            raise SerializationError(f"Failed to deserialize from pickle: {e!s}", "pickle", e)


class ProtobufSerializer(MessageSerializer):
    """Protocol Buffers message serializer."""

    def __init__(self, config: SerializationConfig | None = None):
        super().__init__(config)
        if self.config.format != SerializationFormat.PROTOBUF:
            self.config.format = SerializationFormat.PROTOBUF

        if not self.config.protobuf_message_type:
            raise SerializationError("Protobuf message type must be specified", "protobuf")

    def serialize(self, data: Any) -> bytes:
        """Serialize data to protobuf bytes."""
        try:
            if hasattr(data, "SerializeToString"):
                # Already a protobuf message
                proto_bytes = data.SerializeToString()
            else:
                # Create protobuf message from data
                message = self.config.protobuf_message_type()
                if hasattr(message, "CopyFrom") and hasattr(data, "SerializeToString"):
                    message.CopyFrom(data)
                else:
                    # Assume data is a dict and try to populate fields
                    for key, value in data.items():
                        setattr(message, key, value)
                proto_bytes = message.SerializeToString()

            return self.compress(proto_bytes)

        except Exception as e:
            raise SerializationError(f"Failed to serialize to protobuf: {e!s}", "protobuf", e)

    def deserialize(self, data: bytes) -> Any:
        """Deserialize protobuf bytes to data."""
        try:
            decompressed = self.decompress(data)
            message = self.config.protobuf_message_type()
            message.ParseFromString(decompressed)
            return message

        except Exception as e:
            raise SerializationError(f"Failed to deserialize from protobuf: {e!s}", "protobuf", e)


class AvroSerializer(MessageSerializer):
    """Apache Avro message serializer."""

    def __init__(
        self,
        config: SerializationConfig | None = None,
        schema: builtins.dict | None = None,
    ):
        super().__init__(config)
        if self.config.format != SerializationFormat.AVRO:
            self.config.format = SerializationFormat.AVRO

        self.schema = schema


        self._avro_schema = avro.schema
        self._avro_io = avro.io

    def serialize(self, data: Any) -> bytes:
        """Serialize data to Avro bytes."""

        if not self.schema:
            raise SerializationError("Avro schema must be specified", "avro")

        try:

            schema = self._avro_schema.parse(json.dumps(self.schema))
            bytes_writer = io.BytesIO()
            encoder = self._avro_io.BinaryEncoder(bytes_writer)
            datum_writer = self._avro_io.DatumWriter(schema)
            datum_writer.write(data, encoder)

            avro_bytes = bytes_writer.getvalue()
            return self.compress(avro_bytes)

        except Exception as e:
            raise SerializationError(f"Failed to serialize to Avro: {e!s}", "avro", e)

    def deserialize(self, data: bytes) -> Any:
        """Deserialize Avro bytes to data."""
        if not self.schema:
            raise SerializationError("Avro schema must be specified", "avro")

        try:

            decompressed = self.decompress(data)
            schema = self._avro_schema.parse(json.dumps(self.schema))
            bytes_reader = io.BytesIO(decompressed)
            decoder = self._avro_io.BinaryDecoder(bytes_reader)
            datum_reader = self._avro_io.DatumReader(schema)

            return datum_reader.read(decoder)

        except Exception as e:
            raise SerializationError(f"Failed to deserialize from Avro: {e!s}", "avro", e)


class MessagePackSerializer(MessageSerializer):
    """MessagePack message serializer."""

    def __init__(self, config: SerializationConfig | None = None):
        super().__init__(config)
        if self.config.format != SerializationFormat.MSGPACK:
            self.config.format = SerializationFormat.MSGPACK

        self._msgpack = msgpack

    def serialize(self, data: Any) -> bytes:
        """Serialize data to MessagePack bytes."""

        try:
            msgpack_bytes = self._msgpack.packb(data)
            return self.compress(msgpack_bytes)

        except Exception as e:
            raise SerializationError(f"Failed to serialize to MessagePack: {e!s}", "msgpack", e)

    def deserialize(self, data: bytes) -> Any:
        """Deserialize MessagePack bytes to data."""
        try:
            decompressed = self.decompress(data)
            return self._msgpack.unpackb(decompressed, raw=False)

        except Exception as e:
            raise SerializationError(f"Failed to deserialize from MessagePack: {e!s}", "msgpack", e)


class SerializerFactory:
    """Factory for creating message serializers."""

    _serializers = {
        SerializationFormat.JSON: JSONSerializer,
        SerializationFormat.PICKLE: PickleSerializer,
        SerializationFormat.PROTOBUF: ProtobufSerializer,
        SerializationFormat.AVRO: AvroSerializer,
        SerializationFormat.MSGPACK: MessagePackSerializer,
    }

    @classmethod
    def create_serializer(
        cls,
        format_type: SerializationFormat | str,
        config: SerializationConfig | None = None,
        **kwargs,
    ) -> MessageSerializer:
        """Create serializer for specified format."""

        if isinstance(format_type, str):
            format_type = SerializationFormat(format_type)

        if format_type not in cls._serializers:
            raise SerializationError(
                f"Unsupported serialization format: {format_type}", format_type.value
            )

        serializer_class = cls._serializers[format_type]

        # Update config with specified format
        if config:
            config.format = format_type
        else:
            config = SerializationConfig(format=format_type)

        return serializer_class(config, **kwargs)

    @classmethod
    def register_serializer(
        cls,
        format_type: SerializationFormat,
        serializer_class: builtins.type[MessageSerializer],
    ):
        """Register custom serializer."""
        cls._serializers[format_type] = serializer_class

    @classmethod
    def get_supported_formats(cls) -> builtins.list[SerializationFormat]:
        """Get list of supported serialization formats."""
        return list(cls._serializers.keys())


# Convenience functions
def create_json_serializer(compressed: bool = False) -> JSONSerializer:
    """Create JSON serializer with optional compression."""
    config = SerializationConfig(
        format=SerializationFormat.JSON,
        compression=CompressionType.GZIP if compressed else CompressionType.NONE,
    )
    return JSONSerializer(config)


def create_pickle_serializer(compressed: bool = False) -> PickleSerializer:
    """Create Pickle serializer with optional compression."""
    config = SerializationConfig(
        format=SerializationFormat.PICKLE,
        compression=CompressionType.GZIP if compressed else CompressionType.NONE,
    )
    return PickleSerializer(config)


def create_protobuf_serializer(
    message_type: builtins.type, compressed: bool = False
) -> ProtobufSerializer:
    """Create Protobuf serializer with message type."""
    config = SerializationConfig(
        format=SerializationFormat.PROTOBUF,
        compression=CompressionType.GZIP if compressed else CompressionType.NONE,
        protobuf_message_type=message_type,
    )
    return ProtobufSerializer(config)


def create_avro_serializer(schema: builtins.dict, compressed: bool = False) -> AvroSerializer:
    """Create Avro serializer with schema."""
    config = SerializationConfig(
        format=SerializationFormat.AVRO,
        compression=CompressionType.GZIP if compressed else CompressionType.NONE,
    )
    return AvroSerializer(config, schema)
