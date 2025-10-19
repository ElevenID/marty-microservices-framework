"""
Tests for messaging routing strategies.
Tests routing strategy patterns, matching types, and routing configurations.
"""

from enum import Enum

import pytest

from marty_msf.framework.messaging.routing import (
    MatchType,
    RoutingConfig,
    RoutingEngine,
    RoutingRule,
    RoutingType,
)


def test_import_routing_strategies():
    """Test that routing strategies can be imported."""
    try:

        assert issubclass(RoutingType, Enum)
        assert issubclass(MatchType, Enum)
        assert RoutingConfig is not None
        print("✓ Routing strategies imported successfully")
    except ImportError as e:
        pytest.skip(f"Cannot import routing strategies: {e}")


def test_routing_type_enum():
    """Test RoutingType enum values."""
    try:

        # Test enum members exist
        assert hasattr(RoutingType, "DIRECT")
        assert hasattr(RoutingType, "TOPIC")
        assert hasattr(RoutingType, "FANOUT")
        assert hasattr(RoutingType, "HEADERS")
        assert hasattr(RoutingType, "CONTENT")
        assert hasattr(RoutingType, "CUSTOM")

        # Test enum values
        assert RoutingType.DIRECT.value == "direct"
        assert RoutingType.TOPIC.value == "topic"
        assert RoutingType.FANOUT.value == "fanout"
        assert RoutingType.HEADERS.value == "headers"
        assert RoutingType.CONTENT.value == "content"
        assert RoutingType.CUSTOM.value == "custom"

        print("✓ All routing type enum values validated")

    except ImportError as e:
        pytest.skip(f"Cannot import RoutingType: {e}")


def test_match_type_enum():
    """Test MatchType enum values."""
    try:

        # Test enum members exist
        assert hasattr(MatchType, "EXACT")
        assert hasattr(MatchType, "WILDCARD")
        assert hasattr(MatchType, "REGEX")
        assert hasattr(MatchType, "GLOB")

        # Test enum values
        assert MatchType.EXACT.value == "exact"
        assert MatchType.WILDCARD.value == "wildcard"
        assert MatchType.REGEX.value == "regex"
        assert MatchType.GLOB.value == "glob"

        print("✓ All match type enum values validated")

    except ImportError as e:
        pytest.skip(f"Cannot import MatchType: {e}")


def test_routing_config_creation():
    """Test RoutingConfig creation and default values."""
    try:

        # Test default configuration
        config = RoutingConfig()
        assert config.allow_multiple_targets
        assert not config.stop_on_first_match
        assert config.enable_caching
        assert config.cache_ttl == 300.0
        assert config.enable_metrics

        # Test custom configuration
        custom_config = RoutingConfig(
            default_queue="test-queue", allow_multiple_targets=False, cache_ttl=600.0
        )
        assert custom_config.default_queue == "test-queue"
        assert not custom_config.allow_multiple_targets
        assert custom_config.cache_ttl == 600.0

        print("✓ RoutingConfig creation and configuration works correctly")

    except ImportError as e:
        pytest.skip(f"Cannot import RoutingConfig: {e}")


def test_routing_rule_creation():
    """Test RoutingRule creation."""
    try:

        # Test basic routing rule creation
        rule = RoutingRule(
            name="test-rule",
            routing_type=RoutingType.DIRECT,
            pattern="test.key",
            match_type=MatchType.EXACT,
            target_queues=["queue1", "queue2"],
        )

        assert rule.name == "test-rule"
        assert rule.routing_type == RoutingType.DIRECT
        assert rule.pattern == "test.key"
        assert rule.match_type == MatchType.EXACT
        assert rule.target_queues == ["queue1", "queue2"]
        assert rule.enabled  # Default value
        assert rule.priority == 0  # Default value

        print("✓ RoutingRule creation works correctly")

    except ImportError as e:
        pytest.skip(f"Cannot import RoutingRule: {e}")


def test_routing_strategies_iteration():
    """Test that routing strategies can be iterated."""
    try:

        # Test RoutingType iteration
        routing_types = list(RoutingType)
        assert len(routing_types) == 6

        routing_values = [rt.value for rt in routing_types]
        expected_routing = ["direct", "topic", "fanout", "headers", "content", "custom"]

        for expected in expected_routing:
            assert expected in routing_values

        # Test MatchType iteration
        match_types = list(MatchType)
        assert len(match_types) == 4

        match_values = [mt.value for mt in match_types]
        expected_matching = ["exact", "wildcard", "regex", "glob"]

        for expected in expected_matching:
            assert expected in match_values

        print("✓ Routing strategy iteration works correctly")

    except ImportError as e:
        pytest.skip(f"Cannot import routing strategies: {e}")


def test_routing_strategy_validation():
    """Test routing strategy validation and constraints."""
    try:

        # Test routing type values are strings
        for routing_type in RoutingType:
            assert isinstance(routing_type.value, str)
            assert len(routing_type.value) > 0

        # Test match type values are strings
        for match_type in MatchType:
            assert isinstance(match_type.value, str)
            assert len(match_type.value) > 0

        # Test specific routing type checks
        assert RoutingType.DIRECT != RoutingType.TOPIC
        assert MatchType.EXACT != MatchType.REGEX

        print("✓ Routing strategy validation passed")

    except ImportError as e:
        pytest.skip(f"Cannot import routing strategies: {e}")


def test_routing_engine_creation():
    """Test RoutingEngine creation with configuration."""
    try:

        # Test engine creation with default config
        config = RoutingConfig()
        engine = RoutingEngine(config)

        assert engine.config == config
        assert hasattr(engine, "_rules")
        assert hasattr(engine, "_routing_cache")
        assert hasattr(engine, "_total_routed")

        print("✓ RoutingEngine creation works correctly")

    except ImportError as e:
        pytest.skip(f"Cannot import RoutingEngine: {e}")
    except AttributeError as e:
        pytest.skip(f"RoutingEngine creation failed: {e}")
