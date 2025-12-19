"""PostgreSQL Order Repository Adapter.

This is a driven (output) adapter that implements the OrderRepositoryPort
interface using SQLAlchemy and PostgreSQL.
"""

from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Boolean, Integer, Numeric, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from examples.petstore_domain.services.store_service.application.ports.order_repository import (
    OrderRepositoryPort,
)
from examples.petstore_domain.services.store_service.domain.entities import Order
from examples.petstore_domain.services.store_service.domain.value_objects import (
    Money,
    OrderId,
    OrderStatus,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


class OrderModel(Base):
    """SQLAlchemy model for the orders table."""
    __tablename__ = 'orders'

    id: Mapped[str] = mapped_column(String, primary_key=True)
    pet_id: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    total_price_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_price_currency: Mapped[str] = mapped_column(String, nullable=False)
    delivery_requested: Mapped[bool] = mapped_column(Boolean, default=True)
    delivery_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class PostgresOrderRepository(OrderRepositoryPort):
    """PostgreSQL implementation of the order repository."""

    def __init__(self, connection_string: str) -> None:
        """Initialize the database connection."""
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save(self, order: Order) -> None:
        """Persist an order entity."""
        session = self.Session()
        try:
            existing = session.query(OrderModel).filter_by(id=str(order.id)).first()
            if existing:
                self._update_model_from_order(existing, order)
            else:
                model = OrderModel(
                    id=str(order.id),
                    pet_id=order.pet_id,
                    quantity=order.quantity,
                    customer_name=order.customer_name,
                    status=order.status.value,
                    total_price_amount=order.total_price.amount,
                    total_price_currency=order.total_price.currency,
                    delivery_requested=order.delivery_requested,
                    delivery_address=order.delivery_address,
                )
                session.add(model)
            session.commit()
        finally:
            session.close()

    def find_by_id(self, order_id: OrderId) -> Optional[Order]:
        """Find an order by its unique identifier."""
        session = self.Session()
        try:
            model = session.query(OrderModel).filter_by(id=str(order_id)).first()
            if model:
                return self._map_to_entity(model)
            return None
        finally:
            session.close()

    def find_all(self) -> List[Order]:
        """Retrieve all orders."""
        session = self.Session()
        try:
            models = session.query(OrderModel).all()
            return [self._map_to_entity(model) for model in models]
        finally:
            session.close()

    def update(self, order: Order) -> None:
        """Update an existing order."""
        session = self.Session()
        try:
            existing = session.query(OrderModel).filter_by(id=str(order.id)).first()
            if existing:
                self._update_model_from_order(existing, order)
                session.commit()
        finally:
            session.close()

    def _update_model_from_order(self, model: OrderModel, order: Order) -> None:
        """Update a model from an order entity."""
        model.pet_id = order.pet_id
        model.quantity = order.quantity
        model.customer_name = order.customer_name
        model.status = order.status.value
        model.total_price_amount = order.total_price.amount
        model.total_price_currency = order.total_price.currency
        model.delivery_requested = order.delivery_requested
        model.delivery_address = order.delivery_address

    def _map_to_entity(self, model: OrderModel) -> Order:
        """Map SQLAlchemy model to Domain Entity."""
        return Order(
            id=OrderId(model.id),
            pet_id=model.pet_id,
            quantity=model.quantity,
            customer_name=model.customer_name,
            status=OrderStatus(model.status),
            total_price=Money(model.total_price_amount, model.total_price_currency),
            delivery_requested=model.delivery_requested,
            delivery_address=model.delivery_address,
        )
