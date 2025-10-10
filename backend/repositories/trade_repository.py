from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from backend.entities import Trade
from .base import BaseRepository


class TradeRepository(BaseRepository[Trade]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Trade)

    def paginate(self, *, page: int, limit: int, grid_id: Optional[str] = None, symbol: Optional[str] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Tuple[list[Trade], int]:
        offset = (page - 1) * limit
        stmt: Select[Trade] = select(Trade)
        conditions = []
        if grid_id:
            conditions.append(Trade.grid_id == grid_id)
        if symbol:
            conditions.append(Trade.symbol == symbol)
        if start_date:
            stmt = stmt.where(Trade.timestamp >= start_date)
        if end_date:
            stmt = stmt.where(Trade.timestamp <= end_date)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Trade.timestamp.desc()).offset(offset).limit(limit)
        trades = self.session.execute(stmt).scalars().all()

        count_stmt = select(func.count()).select_from(Trade)
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        if start_date:
            count_stmt = count_stmt.where(Trade.timestamp >= start_date)
        if end_date:
            count_stmt = count_stmt.where(Trade.timestamp <= end_date)
        total = int(self.session.execute(count_stmt).scalar_one())
        return trades, total
