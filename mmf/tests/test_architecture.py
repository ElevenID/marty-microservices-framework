"""Architectural tests enforcing Hexagonal Architecture rules.

These tests use pytest-archon to verify that the codebase adheres to the
strict dependency rules defined in ARCHITECTURE.md.
"""

import sys
from pathlib import Path

import pytest
from pytest_archon import archrule

# Add tools directory to path to import ImportAnalyzer
TOOLS_DIR = Path(__file__).parents[2] / "tools"
sys.path.append(str(TOOLS_DIR))

from analyze_project_imports import ImportAnalyzer


def test_service_domain_isolation():
    """
    Domain layer MUST NOT import from Application or Infrastructure layers.

    The Domain layer should be pure business logic, independent of use cases
    (Application) and external concerns (Infrastructure).
    """
    (
        archrule("service_domain_isolation")
        .match("mmf.services.*.domain")
        .should_not_import("mmf.services.*.infrastructure")
        .should_not_import("mmf.services.*.application")
        .check("mmf")
    )


def test_service_application_isolation():
    """
    Application layer MUST NOT import from Infrastructure layer.

    The Application layer orchestrates use cases using Domain objects and
    Ports (interfaces). It should not depend on concrete adapters (Infrastructure).
    """
    (
        archrule("service_application_isolation")
        .match("mmf.services.*.application")
        .should_not_import("mmf.services.*.infrastructure")
        .check("mmf")
    )


def test_framework_domain_isolation():
    """
    Framework Domain layer MUST NOT import from Adapters.

    Framework modules should also follow Hexagonal Architecture, keeping
    core abstractions (Domain) separate from concrete implementations (Adapters).
    """
    (
        archrule("framework_domain_isolation")
        .match("mmf.framework.*.domain")
        .should_not_import("mmf.framework.*.adapters")
        .check("mmf")
    )


def test_no_circular_dependencies():
    """Ensure there are no circular dependencies in the project using ImportAnalyzer."""
    root_dir = Path(__file__).parents[2]
    analyzer = ImportAnalyzer(str(root_dir), "mmf", real_time=True)
    analyzer.analyze_imports()
    cycles = analyzer.find_circular_dependencies()
    assert len(cycles) == 0, f"Found circular dependencies: {cycles}"
