"""
Unit tests for ObservabilityManager.
"""

import unittest
from unittest.mock import MagicMock, patch

import pytest

from mmf.framework.infrastructure.config_manager import BaseServiceConfig
from mmf.framework.observability.domain.protocols import (
    IHealthChecker,
    IMetricsCollector,
)
from mmf.framework.observability.unified_observability import ObservabilityManager


class TestObservabilityManager:
    @pytest.fixture
    def config(self):
        config = MagicMock(spec=BaseServiceConfig)
        config.service_name = "test-service"
        # Mock monitoring config since it's not explicitly defined in BaseServiceConfig
        config.monitoring = MagicMock()
        config.monitoring.enabled = True
        config.monitoring.custom_labels = {}

        # Explicitly mock environment
        config.environment = MagicMock()
        config.environment.value = "test"
        return config

    def test_initialization_with_injection(self, config):
        """Test initialization with injected dependencies."""
        mock_metrics = MagicMock(spec=IMetricsCollector)
        mock_health = MagicMock(spec=IHealthChecker)

        manager = ObservabilityManager(
            config, metrics_collector=mock_metrics, health_checker=mock_health
        )

        assert manager.get_metrics_collector() == mock_metrics
        # Verify _setup_metrics was NOT called (or at least didn't overwrite)
        # Since we can't easily check if private method was called without mocking the class itself,
        # checking the property is enough.

    def test_initialization_without_injection(self, config):
        """Test initialization without injection (default behavior)."""
        # We need to mock MetricsCollector and HealthChecker classes to avoid real instantiation
        with (
            patch(
                "mmf.framework.observability.unified_observability.MetricsCollector"
            ) as MockMetricsCollector,
            patch(
                "mmf.framework.observability.unified_observability.HealthChecker"
            ) as MockHealthChecker,
            patch("mmf.framework.observability.unified_observability.PROMETHEUS_AVAILABLE", True),
        ):
            manager = ObservabilityManager(config)

            assert manager.get_metrics_collector() is not None
            MockMetricsCollector.assert_called_once()
            MockHealthChecker.assert_called_once()

    def test_counter_delegation(self, config):
        """Test that counter creation works."""
        mock_metrics = MagicMock(spec=IMetricsCollector)
        manager = ObservabilityManager(config, metrics_collector=mock_metrics)

        # ObservabilityManager.counter creates a new Counter object, it doesn't delegate to metrics_collector.counter
        # But it checks if metrics_collector exists.

        with (
            patch("mmf.framework.observability.unified_observability.Counter") as MockCounter,
            patch("mmf.framework.observability.unified_observability.PROMETHEUS_AVAILABLE", True),
        ):
            manager.counter("test_metric", "description")

            MockCounter.assert_called_once()
            args, kwargs = MockCounter.call_args
            assert args[0] == "marty_test-service_test_metric"
