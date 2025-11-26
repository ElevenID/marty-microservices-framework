"""
Tests for External Connectors Enums

Test all enumeration types for external system integration.
"""

from ..enums import ConnectorType, DataFormat, IntegrationPattern, TransformationType


class TestConnectorType:
    """Test ConnectorType enum."""

    def test_all_connector_types_defined(self):
        """Test that all expected connector types are defined."""
        expected_types = [
            "REST_API",
            "SOAP_API",
            "DATABASE",
            "FILE_SYSTEM",
            "FTP",
            "SFTP",
            "LEGACY_MAINFRAME",
            "MESSAGE_QUEUE",
            "WEBHOOK",
            "GRAPHQL",
            "CUSTOM",
        ]

        for type_name in expected_types:
            assert hasattr(ConnectorType, type_name)
            assert isinstance(getattr(ConnectorType, type_name), ConnectorType)

    def test_connector_type_values(self):
        """Test connector type enum values."""
        assert ConnectorType.REST_API.value == "rest_api"
        assert ConnectorType.SOAP_API.value == "soap_api"
        assert ConnectorType.DATABASE.value == "database"
        assert ConnectorType.LEGACY_MAINFRAME.value == "legacy_mainframe"

    def test_connector_type_iteration(self):
        """Test that all connector types can be iterated."""
        types = list(ConnectorType)
        assert len(types) == 11
        assert ConnectorType.REST_API in types
        assert ConnectorType.CUSTOM in types


class TestDataFormat:
    """Test DataFormat enum."""

    def test_all_data_formats_defined(self):
        """Test that all expected data formats are defined."""
        expected_formats = [
            "JSON",
            "XML",
            "CSV",
            "FIXED_WIDTH",
            "DELIMITED",
            "BINARY",
            "YAML",
            "AVRO",
            "PROTOBUF",
        ]

        for format_name in expected_formats:
            assert hasattr(DataFormat, format_name)
            assert isinstance(getattr(DataFormat, format_name), DataFormat)

    def test_data_format_values(self):
        """Test data format enum values."""
        assert DataFormat.JSON.value == "json"
        assert DataFormat.XML.value == "xml"
        assert DataFormat.CSV.value == "csv"
        assert DataFormat.FIXED_WIDTH.value == "fixed_width"


class TestIntegrationPattern:
    """Test IntegrationPattern enum."""

    def test_all_integration_patterns_defined(self):
        """Test that all expected integration patterns are defined."""
        expected_patterns = [
            "REQUEST_RESPONSE",
            "FIRE_AND_FORGET",
            "POLLING",
            "STREAMING",
            "BATCH_PROCESSING",
            "EVENT_SUBSCRIPTION",
            "WEBHOOK_CALLBACK",
        ]

        for pattern_name in expected_patterns:
            assert hasattr(IntegrationPattern, pattern_name)
            assert isinstance(getattr(IntegrationPattern, pattern_name), IntegrationPattern)

    def test_integration_pattern_values(self):
        """Test integration pattern enum values."""
        assert IntegrationPattern.REQUEST_RESPONSE.value == "request_response"
        assert IntegrationPattern.FIRE_AND_FORGET.value == "fire_and_forget"
        assert IntegrationPattern.POLLING.value == "polling"
        assert IntegrationPattern.WEBHOOK_CALLBACK.value == "webhook_callback"


class TestTransformationType:
    """Test TransformationType enum."""

    def test_all_transformation_types_defined(self):
        """Test that all expected transformation types are defined."""
        expected_types = [
            "MAPPING",
            "FILTERING",
            "AGGREGATION",
            "ENRICHMENT",
            "VALIDATION",
            "FORMAT_CONVERSION",
            "PROTOCOL_ADAPTATION",
        ]

        for type_name in expected_types:
            assert hasattr(TransformationType, type_name)
            assert isinstance(getattr(TransformationType, type_name), TransformationType)

    def test_transformation_type_values(self):
        """Test transformation type enum values."""
        assert TransformationType.MAPPING.value == "mapping"
        assert TransformationType.FILTERING.value == "filtering"
        assert TransformationType.FORMAT_CONVERSION.value == "format_conversion"
        assert TransformationType.PROTOCOL_ADAPTATION.value == "protocol_adaptation"

    def test_enum_consistency(self):
        """Test that all enums are properly defined and consistent."""
        # Test that values are unique within each enum
        connector_values = [ct.value for ct in ConnectorType]
        assert len(connector_values) == len(set(connector_values))

        format_values = [df.value for df in DataFormat]
        assert len(format_values) == len(set(format_values))

        pattern_values = [ip.value for ip in IntegrationPattern]
        assert len(pattern_values) == len(set(pattern_values))

        transform_values = [tt.value for tt in TransformationType]
        assert len(transform_values) == len(set(transform_values))
