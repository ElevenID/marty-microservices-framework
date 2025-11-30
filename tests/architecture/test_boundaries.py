import ast
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
MMF_NEW_ROOT = PROJECT_ROOT / "mmf_new"


def get_imports(file_path):
    """Extract all imported modules from a python file."""
    with open(file_path, encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError:
            return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def check_layer_violations(layer_path, forbidden_layers):
    """Check if files in layer_path import from forbidden_layers."""
    violations = []

    if not layer_path.exists():
        return violations

    for file_path in layer_path.rglob("*.py"):
        if "tests" in file_path.parts:
            continue

        imports = get_imports(file_path)
        for imp in imports:
            for forbidden in forbidden_layers:
                # Check for absolute imports like 'mmf_new.infrastructure...'
                if imp.startswith(f"mmf_new.{forbidden}"):
                    violations.append(f"{file_path.relative_to(PROJECT_ROOT)} imports {imp}")
                # Check for relative imports? (Harder with AST, assuming absolute imports for now or standard structure)

    return violations


@pytest.mark.unit
def test_domain_layer_independence():
    """Domain layer should not import Application or Infrastructure."""
    # Based on file structure in prompt: mmf_new/core, mmf_new/application, mmf_new/infrastructure

    violations = []

    # Check core domain
    violations.extend(
        check_layer_violations(MMF_NEW_ROOT / "core" / "domain", ["application", "infrastructure"])
    )

    # Check services domain
    services_path = MMF_NEW_ROOT / "services"
    if services_path.exists():
        for service in services_path.iterdir():
            if service.is_dir():
                violations.extend(
                    check_layer_violations(service / "domain", ["application", "infrastructure"])
                )

    assert not violations, "Domain layer violations found:\n" + "\n".join(violations)


@pytest.mark.unit
def test_application_layer_independence():
    """Application layer should not import Infrastructure."""
    violations = []

    # Check core application
    violations.extend(
        check_layer_violations(MMF_NEW_ROOT / "core" / "application", ["infrastructure"])
    )

    # Check services application
    services_path = MMF_NEW_ROOT / "services"
    if services_path.exists():
        for service in services_path.iterdir():
            if service.is_dir():
                violations.extend(
                    check_layer_violations(service / "application", ["infrastructure"])
                )

    assert not violations, "Application layer violations found:\n" + "\n".join(violations)
