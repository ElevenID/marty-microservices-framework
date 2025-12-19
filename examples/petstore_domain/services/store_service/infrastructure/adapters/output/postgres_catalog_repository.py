"""PostgreSQL Catalog Repository Adapter.

This is a driven (output) adapter that implements the CatalogRepositoryPort
interface using SQLAlchemy and PostgreSQL.
"""

from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Integer, Numeric, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from examples.petstore_domain.services.store_service.application.ports.catalog_repository import (
    CatalogRepositoryPort,
)
from examples.petstore_domain.services.store_service.domain.entities import CatalogItem
from examples.petstore_domain.services.store_service.domain.value_objects import Money


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


class CatalogItemModel(Base):
    """SQLAlchemy model for the catalog table."""
    __tablename__ = 'catalog'

    pet_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    species: Mapped[str] = mapped_column(String, nullable=False)
    price_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price_currency: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_lead_days: Mapped[int] = mapped_column(Integer, default=1)


class PostgresCatalogRepository(CatalogRepositoryPort):
    """PostgreSQL implementation of the catalog repository."""

    def __init__(self, connection_string: str) -> None:
        """Initialize the database connection."""
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def find_by_pet_id(self, pet_id: str) -> Optional[CatalogItem]:
        """Find a catalog item by pet ID."""
        session = self.Session()
        try:
            model = session.query(CatalogItemModel).filter_by(pet_id=pet_id).first()
            if model:
                return self._map_to_entity(model)
            return None
        finally:
            session.close()

    def find_all(self) -> List[CatalogItem]:
        """Retrieve all catalog items."""
        session = self.Session()
        try:
            models = session.query(CatalogItemModel).all()
            return [self._map_to_entity(model) for model in models]
        finally:
            session.close()

    def save(self, item: CatalogItem) -> None:
        """Persist a catalog item."""
        session = self.Session()
        try:
            existing = session.query(CatalogItemModel).filter_by(pet_id=item.pet_id).first()
            if existing:
                existing.name = item.name
                existing.species = item.species
                existing.price_amount = item.price.amount
                existing.price_currency = item.price.currency
                existing.quantity = item.quantity
                existing.delivery_lead_days = item.delivery_lead_days
            else:
                model = CatalogItemModel(
                    pet_id=item.pet_id,
                    name=item.name,
                    species=item.species,
                    price_amount=item.price.amount,
                    price_currency=item.price.currency,
                    quantity=item.quantity,
                    delivery_lead_days=item.delivery_lead_days,
                )
                session.add(model)
            session.commit()
        finally:
            session.close()

    def update(self, item: CatalogItem) -> None:
        """Update an existing catalog item."""
        session = self.Session()
        try:
            existing = session.query(CatalogItemModel).filter_by(pet_id=item.pet_id).first()
            if existing:
                existing.name = item.name
                existing.species = item.species
                existing.price_amount = item.price.amount
                existing.price_currency = item.price.currency
                existing.quantity = item.quantity
                existing.delivery_lead_days = item.delivery_lead_days
                session.commit()
        finally:
            session.close()

    def _map_to_entity(self, model: CatalogItemModel) -> CatalogItem:
        """Map SQLAlchemy model to Domain Entity."""
        return CatalogItem(
            pet_id=model.pet_id,
            name=model.name,
            species=model.species,
            price=Money(model.price_amount, model.price_currency),
            quantity=model.quantity,
            delivery_lead_days=model.delivery_lead_days,
        )
