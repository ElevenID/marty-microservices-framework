"""
Data Transformation Service
"""

import csv
import io
import json
from collections.abc import Callable
from typing import Any

from defusedxml import ElementTree as ET
from mmf.framework.integration.domain.exceptions import TransformationError
from mmf.framework.integration.domain.models import DataFormat
from mmf.framework.integration.ports.transformation import TransformationPort


class DataTransformationService(TransformationPort):
    """Service for transforming data between formats."""

    def __init__(self):
        self._custom_transformers: dict[str, Callable] = {}

    def register_transformer(self, name: str, transformer: Callable) -> None:
        """Register a custom transformer."""
        self._custom_transformers[name] = transformer

    async def transform(self, data: Any, transformation_id: str) -> Any:
        """Transform data using specified transformation."""
        try:
            if transformation_id in self._custom_transformers:
                return self._custom_transformers[transformation_id](data)

            # Built-in transformations
            if transformation_id == "json_to_xml":
                return self._json_to_xml(data)
            elif transformation_id == "xml_to_json":
                return self._xml_to_json(data)
            elif transformation_id == "json_to_csv":
                return self._json_to_csv(data)
            elif transformation_id == "csv_to_json":
                return self._csv_to_json(data)

            raise TransformationError(f"Unknown transformation: {transformation_id}")

        except Exception as e:
            raise TransformationError(f"Transformation failed: {e}")

    async def validate(self, data: Any, schema_id: str) -> bool:
        """Validate data against schema."""
        # Placeholder for schema validation logic (e.g., using jsonschema)
        return True

    def _json_to_xml(self, data: dict | list) -> str:
        """Convert JSON/dict to XML string."""
        root = ET.Element("root")
        self._build_xml(root, data)
        return ET.tostring(root, encoding="unicode")

    def _build_xml(self, parent: ET.Element, data: Any) -> None:
        if isinstance(data, dict):
            for key, value in data.items():
                child = ET.SubElement(parent, str(key))
                self._build_xml(child, value)
        elif isinstance(data, list):
            for item in data:
                child = ET.SubElement(parent, "item")
                self._build_xml(child, item)
        else:
            parent.text = str(data)

    def _xml_to_json(self, xml_str: str) -> dict | str:
        """Convert XML string to dict."""
        root = ET.fromstring(xml_str)
        return self._xml_element_to_dict(root)

    def _xml_element_to_dict(self, element: ET.Element) -> dict | str:
        result = {}
        for child in element:
            child_data = self._xml_element_to_dict(child)
            if child.tag in result:
                if isinstance(result[child.tag], list):
                    result[child.tag].append(child_data)
                else:
                    result[child.tag] = [result[child.tag], child_data]
            else:
                result[child.tag] = child_data

        if not result and element.text:
            return element.text
        return result or ""

    def _json_to_csv(self, data: list[dict]) -> str:
        """Convert list of dicts to CSV string."""
        if not data:
            return ""

        output = io.StringIO()
        keys = data[0].keys()
        writer = csv.DictWriter(output, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()

    def _csv_to_json(self, csv_str: str) -> list[dict]:
        """Convert CSV string to list of dicts."""
        input_io = io.StringIO(csv_str)
        reader = csv.DictReader(input_io)
        return list(reader)
