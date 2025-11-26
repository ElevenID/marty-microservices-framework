"""
Data Transformation Engine

Engine for data transformations between external systems including format conversion,
field mapping, filtering, validation, and enrichment capabilities.
"""

import builtins
import csv
import io
import json
import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from defusedxml import ElementTree as ET

from .config import DataTransformation
from .enums import TransformationType


class DataTransformationEngine:
    """Engine for data transformations between systems."""

    def __init__(self):
        """Initialize transformation engine."""
        self.transformations: builtins.dict[str, DataTransformation] = {}
        self.custom_transformers: builtins.dict[str, Callable] = {}

        # Built-in transformers
        self.built_in_transformers = {
            "json_to_xml": self._json_to_xml,
            "xml_to_json": self._xml_to_json,
            "csv_to_json": self._csv_to_json,
            "json_to_csv": self._json_to_csv,
            "flatten_json": self._flatten_json,
            "unflatten_json": self._unflatten_json,
        }

    def register_transformation(self, transformation: DataTransformation) -> bool:
        """Register data transformation."""
        try:
            self.transformations[transformation.transformation_id] = transformation
            logging.info(f"Registered transformation: {transformation.name}")
            return True

        except Exception as e:
            logging.exception(f"Failed to register transformation: {e}")
            return False

    def register_custom_transformer(self, name: str, transformer: Callable) -> bool:
        """Register custom transformer function."""
        try:
            self.custom_transformers[name] = transformer
            logging.info(f"Registered custom transformer: {name}")
            return True

        except Exception as e:
            logging.exception(f"Failed to register custom transformer: {e}")
            return False

    def transform_data(self, data: Any, transformation_id: str) -> Any:
        """Apply transformation to data."""
        transformation = self.transformations.get(transformation_id)
        if not transformation:
            raise ValueError(f"Transformation not found: {transformation_id}")

        try:
            # Apply transformation based on type
            if transformation.transformation_type == TransformationType.MAPPING:
                return self._apply_mapping_transformation(data, transformation)

            if transformation.transformation_type == TransformationType.FILTERING:
                return self._apply_filtering_transformation(data, transformation)

            if transformation.transformation_type == TransformationType.FORMAT_CONVERSION:
                return self._apply_format_conversion(data, transformation)

            if transformation.transformation_type == TransformationType.VALIDATION:
                return self._apply_validation(data, transformation)

            if transformation.transformation_type == TransformationType.ENRICHMENT:
                return self._apply_enrichment(data, transformation)

            # Execute custom transformation script
            if transformation.transformation_script:
                return self._execute_transformation_script(
                    data, transformation.transformation_script
                )
            return data

        except Exception as e:
            logging.exception(f"Transformation error: {e}")
            raise

    def _apply_mapping_transformation(self, data: Any, transformation: DataTransformation) -> Any:
        """Apply field mapping transformation."""
        if not isinstance(data, dict):
            return data

        result = {}

        for rule in transformation.mapping_rules:
            source_field = rule.get("source_field")
            target_field = rule.get("target_field")
            default_value = rule.get("default_value")

            if source_field in data:
                result[target_field] = data[source_field]
            elif default_value is not None:
                result[target_field] = default_value

        return result

    def _apply_filtering_transformation(self, data: Any, transformation: DataTransformation) -> Any:
        """Apply filtering transformation."""
        if isinstance(data, list):
            # Filter array items
            filtered_items = []

            for item in data:
                if self._matches_filter_conditions(item, transformation.mapping_rules):
                    filtered_items.append(item)

            return filtered_items

        if isinstance(data, dict):
            # Filter object fields
            if self._matches_filter_conditions(data, transformation.mapping_rules):
                return data
            return None

        return data

    def _matches_filter_conditions(
        self,
        item: builtins.dict[str, Any],
        conditions: builtins.list[builtins.dict[str, Any]],
    ) -> bool:
        """Check if item matches filter conditions."""
        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator", "eq")
            value = condition.get("value")

            item_value = item.get(field)

            if (operator == "eq" and item_value != value) or (
                operator == "ne" and item_value == value
            ):
                return False
            if (
                (operator == "gt" and (item_value is None or item_value <= value))
                or (operator == "lt" and (item_value is None or item_value >= value))
                or (operator == "contains" and (item_value is None or value not in str(item_value)))
                or (operator == "in" and (item_value is None or item_value not in value))
            ):
                return False

        return True

    def _apply_format_conversion(self, data: Any, transformation: DataTransformation) -> Any:
        """Apply format conversion transformation."""
        source_format = (
            transformation.source_schema.get("format") if transformation.source_schema else "json"
        )
        target_format = (
            transformation.target_schema.get("format") if transformation.target_schema else "json"
        )

        converter_name = f"{source_format}_to_{target_format}"

        if converter_name in self.built_in_transformers:
            return self.built_in_transformers[converter_name](data)
        if converter_name in self.custom_transformers:
            return self.custom_transformers[converter_name](data)
        return data

    def _apply_validation(self, data: Any, transformation: DataTransformation) -> Any:
        """Apply validation transformation."""
        errors = []

        for rule in transformation.validation_rules:
            field = rule.get("field")
            rule_type = rule.get("type")
            parameters = rule.get("parameters", {})

            if isinstance(data, dict) and field in data:
                field_value = data[field]

                if rule_type == "required" and field_value is None:
                    errors.append(f"Field {field} is required")

                elif rule_type == "type" and not isinstance(
                    field_value, parameters.get("expected_type")
                ):
                    errors.append(
                        f"Field {field} must be of type {parameters.get('expected_type')}"
                    )

                elif rule_type == "range" and isinstance(field_value, int | float):
                    min_val = parameters.get("min")
                    max_val = parameters.get("max")

                    if min_val is not None and field_value < min_val:
                        errors.append(f"Field {field} must be >= {min_val}")

                    if max_val is not None and field_value > max_val:
                        errors.append(f"Field {field} must be <= {max_val}")

                elif rule_type == "pattern" and isinstance(field_value, str):
                    pattern = parameters.get("pattern")
                    if pattern and not re.match(pattern, field_value):
                        errors.append(f"Field {field} does not match pattern {pattern}")

        if errors:
            raise ValueError(f"Validation errors: {'; '.join(errors)}")

        return data

    def _apply_enrichment(self, data: Any, transformation: DataTransformation) -> Any:
        """Apply data enrichment transformation."""
        if not isinstance(data, dict):
            return data

        enriched_data = data.copy()

        for rule in transformation.mapping_rules:
            enrichment_type = rule.get("type")

            if enrichment_type == "add_timestamp":
                enriched_data["enriched_at"] = datetime.now(timezone.utc).isoformat()

            elif enrichment_type == "add_field":
                field_name = rule.get("field_name")
                field_value = rule.get("field_value")
                enriched_data[field_name] = field_value

            elif enrichment_type == "lookup":
                # Placeholder for external lookup
                lookup_field = rule.get("lookup_field")
                lookup_value = data.get(lookup_field)

                if lookup_value:
                    # Simulate lookup result
                    enriched_data[f"{lookup_field}_enriched"] = f"enriched_{lookup_value}"

        return enriched_data

    def _execute_transformation_script(self, data: Any, script: str) -> Any:
        """Execute transformation script with security restrictions."""
        # Security: Use restricted evaluation instead of exec()
        safe_functions = {
            "json": json,
            "datetime": datetime,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "sorted": sorted,
            "reversed": reversed,
            "sum": sum,
            "min": min,
            "max": max,
        }

        local_vars = {"data": data, "result": data}

        try:
            # Only allow simple result assignments for security
            if script.strip().startswith("result = "):
                expression = script.strip()[9:]  # Remove 'result = '

                # Basic safety check - only allow safe characters
                if re.match(r'^[a-zA-Z0-9\[\]{}().,_\'":\s+-]*$', expression):
                    try:
                        result = eval(
                            expression,
                            {"__builtins__": {}},
                            {**safe_functions, **local_vars},
                        )
                        return result
                    except Exception:
                        pass

            # Log blocked unsafe scripts
            logging.warning(f"Unsafe transformation script blocked: {script[:100]}...")
            return data

        except Exception as e:
            logging.exception(f"Transformation script error: {e}")
            raise

    # Built-in transformation functions
    def _json_to_xml(self, data: Any) -> str:
        """Convert JSON to XML."""

        def dict_to_xml(d, root_name="root"):
            xml_str = f"<{root_name}>"

            for key, value in d.items():
                if isinstance(value, dict):
                    xml_str += dict_to_xml(value, key)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            xml_str += dict_to_xml(item, key)
                        else:
                            xml_str += f"<{key}>{item}</{key}>"
                else:
                    xml_str += f"<{key}>{value}</{key}>"

            xml_str += f"</{root_name}>"
            return xml_str

        if isinstance(data, dict):
            return dict_to_xml(data)
        return f"<data>{data}</data>"

    def _xml_to_json(self, xml_data: str) -> builtins.dict[str, Any]:
        """Convert XML to JSON."""
        try:
            root = ET.fromstring(xml_data)

            def xml_to_dict(element):
                result = {}

                # Add attributes
                if element.attrib:
                    result.update(element.attrib)

                # Add text content
                if element.text and element.text.strip():
                    if element.attrib or len(element) > 0:
                        result["_text"] = element.text.strip()
                    else:
                        return element.text.strip()

                # Add child elements
                for child in element:
                    child_data = xml_to_dict(child)

                    if child.tag in result:
                        # Convert to list if multiple elements with same tag
                        if not isinstance(result[child.tag], list):
                            result[child.tag] = [result[child.tag]]
                        result[child.tag].append(child_data)
                    else:
                        result[child.tag] = child_data

                return result

            return {root.tag: xml_to_dict(root)}

        except ET.ParseError as e:
            logging.exception(f"XML parsing error: {e}")
            return {"error": f"Invalid XML: {e}"}

    def _csv_to_json(self, csv_data: str) -> builtins.list[builtins.dict[str, Any]]:
        """Convert CSV to JSON."""
        reader = csv.DictReader(io.StringIO(csv_data))
        return list(reader)

    def _json_to_csv(self, json_data: builtins.list[builtins.dict[str, Any]]) -> str:
        """Convert JSON to CSV."""
        if not json_data:
            return ""

        output = io.StringIO()

        # Get all unique field names
        fieldnames = set()
        for row in json_data:
            fieldnames.update(row.keys())

        fieldnames = sorted(fieldnames)

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in json_data:
            writer.writerow(row)

        return output.getvalue()

    def _flatten_json(
        self, data: builtins.dict[str, Any], separator: str = "."
    ) -> builtins.dict[str, Any]:
        """Flatten nested JSON object."""

        def _flatten(obj, parent_key=""):
            items = []

            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_key = f"{parent_key}{separator}{key}" if parent_key else key
                    items.extend(_flatten(value, new_key).items())
            elif isinstance(obj, list):
                for i, value in enumerate(obj):
                    new_key = f"{parent_key}{separator}{i}" if parent_key else str(i)
                    items.extend(_flatten(value, new_key).items())
            else:
                return {parent_key: obj}

            return dict(items)

        return _flatten(data)

    def _unflatten_json(
        self, data: builtins.dict[str, Any], separator: str = "."
    ) -> builtins.dict[str, Any]:
        """Unflatten flattened JSON object."""
        result = {}

        for key, value in data.items():
            keys = key.split(separator)
            current = result

            for k in keys[:-1]:
                if k.isdigit():
                    k = int(k)
                    if not isinstance(current, list):
                        current = []

                    # Extend list if necessary
                    while len(current) <= k:
                        current.append({})

                    current = current[k]
                else:
                    if k not in current:
                        current[k] = {}
                    current = current[k]

            final_key = keys[-1]
            if final_key.isdigit():
                final_key = int(final_key)
                if not isinstance(current, list):
                    current = []

                while len(current) <= final_key:
                    current.append(None)

                current[final_key] = value
            else:
                current[final_key] = value

        return result
