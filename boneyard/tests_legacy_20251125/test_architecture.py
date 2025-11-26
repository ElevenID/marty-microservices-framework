"""
Architectural Tests.

This module enforces the Hexagonal Architecture rules using pytest-archon.
"""

from pytest_archon import archrule


def test_domain_has_no_infrastructure_imports():
    """Domain layer must not import infrastructure."""
    (
        archrule("domain_isolation")
        .match("mmf_new.services.*.domain")
        .should_not_import("mmf_new.services.*.infrastructure")
        .check("mmf_new")
    )


def test_domain_has_no_application_imports():
    """Domain layer must not import application."""
    (
        archrule("domain_isolation_app")
        .match("mmf_new.services.*.domain")
        .should_not_import("mmf_new.services.*.application")
        .check("mmf_new")
    )


def test_application_has_no_infrastructure_imports():
    """Application layer must not import infrastructure."""
    (
        archrule("application_isolation")
        .match("mmf_new.services.*.application")
        .should_not_import("mmf_new.services.*.infrastructure")
        .check("mmf_new")
    )


def test_framework_domain_isolation():
    """Framework domain must not import adapters."""
    (
        archrule("framework_domain_isolation")
        .match("mmf_new.framework.*.domain")
        .should_not_import("mmf_new.framework.*.adapters")
        .check("mmf_new")
    )
