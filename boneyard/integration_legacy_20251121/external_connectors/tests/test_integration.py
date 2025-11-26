"""
Integration Tests for External Connectors Package

Test the decomposed external connectors package structure and functionality.
"""

import os
import sys
import unittest

from marty_msf.framework.integration.external_connectors.base import (
    ExternalSystemConnector,
)
from marty_msf.framework.integration.external_connectors.config import (
    DataTransformation,
    ExternalSystemConfig,
    IntegrationRequest,
    IntegrationResponse,
)
from marty_msf.framework.integration.external_connectors.connectors.rest_api import (
    RESTAPIConnector,
)
from marty_msf.framework.integration.external_connectors.enums import (
    ConnectorType,
    DataFormat,
    IntegrationPattern,
    TransformationType,
)
from marty_msf.framework.integration.external_connectors.transformation import (
    DataTransformationEngine,
)

# Add the project root to path
project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
sys.path.insert(0, project_root)


class TestExternalConnectorsStructure(unittest.TestCase):
    """Test the structure and imports of the external connectors package."""

    def test_package_structure(self):
        """Test that all expected files exist in the package."""
        base_dir = os.path.dirname(os.path.dirname(__file__))

        expected_files = [
            "enums.py",
            "config.py",
            "base.py",
            "transformation.py",
            "__init__.py",
            "connectors/__init__.py",
            "connectors/rest_api.py",
        ]

        for file_path in expected_files:
            full_path = os.path.join(base_dir, file_path)
            self.assertTrue(os.path.exists(full_path), f"Missing file: {file_path}")

    def test_enum_imports(self):
        """Test that enums can be imported correctly."""
        try:
            # Test that enums have expected values
            self.assertEqual(ConnectorType.REST_API.value, "rest_api")
            self.assertEqual(DataFormat.JSON.value, "json")
            self.assertEqual(IntegrationPattern.REQUEST_RESPONSE.value, "request_response")
            self.assertEqual(TransformationType.MAPPING.value, "mapping")

            # Test that all expected enum members exist
            self.assertIn(ConnectorType.LEGACY_MAINFRAME, list(ConnectorType))
            self.assertIn(DataFormat.XML, list(DataFormat))
            self.assertIn(IntegrationPattern.WEBHOOK_CALLBACK, list(IntegrationPattern))
            self.assertIn(TransformationType.VALIDATION, list(TransformationType))

        except ImportError as e:
            self.fail(f"Failed to import enums: {e}")

    def test_config_dataclasses(self):
        """Test that config dataclasses can be imported and instantiated."""
        try:
            # Test ExternalSystemConfig
            config = ExternalSystemConfig(
                system_id="test_system",
                name="Test System",
                connector_type=ConnectorType.REST_API,
                endpoint_url="https://api.example.com",
            )

            self.assertEqual(config.system_id, "test_system")
            self.assertEqual(config.connector_type, ConnectorType.REST_API)
            self.assertEqual(config.input_format, DataFormat.JSON)  # Default value

            # Test IntegrationRequest
            request = IntegrationRequest(
                request_id="req_123",
                system_id="test_system",
                operation="/users",
                data={"method": "GET"},
            )

            self.assertEqual(request.request_id, "req_123")
            self.assertIsNotNone(request.created_at)

        except ImportError as e:
            self.fail(f"Failed to import config classes: {e}")

    def test_base_connector(self):
        """Test that base connector can be imported."""
        try:
            # Test that it's an abstract class
            self.assertTrue(hasattr(ExternalSystemConnector, "connect"))
            self.assertTrue(hasattr(ExternalSystemConnector, "disconnect"))
            self.assertTrue(hasattr(ExternalSystemConnector, "execute_request"))
            self.assertTrue(hasattr(ExternalSystemConnector, "health_check"))

        except ImportError as e:
            self.fail(f"Failed to import base connector: {e}")

    def test_transformation_engine(self):
        """Test that transformation engine can be imported."""
        try:
            # Test basic functionality
            engine = DataTransformationEngine()
            self.assertIsNotNone(engine.transformations)
            self.assertIsNotNone(engine.custom_transformers)
            self.assertIsNotNone(engine.built_in_transformers)

            # Test built-in transformers exist
            self.assertIn("json_to_xml", engine.built_in_transformers)
            self.assertIn("xml_to_json", engine.built_in_transformers)

        except ImportError as e:
            self.fail(f"Failed to import transformation engine: {e}")

    def test_rest_api_connector(self):
        """Test that REST API connector can be imported."""
        try:
            # Test that it has expected methods
            self.assertTrue(hasattr(RESTAPIConnector, "connect"))
            self.assertTrue(hasattr(RESTAPIConnector, "disconnect"))
            self.assertTrue(hasattr(RESTAPIConnector, "execute_request"))
            self.assertTrue(hasattr(RESTAPIConnector, "health_check"))

        except ImportError as e:
            self.fail(f"Failed to import REST API connector: {e}")


class TestTransformationEngine(unittest.TestCase):
    """Test transformation engine functionality."""

    def setUp(self):
        """Set up test fixtures."""
        try:
            self.engine = DataTransformationEngine()
        except ImportError:
            self.skipTest("Cannot import transformation engine")

    def test_json_to_xml_conversion(self):
        """Test JSON to XML conversion."""
        test_data = {"name": "John", "age": 30, "city": "New York"}
        result = self.engine._json_to_xml(test_data)

        self.assertIsInstance(result, str)
        self.assertIn("<name>John</name>", result)
        self.assertIn("<age>30</age>", result)
        self.assertIn("<city>New York</city>", result)

    def test_csv_to_json_conversion(self):
        """Test CSV to JSON conversion."""
        csv_data = "name,age,city\nJohn,30,New York\nJane,25,Boston"
        result = self.engine._csv_to_json(csv_data)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "John")
        self.assertEqual(result[1]["name"], "Jane")

    def test_flatten_json(self):
        """Test JSON flattening."""
        nested_data = {
            "user": {"name": "John", "address": {"street": "123 Main St", "city": "New York"}}
        }

        result = self.engine._flatten_json(nested_data)

        self.assertIn("user.name", result)
        self.assertIn("user.address.street", result)
        self.assertEqual(result["user.name"], "John")
        self.assertEqual(result["user.address.city"], "New York")


if __name__ == "__main__":
    unittest.main()
