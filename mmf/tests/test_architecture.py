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


# =============================================================================
# Example Services Architecture Rules (petstore_domain)
# =============================================================================


def test_example_petstore_domain_isolation():
    """
    Example service Domain layers MUST NOT import from Application or Infrastructure.

    This ensures examples follow the same strict Hexagonal Architecture rules
    as production services in mmf/services.
    """
    (
        archrule("example_petstore_domain_isolation")
        .match("examples.petstore_domain.services.*.domain")
        .should_not_import("examples.petstore_domain.services.*.infrastructure")
        .should_not_import("examples.petstore_domain.services.*.application")
        .check("examples")
    )


def test_example_petstore_application_isolation():
    """
    Example service Application layers MUST NOT import from Infrastructure.

    Application layers should only depend on Domain and define Ports (interfaces)
    that Infrastructure adapters implement.
    """
    (
        archrule("example_petstore_application_isolation")
        .match("examples.petstore_domain.services.*.application")
        .should_not_import("examples.petstore_domain.services.*.infrastructure")
        .check("examples")
    )


def test_example_bounded_context_isolation():
    """
    Example services MUST NOT import from other services' internal layers.

    Each service is a bounded context with its own domain model. Services
    should only communicate via well-defined APIs, not by importing each
    other's domain, application, or infrastructure modules.
    """
    # pet_service should not import from store_service internals
    (
        archrule("pet_service_bounded_context")
        .match("examples.petstore_domain.services.pet_service")
        .should_not_import("examples.petstore_domain.services.store_service.domain")
        .should_not_import("examples.petstore_domain.services.store_service.application")
        .should_not_import("examples.petstore_domain.services.store_service.infrastructure")
        .should_not_import("examples.petstore_domain.services.delivery_board_service.domain")
        .should_not_import("examples.petstore_domain.services.delivery_board_service.application")
        .should_not_import(
            "examples.petstore_domain.services.delivery_board_service.infrastructure"
        )
        .check("examples")
    )

    # store_service should not import from pet_service internals
    (
        archrule("store_service_bounded_context")
        .match("examples.petstore_domain.services.store_service")
        .should_not_import("examples.petstore_domain.services.pet_service.domain")
        .should_not_import("examples.petstore_domain.services.pet_service.application")
        .should_not_import("examples.petstore_domain.services.pet_service.infrastructure")
        .should_not_import("examples.petstore_domain.services.delivery_board_service.domain")
        .should_not_import("examples.petstore_domain.services.delivery_board_service.application")
        .should_not_import(
            "examples.petstore_domain.services.delivery_board_service.infrastructure"
        )
        .check("examples")
    )

    # delivery_board_service should not import from other services' internals
    (
        archrule("delivery_board_service_bounded_context")
        .match("examples.petstore_domain.services.delivery_board_service")
        .should_not_import("examples.petstore_domain.services.pet_service.domain")
        .should_not_import("examples.petstore_domain.services.pet_service.application")
        .should_not_import("examples.petstore_domain.services.pet_service.infrastructure")
        .should_not_import("examples.petstore_domain.services.store_service.domain")
        .should_not_import("examples.petstore_domain.services.store_service.application")
        .should_not_import("examples.petstore_domain.services.store_service.infrastructure")
        .check("examples")
    )
