"""
Advanced Code Generation Patterns and Customization Engine for Marty Framework

This module provides sophisticated code generation patterns, template customization,
and intelligent code transformation capabilities for enterprise microservices.
"""

import ast
import builtins
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template


class CodePattern(Enum):
    """Supported code generation patterns."""

    REPOSITORY = "repository"
    FACTORY = "factory"
    BUILDER = "builder"
    ADAPTER = "adapter"
    DECORATOR = "decorator"
    OBSERVER = "observer"
    STRATEGY = "strategy"
    COMMAND = "command"
    SINGLETON = "singleton"
    DEPENDENCY_INJECTION = "dependency_injection"
    EVENT_SOURCING = "event_sourcing"
    CQRS = "cqrs"
    SAGA = "saga"
    CIRCUIT_BREAKER = "circuit_breaker"


class ArchitecturalStyle(Enum):
    """Architectural styles for code generation."""

    LAYERED = "layered"
    HEXAGONAL = "hexagonal"
    CLEAN = "clean"
    MICROKERNEL = "microkernel"
    EVENT_DRIVEN = "event_driven"
    PIPE_FILTER = "pipe_filter"
    CQRS_ES = "cqrs_es"


class CodeComplexity(Enum):
    """Code complexity levels."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    ENTERPRISE = "enterprise"


@dataclass
class CodeGenerationSpec:
    """Specification for code generation."""

    pattern: CodePattern
    architectural_style: ArchitecturalStyle
    complexity: CodeComplexity
    domain_objects: builtins.list[str] = field(default_factory=list)
    interfaces: builtins.list[str] = field(default_factory=list)
    dependencies: builtins.list[str] = field(default_factory=list)
    configuration: builtins.dict[str, Any] = field(default_factory=dict)
    custom_attributes: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainModel:
    """Domain model definition."""

    name: str
    attributes: builtins.dict[str, str]
    methods: builtins.list[str] = field(default_factory=list)
    relationships: builtins.dict[str, str] = field(default_factory=dict)
    constraints: builtins.list[str] = field(default_factory=list)
    events: builtins.list[str] = field(default_factory=list)


class CodePatternGenerator(ABC):
    """Base class for code pattern generators."""

    @abstractmethod
    def generate(
        self, spec: CodeGenerationSpec, context: builtins.dict[str, Any]
    ) -> builtins.dict[str, str]:
        """Generate code files for the pattern."""

    @abstractmethod
    def get_dependencies(self) -> builtins.list[str]:
        """Get required dependencies for this pattern."""

    @abstractmethod
    def validate_spec(self, spec: CodeGenerationSpec) -> bool:
        """Validate the generation specification."""


class RepositoryPatternGenerator(CodePatternGenerator):
    """Generates Repository pattern code."""

    def generate(
        self, spec: CodeGenerationSpec, context: builtins.dict[str, Any]
    ) -> builtins.dict[str, str]:
        """Generate Repository pattern files."""
        files = {}

        for domain_object in spec.domain_objects:
            # Generate interface
            interface_code = self._generate_repository_interface(domain_object, spec, context)
            files[f"repositories/{domain_object.lower()}_repository.py"] = interface_code

            # Generate implementation
            impl_code = self._generate_repository_implementation(domain_object, spec, context)
            files[f"repositories/impl/{domain_object.lower()}_repository_impl.py"] = impl_code

            # Generate unit tests
            test_code = self._generate_repository_tests(domain_object, spec, context)
            files[f"tests/repositories/test_{domain_object.lower()}_repository.py"] = test_code

        return files

    def get_dependencies(self) -> builtins.list[str]:
        """Get required dependencies."""
        return ["abc", "typing", "sqlalchemy", "src.framework.database"]

    def validate_spec(self, spec: CodeGenerationSpec) -> bool:
        """Validate specification."""
        return len(spec.domain_objects) > 0

    def _generate_repository_interface(
        self,
        domain_object: str,
        spec: CodeGenerationSpec,
        context: builtins.dict[str, Any],
    ) -> str:
        """Generate repository interface."""
        template = Template(
            '''"""
{{ domain_object }} Repository Interface

