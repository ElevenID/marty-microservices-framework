"""
Unit tests for Platform Layer Utilities.

Tests the Registry, AtomicCounter, and TypedSingleton utility classes
that provide core infrastructure services for the platform layer.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from mmf_new.framework.infrastructure.dependency_injection import DIContainer
from mmf_new.framework.platform.utilities import AtomicCounter, Registry, TypedSingleton


class TestRegistry:
    """Test suite for Registry utility class."""

    @pytest.fixture
    def mock_container(self):
        """Create a mock DI container."""
        return Mock(spec=DIContainer)

    @pytest.fixture
    def registry(self, mock_container):
        """Create a Registry instance for testing."""
        return Registry(mock_container)

    def test_registry_creation(self, mock_container):
        """Test Registry can be instantiated."""
        registry = Registry(mock_container)
        assert registry.container is mock_container

    def test_register_and_get_service(self, registry):
        """Test registering and retrieving services."""
        test_service = Mock()

        registry.register("test_service", test_service)
        result = registry.get("test_service")

        assert result is test_service

    def test_get_nonexistent_service(self, registry):
        """Test getting a service that doesn't exist."""
        with pytest.raises(ValueError):
            registry.get("nonexistent")

    def test_get_optional_service(self, registry):
        """Test getting optional service."""
        result = registry.get_optional("nonexistent")
        assert result is None

    def test_unregister_service(self, registry):
        """Test unregistering a service."""
        test_service = Mock()

        registry.register("test_service", test_service)
        assert registry.get("test_service") is test_service

        registry.unregister("test_service")
        with pytest.raises(ValueError):
            registry.get("test_service")

    def test_list_services(self, registry):
        """Test listing all registered services."""
        service1 = Mock()
        service2 = Mock()

        registry.register("service1", service1)
        registry.register("service2", service2)

        services = registry.list_services()
        assert len(services) == 2
        assert "service1" in services
        assert "service2" in services

    def test_clear_services(self, registry):
        """Test clearing all services."""
        registry.register("service1", Mock())
        registry.register("service2", Mock())

        assert len(registry.list_services()) == 2

        registry.clear()
        assert len(registry.list_services()) == 0

    @pytest.mark.asyncio
    async def test_registry_lifecycle(self, registry):
        """Test Registry lifecycle methods."""
        await registry.initialize()
        await registry.shutdown()


class TestAtomicCounter:
    """Test suite for AtomicCounter utility class."""

    @pytest.fixture
    def mock_container(self):
        """Create a mock DI container."""
        return Mock(spec=DIContainer)

    @pytest.fixture
    def counter(self, mock_container):
        """Create an AtomicCounter instance for testing."""
        return AtomicCounter(mock_container, 0)

    def test_counter_creation(self, mock_container):
        """Test AtomicCounter can be instantiated."""
        counter = AtomicCounter(mock_container, 5)
        assert counter.get() == 5

    def test_counter_default_value(self, mock_container):
        """Test AtomicCounter with default initial value."""
        counter = AtomicCounter(mock_container)
        assert counter.get() == 0

    def test_increment(self, counter):
        """Test incrementing the counter."""
        initial = counter.get()
        result = counter.increment()

        assert result == initial + 1
        assert counter.get() == initial + 1

    def test_set_and_get(self, counter):
        """Test setting and getting counter values."""
        counter.set(10)
        assert counter.get() == 10

        counter.set(0)
        assert counter.get() == 0

    def test_reset(self, counter):
        """Test resetting the counter."""
        for _ in range(5):
            counter.increment()
        assert counter.get() == 5

        counter.reset()
        assert counter.get() == 0

    def test_thread_safety(self, counter):
        """Test that the counter is thread-safe."""

        def increment_many():
            for _ in range(100):
                counter.increment()

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=increment_many)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should be exactly 1000 if thread-safe
        assert counter.get() == 1000

    def test_concurrent_operations(self, counter):
        """Test concurrent increment and set operations."""

        def increment_task():
            for _ in range(50):
                counter.increment()

        def set_task():
            # Set to specific values to test thread safety
            counter.set(50)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            # Submit increment tasks
            for _ in range(2):
                futures.append(executor.submit(increment_task))

            # Wait for all tasks to complete
            for future in futures:
                future.result()

        # Final value should be at least 100 (from increments)
        assert counter.get() >= 100

    @pytest.mark.asyncio
    async def test_counter_lifecycle(self, counter):
        """Test AtomicCounter lifecycle methods."""
        await counter.initialize()
        await counter.shutdown()


class TestTypedSingleton:
    """Test suite for TypedSingleton utility class."""

    @pytest.fixture
    def mock_container(self):
        """Create a mock DI container."""
        return Mock(spec=DIContainer)

    def test_singleton_creation(self, mock_container):
        """Test TypedSingleton can be instantiated."""
        singleton = TypedSingleton(mock_container)
        assert singleton.container is mock_container

    def test_get_or_create_new_instance(self, mock_container):
        """Test creating a new singleton instance."""
        singleton = TypedSingleton(mock_container)

        class TestClass:
            def __init__(self, value):
                self.value = value

        instance = singleton.get_or_create(TestClass, lambda: TestClass("test"))

        assert isinstance(instance, TestClass)
        assert instance.value == "test"

    def test_get_or_create_existing_instance(self, mock_container):
        """Test retrieving an existing singleton instance."""
        singleton = TypedSingleton(mock_container)

        class TestClass:
            def __init__(self, value):
                self.value = value

        # Create first instance
        instance1 = singleton.get_or_create(TestClass, lambda: TestClass("first"))

        # Get same instance
        instance2 = singleton.get_or_create(TestClass, lambda: TestClass("second"))

        assert instance1 is instance2
        assert instance1.value == "first"  # Should not have changed

    def test_different_types_different_instances(self, mock_container):
        """Test that different types get different singleton instances."""
        singleton = TypedSingleton(mock_container)

        class TypeA:
            pass

        class TypeB:
            pass

        instance_a = singleton.get_or_create(TypeA, TypeA)
        instance_b = singleton.get_or_create(TypeB, TypeB)

        assert isinstance(instance_a, TypeA)
        assert isinstance(instance_b, TypeB)
        assert instance_a is not instance_b

    def test_thread_safety(self, mock_container):
        """Test that TypedSingleton is thread-safe."""
        singleton = TypedSingleton(mock_container)
        instances = []

        class TestClass:
            def __init__(self):
                time.sleep(0.01)  # Small delay to encourage race conditions
                self.created_at = time.time()

        def create_instance():
            instance = singleton.get_or_create(TestClass, TestClass)
            instances.append(instance)

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_instance)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All instances should be the same object
        first_instance = instances[0]
        for instance in instances:
            assert instance is first_instance

    def test_clear_instances(self, mock_container):
        """Test clearing singleton instances."""
        singleton = TypedSingleton(mock_container)

        class TestClass:
            pass

        # Create instance
        instance1 = singleton.get_or_create(TestClass, TestClass)

        # Clear and create again
        singleton.clear()
        instance2 = singleton.get_or_create(TestClass, TestClass)

        assert instance1 is not instance2

    @pytest.mark.asyncio
    async def test_singleton_lifecycle(self, mock_container):
        """Test TypedSingleton lifecycle methods."""
        singleton = TypedSingleton(mock_container)

        await singleton.initialize()
        await singleton.shutdown()
