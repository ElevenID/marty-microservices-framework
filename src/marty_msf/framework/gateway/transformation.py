"""
Request/Response Transformation Module for API Gateway

Advanced request and response transformation capabilities including header manipulation,
body transformation, content type conversion, and sophisticated mapping rules.
"""

import builtins
import json
import logging
import re
import urllib.parse
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from defusedxml import ElementTree as ET

from .core import GatewayRequest, GatewayResponse

logger = logging.getLogger(__name__)


class TransformationType(Enum):
    """Transformation types."""

    HEADER = "header"
    QUERY_PARAM = "query_param"
    BODY = "body"
    PATH = "path"
    METHOD = "method"
    CONTENT_TYPE = "content_type"


class TransformationDirection(Enum):
    """Transformation direction."""

    REQUEST = "request"
    RESPONSE = "response"
    BOTH = "both"


class BodyFormat(Enum):
    """Supported body formats."""

    JSON = "json"
    XML = "xml"
    FORM_DATA = "form_data"
    TEXT = "text"
    BINARY = "binary"
    YAML = "yaml"


@dataclass
class TransformationRule:
    """Rule for data transformation."""

    name: str
    type: TransformationType
    direction: TransformationDirection
    condition: str | None = None  # JSONPath, XPath, or regex condition
    action: str = "set"  # set, add, remove, rename, map

    # Source and target specifications
    source: str | None = None
    target: str | None = None
    value: Any | None = None

    # Advanced options
    preserve_original: bool = False
    case_sensitive: bool = True
    regex_pattern: str | None = None
    replacement: str | None = None

    # Conditional logic
    when_present: bool = True
    when_absent: bool = False
    priority: int = 0


@dataclass
class TransformationConfig:
    """Configuration for transformations."""

    # General settings
    enabled: bool = True
    fail_on_error: bool = False
    log_transformations: bool = False

    # Content type handling
    auto_detect_content_type: bool = True
    default_input_format: BodyFormat = BodyFormat.JSON
    default_output_format: BodyFormat = BodyFormat.JSON

    # Performance settings
    max_body_size: int = 10 * 1024 * 1024  # 10MB
    timeout_seconds: float = 5.0

    # Security settings
    allow_script_injection: bool = False
    sanitize_html: bool = True

    # Encoding settings
    input_encoding: str = "utf-8"
    output_encoding: str = "utf-8"


class Transformer(ABC):
    """Abstract transformer interface."""

    @abstractmethod
    def transform_request(
        self, request: GatewayRequest, rules: builtins.list[TransformationRule]
    ) -> GatewayRequest:
        """Transform request according to rules."""
        raise NotImplementedError

    @abstractmethod
    def transform_response(
        self, response: GatewayResponse, rules: builtins.list[TransformationRule]
    ) -> GatewayResponse:
        """Transform response according to rules."""
        raise NotImplementedError