This interface defines the contract for {{ domain_object.lower() }} data access operations.
Generated using the Repository pattern.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Union
from uuid import UUID

from app.models.{{ domain_object.lower() }} import {{ domain_object }}


class {{ domain_object }}Repository(ABC):
    """Abstract repository for {{ domain_object }} entities."""

    @abstractmethod
    async def create(self, entity: {{ domain_object }}) -> {{ domain_object }}:
        """Create a new {{ domain_object.lower() }} entity."""
        pass

    @abstractmethod
    async def get_by_id(self, entity_id: Union[str, UUID]) -> Optional[{{ domain_object }}]:
        """Get {{ domain_object.lower() }} by ID."""
        pass

    @abstractmethod
    async def get_all(self, limit: int = 100, offset: int = 0) -> List[{{ domain_object }}]:
        """Get all {{ domain_object.lower() }} entities with pagination."""
        pass

    @abstractmethod
    async def update(self, entity: {{ domain_object }}) -> {{ domain_object }}:
        """Update an existing {{ domain_object.lower() }} entity."""
        pass

    @abstractmethod
    async def delete(self, entity_id: Union[str, UUID]) -> bool:
        """Delete a {{ domain_object.lower() }} entity."""
        pass

    @abstractmethod
    async def exists(self, entity_id: Union[str, UUID]) -> bool:
        """Check if {{ domain_object.lower() }} exists."""
        pass

    {% for method in custom_methods %}
    @abstractmethod
    async def {{ method }}(self, **kwargs) -> Union[{{ domain_object }}, List[{{ domain_object }}], bool]:
        """{{ method.replace('_', ' ').title() }} operation."""
        pass

    {% endfor %}
'''
        )

        return template.render(
            domain_object=domain_object,
            custom_methods=spec.configuration.get("custom_methods", []),
        )

    def _generate_repository_implementation(
        self,
        domain_object: str,
        spec: CodeGenerationSpec,
        context: builtins.dict[str, Any],
    ) -> str:
        """Generate repository implementation."""
        template = Template(
            '''"""
{{ domain_object }} Repository Implementation

Concrete implementation of {{ domain_object }}Repository using SQLAlchemy.
Generated using the Repository pattern with {{ architectural_style.value }} architecture.
"""

from typing import List, Optional, Union
from uuid import UUID
import logging

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.{{ domain_object.lower() }} import {{ domain_object }}
from app.repositories.{{ domain_object.lower() }}_repository import {{ domain_object }}Repository
from marty_msf.framework.database import DatabaseManager


logger = logging.getLogger(__name__)


