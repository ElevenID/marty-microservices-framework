"""
Template Customization Engine for Marty Framework

This module provides advanced template customization capabilities including
template inheritance, composition, variable injection, and dynamic generation.
"""

import json
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from jinja2 import BaseLoader, Environment, Template, meta
from jinja2.exceptions import TemplateNotFound


class TemplateType(Enum):
    """Types of templates supported."""

    JINJA2 = "jinja2"
    MUSTACHE = "mustache"
    HANDLEBARS = "handlebars"
    PYTHON_FORMAT = "python_format"
    CUSTOM = "custom"


class InheritanceMode(Enum):
    """Template inheritance modes."""

    EXTENDS = "extends"
    INCLUDES = "includes"
    COMPOSITION = "composition"
    MIXIN = "mixin"


@dataclass
class TemplateContext:
    """Context for template rendering."""

    variables: dict[str, Any] = field(default_factory=dict)
    functions: dict[str, Callable] = field(default_factory=dict)
    filters: dict[str, Callable] = field(default_factory=dict)
    globals: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TemplateSpec:
    """Template specification."""

    name: str
    path: Path
    template_type: TemplateType
    inheritance_mode: InheritanceMode | None = None
    parent_template: str | None = None
    includes: list[str] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    required_variables: list[str] = field(default_factory=list)
    optional_variables: list[str] = field(default_factory=list)
    conditions: dict[str, str] = field(default_factory=dict)
    transformations: list[str] = field(default_factory=list)


class TemplateLoader(BaseLoader):
    """Custom template loader with caching and validation."""

    def __init__(self, template_dirs: list[Path]):
        """Initialize with template directories."""
        self.template_dirs = template_dirs
        self._cache = {}

    def get_source(self, environment: Environment, template: str):
        """Get template source."""
        if template in self._cache:
            return self._cache[template]

        for template_dir in self.template_dirs:
            template_path = template_dir / template
            if template_path.exists():
                with open(template_path, encoding="utf-8") as f:
                    source = f.read()

                mtime = template_path.stat().st_mtime

                def create_uptodate_checker(path, original_mtime):
                    def uptodate():
                        try:
                            return path.stat().st_mtime == original_mtime
                        except OSError:
                            return False

                    return uptodate

                result = (
                    source,
                    str(template_path),
                    create_uptodate_checker(template_path, mtime),
                )
                self._cache[template] = result
                return result

        raise TemplateNotFound(template)


class TemplateTransformer(ABC):
    """Base class for template transformers."""

    @abstractmethod
    def transform(self, content: str, context: TemplateContext) -> str:
        """Transform template content."""

    @abstractmethod
    def get_name(self) -> str:
        """Get transformer name."""


class VariableInjectionTransformer(TemplateTransformer):
    """Injects variables into templates."""

    def transform(self, content: str, context: TemplateContext) -> str:
        """Inject variables into template content."""
        # Replace variable placeholders
        for var_name, var_value in context.variables.items():
            placeholder = f"${{{var_name}}}"
            if placeholder in content:
                content = content.replace(placeholder, str(var_value))

        return content

    def get_name(self) -> str:
        """Get transformer name."""
        return "variable_injection"


class ConditionalBlockTransformer(TemplateTransformer):
    """Handles conditional blocks in templates."""

    def transform(self, content: str, context: TemplateContext) -> str:
        """Process conditional blocks."""
        # Pattern: {% if condition %}...{% endif %}
        pattern = r"{%\s*if\s+(\w+)\s*%}(.*?){%\s*endif\s*%}"

        def replace_conditional(match):
            condition = match.group(1)
            block_content = match.group(2)

            # Evaluate condition from context
            condition_value = context.variables.get(condition, False)

            # Convert string values to boolean
            if isinstance(condition_value, str):
                condition_value = condition_value.lower() in ("true", "1", "yes", "on")

            return block_content if condition_value else ""

        return re.sub(pattern, replace_conditional, content, flags=re.DOTALL)

    def get_name(self) -> str:
        """Get transformer name."""
        return "conditional_blocks"


