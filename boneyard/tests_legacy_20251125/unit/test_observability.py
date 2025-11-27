"""
Tests for observability components
"""

import pytest
from marty_msf.observability.kafka import EventBus, EventMessage, KafkaConfig
from marty_msf.observability.load_testing.load_tester import (
    LoadTestConfig,
    LoadTestRunner,
)
from marty_msf.observability.metrics import MetricsCollector, MetricsConfig
from observability import setup_observability


@pytest.fixture
def kafka_config():
    return KafkaConfig(bootstrap_servers=["localhost:9092"], consumer_group_id="test-group")


@pytest.fixture
def metrics_config():
    return MetricsConfig(service_name="test-service", service_version="1.0.0")


@pytest.fixture
def event_bus(kafka_config):
    return EventBus(kafka_config, "test-service")


@pytest.fixture
def metrics_collector(metrics_config):
    return MetricsCollector(metrics_config)


class TestEventBus:
    """Test event bus functionality"""

    def test_event_bus_creation(self, event_bus):
        assert event_bus.service_name == "test-service"
        assert event_bus.config.bootstrap_servers == ["localhost:9092"]

    def test_event_message_creation(self):
        event = EventMessage(
            event_type="test.event",
            service_name="test-service",
            payload={"key": "value"},
        )

        assert event.event_type == "test.event"
        assert event.service_name == "test-service"
        assert event.payload == {"key": "value"}
        assert event.event_id is not None

    @pytest.mark.asyncio
    async def test_event_handler_registration(self, event_bus):
        handler_called = False

        async def test_handler(event):
            nonlocal handler_called
            handler_called = True

        event_bus.register_handler("test.topic", test_handler)

        assert "test.topic" in event_bus.event_handlers
        assert len(event_bus.event_handlers["test.topic"]) == 1


class TestMetricsCollector:
    """Test metrics collection functionality"""

    def test_metrics_collector_creation(self, metrics_collector):
        assert metrics_collector.config.service_name == "test-service"
        assert metrics_collector.config.service_version == "1.0.0"

    def test_grpc_metrics_recording(self, metrics_collector):
        # Test that metrics can be recorded without errors
        metrics_collector.record_grpc_request(
            method="GetUser",
            service="UserService",
            duration=0.1,
            request_size=100,
            response_size=200,
            status_code="OK",
        )

        # Verify metrics are available
        metrics_output = metrics_collector.get_metrics()
        assert "marty_grpc_requests_total" in metrics_output
        assert "marty_grpc_request_duration_seconds" in metrics_output

    def test_business_metrics_recording(self, metrics_collector):
        metrics_collector.record_business_transaction(
            transaction_type="user_creation", duration=0.5, status="success"
        )

        metrics_output = metrics_collector.get_metrics()
        assert "marty_business_transactions_total" in metrics_output
        assert "marty_business_transaction_duration_seconds" in metrics_output

    def test_custom_metrics_creation(self, metrics_collector):
        counter = metrics_collector.create_custom_counter(
            name="test_counter", description="Test counter", labels=["label1", "label2"]
        )

        assert counter is not None

        # Test incrementing counter
        counter.labels(label1="value1", label2="value2").inc()

        metrics_output = metrics_collector.get_metrics()
        assert "marty_test_counter" in metrics_output


class TestLoadTesting:
    """Test load testing functionality"""

    def test_load_test_config_creation(self):
        config = LoadTestConfig(
            target_host="localhost",
            target_port=8080,
            test_duration_seconds=30,
            concurrent_users=5,
            protocol="http",
        )

        assert config.target_host == "localhost"
        assert config.target_port == 8080
        assert config.test_duration_seconds == 30
        assert config.concurrent_users == 5
        assert config.protocol == "http"

    def test_load_test_runner_creation(self):
        runner = LoadTestRunner()
        assert runner is not None


class TestObservabilityIntegration:
    """Test integration between observability components"""

    @pytest.mark.asyncio
    async def test_metrics_and_events_integration(self, metrics_collector):
        # Test that metrics can track event-related operations
        KafkaConfig(bootstrap_servers=["localhost:9092"], consumer_group_id="test-integration")

        # Record event publishing metric
        metrics_collector.record_event_published("test.event", "test.topic")

        # Verify metric was recorded
        metrics_output = metrics_collector.get_metrics()
        assert "marty_events_published_total" in metrics_output

    def test_observability_setup_function(self):
        """Test the main setup function"""

        # Test that the function exists and is callable
        assert callable(setup_observability)


# Integration test to verify observability components work together
@pytest.mark.integration
class TestObservabilityStack:
    """Integration tests for the complete observability stack"""

    @pytest.mark.asyncio
    async def test_full_observability_stack(self):
        """Test that all components can be initialized together"""

        # This would require actual Kafka running for full test
        # For now, just test the setup function doesn't crash
        try:
            metrics, event_bus = await setup_observability(
                service_name="integration-test",
                service_version="1.0.0",
                enable_events=False,  # Disable events to avoid Kafka dependency
            )

            assert metrics is not None
            assert event_bus is None  # Disabled

        except Exception as e:
            pytest.fail(f"Observability setup failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
