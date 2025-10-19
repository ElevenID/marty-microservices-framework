#!/usr/bin/env python3
"""
Template Validator for Marty Microservices Framework

This script validates all service templates to ensure they:
1. Have valid Jinja2 syntax
2. Generate valid Python code
3. Have proper structure and required files
"""

import ast
import builtins
import sys
from pathlib import Path
from typing import Any, cast

from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError


class ServiceTemplateValidator:
    """Validator for service templates."""

    def __init__(self, templates_dir: Path) -> None:
        """Initialize validator with services directory."""
        self.templates_dir = templates_dir  # Now points to services/
        self.service_templates_dirs = [
            templates_dir / "fastapi",
            templates_dir / "grpc",
            templates_dir / "hybrid",
            templates_dir / "shared"
        ]

        if not templates_dir.exists():
            raise ValueError(f"Services directory not found: {templates_dir}")

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )

    def validate_all_templates(self) -> builtins.dict[str, Any]:
        """
        Validate all service templates.

        Returns:
            Dictionary with validation results
        """
        results: builtins.dict[str, Any] = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "templates": {},
            "success_rate": 0.0,
        }

        # Find all template directories from all service directories
        template_dirs = []
        for service_dir in self.service_templates_dirs:
            if service_dir.exists():
                template_dirs.extend([
                    d
                    for d in service_dir.iterdir()
                    if d.is_dir() and d.name not in ["morty_service", "__pycache__"]  # Exclude concrete implementations
                ])
        results["total"] = len(template_dirs)

        print("🚀 Starting Marty Service Template Validation")
        print("=" * 60)
        print()

        for template_dir in template_dirs:
            template_name = template_dir.name
            print(f"🔍 Testing template: {template_name}")

            try:
                template_result = self._validate_template(template_dir)
                results["templates"][template_name] = template_result

                if template_result["valid"]:
                    results["passed"] = cast(int, results["passed"]) + 1
                    print(f"✅ {template_name}: PASSED")
                else:
                    results["failed"] = cast(int, results["failed"]) + 1
                    print(f"❌ {template_name}: FAILED")
                    for error in template_result["errors"]:
                        print(f"   - {error}")

            except Exception as e:
                results["failed"] = cast(int, results["failed"]) + 1
                results["templates"][template_name] = {
                    "valid": False,
                    "errors": [f"Validation exception: {e!s}"],
                    "files_validated": 0,
                }
                print(f"❌ {template_name}: FAILED - {e!s}")

            print()

        # Calculate success rate
        total = cast(int, results["total"])
        passed = cast(int, results["passed"])
        if total > 0:
            results["success_rate"] = (passed / total) * 100

        self._print_summary(results)
        return results

    def _validate_template(self, template_dir: Path) -> builtins.dict[str, Any]:
        """
        Validate a single template directory.

        Args:
            template_dir: Path to template directory

        Returns:
            Validation result dictionary
        """
        result: builtins.dict[str, Any] = {
            "valid": True,
            "errors": [],
            "files_validated": 0,
            "template_files": [],
        }

        # Find all template files
        template_files = list(template_dir.glob("**/*.j2"))
        result["template_files"] = [f.name for f in template_files]

        if not template_files:
            result["valid"] = False
            cast(builtins.list[str], result["errors"]).append("No template files (.j2) found")
            return result

        # Validate each template file
        for template_file in template_files:
            try:
                # Validate Jinja2 syntax
                self._validate_jinja2_syntax(template_file, template_dir)

                # Validate generated Python code (if .py template)
                if template_file.name.endswith(".py.j2"):
                    self._validate_python_generation(template_file, template_dir)

                result["files_validated"] = cast(int, result["files_validated"]) + 1

            except Exception as e:
                result["valid"] = False
                cast(builtins.list[str], result["errors"]).append(f"{template_file.name}: {e!s}")

        return result

    def _validate_jinja2_syntax(self, template_file: Path, template_dir: Path) -> None:
        """
        Validate Jinja2 syntax of a template file.

        Args:
            template_file: Path to template file
            template_dir: Template directory for relative path calculation
        """
        # Calculate relative path for Jinja2 loader
        relative_path = template_file.relative_to(self.templates_dir)
        template_path = str(relative_path).replace("\\", "/")  # Ensure forward slashes

        try:
            # This will raise TemplateSyntaxError if syntax is invalid
            self.env.get_template(template_path)
        except TemplateSyntaxError as e:
            raise Exception(f"Jinja2 syntax error: {e!s}")

    def _validate_python_generation(self, template_file: Path, template_dir: Path) -> None:
        """
        Validate that a Python template generates valid Python code.

        Args:
            template_file: Path to Python template file
            template_dir: Template directory
        """
        # Calculate relative path for Jinja2 loader
        relative_path = template_file.relative_to(self.templates_dir)
        template_path = str(relative_path).replace("\\", "/")

        try:
            # Get the template
            template = self.env.get_template(template_path)

            # Render with sample variables
            sample_vars = self._get_sample_template_vars()
            rendered_content = template.render(**sample_vars)

            # Try to parse as Python AST
            ast.parse(rendered_content)

        except TemplateSyntaxError as e:
            raise Exception(f"Jinja2 syntax error during rendering: {e!s}")
        except SyntaxError as e:
            raise Exception(f"Generated Python code has syntax errors: {e!s}")
        except Exception as e:
            raise Exception(f"Template rendering failed: {e!s}")

    def _get_sample_template_vars(self) -> builtins.dict[str, Any]:
        """
        Get sample template variables for testing.

        Returns:
            Dictionary of sample template variables
        """
        return {
            "service_name": "test_service",
            "service_package": "test_service",
            "service_class": "TestService",
            "service_description": "Test service for validation",
            "author": "Test Author",
            "grpc_port": 50051,
            "http_port": 8080,
            "use_database": True,
        }

    def _print_summary(self, results: builtins.dict[str, Any]) -> None:
        """
        Print validation summary.

        Args:
            results: Validation results dictionary
        """
        print("=" * 60)
        print("SERVICE TEMPLATE VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total templates: {results['total']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Success rate: {results['success_rate']:.1f}%")
        print()

        if results["passed"] > 0:
            print("✅ PASSED TEMPLATES:")
            for template_name, template_result in results["templates"].items():
                if template_result["valid"]:
                    files_count = template_result["files_validated"]
                    print(f"  - {template_name}: {files_count} Python files validated")

        if results["failed"] > 0:
            print()
            print("❌ FAILED TEMPLATES:")
            for template_name, template_result in results["templates"].items():
                if not template_result["valid"]:
                    print(f"  - {template_name}:")
                    for error in template_result["errors"]:
                        print(f"    • {error}")

        print()
        if results["failed"] == 0:
            print("✅ All templates passed validation!")
        else:
            print(f"⚠️ {results['failed']} template(s) need attention.")


def main() -> None:
    """Main entry point for template validation."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent  # Go up to project root
    templates_dir = project_root / "services"

    try:
        validator = ServiceTemplateValidator(templates_dir)
        results = validator.validate_all_templates()

        # Exit with error code if any templates failed
        if results["failed"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
