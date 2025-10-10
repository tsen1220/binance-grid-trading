from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from backend.entities import Order, OrderStatus
from backend.repositories import OrderRepository
from backend.utils import ResourceNotFoundError, ValidationError


class OrderService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = OrderRepository(session)

    def list_orders(self, *, page: int, limit: int, grid_id: Optional[str] = None, status: Optional[str] = None) -> Tuple[list[Order], int]:
        status_enum = None
        if status:
            try:
                status_enum = OrderStatus(status.upper())
            except ValueError as exc:
                raise ValidationError(f"Unsupported order status: {status}") from exc
        orders, total = self.repository.paginate(page=page, limit=limit, grid_id=grid_id, status=status_enum)
        return orders, total

    def cancel_order(self, order_id: str) -> Order:
        order = self.repository.find(order_id)
        if not order:
            raise ResourceNotFoundError(f"Order {order_id} not found")
        order.status = OrderStatus.CANCELLED
        self.session.commit()
        return order
