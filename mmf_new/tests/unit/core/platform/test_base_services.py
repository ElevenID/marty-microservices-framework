"""
Unit tests for Platform Layer Base Services.

Tests the BaseService and ServiceWithDependencies classes that provide
foundation for all platform services with dependency injection integration.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from mmf_new.core.platform.base_services import BaseService, ServiceWithDependencies
from mmf_new.framework.infrastructure.dependency_injection import DIContainer


class ConcreteBaseService(BaseService):
    """Concrete implementation of BaseService for testing."""

    async def _on_initialize(self) -> None:
        pass

    async def _on_shutdown(self) -> None:
        pass


class TestBaseService:
    """Test suite for BaseService class."""

    @pytest.fixture
    def mock_container(self):
        """Create a mock DI container."""
        container = Mock(spec=DIContainer)
        return container

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        return {"test_key": "test_value", "debug": True}

    def test_base_service_creation(self, mock_container, mock_config):
        """Test BaseService can be instantiated with container and config."""
        service = ConcreteBaseService(mock_container, mock_config)

        assert service.container is mock_container
        assert service.config == mock_config

    def test_base_service_default_config(self, mock_container):
        """Test BaseService handles None config gracefully."""
        service = ConcreteBaseService(mock_container, None)

        assert service.container is mock_container
        assert service.config == {}

    @pytest.mark.asyncio
    async def test_base_service_lifecycle_methods(self, mock_container, mock_config):
        """Test BaseService lifecycle methods are callable."""
        service = ConcreteBaseService(mock_container, mock_config)

        # These should not raise exceptions
        await service.initialize()
        await service.shutdown()

    def test_base_service_immutable_after_creation(self, mock_container, mock_config):
        """Test BaseService properties are set during initialization."""
        service = ConcreteBaseService(mock_container, mock_config)

        # Should not be able to reassign
        with pytest.raises(AttributeError):
            service.container = Mock()


class TestServiceWithDependencies:
    """Test suite for ServiceWithDependencies class."""

    @pytest.fixture
    def mock_container(self):
        """Create a mock DI container with dependency resolution."""
        container = Mock(spec=DIContainer)
        container.get = Mock()
        return container

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        return {"dependencies": ["ServiceA", "ServiceB"]}

    def test_service_with_dependencies_creation(self, mock_container, mock_config):
        """Test ServiceWithDependencies instantiation."""
        service = ServiceWithDependencies(mock_container, mock_config)

        assert service.container is mock_container
        assert service.config == mock_config

    def test_get_dependency_success(self, mock_container, mock_config):
        """Test successful dependency resolution."""
        mock_dependency = Mock()
        
        class TestDependency:
            pass
            
        mock_container.get.return_value = mock_dependency

        service = ServiceWithDependencies(mock_container, mock_config)
        service.add_dependency("test_dep", TestDependency)

        # Mock the container.get to return the dependency when called with the type
        mock_container.get.side_effect = lambda type_: mock_dependency if type_ == TestDependency else None

        result = service.get_dependency("test_dep")

        assert result is mock_dependency
        mock_container.get.assert_called_with(TestDependency)

    def test_get_dependency_not_registered(self, mock_container, mock_config):
        """Test error when getting unregistered dependency."""
        service = ServiceWithDependencies(mock_container, mock_config)
        
        with pytest.raises(ValueError, match="Dependency 'unknown' not registered"):
            service.get_dependency("unknown")

    @pytest.mark.asyncio
    async def test_service_with_dependencies_lifecycle(
        self, mock_container, mock_config
    ):
        """Test ServiceWithDependencies inherits lifecycle methods."""
        service = ServiceWithDependencies(mock_container, mock_config)

        # Should inherit lifecycle methods from BaseService
        await service.initialize()
        await service.shutdown()


class ConcreteServiceWithDeps(ServiceWithDependencies):
    """Concrete service for testing inheritance."""

    def __init__(self, container, config=None):
        super().__init__(container, config)
        self.initialize_called = False
        self.dependency_a = None

    async def _on_initialize(self):
        """Initialize with dependency resolution."""
        await super()._on_initialize()
        self.initialize_called = True
        
        # In a real scenario, we would have added the dependency in __init__
        # and retrieved it here.
        try:
            self.dependency_a = self.get_dependency("service_a")
        except ValueError:
            pass
    
    async def _on_shutdown(self):
        await super()._on_shutdown()


class TestServiceInheritance:
    """Test inheritance patterns with base services."""

    @pytest.fixture
    def mock_container(self):
        """Create mock container."""
        container = Mock(spec=DIContainer)
        container.get = Mock(return_value="mock_service_a")
        return container

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        return {"service_name": "test_service"}

    @pytest.mark.asyncio
    async def test_concrete_service_initialization(self, mock_container, mock_config):
        """Test concrete service can properly initialize with dependencies."""
        service = ConcreteServiceWithDeps(mock_container, mock_config)
        
        class ServiceA:
            pass
            
        service.add_dependency("service_a", ServiceA)

        assert not service.initialize_called
        assert service.dependency_a is None

        await service.initialize()

        assert service.initialize_called
        assert service.dependency_a == "mock_service_a"

    def test_concrete_service_inherits_base_functionality(
        self, mock_container, mock_config
    ):
        """Test concrete service inherits base properties."""
        service = ConcreteServiceWithDeps(mock_container, mock_config)
        
        assert service.container is mock_container
        assert service.config == mock_config



