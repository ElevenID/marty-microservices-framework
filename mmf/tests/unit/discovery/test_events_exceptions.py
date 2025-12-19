"""
Unit tests for Service Discovery events and exceptions.
"""

import time
import uuid

import pytest

from mmf.discovery.domain.events import ServiceEvent
from mmf.discovery.domain.exceptions import (
    HealthCheckError,
    ServiceDeregistrationError,
    ServiceDiscoveryError,
    ServiceNotFoundError,
    ServiceRegistrationError,
)
from mmf.discovery.domain.models import (
    ServiceEndpoint,
    ServiceInstance,
    ServiceInstanceType,
)


class TestServiceEvent:
    """Tests for ServiceEvent class."""

    def _create_instance(self) -> ServiceInstance:
        """Create a test service instance."""
        return ServiceInstance(
            service_name="test-service",
            instance_id="inst-1",
            endpoint=ServiceEndpoint(
                host="localhost",
                port=8080,
                protocol=ServiceInstanceType.HTTP,
            ),
        )

    def test_event_creation_basic(self):
        """Test creating a basic event."""
        event = ServiceEvent(
            event_type="register",
            service_name="test-service",
            instance_id="inst-1",
        )

        assert event.event_type == "register"
        assert event.service_name == "test-service"
        assert event.instance_id == "inst-1"
        assert event.instance is None
        assert event.timestamp is not None
        assert event.event_id is not None

    def test_event_creation_with_instance(self):
        """Test creating event with instance."""
        instance = self._create_instance()

        event = ServiceEvent(
            event_type="register",
            service_name="test-service",
            instance_id="inst-1",
            instance=instance,
        )

        assert event.instance == instance

    def test_event_creation_with_timestamp(self):
        """Test creating event with custom timestamp."""
        custom_time = 1234567890.0

        event = ServiceEvent(
            event_type="register",
            service_name="test-service",
            instance_id="inst-1",
            timestamp=custom_time,
        )

        assert event.timestamp == custom_time

    def test_event_id_is_uuid(self):
        """Test that event_id is a valid UUID."""
        event = ServiceEvent(
            event_type="register",
            service_name="test-service",
            instance_id="inst-1",
        )

        # Should not raise
        uuid.UUID(event.event_id)

    def test_event_timestamp_auto_generated(self):
        """Test that timestamp is auto-generated close to now."""
        before = time.time()
        event = ServiceEvent(
            event_type="register",
            service_name="test-service",
            instance_id="inst-1",
        )
        after = time.time()

        assert before <= event.timestamp <= after

    def test_event_types(self):
        """Test various event types."""
        event_types = ["register", "deregister", "health_change", "status_update"]

        for event_type in event_types:
            event = ServiceEvent(
                event_type=event_type,
                service_name="test-service",
                instance_id="inst-1",
            )
            assert event.event_type == event_type

    def test_to_dict_basic(self):
        """Test converting event to dict without instance."""
        event = ServiceEvent(
            event_type="register",
            service_name="test-service",
            instance_id="inst-1",
        )

        data = event.to_dict()

        assert data["event_id"] == event.event_id
        assert data["event_type"] == "register"
        assert data["service_name"] == "test-service"
        assert data["instance_id"] == "inst-1"
        assert data["instance"] is None
        assert data["timestamp"] == event.timestamp

    def test_to_dict_with_instance(self):
        """Test converting event to dict with instance."""
        instance = self._create_instance()

        event = ServiceEvent(
            event_type="register",
            service_name="test-service",
            instance_id="inst-1",
            instance=instance,
        )

        data = event.to_dict()

        assert data["instance"] is not None
        assert isinstance(data["instance"], dict)
        assert data["instance"]["service_name"] == "test-service"


class TestServiceDiscoveryExceptions:
    """Tests for service discovery exception hierarchy."""

    def test_base_exception(self):
        """Test base ServiceDiscoveryError."""
        error = ServiceDiscoveryError("Base error")

        assert str(error) == "Base error"
        assert isinstance(error, Exception)

    def test_service_not_found_error(self):
        """Test ServiceNotFoundError."""
        error = ServiceNotFoundError("Service 'user-service' not found")

        assert isinstance(error, ServiceDiscoveryError)
        assert "user-service" in str(error)

    def test_service_registration_error(self):
        """Test ServiceRegistrationError."""
        error = ServiceRegistrationError("Registration failed: limit exceeded")

        assert isinstance(error, ServiceDiscoveryError)
        assert "Registration failed" in str(error)

    def test_service_deregistration_error(self):
        """Test ServiceDeregistrationError."""
        error = ServiceDeregistrationError("Deregistration failed: not found")

        assert isinstance(error, ServiceDiscoveryError)
        assert "Deregistration failed" in str(error)

    def test_health_check_error(self):
        """Test HealthCheckError."""
        error = HealthCheckError("Health check timed out")

        assert isinstance(error, ServiceDiscoveryError)
        assert "timed out" in str(error)

    def test_exception_inheritance_allows_catching(self):
        """Test that all exceptions can be caught by base class."""
        exceptions = [
            ServiceNotFoundError("Not found"),
            ServiceRegistrationError("Registration failed"),
            ServiceDeregistrationError("Deregistration failed"),
            HealthCheckError("Health check failed"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except ServiceDiscoveryError as e:
                assert e is exc  # Should catch all

    def test_exception_with_no_message(self):
        """Test exceptions can be raised without message."""
        errors = [
            ServiceDiscoveryError(),
            ServiceNotFoundError(),
            ServiceRegistrationError(),
            ServiceDeregistrationError(),
            HealthCheckError(),
        ]

        for error in errors:
            assert error is not None


class TestServiceEventEquality:
    """Tests for ServiceEvent edge cases."""

    def test_two_events_have_different_ids(self):
        """Test that two events always have different IDs."""
        event1 = ServiceEvent(
            event_type="register",
            service_name="test-service",
            instance_id="inst-1",
        )
        event2 = ServiceEvent(
            event_type="register",
            service_name="test-service",
            instance_id="inst-1",
        )

        assert event1.event_id != event2.event_id

    def test_event_with_empty_strings(self):
        """Test event with empty strings."""
        event = ServiceEvent(
            event_type="",
            service_name="",
            instance_id="",
        )

        assert event.event_type == ""
        assert event.service_name == ""
        assert event.instance_id == ""
