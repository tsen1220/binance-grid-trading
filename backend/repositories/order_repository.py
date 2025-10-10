from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.entities import Order, OrderSide, OrderStatus
from .base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Order)

    def get_pending_orders(self, *, grid_id: Optional[str] = None) -> List[Order]:
        stmt: Select[Order] = select(Order).where(Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]))
        if grid_id:
            stmt = stmt.where(Order.grid_id == grid_id)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def find_by_binance_order_id(self, binance_order_id: str) -> Optional[Order]:
        """Find an order by its Binance order ID.

        Args:
            binance_order_id: The Binance order ID to search for

        Returns:
            The order if found, None otherwise
        """
        stmt: Select[Order] = select(Order).where(Order.binance_order_id == binance_order_id)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def find_active_orders_at_level(
        self, *, grid_id: str, grid_level: int, side: Optional[OrderSide] = None
    ) -> List[Order]:
        """Find active orders (NEW or PARTIALLY_FILLED) at a specific grid level.

        Args:
            grid_id: The grid ID to filter by
            grid_level: The grid level to filter by
            side: Optional order side filter (BUY or SELL)

        Returns:
            List of active orders at the specified grid level
        """
        stmt: Select[Order] = select(Order).where(
            Order.grid_id == grid_id,
            Order.grid_level == grid_level,
            Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]),
        )
        if side:
            stmt = stmt.where(Order.side == side)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def find_filled_buys_without_pair(self, *, grid_id: str) -> List[Order]:
        """Find FILLED BUY orders that don't have a paired SELL order yet.

        This is used by OrderMonitorService to identify which BUY orders need
        a paired SELL order created. A BUY is considered unpaired if there's
        no SELL order with paired_order_id pointing to it.

        Args:
            grid_id: The grid ID to filter by

        Returns:
            List of FILLED BUY orders without paired SELL orders
        """
        # Subquery to find all BUY order IDs that already have paired SELLs
        paired_buy_ids_subquery = (
            select(Order.paired_order_id)
            .where(Order.grid_id == grid_id, Order.side == OrderSide.SELL, Order.paired_order_id.isnot(None))
            .scalar_subquery()
        )

        # Find FILLED BUYs that are NOT in the paired list
        stmt: Select[Order] = select(Order).where(
            Order.grid_id == grid_id,
            Order.side == OrderSide.BUY,
            Order.status == OrderStatus.FILLED,
            Order.id.notin_(paired_buy_ids_subquery),
        )
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def get_orders(
        self,
        *,
        page: int,
        limit: int,
        grid_id: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        side: Optional[OrderSide] = None,
        grid_level: Optional[int] = None,
    ) -> Tuple[List[Order], int]:
        offset = (page - 1) * limit
        stmt: Select[Order] = select(Order)
        if grid_id:
            stmt = stmt.where(Order.grid_id == grid_id)
        if status:
            stmt = stmt.where(Order.status == status)
        if side:
            stmt = stmt.where(Order.side == side)
        if grid_level is not None:
            stmt = stmt.where(Order.grid_level == grid_level)
        stmt = stmt.order_by(Order.created_at.desc()).offset(offset).limit(limit)
        orders = self.session.execute(stmt).scalars().all()

        count_stmt = select(func.count()).select_from(Order)
        if grid_id:
            count_stmt = count_stmt.where(Order.grid_id == grid_id)
        if status:
            count_stmt = count_stmt.where(Order.status == status)
        if side:
            count_stmt = count_stmt.where(Order.side == side)
        if grid_level is not None:
            count_stmt = count_stmt.where(Order.grid_level == grid_level)
        total = int(self.session.execute(count_stmt).scalar_one())
        return orders, total
