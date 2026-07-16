"""
Unit tests for MMF Cache Infrastructure.

Tests for:
- KeyPrefixConfig key building and stripping
- ICacheManager protocol compliance
- InMemoryCacheManager operations
- RedisCacheManager operations (with mock Redis)
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mmf.core.cache import (
    BaseCacheManager,
    ICacheManager,
    InMemoryCacheManager,
    KeyPrefixConfig,
)

# =============================================================================
# KeyPrefixConfig Tests
# =============================================================================


class TestKeyPrefixConfig:
    """Tests for KeyPrefixConfig."""

    def test_full_prefix_default(self):
        """Test default prefix configuration."""
        config = KeyPrefixConfig()
        assert config.full_prefix == "marty:"

    def test_full_prefix_with_plugin(self):
        """Test prefix with plugin specified."""
        config = KeyPrefixConfig(
            app_prefix="marty",
            plugin_prefix="auth",
        )
        assert config.full_prefix == "marty:auth:"

    def test_full_prefix_with_component(self):
        """Test prefix with plugin and component."""
        config = KeyPrefixConfig(
            app_prefix="marty",
            plugin_prefix="auth",
            component_prefix="pkce",
        )
        assert config.full_prefix == "marty:auth:pkce:"

    def test_full_prefix_with_tenant(self):
        """Test prefix with tenant isolation."""
        config = KeyPrefixConfig(
            app_prefix="marty",
            plugin_prefix="auth",
            tenant_id="acme-corp",
            component_prefix="session",
        )
        assert config.full_prefix == "marty:auth:tenant-acme-corp:session:"

    def test_build_key_single_part(self):
        """Test building key with single part."""
        config = KeyPrefixConfig(app_prefix="marty", plugin_prefix="auth")
        key = config.build_key("user123")
        assert key == "marty:auth:user123"

    def test_build_key_multiple_parts(self):
        """Test building key with multiple parts."""
        config = KeyPrefixConfig(app_prefix="marty", plugin_prefix="auth")
        key = config.build_key("session", "user123", "token")
        assert key == "marty:auth:session:user123:token"

    def test_strip_prefix(self):
        """Test stripping prefix from full key."""
        config = KeyPrefixConfig(app_prefix="marty", plugin_prefix="auth")
        full_key = "marty:auth:user123"
        assert config.strip_prefix(full_key) == "user123"

    def test_strip_prefix_no_match(self):
        """Test stripping prefix when key doesn't match."""
        config = KeyPrefixConfig(app_prefix="marty", plugin_prefix="auth")
        full_key = "other:prefix:user123"
        assert config.strip_prefix(full_key) == "other:prefix:user123"


# =============================================================================
# InMemoryCacheManager Tests
# =============================================================================


class TestInMemoryCacheManager:
    """Tests for InMemoryCacheManager."""

    @pytest.fixture
    def cache(self):
        """Create a fresh cache instance."""
        return InMemoryCacheManager(
            prefix_config=KeyPrefixConfig(app_prefix="test", plugin_prefix="unit"),
            default_ttl=60,
        )

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """Test basic set and get operations."""
        await cache.set("key1", {"data": "value1"})
        result = await cache.get("key1")
        assert result == {"data": "value1"}

    @pytest.mark.asyncio
    async def test_get_missing_key(self, cache):
        """Test getting a non-existent key."""
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """Test delete operation."""
        await cache.set("key1", "value1")
        assert await cache.exists("key1") is True

        deleted = await cache.delete("key1")
        assert deleted is True
        assert await cache.exists("key1") is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache):
        """Test deleting non-existent key."""
        deleted = await cache.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_exists(self, cache):
        """Test exists check."""
        assert await cache.exists("key1") is False
        await cache.set("key1", "value1")
        assert await cache.exists("key1") is True

    @pytest.mark.asyncio
    async def test_get_and_delete(self, cache):
        """Test atomic get and delete (consume pattern)."""
        await cache.set("key1", {"token": "abc123"})

        # First consume should return value
        result = await cache.get_and_delete("key1")
        assert result == {"token": "abc123"}

        # Second consume should return None
        result = await cache.get_and_delete("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_if_not_exists_new_key(self, cache):
        """Test SETNX with new key."""
        result = await cache.set_if_not_exists("key1", "value1")
        assert result is True
        assert await cache.get("key1") == "value1"

    @pytest.mark.asyncio
    async def test_set_if_not_exists_existing_key(self, cache):
        """Test SETNX with existing key."""
        await cache.set("key1", "original")
        result = await cache.set_if_not_exists("key1", "new")
        assert result is False
        assert await cache.get("key1") == "original"

    @pytest.mark.asyncio
    async def test_increment_new_key(self, cache):
        """Test increment on new key."""
        result = await cache.increment("counter")
        assert result == 1

    @pytest.mark.asyncio
    async def test_increment_existing_key(self, cache):
        """Test increment on existing key."""
        await cache.set("counter", 5)
        result = await cache.increment("counter", 3)
        assert result == 8

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache):
        """Test that entries expire after TTL."""
        # Set with very short TTL
        await cache.set("short_lived", "value", ttl=1)

        # Should exist immediately
        assert await cache.get("short_lived") == "value"

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should be expired now
        assert await cache.get("short_lived") is None

    @pytest.mark.asyncio
    async def test_expire_existing_key(self, cache):
        """Test setting expiration on existing key."""
        await cache.set("key1", "value1", ttl=None)

        result = await cache.expire("key1", 10)
        assert result is True

        ttl = await cache.ttl("key1")
        assert 0 < ttl <= 10

    @pytest.mark.asyncio
    async def test_expire_nonexistent_key(self, cache):
        """Test setting expiration on non-existent key."""
        result = await cache.expire("nonexistent", 10)
        assert result is False

    @pytest.mark.asyncio
    async def test_ttl_no_expiration(self, cache):
        """Test TTL for key without expiration."""
        # InMemoryCacheManager uses default_ttl, but we can test the API
        await cache.set("key1", "value1")
        ttl = await cache.ttl("key1")
        assert ttl > 0  # Has TTL from default

    @pytest.mark.asyncio
    async def test_ttl_nonexistent_key(self, cache):
        """Test TTL for non-existent key."""
        ttl = await cache.ttl("nonexistent")
        assert ttl == -2