class LoopTransformer(TemplateTransformer):
    """Handles loop constructs in templates."""

    def transform(self, content: str, context: TemplateContext) -> str:
        """Process loop constructs."""
        # Pattern: {% for item in items %}...{% endfor %}
        pattern = r"{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%}(.*?){%\s*endfor\s*%}"

        def replace_loop(match):
            item_var = match.group(1)
            items_var = match.group(2)
            loop_content = match.group(3)

            items = context.variables.get(items_var, [])
            if not isinstance(items, list | tuple):
                return ""

            result = ""
            for item in items:
                # Create temporary context with loop variable
                temp_content = loop_content.replace(f"{{{{{item_var}}}}}", str(item))
                result += temp_content

            return result

        return re.sub(pattern, replace_loop, content, flags=re.DOTALL)

    def get_name(self) -> str:
        """Get transformer name."""
        return "loops"


class IncludeTransformer(TemplateTransformer):
    """Handles template includes."""

    def __init__(self, template_loader: TemplateLoader):
        """Initialize with template loader."""
        self.template_loader = template_loader

    def transform(self, content: str, context: TemplateContext) -> str:
        """Process template includes."""
        # Pattern: {% include "template_name" %}
        pattern = r'{%\s*include\s+"([^"]+)"\s*%}'

        def replace_include(match):
            template_name = match.group(1)

            try:
                env = Environment(loader=self.template_loader, autoescape=True)
                source, _, _ = self.template_loader.get_source(env, template_name)
                return source
            except TemplateNotFound:
                return f"<!-- Template '{template_name}' not found -->"

        return re.sub(pattern, replace_include, content)

    def get_name(self) -> str:
        """Get transformer name."""
        return "includes"


class MacroTransformer(TemplateTransformer):
    """Handles macro definitions and calls."""

    def __init__(self):
        """Initialize macro transformer."""
        self.macros = {}

    def transform(self, content: str, context: TemplateContext) -> str:
        """Process macros."""
        # First pass: extract macro definitions
        content = self._extract_macros(content)

        # Second pass: expand macro calls
        content = self._expand_macros(content, context)

        return content

    def _extract_macros(self, content: str) -> str:
        """Extract macro definitions."""
        # Pattern: {% macro name(params) %}...{% endmacro %}
        pattern = r"{%\s*macro\s+(\w+)\(([^)]*)\)\s*%}(.*?){%\s*endmacro\s*%}"

        def extract_macro(match):
            macro_name = match.group(1)
            params = [p.strip() for p in match.group(2).split(",") if p.strip()]
            macro_body = match.group(3)

            self.macros[macro_name] = {"params": params, "body": macro_body}

            return ""  # Remove macro definition from content

        return re.sub(pattern, extract_macro, content, flags=re.DOTALL)

    def _expand_macros(self, content: str, context: TemplateContext) -> str:
        """Expand macro calls."""
        # Pattern: {{ macro_name(args) }}
        pattern = r"{{\s*(\w+)\(([^)]*)\)\s*}}"

        def expand_macro(match):
            macro_name = match.group(1)
            args = [arg.strip().strip("\"'") for arg in match.group(2).split(",") if arg.strip()]

            if macro_name not in self.macros:
                return match.group(0)  # Return original if macro not found

            macro = self.macros[macro_name]
            macro_body = macro["body"]

            # Replace parameters with arguments
            for i, param in enumerate(macro["params"]):
                if i < len(args):
                    macro_body = macro_body.replace(f"{{{{{param}}}}}", args[i])

            return macro_body

        return re.sub(pattern, expand_macro, content)

    def get_name(self) -> str:
        """Get transformer name."""
        return "macros"


