"""Architectural tests enforcing Hexagonal Architecture rules.

These tests use pytest-archon to verify that the codebase adheres to the
strict dependency rules defined in ARCHITECTURE.md.
"""

from pytest_archon import archrule


def test_service_domain_isolation():
    """
    Domain layer MUST NOT import from Application or Infrastructure layers.

    The Domain layer should be pure business logic, independent of use cases
    (Application) and external concerns (Infrastructure).
    """
    (
        archrule("service_domain_isolation")
        .match("mmf_new.services.*.domain")
        .should_not_import("mmf_new.services.*.infrastructure")
        .should_not_import("mmf_new.services.*.application")
        .check("mmf_new")
    )


def test_service_application_isolation():
    """
    Application layer MUST NOT import from Infrastructure layer.

    The Application layer orchestrates use cases using Domain objects and
    Ports (interfaces). It should not depend on concrete adapters (Infrastructure).
    """
    (
        archrule("service_application_isolation")
        .match("mmf_new.services.*.application")
        .should_not_import("mmf_new.services.*.infrastructure")
        .check("mmf_new")
    )


def test_framework_domain_isolation():
    """
    Framework Domain layer MUST NOT import from Adapters.

    Framework modules should also follow Hexagonal Architecture, keeping
    core abstractions (Domain) separate from concrete implementations (Adapters).
    """
    (
        archrule("framework_domain_isolation")
        .match("mmf_new.framework.*.domain")
        .should_not_import("mmf_new.framework.*.adapters")
        .check("mmf_new")
    )
