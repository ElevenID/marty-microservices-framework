#!/usr/bin/env python3
"""
Observability validation script for pre-commit hooks

Validates:
- Kafka configuration files are valid
- Prometheus configurations are syntactically correct
- Grafana dashboards are valid JSON
- Load testing examples can be imported
- Metrics collection components work correctly
"""

import builtins
import json
import sys
from pathlib import Path
from typing import list

import yaml
from observability.kafka import EventBus, KafkaConfig
from observability.load_testing.load_tester import LoadTestConfig, LoadTestRunner
from observability.metrics import MetricsCollector, MetricsConfig


def validate_kafka_configs() -> builtins.list[str]:
    """Validate Kafka configuration files"""
    errors = []
    kafka_dir = Path("observability/kafka")

    if not kafka_dir.exists():
        return ["Kafka directory not found"]

    # Validate docker-compose file
    docker_compose_file = kafka_dir / "docker-compose.kafka.yml"
    if docker_compose_file.exists():
        try:
            with open(docker_compose_file) as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(f"Invalid Kafka docker-compose.yml: {e}")
    else:
        errors.append("Kafka docker-compose.yml not found")

    # Validate Python modules can be imported
    try:
        sys.path.insert(0, str(Path.cwd()))

        # Basic instantiation test
        config = KafkaConfig()
        EventBus(config, "test")
    except ImportError as e:
        errors.append(f"Cannot import Kafka modules: {e}")
    except Exception as e:
        errors.append(f"Kafka module validation error: {e}")

    return errors


def validate_prometheus_configs() -> builtins.list[str]:
    """Validate Prometheus configuration files"""
    errors = []
    prometheus_dir = Path("observability/monitoring/prometheus")

    if not prometheus_dir.exists():
        return ["Prometheus directory not found"]

    # Validate prometheus.yml
    prometheus_config = prometheus_dir / "prometheus.yml"
    if prometheus_config.exists():
        try:
            with open(prometheus_config) as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(f"Invalid prometheus.yml: {e}")
    else:
        errors.append("prometheus.yml not found")

    # Validate alert rules
    alert_rules = prometheus_dir / "alert_rules.yml"
    if alert_rules.exists():
        try:
            with open(alert_rules) as f:
                rules = yaml.safe_load(f)

            # Basic validation of alert rules structure
            if not isinstance(rules, dict) or "groups" not in rules:
                errors.append("Alert rules missing 'groups' section")
            else:
                for group in rules["groups"]:
                    if "rules" not in group:
                        errors.append(f"Alert group {group.get('name', 'unknown')} missing 'rules'")

        except yaml.YAMLError as e:
            errors.append(f"Invalid alert_rules.yml: {e}")
    else:
        errors.append("alert_rules.yml not found")

    return errors


def validate_grafana_dashboards() -> builtins.list[str]:
    """Validate Grafana dashboard JSON files"""
    errors = []
    grafana_dir = Path("observability/monitoring/grafana/dashboards")

    if not grafana_dir.exists():
        return ["Grafana dashboards directory not found"]

    dashboard_files = list(grafana_dir.glob("*.json"))
    if not dashboard_files:
        errors.append("No Grafana dashboard files found")
        return errors

    for dashboard_file in dashboard_files:
        try:
            with open(dashboard_file) as f:
                dashboard = json.load(f)

            # Basic dashboard structure validation
            required_fields = ["title", "panels"]
            for field in required_fields:
                if field not in dashboard:
                    errors.append(
                        f"Dashboard {dashboard_file.name} missing required field: {field}"
                    )

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in {dashboard_file.name}: {e}")

    return errors


def validate_metrics_components() -> builtins.list[str]:
    """Validate metrics collection components"""
    errors = []

    try:
        sys.path.insert(0, str(Path.cwd()))

        # Test basic metrics collector functionality
        config = MetricsConfig(service_name="test-service")
        collector = MetricsCollector(config)

        # Test metrics generation
        metrics_output = collector.get_metrics()
        if not isinstance(metrics_output, str):
            errors.append("Metrics output is not a string")

        # Test custom metrics creation
        try:
            custom_counter = collector.create_custom_counter(
                name="test_counter", description="Test counter", labels=["label1"]
            )
            custom_counter.labels(label1="value1").inc()
        except Exception as e:
            errors.append(f"Custom metrics creation failed: {e}")

    except ImportError as e:
        errors.append(f"Cannot import metrics modules: {e}")
    except Exception as e:
        errors.append(f"Metrics validation error: {e}")

    return errors


def validate_load_testing() -> builtins.list[str]:
    """Validate load testing components"""
    errors = []

    try:
        sys.path.insert(0, str(Path.cwd()))

        # Test configuration creation
        config = LoadTestConfig(
            target_host="localhost",
            target_port=8080,
            test_duration_seconds=1,
            concurrent_users=1,
        )

        if config.target_host != "localhost":
            errors.append("LoadTestConfig not working correctly")

        # Test runner creation
        runner = LoadTestRunner()
        if runner is None:
            errors.append("LoadTestRunner creation failed")

    except ImportError as e:
        errors.append(f"Cannot import load testing modules: {e}")
    except Exception as e:
        errors.append(f"Load testing validation error: {e}")

    return errors


def validate_docker_configs() -> builtins.list[str]:
    """Validate Docker Compose files"""
    errors = []

    docker_files = [
        "observability/kafka/docker-compose.kafka.yml",
        "observability/monitoring/docker-compose.monitoring.yml",
    ]

    for docker_file in docker_files:
        if Path(docker_file).exists():
            try:
                with open(docker_file) as f:
                    compose_config = yaml.safe_load(f)

                # Basic validation
                if "services" not in compose_config:
                    errors.append(f"{docker_file} missing 'services' section")

            except yaml.YAMLError as e:
                errors.append(f"Invalid {docker_file}: {e}")
        else:
            errors.append(f"Docker compose file not found: {docker_file}")

    return errors


def main() -> int:
    """Main validation function"""
    print("🔍 Validating observability components...")

    all_errors = []

    # Run all validations
    validations = [
        ("Kafka configurations", validate_kafka_configs),
        ("Prometheus configurations", validate_prometheus_configs),
        ("Grafana dashboards", validate_grafana_dashboards),
        ("Metrics components", validate_metrics_components),
        ("Load testing components", validate_load_testing),
        ("Docker configurations", validate_docker_configs),
    ]

    for validation_name, validation_func in validations:
        print(f"  Checking {validation_name}...")
        errors = validation_func()
        if errors:
            print(f"    ❌ {len(errors)} error(s) found")
            for error in errors:
                print(f"       • {error}")
            all_errors.extend(errors)
        else:
            print(f"    ✅ {validation_name} validation passed")

    if all_errors:
        print(f"\n❌ Observability validation failed with {len(all_errors)} error(s)")
        return 1
    print("\n✅ All observability components validated successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
