"""PostgreSQL Truck Repository Adapter.

This is a driven (output) adapter that implements the TruckRepositoryPort
interface using SQLAlchemy and PostgreSQL.
"""

from typing import List, Optional

from sqlalchemy import Boolean, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from examples.petstore_domain.services.delivery_board_service.application.ports.truck_repository import (
    TruckRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Truck,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    TruckId,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


class TruckModel(Base):
    """SQLAlchemy model for the trucks table."""
    __tablename__ = 'trucks'

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    current_load: Mapped[int] = mapped_column(Integer, default=0)
    auto_scaled: Mapped[bool] = mapped_column(Boolean, default=False)

class PostgresTruckRepository(TruckRepositoryPort):
    """PostgreSQL implementation of the truck repository."""

    def __init__(self, connection_string: str) -> None:
        """Initialize the database connection."""
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save(self, truck: Truck) -> None:
        """Persist a truck entity."""
        self._save_or_update(truck)

    def update(self, truck: Truck) -> None:
        """Update an existing truck."""
        self._save_or_update(truck)

    def _save_or_update(self, truck: Truck) -> None:
        session = self.Session()
        try:
            existing = session.query(TruckModel).filter_by(id=str(truck.id)).first()
            if existing:
                existing.name = truck.name
                existing.capacity = truck.capacity
                existing.region = truck.region
                existing.current_load = truck.current_load
                existing.auto_scaled = truck.auto_scaled
            else:
                model = TruckModel(
                    id=str(truck.id),
                    name=truck.name,
                    capacity=truck.capacity,
                    region=truck.region,
                    current_load=truck.current_load,
                    auto_scaled=truck.auto_scaled
                )
                session.add(model)
            session.commit()
        finally:
            session.close()

    def find_by_id(self, truck_id: TruckId) -> Optional[Truck]:
        """Find a truck by its unique identifier."""
        session = self.Session()
        try:
            model = session.query(TruckModel).filter_by(id=str(truck_id)).first()
            if model:
                return self._map_to_entity(model)
            return None
        finally:
            session.close()

    def find_all(self) -> List[Truck]:
        """Retrieve all trucks."""
        session = self.Session()
        try:
            models = session.query(TruckModel).all()
            return [self._map_to_entity(model) for model in models]
        finally:
            session.close()

    def find_available(self) -> List[Truck]:
        """Retrieve all available trucks (with capacity)."""
        session = self.Session()
        try:
            # Available trucks are those where current_load < capacity
            models = session.query(TruckModel).filter(
                TruckModel.current_load < TruckModel.capacity
            ).all()
            return [self._map_to_entity(model) for model in models]
        finally:
            session.close()

    def _map_to_entity(self, model: TruckModel) -> Truck:
        """Map SQLAlchemy model to Domain Entity."""
        truck = Truck(
            id=TruckId(model.id),
            name=model.name,
            capacity=model.capacity,
            region=model.region,
            current_load=model.current_load,
            auto_scaled=model.auto_scaled
        )
        return truck