class HeaderTransformer(Transformer):
    """Header transformation."""

    def __init__(self, config: TransformationConfig):
        self.config = config

    def transform_request(
        self, request: GatewayRequest, rules: builtins.list[TransformationRule]
    ) -> GatewayRequest:
        """Transform request headers."""
        header_rules = [
            r
            for r in rules
            if r.type == TransformationType.HEADER
            and r.direction in [TransformationDirection.REQUEST, TransformationDirection.BOTH]
        ]

        for rule in sorted(header_rules, key=lambda r: r.priority, reverse=True):
            if self._should_apply_rule(rule, request=request):
                self._apply_header_rule(rule, request.headers)

        return request

    def transform_response(
        self, response: GatewayResponse, rules: builtins.list[TransformationRule]
    ) -> GatewayResponse:
        """Transform response headers."""
        header_rules = [
            r
            for r in rules
            if r.type == TransformationType.HEADER
            and r.direction in [TransformationDirection.RESPONSE, TransformationDirection.BOTH]
        ]

        for rule in sorted(header_rules, key=lambda r: r.priority, reverse=True):
            if self._should_apply_rule(rule, response=response):
                self._apply_header_rule(rule, response.headers)

        return response

    def _apply_header_rule(self, rule: TransformationRule, headers: builtins.dict[str, str]):
        """Apply header transformation rule."""
        if rule.action == "set":
            if rule.target and rule.value is not None:
                headers[rule.target] = str(rule.value)

        elif rule.action == "add":
            if rule.target and rule.value is not None:
                existing = headers.get(rule.target, "")
                if existing:
                    headers[rule.target] = f"{existing}, {rule.value}"
                else:
                    headers[rule.target] = str(rule.value)

        elif rule.action == "remove":
            if rule.target and rule.target in headers:
                del headers[rule.target]

        elif rule.action == "rename":
            if rule.source and rule.target and rule.source in headers:
                value = headers[rule.source]
                headers[rule.target] = value
                if not rule.preserve_original:
                    del headers[rule.source]

        elif rule.action == "map":
            # Transform header value based on mapping
            if rule.source and rule.source in headers:
                original_value = headers[rule.source]
                if rule.regex_pattern and rule.replacement:
                    flags = 0 if rule.case_sensitive else re.IGNORECASE
                    new_value = re.sub(
                        rule.regex_pattern,
                        rule.replacement,
                        original_value,
                        flags=flags,
                    )
                    target_header = rule.target or rule.source
                    headers[target_header] = new_value

    def _should_apply_rule(
        self,
        rule: TransformationRule,
        request: GatewayRequest = None,
        response: GatewayResponse = None,
    ) -> bool:
        """Check if rule should be applied."""
        if rule.condition:
            # Evaluate condition (simplified implementation)
            if request and rule.source:
                header_value = request.get_header(rule.source)
                if rule.when_present and not header_value:
                    return False
                if rule.when_absent and header_value:
                    return False

            if response and rule.source:
                header_value = response.get_header(rule.source)
                if rule.when_present and not header_value:
                    return False
                if rule.when_absent and header_value:
                    return False

        return True


class QueryParamTransformer(Transformer):
    """Query parameter transformation."""

    def __init__(self, config: TransformationConfig):
        self.config = config

    def transform_request(
        self, request: GatewayRequest, rules: builtins.list[TransformationRule]
    ) -> GatewayRequest:
        """Transform request query parameters."""
        query_rules = [
            r
            for r in rules
            if r.type == TransformationType.QUERY_PARAM
            and r.direction in [TransformationDirection.REQUEST, TransformationDirection.BOTH]
        ]

        for rule in sorted(query_rules, key=lambda r: r.priority, reverse=True):
            self._apply_query_rule(rule, request.query_params)

        return request

    def transform_response(
        self, response: GatewayResponse, rules: builtins.list[TransformationRule]
    ) -> GatewayResponse:
        """Query parameters not applicable to responses."""
        return response

    def _apply_query_rule(self, rule: TransformationRule, params: builtins.dict[str, str]):
        """Apply query parameter transformation rule."""
        if rule.action == "set":
            if rule.target and rule.value is not None:
                params[rule.target] = str(rule.value)

        elif rule.action == "remove":
            if rule.target and rule.target in params:
                del params[rule.target]

        elif rule.action == "rename":
            if rule.source and rule.target and rule.source in params:
                value = params[rule.source]
                params[rule.target] = value
                if not rule.preserve_original:
                    del params[rule.source]


