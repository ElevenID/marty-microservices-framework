"""PostgreSQL Pet Repository Adapter.

This is a driven (output) adapter that implements the PetRepositoryPort
interface using SQLAlchemy and PostgreSQL.
"""

from typing import List, Optional

from sqlalchemy import Integer, String, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from examples.petstore_domain.services.pet_service.application.ports.pet_repository import (
    PetRepositoryPort,
)
from examples.petstore_domain.services.pet_service.domain.entities import Pet
from examples.petstore_domain.services.pet_service.domain.exceptions import (
    DuplicatePetError,
)
from examples.petstore_domain.services.pet_service.domain.value_objects import (
    PetId,
    Species,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


class PetModel(Base):
    """SQLAlchemy model for the pets table."""
    __tablename__ = 'pets'

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    species: Mapped[str] = mapped_column(String, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

class PostgresPetRepository(PetRepositoryPort):
    """PostgreSQL implementation of the pet repository."""

    def __init__(self, connection_string: str) -> None:
        """Initialize the database connection.

        Args:
            connection_string: The database connection URL
        """
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save(self, pet: Pet) -> None:
        """Persist a pet entity to the database.

        Args:
            pet: The pet entity to save

        Raises:
            DuplicatePetError: If a pet with the same ID already exists
        """
        session = self.Session()
        try:
            pet_model = PetModel(
                id=str(pet.id),
                name=pet.name,
                species=pet.species.value,
                age=pet.age,
                owner_id=pet.owner_id
            )
            session.add(pet_model)
            session.commit()
        except IntegrityError:
            session.rollback()
            raise DuplicatePetError(str(pet.id))
        finally:
            session.close()

    def find_by_id(self, pet_id: PetId) -> Optional[Pet]:
        """Find a pet by its unique identifier.

        Args:
            pet_id: The pet's unique identifier

        Returns:
            The pet if found, None otherwise
        """
        session = self.Session()
        try:
            pet_model = session.query(PetModel).filter_by(id=str(pet_id)).first()
            if pet_model:
                return Pet(
                    id=PetId(pet_model.id),
                    name=pet_model.name,
                    species=Species(pet_model.species),
                    age=pet_model.age,
                    owner_id=pet_model.owner_id
                )
            return None
        finally:
            session.close()

    def find_all(self) -> List[Pet]:
        """Retrieve all pets.

        Returns:
            List of all pet entities
        """
        session = self.Session()
        try:
            pet_models = session.query(PetModel).all()
            return [
                Pet(
                    id=PetId(model.id),
                    name=model.name,
                    species=Species(model.species),
                    age=model.age,
                    owner_id=model.owner_id
                )
                for model in pet_models
            ]
        finally:
            session.close()

    def delete(self, pet_id: PetId) -> bool:
        """Delete a pet by its unique identifier.

        Args:
            pet_id: The pet's unique identifier

        Returns:
            True if the pet was deleted, False if not found
        """
        session = self.Session()
        try:
            result = session.query(PetModel).filter_by(id=str(pet_id)).delete()
            session.commit()
            return result > 0
        finally:
            session.close()

    def exists(self, pet_id: PetId) -> bool:
        """Check if a pet exists.

        Args:
            pet_id: The pet's unique identifier

        Returns:
            True if the pet exists, False otherwise
        """
        session = self.Session()
        try:
            return session.query(PetModel).filter_by(id=str(pet_id)).count() > 0
        finally:
            session.close()
