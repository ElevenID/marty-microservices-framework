"""
Tests for observability validation.

This module converts the legacy validate_observability.py script into proper automated tests.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from marty_msf.framework.logging import UnifiedServiceLogger
from marty_msf.framework.monitoring.core import MetricsCollector
from marty_msf.observability.kafka import EventBus, KafkaConfig
from scripts import validate_observability
from scripts.validate_observability import validate_kafka_configs


class TestObservabilityValidation:
    """Test suite for observability component validation."""

    def test_kafka_config_validation(self):
        """Test Kafka configuration file validation."""
        kafka_dir = Path("observability/kafka")

        if not kafka_dir.exists():
            pytest.skip("Kafka directory not found")

        # Check for docker-compose file
        docker_compose_file = kafka_dir / "docker-compose.kafka.yml"
        if docker_compose_file.exists():
            try:
                with open(docker_compose_file) as f:
                    config = yaml.safe_load(f)

                # Basic validation
                assert isinstance(config, dict), "Docker compose should be a dictionary"
                assert "services" in config, "Docker compose should have services"

            except yaml.YAMLError as e:
                pytest.fail(f"Invalid Kafka docker-compose.yml: {e}")
        else:
            pytest.skip("Kafka docker-compose.yml not found")

    def test_kafka_modules_import(self):
        """Test that Kafka modules can be imported and instantiated."""
        try:
            sys.path.insert(0, str(Path.cwd()))

            # Basic instantiation test
            config = KafkaConfig()
            assert config is not None

            event_bus = EventBus(config, "test")
            assert event_bus is not None

        except ImportError as e:
            pytest.skip(f"Cannot import Kafka modules: {e}")

    def test_prometheus_config_validation(self):
        """Test Prometheus configuration validation."""
        prometheus_dir = Path("observability/metrics")

        if not prometheus_dir.exists():
            pytest.skip("Prometheus/metrics directory not found")

        # Look for prometheus config files
        config_files = list(prometheus_dir.glob("*prometheus*.yml")) + list(
            prometheus_dir.glob("*prometheus*.yaml")
        )

        if not config_files:
            pytest.skip("No Prometheus config files found")

        for config_file in config_files:
            try:
                with open(config_file) as f:
                    config = yaml.safe_load(f)

                # Basic Prometheus config validation
                if isinstance(config, dict):
                    # Check for typical Prometheus sections
                    expected_sections = ["global", "scrape_configs", "rule_files"]
                    found_sections = [section for section in expected_sections if section in config]

                    if not found_sections:
                        print(f"⚠️  {config_file} may not be a valid Prometheus config")

            except yaml.YAMLError as e:
                pytest.fail(f"Invalid Prometheus config {config_file}: {e}")

    def test_grafana_dashboard_validation(self):
        """Test Grafana dashboard JSON validation."""
        grafana_dir = Path("observability/monitoring")

        if not grafana_dir.exists():
            pytest.skip("Grafana/monitoring directory not found")

        # Look for Grafana dashboard files
        dashboard_files = list(grafana_dir.glob("**/*.json"))

        if not dashboard_files:
            pytest.skip("No Grafana dashboard files found")

        for dashboard_file in dashboard_files:
            try:
                with open(dashboard_file) as f:
                    dashboard = json.load(f)

                # Basic Grafana dashboard validation
                if isinstance(dashboard, dict):
                    # Check for typical Grafana dashboard fields

                    # Some dashboards have different structures
                    if "dashboard" in dashboard:
                        dashboard_data = dashboard["dashboard"]
                    else:
                        dashboard_data = dashboard

                    if isinstance(dashboard_data, dict):
                        has_title = "title" in dashboard_data
                        has_panels = "panels" in dashboard_data

                        if not (has_title or has_panels):
                            print(f"⚠️  {dashboard_file} may not be a valid Grafana dashboard")

            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in Grafana dashboard {dashboard_file}: {e}")

    def test_load_testing_components(self):
        """Test load testing example imports."""
        load_testing_dir = Path("observability/load_testing")

        if not load_testing_dir.exists():
            pytest.skip("Load testing directory not found")

        # Look for Python files in load testing directory
        python_files = list(load_testing_dir.glob("*.py"))

        if not python_files:
            pytest.skip("No load testing Python files found")

        import_errors = []
        for py_file in python_files:
            if py_file.name == "__init__.py":
                continue

            module_name = py_file.stem
            try:
                # Add the load testing directory to Python path
                sys.path.insert(0, str(load_testing_dir))
                __import__(module_name)

            except ImportError as e:
                import_errors.append((py_file, str(e)))
            finally:
                # Clean up path
                if str(load_testing_dir) in sys.path:
                    sys.path.remove(str(load_testing_dir))

        if import_errors:
            error_msg = "\n".join([f"  {file}: {error}" for file, error in import_errors])
            pytest.fail(f"Load testing import errors:\n{error_msg}")

    def test_metrics_collection_components(self):
        """Test metrics collection components."""
        try:
            # Basic instantiation test
            collector = MetricsCollector()
            assert collector is not None

            # Test basic methods exist
            assert hasattr(collector, "increment_counter")
            assert hasattr(collector, "set_gauge")

        except ImportError as e:
            pytest.skip(f"Cannot import metrics collector: {e}")

    def test_logging_configuration(self):
        """Test logging configuration validation."""
        try:
            # Test logger instantiation
            logger = UnifiedServiceLogger("test-service")
            assert logger is not None

            # Test basic logging methods
            assert hasattr(logger, "info")
            assert hasattr(logger, "error")
            assert hasattr(logger, "warning")

        except ImportError as e:
            pytest.skip(f"Cannot import logging components: {e}")

    def test_tracing_configuration(self):
        """Test distributed tracing configuration."""
        tracing_dir = Path("observability/tracing")

        if not tracing_dir.exists():
            pytest.skip("Tracing directory not found")

        # Look for tracing configuration files
        config_files = list(tracing_dir.glob("*.yml")) + list(tracing_dir.glob("*.yaml"))

        for config_file in config_files:
            try:
                with open(config_file) as f:
                    config = yaml.safe_load(f)

                if isinstance(config, dict):
                    # Basic validation for common tracing fields
                    if "jaeger" in str(config_file).lower():
                        # Jaeger-specific validation
                        pass
                    elif "zipkin" in str(config_file).lower():
                        # Zipkin-specific validation
                        pass

            except yaml.YAMLError as e:
                pytest.fail(f"Invalid tracing config {config_file}: {e}")

    @patch("subprocess.run")
    def test_observability_service_health(self, mock_run):
        """Test observability service health checks."""
        # Mock successful health check
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "OK"
        mock_run.return_value = mock_result

        # Import and test the original validation function
        try:
            errors = validate_kafka_configs()

            # Should return empty list if no errors
            assert isinstance(errors, list)

        except ImportError:
            pytest.skip("Cannot import observability validation script")

    def test_slo_configuration(self):
        """Test Service Level Objective configuration."""
        slo_dir = Path("observability/slo")

        if not slo_dir.exists():
            pytest.skip("SLO directory not found")

        # Look for SLO configuration files
        config_files = (
            list(slo_dir.glob("*.yml"))
            + list(slo_dir.glob("*.yaml"))
            + list(slo_dir.glob("*.json"))
        )

        if not config_files:
            pytest.skip("No SLO configuration files found")

        for config_file in config_files:
            try:
                if config_file.suffix in [".yml", ".yaml"]:
                    with open(config_file) as f:
                        config = yaml.safe_load(f)
                elif config_file.suffix == ".json":
                    with open(config_file) as f:
                        config = json.load(f)
                else:
                    continue

                # Basic SLO validation
                if isinstance(config, dict):
                    # Check for common SLO fields
                    slo_fields = ["sli", "target", "window", "objectives"]

                    has_slo_content = any(field in str(config).lower() for field in slo_fields)

                    if not has_slo_content:
                        print(f"⚠️  {config_file} may not contain SLO configuration")

            except (yaml.YAMLError, json.JSONDecodeError) as e:
                pytest.fail(f"Invalid SLO config {config_file}: {e}")

    def test_observability_docker_compose(self):
        """Test observability Docker Compose configurations."""
        observability_dir = Path("observability")

        if not observability_dir.exists():
            pytest.skip("Observability directory not found")

        # Look for docker-compose files
        compose_files = list(observability_dir.glob("**/docker-compose*.yml")) + list(
            observability_dir.glob("**/docker-compose*.yaml")
        )

        if not compose_files:
            pytest.skip("No Docker Compose files found")

        for compose_file in compose_files:
            try:
                with open(compose_file) as f:
                    config = yaml.safe_load(f)

                # Basic Docker Compose validation
                assert isinstance(config, dict), f"Invalid Docker Compose format in {compose_file}"
                assert "services" in config, f"No services defined in {compose_file}"

                services = config["services"]
                assert isinstance(services, dict), (
                    f"Services should be a dictionary in {compose_file}"
                )
                assert len(services) > 0, f"No services defined in {compose_file}"

                # Check that each service has required fields
                for service_name, service_config in services.items():
                    assert isinstance(service_config, dict), (
                        f"Service {service_name} config should be a dict"
                    )

                    # Either image or build should be specified
                    has_image = "image" in service_config
                    has_build = "build" in service_config

                    if not (has_image or has_build):
                        print(
                            f"⚠️  Service {service_name} in {compose_file} has no image or build config"
                        )

            except yaml.YAMLError as e:
                pytest.fail(f"Invalid Docker Compose file {compose_file}: {e}")

    def test_import_original_validation_script(self):
        """Test that the original validation script can be imported."""
        try:
            # Check that main validation functions exist
            assert hasattr(validate_observability, "validate_kafka_configs")

            # Test that we can call the main functions
            kafka_errors = validate_observability.validate_kafka_configs()
            assert isinstance(kafka_errors, list)

        except ImportError as e:
            pytest.fail(f"Could not import validate_observability script: {e}")
