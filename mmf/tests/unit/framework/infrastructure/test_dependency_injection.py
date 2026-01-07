from unittest.mock import MagicMock, Mock

import pytest

from mmf.framework.infrastructure.dependency_injection import (
    _MISSING,
    DIContainer,
    LambdaFactory,
    RegistrationInfo,
    ServiceFactory,
    ServiceScope,
    SingletonFactory,
)


class TestServiceScope:
    def test_scope_initialization(self):
        scope = ServiceScope("test_scope")
        assert scope.name == "test_scope"
        assert scope.parent is None
        assert scope._services == {}

    def test_scope_with_parent(self):
        parent = ServiceScope("parent")
        child = ServiceScope("child", parent)
        assert child.parent == parent

    def test_set_and_get_service(self):
        scope = ServiceScope("test")
        service_type = str
        instance = "test_instance"

        scope.set_service(service_type, instance)
        assert scope.get_service(service_type) == instance

    def test_get_service_from_parent(self):
        parent = ServiceScope("parent")
        child = ServiceScope("child", parent)
        service_type = str
        instance = "test_instance"

        parent.set_service(service_type, instance)
        assert child.get_service(service_type) == instance

    def test_child_overrides_parent(self):
        parent = ServiceScope("parent")
        child = ServiceScope("child", parent)
        service_type = str
        parent_instance = "parent_instance"
        child_instance = "child_instance"

        parent.set_service(service_type, parent_instance)
        child.set_service(service_type, child_instance)

        assert child.get_service(service_type) == child_instance
        assert parent.get_service(service_type) == parent_instance

    def test_clear_scope(self):
        scope = ServiceScope("test")
        scope.set_service(str, "test")
        scope.clear()
        assert scope.get_service(str) is None


class TestLambdaFactory:
    def test_create(self):
        factory_func = Mock(return_value="created")
        factory = LambdaFactory(str, factory_func)

        result = factory.create({"key": "value"})

        assert result == "created"
        factory_func.assert_called_once_with({"key": "value"})

    def test_get_service_type(self):
        factory = LambdaFactory(str, lambda x: "test")
        assert factory.get_service_type() is str


class TestSingletonFactory:
    def test_create_singleton(self):
        inner_factory = Mock()
        inner_factory.create.side_effect = ["instance1", "instance2"]

        factory = SingletonFactory(str, inner_factory)

        instance1 = factory.create({})
        instance2 = factory.create({})

        assert instance1 == "instance1"
        assert instance2 == "instance1"  # Should be the same instance
        assert inner_factory.create.call_count == 1

    def test_get_service_type(self):
        inner_factory = Mock()
        factory = SingletonFactory(str, inner_factory)
        assert factory.get_service_type() is str


