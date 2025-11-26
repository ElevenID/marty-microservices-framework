"""
External System Integration Enums

Enumeration definitions for external connector types, integration patterns,
data formats, and transformation types.
"""

from enum import Enum


class ConnectorType(Enum):
    """External connector types."""

    REST_API = "rest_api"
    SOAP_API = "soap_api"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    FTP = "ftp"
    SFTP = "sftp"
    LEGACY_MAINFRAME = "legacy_mainframe"
    MESSAGE_QUEUE = "message_queue"
    WEBHOOK = "webhook"
    GRAPHQL = "graphql"
    CUSTOM = "custom"


class IntegrationPattern(Enum):
    """Integration patterns."""

    REQUEST_RESPONSE = "request_response"
    FIRE_AND_FORGET = "fire_and_forget"
    POLLING = "polling"
    STREAMING = "streaming"
    BATCH_PROCESSING = "batch_processing"
    EVENT_SUBSCRIPTION = "event_subscription"
    WEBHOOK_CALLBACK = "webhook_callback"


class DataFormat(Enum):
    """Data formats for integration."""

    JSON = "json"
    XML = "xml"
    CSV = "csv"
    FIXED_WIDTH = "fixed_width"
    DELIMITED = "delimited"
    BINARY = "binary"
    YAML = "yaml"
    AVRO = "avro"
    PROTOBUF = "protobuf"


class TransformationType(Enum):
    """Data transformation types."""

    MAPPING = "mapping"
    FILTERING = "filtering"
    AGGREGATION = "aggregation"
    ENRICHMENT = "enrichment"
    VALIDATION = "validation"
    FORMAT_CONVERSION = "format_conversion"
    PROTOCOL_ADAPTATION = "protocol_adaptation"
