from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.entities import TradeSide

from .base import APIResponse


class TradeItem(BaseModel):
    trade_id: str = Field(alias="id")
    grid_id: str
    order_id: str
    symbol: str
    side: TradeSide
    price: Decimal
    quantity: Decimal
    quote_quantity: Decimal
    commission: Optional[Decimal]
    commission_asset: Optional[str]
    timestamp: datetime
    is_maker: bool

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TradesResponse(APIResponse):
    total: int
    page: int
    limit: int
    trades: List[TradeItem]