class BodyTransformer(Transformer):
    """Body content transformation."""

    def __init__(self, config: TransformationConfig):
        self.config = config

    def transform_request(
        self, request: GatewayRequest, rules: builtins.list[TransformationRule]
    ) -> GatewayRequest:
        """Transform request body."""
        body_rules = [
            r
            for r in rules
            if r.type == TransformationType.BODY
            and r.direction in [TransformationDirection.REQUEST, TransformationDirection.BOTH]
        ]

        if not body_rules or not request.body:
            return request

        try:
            # Parse body based on content type
            content_type = request.get_header("Content-Type", "").lower()
            body_data = self._parse_body(request.body, content_type)

            # Apply transformations
            for rule in sorted(body_rules, key=lambda r: r.priority, reverse=True):
                body_data = self._apply_body_rule(rule, body_data)

            # Serialize back to string
            request.body = self._serialize_body(body_data, content_type)

        except Exception as e:
            if self.config.fail_on_error:
                raise
            logger.error(f"Error transforming request body: {e}")

        return request

    def transform_response(
        self, response: GatewayResponse, rules: builtins.list[TransformationRule]
    ) -> GatewayResponse:
        """Transform response body."""
        body_rules = [
            r
            for r in rules
            if r.type == TransformationType.BODY
            and r.direction in [TransformationDirection.RESPONSE, TransformationDirection.BOTH]
        ]

        if not body_rules or not response.body:
            return response

        try:
            # Parse body based on content type
            content_type = response.get_header("Content-Type", "").lower()
            body_data = self._parse_body(response.body, content_type)

            # Apply transformations
            for rule in sorted(body_rules, key=lambda r: r.priority, reverse=True):
                body_data = self._apply_body_rule(rule, body_data)

            # Serialize back to string
            response.body = self._serialize_body(body_data, content_type)

        except Exception as e:
            if self.config.fail_on_error:
                raise
            logger.error(f"Error transforming response body: {e}")

        return response

    def _parse_body(self, body: str, content_type: str) -> Any:
        """Parse body content based on content type."""
        if "application/json" in content_type:
            return json.loads(body)
        if "application/xml" in content_type or "text/xml" in content_type:
            return ET.fromstring(body)
        if "application/x-www-form-urlencoded" in content_type:
            return dict(urllib.parse.parse_qsl(body))
        return body  # Return as string for unknown types

    def _serialize_body(self, data: Any, content_type: str) -> str:
        """Serialize body content based on content type."""
        if "application/json" in content_type:
            return json.dumps(data, ensure_ascii=False)
        if "application/xml" in content_type or "text/xml" in content_type:
            if isinstance(data, ET.Element):
                return ET.tostring(data, encoding="unicode")
            return str(data)
        if "application/x-www-form-urlencoded" in content_type:
            if isinstance(data, dict):
                return urllib.parse.urlencode(data)
            return str(data)
        return str(data)

    def _apply_body_rule(self, rule: TransformationRule, data: Any) -> Any:
        """Apply body transformation rule."""
        if rule.action == "set":
            if isinstance(data, dict) and rule.target:
                self._set_nested_value(data, rule.target, rule.value)

        elif rule.action == "remove":
            if isinstance(data, dict) and rule.target:
                self._remove_nested_value(data, rule.target)

        elif rule.action == "rename":
            if isinstance(data, dict) and rule.source and rule.target:
                value = self._get_nested_value(data, rule.source)
                if value is not None:
                    self._set_nested_value(data, rule.target, value)
                    if not rule.preserve_original:
                        self._remove_nested_value(data, rule.source)

        elif rule.action == "map":
            if isinstance(data, dict) and rule.source:
                value = self._get_nested_value(data, rule.source)
                if value is not None and rule.regex_pattern and rule.replacement:
                    flags = 0 if rule.case_sensitive else re.IGNORECASE
                    new_value = re.sub(
                        rule.regex_pattern, rule.replacement, str(value), flags=flags
                    )
                    target_path = rule.target or rule.source
                    self._set_nested_value(data, target_path, new_value)

        return data

    def _get_nested_value(self, data: builtins.dict, path: str) -> Any:
        """Get nested value using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def _set_nested_value(self, data: builtins.dict, path: str, value: Any):
        """Set nested value using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def _remove_nested_value(self, data: builtins.dict, path: str):
        """Remove nested value using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys[:-1]:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return

        if isinstance(current, dict) and keys[-1] in current:
            del current[keys[-1]]


class PathTransformer(Transformer):
    """Path transformation."""

    def __init__(self, config: TransformationConfig):
        self.config = config

    def transform_request(
        self, request: GatewayRequest, rules: builtins.list[TransformationRule]
    ) -> GatewayRequest:
        """Transform request path."""
        path_rules = [
            r
            for r in rules
            if r.type == TransformationType.PATH
            and r.direction in [TransformationDirection.REQUEST, TransformationDirection.BOTH]
        ]

        for rule in sorted(path_rules, key=lambda r: r.priority, reverse=True):
            request.path = self._apply_path_rule(rule, request.path)

        return request

    def transform_response(
        self, response: GatewayResponse, rules: builtins.list[TransformationRule]
    ) -> GatewayResponse:
        """Path transformation not applicable to responses."""
        return response

    def _apply_path_rule(self, rule: TransformationRule, path: str) -> str:
        """Apply path transformation rule."""
        if rule.action == "set" and rule.value:
            return str(rule.value)

        if rule.action == "map" and rule.regex_pattern and rule.replacement:
            flags = 0 if rule.case_sensitive else re.IGNORECASE
            return re.sub(rule.regex_pattern, rule.replacement, path, flags=flags)

        return path


class ContentTypeTransformer(Transformer):
    """Content type transformation."""

    def __init__(self, config: TransformationConfig):
        self.config = config
        self.format_converters = {
            (BodyFormat.JSON, BodyFormat.XML): self._json_to_xml,
            (BodyFormat.XML, BodyFormat.JSON): self._xml_to_json,
            (BodyFormat.JSON, BodyFormat.FORM_DATA): self._json_to_form,
            (BodyFormat.FORM_DATA, BodyFormat.JSON): self._form_to_json,
        }

    def transform_request(
        self, request: GatewayRequest, rules: builtins.list[TransformationRule]
    ) -> GatewayRequest:
        """Transform request content type."""
        ct_rules = [
            r
            for r in rules
            if r.type == TransformationType.CONTENT_TYPE
            and r.direction in [TransformationDirection.REQUEST, TransformationDirection.BOTH]
        ]

        for rule in ct_rules:
            if rule.source and rule.target and request.body:
                source_format = self._detect_format(rule.source)
                target_format = self._detect_format(rule.target)

                if source_format != target_format:
                    converter = self.format_converters.get((source_format, target_format))
                    if converter:
                        try:
                            request.body = converter(request.body)
                            request.set_header("Content-Type", rule.target)
                        except Exception as e:
                            if self.config.fail_on_error:
                                raise
                            logger.error(f"Error converting content type: {e}")

        return request

    def transform_response(
        self, response: GatewayResponse, rules: builtins.list[TransformationRule]
    ) -> GatewayResponse:
        """Transform response content type."""
        ct_rules = [
            r
            for r in rules
            if r.type == TransformationType.CONTENT_TYPE
            and r.direction in [TransformationDirection.RESPONSE, TransformationDirection.BOTH]
        ]

        for rule in ct_rules:
            if rule.source and rule.target and response.body:
                source_format = self._detect_format(rule.source)
                target_format = self._detect_format(rule.target)

                if source_format != target_format:
                    converter = self.format_converters.get((source_format, target_format))
                    if converter:
                        try:
                            response.body = converter(response.body)
                            response.set_header("Content-Type", rule.target)
                        except Exception as e:
                            if self.config.fail_on_error:
                                raise
                            logger.error(f"Error converting content type: {e}")

        return response

    def _detect_format(self, content_type: str) -> BodyFormat:
        """Detect body format from content type."""
        content_type = content_type.lower()

        if "json" in content_type:
            return BodyFormat.JSON
        if "xml" in content_type:
            return BodyFormat.XML
        if "form" in content_type:
            return BodyFormat.FORM_DATA
        return BodyFormat.TEXT

    def _json_to_xml(self, json_data: str) -> str:
        """Convert JSON to XML."""
        data = json.loads(json_data)
        root = ET.Element("root")
        self._dict_to_xml(data, root)
        return ET.tostring(root, encoding="unicode")

    def _xml_to_json(self, xml_data: str) -> str:
        """Convert XML to JSON."""
        root = ET.fromstring(xml_data)
        data = self._xml_to_dict(root)
        return json.dumps(data, ensure_ascii=False)

    def _json_to_form(self, json_data: str) -> str:
        """Convert JSON to form data."""
        data = json.loads(json_data)
        if isinstance(data, dict):
            return urllib.parse.urlencode(data)
        raise ValueError("JSON data must be an object for form conversion")

    def _form_to_json(self, form_data: str) -> str:
        """Convert form data to JSON."""
        data = dict(urllib.parse.parse_qsl(form_data))
        return json.dumps(data, ensure_ascii=False)

    def _dict_to_xml(self, data: Any, parent: ET.Element):
        """Convert dictionary to XML elements."""
        if isinstance(data, dict):
            for key, value in data.items():
                element = ET.SubElement(parent, str(key))
                self._dict_to_xml(value, element)
        elif isinstance(data, list):
            for item in data:
                item_element = ET.SubElement(parent, "item")
                self._dict_to_xml(item, item_element)
        else:
            parent.text = str(data)

    def _xml_to_dict(self, element: ET.Element) -> Any:
        """Convert XML element to dictionary."""
        result = {}

        # Add attributes
        if element.attrib:
            result.update(element.attrib)

        # Add text content
        if element.text and element.text.strip():
            if result:
                result["_text"] = element.text.strip()
            else:
                return element.text.strip()

        # Add child elements
        for child in element:
            child_data = self._xml_to_dict(child)
            if child.tag in result:
                # Convert to list if multiple elements with same tag
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data

        return result


class TransformationEngine:
    """Main transformation engine orchestrating all transformers."""

    def __init__(self, config: TransformationConfig = None):
        self.config = config or TransformationConfig()
        self.transformers = {
            TransformationType.HEADER: HeaderTransformer(self.config),
            TransformationType.QUERY_PARAM: QueryParamTransformer(self.config),
            TransformationType.BODY: BodyTransformer(self.config),
            TransformationType.PATH: PathTransformer(self.config),
            TransformationType.CONTENT_TYPE: ContentTypeTransformer(self.config),
        }
        self.rules: builtins.list[TransformationRule] = []

    def add_rule(self, rule: TransformationRule):
        """Add transformation rule."""
        self.rules.append(rule)
        # Sort rules by priority
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def add_rules(self, rules: builtins.list[TransformationRule]):
        """Add multiple transformation rules."""
        self.rules.extend(rules)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def transform_request(self, request: GatewayRequest) -> GatewayRequest:
        """Transform request using all applicable rules."""
        if not self.config.enabled:
            return request

        try:
            # Group rules by type for efficient processing
            rules_by_type = {}
            for rule in self.rules:
                if rule.direction in [
                    TransformationDirection.REQUEST,
                    TransformationDirection.BOTH,
                ]:
                    if rule.type not in rules_by_type:
                        rules_by_type[rule.type] = []
                    rules_by_type[rule.type].append(rule)

            # Apply transformations in order
            transform_order = [
                TransformationType.HEADER,
                TransformationType.QUERY_PARAM,
                TransformationType.PATH,
                TransformationType.CONTENT_TYPE,
                TransformationType.BODY,
            ]

            for transform_type in transform_order:
                if transform_type in rules_by_type:
                    transformer = self.transformers[transform_type]
                    request = transformer.transform_request(request, rules_by_type[transform_type])

            if self.config.log_transformations:
                logger.info(
                    f"Transformed request: {len([r for r in self.rules if r.direction != TransformationDirection.RESPONSE])} rules applied"
                )

        except Exception as e:
            if self.config.fail_on_error:
                raise
            logger.error(f"Error transforming request: {e}")

        return request

    def transform_response(self, response: GatewayResponse) -> GatewayResponse:
        """Transform response using all applicable rules."""
        if not self.config.enabled:
            return response

        try:
            # Group rules by type for efficient processing
            rules_by_type = {}
            for rule in self.rules:
                if rule.direction in [
                    TransformationDirection.RESPONSE,
                    TransformationDirection.BOTH,
                ]:
                    if rule.type not in rules_by_type:
                        rules_by_type[rule.type] = []
                    rules_by_type[rule.type].append(rule)

            # Apply transformations in order
            transform_order = [
                TransformationType.CONTENT_TYPE,
                TransformationType.BODY,
                TransformationType.HEADER,
            ]

            for transform_type in transform_order:
                if transform_type in rules_by_type:
                    transformer = self.transformers[transform_type]
                    response = transformer.transform_response(
                        response, rules_by_type[transform_type]
                    )

            if self.config.log_transformations:
                logger.info(
                    f"Transformed response: {len([r for r in self.rules if r.direction != TransformationDirection.REQUEST])} rules applied"
                )

        except Exception as e:
            if self.config.fail_on_error:
                raise
            logger.error(f"Error transforming response: {e}")

        return response


class TransformationMiddleware:
    """Transformation middleware for API Gateway."""

    def __init__(self, config: TransformationConfig = None):
        self.engine = TransformationEngine(config)

    def add_rule(self, rule: TransformationRule):
        """Add transformation rule."""
        self.engine.add_rule(rule)

    def add_rules(self, rules: builtins.list[TransformationRule]):
        """Add multiple transformation rules."""
        self.engine.add_rules(rules)

    def process_request(self, request: GatewayRequest) -> GatewayResponse | None:
        """Process request transformation."""
        try:
            self.engine.transform_request(request)
            return None  # Continue processing
        except Exception as e:
            logger.error(f"Request transformation failed: {e}")
            if self.engine.config.fail_on_error:

                return GatewayResponse(
                    status_code=500,
                    body="Request transformation failed",
                    content_type="text/plain",
                )
            return None

    def process_response(self, response: GatewayResponse) -> GatewayResponse:
        """Process response transformation."""
        try:
            return self.engine.transform_response(response)
        except Exception as e:
            logger.error(f"Response transformation failed: {e}")
            if self.engine.config.fail_on_error:
                response.status_code = 500
                response.body = "Response transformation failed"
                response.content_type = "text/plain"
            return response


# Convenience functions
def create_header_rule(
    name: str,
    action: str,
    target: str,
    value: str = None,
    direction: TransformationDirection = TransformationDirection.BOTH,
) -> TransformationRule:
    """Create header transformation rule."""
    return TransformationRule(
        name=name,
        type=TransformationType.HEADER,
        direction=direction,
        action=action,
        target=target,
        value=value,
    )


def create_body_rule(
    name: str,
    action: str,
    target: str,
    value: Any = None,
    direction: TransformationDirection = TransformationDirection.BOTH,
) -> TransformationRule:
    """Create body transformation rule."""
    return TransformationRule(
        name=name,
        type=TransformationType.BODY,
        direction=direction,
        action=action,
        target=target,
        value=value,
    )


def create_path_rewrite_rule(name: str, pattern: str, replacement: str) -> TransformationRule:
    """Create path rewrite rule."""
    return TransformationRule(
        name=name,
        type=TransformationType.PATH,
        direction=TransformationDirection.REQUEST,
        action="map",
        regex_pattern=pattern,
        replacement=replacement,
    )