class {{ domain_object }}RepositoryImpl({{ domain_object }}Repository):
    """SQLAlchemy implementation of {{ domain_object }}Repository."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize repository with database manager."""
        self.db_manager = db_manager

    async def create(self, entity: {{ domain_object }}) -> {{ domain_object }}:
        """Create a new {{ domain_object.lower() }} entity."""
        async with self.db_manager.get_session() as session:
            try:
                session.add(entity)
                await session.commit()
                await session.refresh(entity)
                logger.info(f"Created {{ domain_object.lower() }} with ID: {entity.id}")
                return entity
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create {{ domain_object.lower() }}: {e}")
                raise

    async def get_by_id(self, entity_id: Union[str, UUID]) -> Optional[{{ domain_object }}]:
        """Get {{ domain_object.lower() }} by ID."""
        async with self.db_manager.get_session() as session:
            try:
                stmt = select({{ domain_object }}).where({{ domain_object }}.id == entity_id)
                result = await session.execute(stmt)
                entity = result.scalar_one_or_none()

                if entity:
                    logger.debug(f"Found {{ domain_object.lower() }} with ID: {entity_id}")
                else:
                    logger.debug(f"No {{ domain_object.lower() }} found with ID: {entity_id}")

                return entity
            except Exception as e:
                logger.error(f"Failed to get {{ domain_object.lower() }} by ID {entity_id}: {e}")
                raise

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[{{ domain_object }}]:
        """Get all {{ domain_object.lower() }} entities with pagination."""
        async with self.db_manager.get_session() as session:
            try:
                stmt = select({{ domain_object }}).limit(limit).offset(offset)
                result = await session.execute(stmt)
                entities = result.scalars().all()

                logger.debug(f"Retrieved {len(entities)} {{ domain_object.lower() }} entities")
                return list(entities)
            except Exception as e:
                logger.error(f"Failed to get all {{ domain_object.lower() }} entities: {e}")
                raise

    async def update(self, entity: {{ domain_object }}) -> {{ domain_object }}:
        """Update an existing {{ domain_object.lower() }} entity."""
        async with self.db_manager.get_session() as session:
            try:
                await session.merge(entity)
                await session.commit()
                await session.refresh(entity)
                logger.info(f"Updated {{ domain_object.lower() }} with ID: {entity.id}")
                return entity
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update {{ domain_object.lower() }}: {e}")
                raise

    async def delete(self, entity_id: Union[str, UUID]) -> bool:
        """Delete a {{ domain_object.lower() }} entity."""
        async with self.db_manager.get_session() as session:
            try:
                stmt = delete({{ domain_object }}).where({{ domain_object }}.id == entity_id)
                result = await session.execute(stmt)
                await session.commit()

                deleted = result.rowcount > 0
                if deleted:
                    logger.info(f"Deleted {{ domain_object.lower() }} with ID: {entity_id}")
                else:
                    logger.warning(f"No {{ domain_object.lower() }} found to delete with ID: {entity_id}")

                return deleted
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to delete {{ domain_object.lower() }} with ID {entity_id}: {e}")
                raise

    async def exists(self, entity_id: Union[str, UUID]) -> bool:
        """Check if {{ domain_object.lower() }} exists."""
        entity = await self.get_by_id(entity_id)
        return entity is not None

    {% for method in custom_methods %}
    async def {{ method }}(self, **kwargs) -> Union[{{ domain_object }}, List[{{ domain_object }}], bool]:
        """{{ method.replace('_', ' ').title() }} operation.

        Args:
            **kwargs: Method-specific arguments

        Returns:
            Result depends on the operation:
            - Single {{ domain_object }} for get operations
            - List[{{ domain_object }}] for search/list operations
            - bool for validation/check operations

        Raises:
            ValueError: For invalid parameters
            DatabaseError: For database operation failures
        """
        async with self.db_manager.get_session() as session:
            try:
                # Custom method implementation for {{ method }}
                # Common patterns:

                if "{{ method }}".startswith("find_by_"):
                    # Search operations
                    filter_field = "{{ method }}".replace("find_by_", "")
                    filter_value = kwargs.get(filter_field)
                    if not filter_value:
                        raise ValueError(f"Missing required parameter: {filter_field}")

                    query = select({{ domain_object }}).where(
                        getattr({{ domain_object }}, filter_field) == filter_value
                    )
                    result = await session.execute(query)
                    return result.scalars().all()

                elif "{{ method }}".startswith("count_"):
                    # Count operations
                    query = select(func.count({{ domain_object }}.id))
                    # Add your filter conditions here based on kwargs
                    result = await session.execute(query)
                    return result.scalar()

                elif "{{ method }}".startswith("update_"):
                    # Update operations
                    entity_id = kwargs.get("id")
                    if not entity_id:
                        raise ValueError("Missing required parameter: id")

                    entity = await self.get_by_id(entity_id)
                    if not entity:
                        raise ValueError(f"{{ domain_object }} not found with id: {entity_id}")

                    # Update fields based on kwargs
                    for key, value in kwargs.items():
                        if key != "id" and hasattr(entity, key):
                            setattr(entity, key, value)

                    await session.commit()
                    await session.refresh(entity)
                    return entity

                elif "{{ method }}".startswith("validate_"):
                    # Validation operations
                    # Implement your validation logic here
                    return True

                else:
                    # Generic implementation - customize based on your needs
                    logger.warning("Generic implementation for custom method {{ method }}")
                    # Add your specific business logic here
                    return None

            except Exception as e:
                logger.error("Failed to execute {{ method }}: %s", e)
                raise

    {% endfor %}