class TemplateCustomizationEngine:
    """Advanced template customization engine."""

    def __init__(self, template_dirs: list[Path]):
        """Initialize the customization engine."""
        self.template_dirs = template_dirs
        self.template_loader = TemplateLoader(template_dirs)
        self.jinja_env = Environment(loader=self.template_loader, autoescape=True)

        # Initialize transformers
        self.transformers = {
            "variable_injection": VariableInjectionTransformer(),
            "conditional_blocks": ConditionalBlockTransformer(),
            "loops": LoopTransformer(),
            "includes": IncludeTransformer(self.template_loader),
            "macros": MacroTransformer(),
        }

        # Template specifications cache
        self._template_specs = {}

    def load_template_spec(self, spec_path: Path) -> TemplateSpec:
        """Load template specification from file."""
        if spec_path in self._template_specs:
            return self._template_specs[spec_path]

        with open(spec_path, encoding="utf-8") as f:
            if spec_path.suffix.lower() == ".json":
                spec_data = json.load(f)
            else:
                spec_data = yaml.safe_load(f)

        spec = TemplateSpec(
            name=spec_data["name"],
            path=Path(spec_data["path"]),
            template_type=TemplateType(spec_data.get("type", "jinja2")),
            inheritance_mode=InheritanceMode(spec_data["inheritance_mode"])
            if "inheritance_mode" in spec_data
            else None,
            parent_template=spec_data.get("parent_template"),
            includes=spec_data.get("includes", []),
            variables=spec_data.get("variables", {}),
            required_variables=spec_data.get("required_variables", []),
            optional_variables=spec_data.get("optional_variables", []),
            conditions=spec_data.get("conditions", {}),
            transformations=spec_data.get("transformations", []),
        )

        self._template_specs[spec_path] = spec
        return spec

    def customize_template(
        self,
        template_name: str,
        context: TemplateContext,
        spec: TemplateSpec | None = None,
    ) -> str:
        """Customize a template with the given context."""
        # Load template content
        try:
            source, _, _ = self.template_loader.get_source(self.jinja_env, template_name)
        except TemplateNotFound:
            raise ValueError(f"Template '{template_name}' not found")

        # Apply specification if provided
        if spec:
            context = self._apply_spec_to_context(context, spec)
            source = self._apply_spec_transformations(source, spec, context)

        # Apply transformations
        for transformer_name in [
            "includes",
            "macros",
            "variable_injection",
            "conditional_blocks",
            "loops",
        ]:
            if transformer_name in self.transformers:
                source = self.transformers[transformer_name].transform(source, context)

        return source

    def render_template(
        self,
        template_name: str,
        context: TemplateContext,
        spec: TemplateSpec | None = None,
    ) -> str:
        """Render a customized template."""
        customized_content = self.customize_template(template_name, context, spec)

        # Use Jinja2 for final rendering
        template = Template(customized_content)

        # Combine all context elements
        render_context = {**context.variables, **context.globals}

        # Add functions and filters to Jinja environment
        for name, func in context.functions.items():
            self.jinja_env.globals[name] = func

        for name, filter_func in context.filters.items():
            self.jinja_env.filters[name] = filter_func

        return template.render(**render_context)

    def create_template_composition(
        self, base_template: str, mixins: list[str], context: TemplateContext
    ) -> str:
        """Create a composed template from base and mixins."""
        # Load base template
        base_content = self.customize_template(base_template, context)

        # Process mixins
        for mixin in mixins:
            mixin_content = self.customize_template(mixin, context)
            base_content = self._compose_templates(base_content, mixin_content)

        return base_content

    def validate_template_variables(
        self, template_name: str, provided_variables: dict[str, Any]
    ) -> dict[str, list[str]]:
        """Validate template variables."""
        # Load template and extract variables
        try:
            source, _, _ = self.template_loader.get_source(self.jinja_env, template_name)
        except TemplateNotFound:
            raise ValueError(f"Template '{template_name}' not found")

        # Parse template to find variables
        ast = self.jinja_env.parse(source)
        template_variables = meta.find_undeclared_variables(ast)

        missing_variables = []
        unused_variables = []

        # Check for missing required variables
        for var in template_variables:
            if var not in provided_variables:
                missing_variables.append(var)

        # Check for unused provided variables
        for var in provided_variables:
            if var not in template_variables:
                unused_variables.append(var)

        return {
            "missing": missing_variables,
            "unused": unused_variables,
            "required": list(template_variables),
            "provided": list(provided_variables.keys()),
        }

    def generate_template_documentation(self, template_name: str) -> dict[str, Any]:
        """Generate documentation for a template."""
        try:
            source, template_path, _ = self.template_loader.get_source(
                self.jinja_env, template_name
            )
        except TemplateNotFound:
            raise ValueError(f"Template '{template_name}' not found")

        # Parse template
        ast = self.jinja_env.parse(source)
        variables = meta.find_undeclared_variables(ast)

        # Extract blocks and macros
        blocks = []
        macros = []

        for node in ast.find_all(self.jinja_env.block_class):
            blocks.append(node.name)

        for node in ast.find_all(self.jinja_env.macro_class):
            macros.append({"name": node.name, "args": [arg.name for arg in node.args]})

        # Extract comments and docstrings
        comments = re.findall(r"{#\s*(.*?)\s*#}", source, re.DOTALL)

        return {
            "name": template_name,
            "path": template_path,
            "variables": list(variables),
            "blocks": blocks,
            "macros": macros,
            "comments": comments,
            "size": len(source),
            "lines": source.count("\n") + 1,
        }

    def _apply_spec_to_context(
        self, context: TemplateContext, spec: TemplateSpec
    ) -> TemplateContext:
        """Apply specification to context."""
        # Merge specification variables
        merged_variables = {**spec.variables, **context.variables}

        # Validate required variables
        for required_var in spec.required_variables:
            if required_var not in merged_variables:
                raise ValueError(f"Required variable '{required_var}' not provided")

        return TemplateContext(
            variables=merged_variables,
            functions=context.functions,
            filters=context.filters,
            globals=context.globals,
            metadata={**context.metadata, **spec.variables},
        )

    def _apply_spec_transformations(
        self, content: str, spec: TemplateSpec, context: TemplateContext
    ) -> str:
        """Apply specification transformations."""
        for transformation in spec.transformations:
            if transformation in self.transformers:
                content = self.transformers[transformation].transform(content, context)

        return content

    def _compose_templates(self, base_content: str, mixin_content: str) -> str:
        """Compose two templates."""
        # Simple composition: append mixin to base
        # More sophisticated composition logic can be added here

        # Look for composition points in base template
        composition_pattern = r'{%\s*compose\s+"([^"]+)"\s*%}'

        def replace_composition(match):
            composition_name = match.group(1)
            return mixin_content if composition_name in mixin_content else ""

        return re.sub(composition_pattern, replace_composition, base_content)

    def add_custom_transformer(self, transformer: TemplateTransformer) -> None:
        """Add a custom transformer."""
        self.transformers[transformer.get_name()] = transformer

    def add_custom_filter(self, name: str, filter_func: Callable) -> None:
        """Add a custom Jinja2 filter."""
        self.jinja_env.filters[name] = filter_func

    def add_custom_function(self, name: str, func: Callable) -> None:
        """Add a custom Jinja2 global function."""
        self.jinja_env.globals[name] = func


def create_template_context(**kwargs) -> TemplateContext:
    """Convenience function to create a template context."""
    return TemplateContext(
        variables=kwargs.get("variables", {}),
        functions=kwargs.get("functions", {}),
        filters=kwargs.get("filters", {}),
        globals=kwargs.get("globals", {}),
        metadata=kwargs.get("metadata", {}),
    )


def create_basic_template_spec(name: str, path: str, **kwargs) -> TemplateSpec:
    """Convenience function to create a basic template specification."""
    return TemplateSpec(
        name=name,
        path=Path(path),
        template_type=TemplateType(kwargs.get("template_type", "jinja2")),
        inheritance_mode=InheritanceMode(kwargs["inheritance_mode"])
        if "inheritance_mode" in kwargs
        else None,
        parent_template=kwargs.get("parent_template"),
        includes=kwargs.get("includes", []),
        variables=kwargs.get("variables", {}),
        required_variables=kwargs.get("required_variables", []),
        optional_variables=kwargs.get("optional_variables", []),
        conditions=kwargs.get("conditions", {}),
        transformations=kwargs.get("transformations", []),
    )
