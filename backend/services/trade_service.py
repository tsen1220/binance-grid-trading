from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from backend.entities import Trade
from backend.repositories import TradeRepository


class TradeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = TradeRepository(session)

    def list_trades(
        self,
        *,
        page: int,
        limit: int,
        grid_id: Optional[str] = None,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[list[Trade], int]:
        trades, total = self.repository.paginate(
            page=page,
            limit=limit,
            grid_id=grid_id,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
        return trades, total