'''
        )

        return template.render(
            domain_object=domain_object,
            architectural_style=spec.architectural_style,
            custom_methods=spec.configuration.get("custom_methods", []),
        )

    def _generate_repository_tests(
        self,
        domain_object: str,
        spec: CodeGenerationSpec,
        context: builtins.dict[str, Any],
    ) -> str:
        """Generate repository unit tests."""
        template = Template(
            '''"""
Unit tests for {{ domain_object }}Repository implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

from app.models.{{ domain_object.lower() }} import {{ domain_object }}
from app.repositories.impl.{{ domain_object.lower() }}_repository_impl import {{ domain_object }}RepositoryImpl


@pytest.fixture
def mock_db_manager():
    """Mock database manager."""
    return Mock()


@pytest.fixture
def repository(mock_db_manager):
    """Create repository instance for testing."""
    return {{ domain_object }}RepositoryImpl(mock_db_manager)


@pytest.fixture
def sample_{{ domain_object.lower() }}():
    """Create sample {{ domain_object.lower() }} for testing."""
    return {{ domain_object }}(
        id=uuid4(),
        # Add sample attributes here
    )


@pytest.mark.asyncio
class Test{{ domain_object }}Repository:
    """Test cases for {{ domain_object }}Repository."""

    async def test_create(self, repository, sample_{{ domain_object.lower() }}, mock_db_manager):
        """Test entity creation."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_db_manager.get_session.return_value.__aenter__.return_value = mock_session

        # Execute
        result = await repository.create(sample_{{ domain_object.lower() }})

        # Verify
        assert result == sample_{{ domain_object.lower() }}
        mock_session.add.assert_called_once_with(sample_{{ domain_object.lower() }})
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(sample_{{ domain_object.lower() }})

    async def test_get_by_id(self, repository, sample_{{ domain_object.lower() }}, mock_db_manager):
        """Test getting entity by ID."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_{{ domain_object.lower() }}
        mock_session.execute.return_value = mock_result
        mock_db_manager.get_session.return_value.__aenter__.return_value = mock_session

        # Execute
        result = await repository.get_by_id(sample_{{ domain_object.lower() }}.id)

        # Verify
        assert result == sample_{{ domain_object.lower() }}
        mock_session.execute.assert_called_once()

    async def test_get_all(self, repository, mock_db_manager):
        """Test getting all entities."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_db_manager.get_session.return_value.__aenter__.return_value = mock_session

        # Execute
        result = await repository.get_all()

        # Verify
        assert isinstance(result, list)
        mock_session.execute.assert_called_once()

    async def test_update(self, repository, sample_{{ domain_object.lower() }}, mock_db_manager):
        """Test entity update."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_db_manager.get_session.return_value.__aenter__.return_value = mock_session

        # Execute
        result = await repository.update(sample_{{ domain_object.lower() }})

        # Verify
        assert result == sample_{{ domain_object.lower() }}
        mock_session.merge.assert_called_once_with(sample_{{ domain_object.lower() }})
        mock_session.commit.assert_called_once()

    async def test_delete(self, repository, sample_{{ domain_object.lower() }}, mock_db_manager):
        """Test entity deletion."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result
        mock_db_manager.get_session.return_value.__aenter__.return_value = mock_session

        # Execute
        result = await repository.delete(sample_{{ domain_object.lower() }}.id)

        # Verify
        assert result is True
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    async def test_exists(self, repository, sample_{{ domain_object.lower() }}, mock_db_manager):
        """Test entity existence check."""
        # Mock get_by_id to return entity
        repository.get_by_id = AsyncMock(return_value=sample_{{ domain_object.lower() }})

        # Execute
        result = await repository.exists(sample_{{ domain_object.lower() }}.id)

        # Verify
        assert result is True
        repository.get_by_id.assert_called_once_with(sample_{{ domain_object.lower() }}.id)
