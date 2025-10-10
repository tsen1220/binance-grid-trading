from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from backend.entities import Order, OrderStatus
from backend.exceptions import ResourceNotFoundError, ValidationError
from backend.repositories import OrderRepository
from backend.services import ConfigService


class OrderService:
    def __init__(self, session: Session, config_service: ConfigService) -> None:
        self.session = session
        self.config_service = config_service
        self.repository = OrderRepository(session)

    def get_orders(self, *, page: int, limit: int, grid_id: Optional[str] = None, status: Optional[str] = None) -> Tuple[list[Order], int]:
        status_enum = None
        if status:
            try:
                status_enum = OrderStatus(status.upper())
            except ValueError as exc:
                raise ValidationError(f"Unsupported order status: {status}") from exc
        orders, total = self.repository.get_orders(page=page, limit=limit, grid_id=grid_id, status=status_enum)
        return orders, total

    def cancel_order(self, order_id: str) -> Order:
        order = self.repository.find(order_id)
        if not order:
            raise ResourceNotFoundError(f"Order {order_id} not found")

        # Check if order is already in a final state
        if order.status in {OrderStatus.FILLED, OrderStatus.CANCELLED}:
            raise ValidationError(f"Cannot cancel order with status {order.status.value}")

        # Cancel order on Binance if it has a Binance order ID
        if order.binance_order_id:
            try:
                client = self.config_service.create_client()
                client.cancel_order(symbol=order.symbol, order_id=int(order.binance_order_id))
            except Exception as e:
                raise ValidationError(f"Failed to cancel order on Binance: {str(e)}")

        # Update order status in database
        order.status = OrderStatus.CANCELLED
        self.session.commit()
        return order