# =============================================================================
# Cache Metrics Integration Tests
# =============================================================================


class TestCacheMetricsIntegration:
    """Tests for cache metrics collection."""

    @pytest.fixture
    def mock_metrics(self):
        """Create mock metrics collector."""
        return MagicMock()

    @pytest.fixture
    def cache_with_metrics(self, mock_metrics):
        """Create cache with mock metrics."""
        return InMemoryCacheManager(
            prefix_config=KeyPrefixConfig(app_prefix="test"),
            metrics=mock_metrics,
        )

    @pytest.mark.asyncio
    async def test_hit_metric_recorded(self, cache_with_metrics, mock_metrics):
        """Test that cache hit is recorded."""
        await cache_with_metrics.set("key1", "value1")
        await cache_with_metrics.get("key1")

        mock_metrics.record_hit.assert_called_once()

    @pytest.mark.asyncio
    async def test_miss_metric_recorded(self, cache_with_metrics, mock_metrics):
        """Test that cache miss is recorded."""
        await cache_with_metrics.get("nonexistent")

        mock_metrics.record_miss.assert_called_once()

    @pytest.mark.asyncio
    async def test_latency_metric_recorded(self, cache_with_metrics, mock_metrics):
        """Test that operation latency is recorded."""
        await cache_with_metrics.set("key1", "value1")

        mock_metrics.record_latency.assert_called()
        call_args = mock_metrics.record_latency.call_args
        assert call_args[0][1] == "set"  # operation name
        assert call_args[0][2] >= 0  # latency in seconds


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestICacheManagerProtocol:
    """Tests for ICacheManager protocol compliance."""

    def test_in_memory_cache_is_cache_manager(self):
        """Test that InMemoryCacheManager implements ICacheManager."""
        cache = InMemoryCacheManager()
        assert isinstance(cache, ICacheManager)

    def test_protocol_has_required_methods(self):
        """Test that protocol defines all required methods."""
        required_methods = [
            "get",
            "set",
            "delete",
            "exists",
            "get_and_delete",
            "set_if_not_exists",
            "increment",
            "expire",
            "ttl",
        ]

        for method in required_methods:
            assert hasattr(ICacheManager, method)


# =============================================================================
# PluginContextBuilder Tests
# =============================================================================


class TestPluginContextBuilder:
    """Tests for PluginContextBuilder."""

    def test_build_minimal_context(self):
        """Test building context with minimal configuration."""
        from mmf.core.plugins import PluginContextBuilder

        context = PluginContextBuilder("test-plugin").build()

        assert context.plugin_id == "test-plugin"
        assert context.config == {}
        assert context.cache is None

    def test_build_with_cache(self):
        """Test building context with cache manager."""
        from mmf.core.plugins import PluginContextBuilder

        mock_cache = MagicMock()
        context = PluginContextBuilder("test-plugin").with_cache(mock_cache).build()

        assert context.cache is mock_cache

    def test_build_with_all_dependencies(self):
        """Test building context with all dependencies."""
        from mmf.core.plugins import PluginContextBuilder

        mock_cache = MagicMock()
        mock_event_bus = MagicMock()
        mock_security = MagicMock()
        mock_database = MagicMock()

        context = (
            PluginContextBuilder("test-plugin")
            .with_config({"key": "value"})
            .with_cache(mock_cache)
            .with_event_bus(mock_event_bus)
            .with_security(mock_security)
            .with_database(mock_database)
            .build()
        )

        assert context.plugin_id == "test-plugin"
        assert context.config == {"key": "value"}
        assert context.cache is mock_cache
        assert context.event_bus is mock_event_bus
        assert context.security is mock_security
        assert context.database is mock_database

    def test_builder_fluent_interface(self):
        """Test that builder methods return self."""
        from mmf.core.plugins import PluginContextBuilder

        builder = PluginContextBuilder("test-plugin")

        assert builder.with_config({}) is builder
        assert builder.with_cache(None) is builder
        assert builder.with_event_bus(None) is builder