'''
        )

        return template.render(domain_object=domain_object)


class FactoryPatternGenerator(CodePatternGenerator):
    """Generates Factory pattern code."""

    def generate(
        self, spec: CodeGenerationSpec, context: builtins.dict[str, Any]
    ) -> builtins.dict[str, str]:
        """Generate Factory pattern files."""
        files = {}

        # Generate abstract factory
        factory_code = self._generate_abstract_factory(spec, context)
        files["factories/abstract_factory.py"] = factory_code

        # Generate concrete factories
        for factory_type in spec.configuration.get("factory_types", ["default"]):
            concrete_factory = self._generate_concrete_factory(factory_type, spec, context)
            files[f"factories/{factory_type}_factory.py"] = concrete_factory

        return files

    def get_dependencies(self) -> builtins.list[str]:
        """Get required dependencies."""
        return ["abc", "typing"]

    def validate_spec(self, spec: CodeGenerationSpec) -> bool:
        """Validate specification."""
        return "factory_types" in spec.configuration

    def _generate_abstract_factory(
        self, spec: CodeGenerationSpec, context: builtins.dict[str, Any]
    ) -> str:
        """Generate abstract factory interface."""
        template = Template(
            '''"""
Abstract Factory Pattern Implementation

This module defines the abstract factory interface for creating related objects.
Generated using the Factory pattern with {{ architectural_style.value }} architecture.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic

{% for domain_object in domain_objects %}
from app.models.{{ domain_object.lower() }} import {{ domain_object }}
{% endfor %}

T = TypeVar('T')


class AbstractFactory(ABC, Generic[T]):
    """Abstract factory for creating domain objects."""

    {% for domain_object in domain_objects %}
    @abstractmethod
    def create_{{ domain_object.lower() }}(self, **kwargs) -> {{ domain_object }}:
        """Create a {{ domain_object }} instance."""
        pass

    {% endfor %}

    @abstractmethod
    def get_factory_type(self) -> str:
        """Get the factory type identifier."""
        pass
'''
        )

        return template.render(
            domain_objects=spec.domain_objects,
            architectural_style=spec.architectural_style,
        )

    def _generate_concrete_factory(
        self,
        factory_type: str,
        spec: CodeGenerationSpec,
        context: builtins.dict[str, Any],
    ) -> str:
        """Generate concrete factory implementation."""
        template = Template(
            '''"""
{{ factory_type.title() }} Factory Implementation

Concrete factory for creating {{ factory_type }} variants of domain objects.
"""

import logging
from typing import Any

{% for domain_object in domain_objects %}
from app.models.{{ domain_object.lower() }} import {{ domain_object }}
{% endfor %}
from app.factories.abstract_factory import AbstractFactory


logger = logging.getLogger(__name__)


class {{ factory_type.title() }}Factory(AbstractFactory):
    """{{ factory_type.title() }} implementation of the abstract factory."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize factory with configuration."""
        self.config = config or {}
        logger.info(f"Initialized {{ factory_type }} factory")

    {% for domain_object in domain_objects %}
    def create_{{ domain_object.lower() }}(self, **kwargs) -> {{ domain_object }}:
        """Create a {{ domain_object }} instance with {{ factory_type }} configuration."""
        logger.debug(f"Creating {{ domain_object.lower() }} with {{ factory_type }} factory")

        # Apply factory-specific defaults
        factory_defaults = self.config.get('{{ domain_object.lower() }}_defaults', {})
        final_kwargs = {**factory_defaults, **kwargs}

        # Create and configure the object
        instance = {{ domain_object }}(**final_kwargs)

        # Apply factory-specific post-processing
        self._configure_{{ domain_object.lower() }}(instance)

        return instance

    def _configure_{{ domain_object.lower() }}(self, instance: {{ domain_object }}) -> None:
        """Apply {{ factory_type }}-specific configuration to {{ domain_object }}."""
        # Add factory-specific configuration logic here
        pass

    {% endfor %}

    def get_factory_type(self) -> str:
        """Get the factory type identifier."""
        return "{{ factory_type }}"