class TestDIContainer:
    @pytest.fixture
    def container(self):
        # Reset singleton before each test
        from mmf.framework.infrastructure.dependency_injection import (
            _ContainerSingleton,
        )

        _ContainerSingleton.reset()
        return DIContainer()

    def test_register_and_get_instance(self, container):
        instance = "test_instance"
        container.register_instance(str, instance)
        assert container.get(str) == instance

    def test_register_and_get_factory(self, container):
        factory = Mock()
        factory.create.return_value = "created"
        container.register_factory(str, factory)

        assert container.get(str) == "created"
        factory.create.assert_called_once()

    def test_get_missing_service_raises_error(self, container):
        with pytest.raises(ValueError, match="No factory or instance registered"):
            container.get(str)

    def test_get_missing_service_returns_default(self, container):
        default = "default"
        assert container.get(str, default=default) == default

    def test_get_or_create(self, container):
        factory_func = Mock(return_value="created")

        # First call creates
        result1 = container.get_or_create(str, factory_func)
        assert result1 == "created"
        factory_func.assert_called_once()

        # Second call returns existing
        result2 = container.get_or_create(str, factory_func)
        assert result2 == "created"
        factory_func.assert_called_once()

    def test_has_service(self, container):
        assert not container.has(str)
        container.register_instance(str, "test")
        assert container.has(str)

    def test_remove_service(self, container):
        container.register_instance(str, "test")
        assert container.remove(str)
        assert not container.has(str)
        assert not container.remove(str)

    def test_configure_service(self, container):
        service = Mock()
        container.register_instance(Mock, service)

        config = {"key": "value"}
        container.configure(Mock, config)

        service.configure.assert_called_once_with(config)

    def test_clear(self, container):
        service = Mock()
        container.register_instance(Mock, service)
        container.clear()

        assert not container.has(Mock)
        service.shutdown.assert_called_once()

    def test_register_service_enhanced(self, container):
        registration = container.register_service(str, instance="test", is_singleton=True)

        assert registration.service_type is str
        assert registration.instance == "test"
        assert container.get_service_typed(str) == "test"

    def test_get_service_optional(self, container):
        assert container.get_service_optional(str) is None
        container.register_instance(str, "test")
        assert container.get_service_optional(str) == "test"

    def test_scope_management(self, container):
        with container.create_scope("test_scope") as scope:
            assert scope.name == "test_scope"
            assert container._current_scope == scope

            # Register in scope (via set_service on scope directly for now as register_service puts in global registry)
            scope.set_service(str, "scoped_value")
            assert container.get_service_typed(str) == "scoped_value"

        # Outside scope
        assert container._current_scope.name == "default"
        # Should fall back to global/default scope or fail
        with pytest.raises(ValueError):
            container.get_service_typed(str)

    @pytest.mark.asyncio
    async def test_lifecycle(self, container):
        service = Mock()
        service.initialize = MagicMock(
            return_value=None
        )  # Async mock needed? initialize is async in initialize_all_services
        # Actually initialize_all_services calls await instance.initialize()
        # So we need an async mock or an object with async initialize method

        class AsyncService:
            def __init__(self):
                self.initialized = False
                self.shutdown_called = False

            async def initialize(self):
                self.initialized = True

            async def shutdown(self):
                self.shutdown_called = True

        service = AsyncService()
        container.register_service(AsyncService, instance=service)

        await container.initialize_all_services()
        assert service.initialized

        await container.shutdown_all_services()
        assert service.shutdown_called

    def test_scope_context_manager(self, container):
        container.register_instance(str, "original")

        with container.scope() as scoped_container:
            scoped_container.register_instance(str, "modified")
            assert scoped_container.get(str) == "modified"

        assert container.get(str) == "original"

    @pytest.mark.asyncio
    async def test_start_stop(self, container):
        # Mock caches
        container._services_cache = Mock()
        container._services_cache.start = MagicMock()  # Async mock
        container._services_cache.stop = MagicMock()

        container._factories_cache = Mock()
        container._factories_cache.start = MagicMock()
        container._factories_cache.stop = MagicMock()

        container._configurations_cache = Mock()
        container._configurations_cache.start = MagicMock()
        container._configurations_cache.stop = MagicMock()

        # Need to make start/stop awaitable
        async def async_mock():
            pass

        container._services_cache.start.side_effect = async_mock
        container._services_cache.stop.side_effect = async_mock
        container._factories_cache.start.side_effect = async_mock
        container._factories_cache.stop.side_effect = async_mock
        container._configurations_cache.start.side_effect = async_mock
        container._configurations_cache.stop.side_effect = async_mock

        await container.start()
        assert container._started

        await container.stop()
        assert not container._started

    def test_clear_scope_method(self, container):
        with container.create_scope("test_scope") as scope:
            scope.set_service(str, "scoped")

        container.clear_scope("test_scope")
        assert "test_scope" not in container._scopes

    def test_convenience_functions(self):
        from mmf.framework.infrastructure.dependency_injection import (
            _ContainerSingleton,
            configure_service,
            get_service,
            get_service_optional,
            get_service_typed,
            has_service,
            injectable,
            register_factory,
            register_instance,
            register_service,
            service_scope,
            with_dependency_injection,
        )

        _ContainerSingleton.reset()

        # register_instance
        register_instance(str, "test")
        assert get_service(str) == "test"
        assert has_service(str)

        # get_service_optional
        assert get_service_optional(int) is None

        # register_factory
        register_factory(int, LambdaFactory(int, lambda x: 123))
        assert get_service(int) == 123

        # configure_service
        service = Mock()
        register_instance(Mock, service)
        configure_service(Mock, {"a": 1})
        service.configure.assert_called_with({"a": 1})

        # register_service
        register_service(float, instance=1.0)
        assert get_service_typed(float) == 1.0

        # service_scope
        with service_scope("test") as scope:
            assert scope.name == "test"

        # injectable
        @injectable()
        class MyService:
            pass

        assert has_service(MyService)
        assert isinstance(get_service(MyService), MyService)

    @pytest.mark.asyncio
    async def test_with_dependency_injection(self):
        from mmf.framework.infrastructure.dependency_injection import (
            _ContainerSingleton,
            with_dependency_injection,
        )

        _ContainerSingleton.reset()

        async with with_dependency_injection() as _container:
            pass
