from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.entities import Order, OrderStatus
from .base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Order)

    def find_pending_orders(self, *, grid_id: Optional[str] = None) -> List[Order]:
        stmt: Select[Order] = select(Order).where(Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]))
        if grid_id:
            stmt = stmt.where(Order.grid_id == grid_id)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def paginate(self, *, page: int, limit: int, grid_id: Optional[str] = None, status: Optional[OrderStatus] = None) -> Tuple[List[Order], int]:
        offset = (page - 1) * limit
        stmt: Select[Order] = select(Order)
        if grid_id:
            stmt = stmt.where(Order.grid_id == grid_id)
        if status:
            stmt = stmt.where(Order.status == status)
        stmt = stmt.order_by(Order.created_at.desc()).offset(offset).limit(limit)
        orders = self.session.execute(stmt).scalars().all()

        count_stmt = select(func.count()).select_from(Order)
        if grid_id:
            count_stmt = count_stmt.where(Order.grid_id == grid_id)
        if status:
            count_stmt = count_stmt.where(Order.status == status)
        total = int(self.session.execute(count_stmt).scalar_one())
        return orders, total