'''
        )

        return template.render(factory_type=factory_type, domain_objects=spec.domain_objects)


class BuilderPatternGenerator(CodePatternGenerator):
    """Generates Builder pattern code."""

    def generate(
        self, spec: CodeGenerationSpec, context: builtins.dict[str, Any]
    ) -> builtins.dict[str, str]:
        """Generate Builder pattern files."""
        files = {}

        for domain_object in spec.domain_objects:
            builder_code = self._generate_builder(domain_object, spec, context)
            files[f"builders/{domain_object.lower()}_builder.py"] = builder_code

        return files

    def get_dependencies(self) -> builtins.list[str]:
        """Get required dependencies."""
        return ["typing"]

    def validate_spec(self, spec: CodeGenerationSpec) -> bool:
        """Validate specification."""
        return len(spec.domain_objects) > 0

    def _generate_builder(
        self,
        domain_object: str,
        spec: CodeGenerationSpec,
        context: builtins.dict[str, Any],
    ) -> str:
        """Generate builder class."""
        template = Template(
            '''"""
{{ domain_object }} Builder Pattern Implementation

Provides a fluent interface for constructing {{ domain_object }} instances.
Generated using the Builder pattern with {{ architectural_style.value }} architecture.
"""

from typing import Optional, Any
import logging

from app.models.{{ domain_object.lower() }} import {{ domain_object }}


logger = logging.getLogger(__name__)


class {{ domain_object }}Builder:
    """Builder for creating {{ domain_object }} instances with fluent interface."""

    def __init__(self):
        """Initialize the builder."""
        self._data = {}
        logger.debug("Initialized {{ domain_object }}Builder")

    {% for attribute, attr_type in attributes.items() %}
    def with_{{ attribute }}(self, {{ attribute }}: {{ attr_type }}) -> '{{ domain_object }}Builder':
        """Set {{ attribute }} value."""
        self._data['{{ attribute }}'] = {{ attribute }}
        return self

    {% endfor %}

    def with_defaults(self) -> '{{ domain_object }}Builder':
        """Apply default values for all attributes."""
        defaults = {
            {% for attribute, attr_type in attributes.items() %}
            '{{ attribute }}': self._get_default_{{ attribute }}(),
            {% endfor %}
        }
        self._data.update(defaults)
        return self

    def with_config(self, config: dict[str, Any]) -> '{{ domain_object }}Builder':
        """Apply configuration dictionary."""
        self._data.update(config)
        return self

    def build(self) -> {{ domain_object }}:
        """Build the {{ domain_object }} instance."""
        self._validate()

        instance = {{ domain_object }}(**self._data)
        logger.info(f"Built {{ domain_object }} instance with ID: {getattr(instance, 'id', 'N/A')}")

        return instance

    def reset(self) -> '{{ domain_object }}Builder':
        """Reset the builder to initial state."""
        self._data.clear()
        return self

    def _validate(self) -> None:
        """Validate the builder state before building."""
        required_fields = {{ required_fields }}

        for field in required_fields:
            if field not in self._data:
                raise ValueError(f"Required field '{field}' is missing")

    {% for attribute, attr_type in attributes.items() %}
    def _get_default_{{ attribute }}(self) -> {{ attr_type }}:
        """Get default value for {{ attribute }}."""
        # Return appropriate default based on type
        {% if 'str' in attr_type %}
        return ""
        {% elif 'int' in attr_type %}
        return 0
        {% elif 'float' in attr_type %}
        return 0.0
        {% elif 'bool' in attr_type %}
        return False
        {% elif 'list' in attr_type %}
        return []
        {% elif 'dict' in attr_type %}
        return {}
        {% else %}
        return None
        {% endif %}

    {% endfor %}


def create_{{ domain_object.lower() }}() -> {{ domain_object }}Builder:
    """Convenience function to create a new {{ domain_object }}Builder."""
    return {{ domain_object }}Builder()
