"""PostgreSQL Delivery Repository Adapter.

This is a driven (output) adapter that implements the DeliveryRepositoryPort
interface using SQLAlchemy and PostgreSQL.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from examples.petstore_domain.services.delivery_board_service.application.ports.delivery_repository import (
    DeliveryRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Delivery,
    DeliveryItem,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    DeliveryId,
    DeliveryStatus,
    TruckId,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


class DeliveryModel(Base):
    """SQLAlchemy model for the deliveries table."""
    __tablename__ = 'deliveries'

    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    items: Mapped[Any] = mapped_column(JSON, nullable=False)  # List of {description, quantity}
    status: Mapped[str] = mapped_column(String, nullable=False)
    truck_id: Mapped[str] = mapped_column(String, nullable=False)
    eta_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[str] = mapped_column(String, default="standard")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

class PostgresDeliveryRepository(DeliveryRepositoryPort):
    """PostgreSQL implementation of the delivery repository."""

    def __init__(self, connection_string: str) -> None:
        """Initialize the database connection."""
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save(self, delivery: Delivery) -> None:
        """Persist a delivery entity."""
        self._save_or_update(delivery)

    def update(self, delivery: Delivery) -> None:
        """Update an existing delivery."""
        self._save_or_update(delivery)

    def _save_or_update(self, delivery: Delivery) -> None:
        session = self.Session()
        try:
            # Serialize items to JSON-compatible format
            items_data = [{"description": item.description, "quantity": item.quantity} for item in delivery.items]

            existing = session.query(DeliveryModel).filter_by(id=str(delivery.id)).first()
            if existing:
                existing.order_id = delivery.order_id
                existing.address = delivery.address
                existing.items = items_data
                existing.status = delivery.status.value
                existing.truck_id = str(delivery.truck_id)
                existing.eta_minutes = delivery.eta_minutes
                existing.priority = delivery.priority
                existing.created_at = delivery.created_at
                existing.updated_at = delivery.updated_at
            else:
                model = DeliveryModel(
                    id=str(delivery.id),
                    order_id=delivery.order_id,
                    address=delivery.address,
                    items=items_data,
                    status=delivery.status.value,
                    truck_id=str(delivery.truck_id),
                    eta_minutes=delivery.eta_minutes,
                    priority=delivery.priority,
                    created_at=delivery.created_at,
                    updated_at=delivery.updated_at
                )
                session.add(model)
            session.commit()
        finally:
            session.close()

    def find_by_id(self, delivery_id: DeliveryId) -> Optional[Delivery]:
        """Find a delivery by its unique identifier."""
        session = self.Session()
        try:
            model = session.query(DeliveryModel).filter_by(id=str(delivery_id)).first()
            if model:
                return self._map_to_entity(model)
            return None
        finally:
            session.close()

    def find_all(
        self, *, limit: int | None = None, offset: int = 0
    ) -> tuple[list[Delivery], int]:
        """Retrieve all deliveries with optional pagination.

        Args:
            limit: Maximum number of deliveries to return (None for all)
            offset: Number of deliveries to skip

        Returns:
            Tuple of (list of delivery entities, total count)
        """
        session = self.Session()
        try:
            # Get total count
            total_count = session.query(DeliveryModel).count()

            # Apply pagination
            query = session.query(DeliveryModel)
            if offset:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            models = query.all()
            return [self._map_to_entity(model) for model in models], total_count
        finally:
            session.close()

    def _map_to_entity(self, model: DeliveryModel) -> Delivery:
        """Map SQLAlchemy model to Domain Entity."""
        # Deserialize items from JSON
        items = [DeliveryItem(description=item["description"], quantity=item["quantity"]) for item in model.items]

        delivery = Delivery(
            id=DeliveryId(model.id),
            order_id=model.order_id,
            address=model.address,
            items=items,
            status=DeliveryStatus(model.status),
            truck_id=TruckId(model.truck_id),
            eta_minutes=model.eta_minutes,
            priority=model.priority,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
        return delivery
