from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from backend.api import get_trade_service
from backend.models import TradesResponse
from backend.services import TradeService

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("", response_model=TradesResponse)
def list_trades(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    grid_id: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    service: TradeService = Depends(get_trade_service),
) -> TradesResponse:
    trades, total = service.list_trades(
        page=page,
        limit=limit,
        grid_id=grid_id,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )
    return TradesResponse(success=True, total=total, page=page, limit=limit, trades=trades)