'''
        )

        # Extract attributes from context or use defaults
        attributes = (
            context.get("domain_models", {})
            .get(domain_object, {})
            .get(
                "attributes",
                {
                    "id": "str",
                    "name": "str",
                    "created_at": "datetime",
                    "updated_at": "datetime",
                },
            )
        )

        required_fields = (
            context.get("domain_models", {})
            .get(domain_object, {})
            .get("required_fields", ["id", "name"])
        )

        return template.render(
            domain_object=domain_object,
            architectural_style=spec.architectural_style,
            attributes=attributes,
            required_fields=required_fields,
        )


class AdvancedCodeGenerator:
    """Main code generation engine with pattern support."""

    def __init__(self, framework_root: Path):
        """Initialize the code generator."""
        self.framework_root = framework_root
        self.pattern_generators = {
            CodePattern.REPOSITORY: RepositoryPatternGenerator(),
            CodePattern.FACTORY: FactoryPatternGenerator(),
            CodePattern.BUILDER: BuilderPatternGenerator(),
        }

        # Template environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(framework_root / "templates")),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )

    def generate_pattern(
        self,
        spec: CodeGenerationSpec,
        output_dir: Path,
        context: builtins.dict[str, Any] = None,
    ) -> builtins.list[Path]:
        """Generate code for a specific pattern."""
        if spec.pattern not in self.pattern_generators:
            raise ValueError(f"Unsupported pattern: {spec.pattern}")

        generator = self.pattern_generators[spec.pattern]

        # Validate specification
        if not generator.validate_spec(spec):
            raise ValueError(f"Invalid specification for pattern: {spec.pattern}")

        # Generate code
        context = context or {}
        generated_files = generator.generate(spec, context)

        # Write files to disk
        created_files = []
        for file_path, content in generated_files.items():
            full_path = output_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            created_files.append(full_path)

        return created_files

    def analyze_domain_model(self, model_file: Path) -> DomainModel:
        """Analyze a domain model file and extract metadata."""
        with open(model_file, encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        # Find class definition
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                return self._extract_domain_model(node, source)

        raise ValueError(f"No class definition found in {model_file}")

    def _extract_domain_model(self, class_node: ast.ClassDef, source: str) -> DomainModel:
        """Extract domain model information from AST."""
        model_name = class_node.name
        attributes = {}
        methods = []
        relationships = {}

        # Extract attributes and methods
        for node in class_node.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                # Type-annotated attribute
                attr_name = node.target.id
                attr_type = ast.unparse(node.annotation) if node.annotation else "Any"
                attributes[attr_name] = attr_type

                # Check for relationships (simple heuristic)
                if "relationship" in attr_type.lower() or "foreignkey" in attr_type.lower():
                    relationships[attr_name] = attr_type

            elif isinstance(node, ast.FunctionDef):
                # Method
                if not node.name.startswith("_"):  # Skip private methods
                    methods.append(node.name)

        return DomainModel(
            name=model_name,
            attributes=attributes,
            methods=methods,
            relationships=relationships,
        )

    def generate_architectural_scaffold(
        self, style: ArchitecturalStyle, service_name: str, output_dir: Path
    ) -> builtins.list[Path]:
        """Generate architectural scaffold based on style."""
        created_files = []

        if style == ArchitecturalStyle.LAYERED:
            created_files.extend(self._generate_layered_architecture(service_name, output_dir))
        elif style == ArchitecturalStyle.HEXAGONAL:
            created_files.extend(self._generate_hexagonal_architecture(service_name, output_dir))
        elif style == ArchitecturalStyle.CLEAN:
            created_files.extend(self._generate_clean_architecture(service_name, output_dir))
        elif style == ArchitecturalStyle.CQRS_ES:
            created_files.extend(self._generate_cqrs_es_architecture(service_name, output_dir))

        return created_files

    def _generate_layered_architecture(
        self, service_name: str, output_dir: Path
    ) -> builtins.list[Path]:
        """Generate layered architecture structure."""
        directories = [
            "app/presentation",
            "app/application",
            "app/domain",
            "app/infrastructure",
            "app/shared",
        ]

        created_files = []

        for directory in directories:
            dir_path = output_dir / directory
            dir_path.mkdir(parents=True, exist_ok=True)

            # Create __init__.py
            init_file = dir_path / "__init__.py"
            init_file.write_text('"""Package initialization."""\n', encoding="utf-8")
            created_files.append(init_file)

        return created_files

    def _generate_hexagonal_architecture(
        self, service_name: str, output_dir: Path
    ) -> builtins.list[Path]:
        """Generate hexagonal architecture structure."""
        directories = [
            "app/domain/model",
            "app/domain/service",
            "app/application/port/in",
            "app/application/port/out",
            "app/application/service",
            "app/adapter/in/web",
            "app/adapter/in/grpc",
            "app/adapter/out/persistence",
            "app/adapter/out/messaging",
        ]

        created_files = []

        for directory in directories:
            dir_path = output_dir / directory
            dir_path.mkdir(parents=True, exist_ok=True)

            # Create __init__.py
            init_file = dir_path / "__init__.py"
            init_file.write_text('"""Package initialization."""\n', encoding="utf-8")
            created_files.append(init_file)

        return created_files

    def _generate_clean_architecture(
        self, service_name: str, output_dir: Path
    ) -> builtins.list[Path]:
        """Generate clean architecture structure."""
        directories = [
            "app/entities",
            "app/use_cases",
            "app/interface_adapters/controllers",
            "app/interface_adapters/gateways",
            "app/interface_adapters/presenters",
            "app/frameworks_drivers/web",
            "app/frameworks_drivers/database",
            "app/frameworks_drivers/external",
        ]

        created_files = []

        for directory in directories:
            dir_path = output_dir / directory
            dir_path.mkdir(parents=True, exist_ok=True)

            # Create __init__.py
            init_file = dir_path / "__init__.py"
            init_file.write_text('"""Package initialization."""\n', encoding="utf-8")
            created_files.append(init_file)

        return created_files

    def _generate_cqrs_es_architecture(
        self, service_name: str, output_dir: Path
    ) -> builtins.list[Path]:
        """Generate CQRS/Event Sourcing architecture structure."""
        directories = [
            "app/commands",
            "app/queries",
            "app/events",
            "app/aggregates",
            "app/projections",
            "app/handlers/command",
            "app/handlers/event",
            "app/handlers/query",
            "app/read_models",
            "app/event_store",
        ]

        created_files = []

        for directory in directories:
            dir_path = output_dir / directory
            dir_path.mkdir(parents=True, exist_ok=True)

            # Create __init__.py
            init_file = dir_path / "__init__.py"
            init_file.write_text('"""Package initialization."""\n', encoding="utf-8")
            created_files.append(init_file)

        return created_files

    def customize_template(
        self, template_path: Path, customizations: builtins.dict[str, Any]
    ) -> str:
        """Apply customizations to a template."""
        with open(template_path, encoding="utf-8") as f:
            template_content = f.read()

        # Apply string replacements
        for placeholder, replacement in customizations.get("replacements", {}).items():
            template_content = template_content.replace(placeholder, replacement)

        # Apply regex replacements
        for pattern, replacement in customizations.get("regex_replacements", {}).items():
            template_content = re.sub(pattern, replacement, template_content)

        # Apply Jinja2 rendering with variables
        if customizations.get("jinja_variables"):
            template = Template(template_content)
            template_content = template.render(**customizations["jinja_variables"])

        return template_content


def create_pattern_specification(
    pattern: CodePattern, domain_objects: builtins.list[str], **kwargs
) -> CodeGenerationSpec:
    """Convenience function to create a pattern specification."""
    return CodeGenerationSpec(
        pattern=pattern,
        architectural_style=kwargs.get("architectural_style", ArchitecturalStyle.LAYERED),
        complexity=kwargs.get("complexity", CodeComplexity.MODERATE),
        domain_objects=domain_objects,
        interfaces=kwargs.get("interfaces", []),
        dependencies=kwargs.get("dependencies", []),
        configuration=kwargs.get("configuration", {}),
        custom_attributes=kwargs.get("custom_attributes", {}),
    )
