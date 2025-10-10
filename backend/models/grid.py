from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, conint, validator

from .base import APIResponse


class GridConfig(BaseModel):
    trading_pair: str
    upper_price: Decimal
    lower_price: Decimal
    grid_count: conint(ge=5, le=100)
    total_investment: Decimal

    @validator("trading_pair")
    def uppercase_symbol(cls, value: str) -> str:
        return value.upper()


class GridStartRequest(GridConfig):
    pass


class GridStartResponse(APIResponse):
    grid_id: str
    message: str
    config: dict
    initial_orders: int


class GridStopRequest(BaseModel):
    grid_id: str
    cancel_orders: bool = True


class GridStopResponse(APIResponse):
    message: str
    cancelled_orders: int
    final_status: Optional[dict] = None


class GridLevelSnapshot(BaseModel):
    grid_level: int
    price: Decimal
    buy_order_id: Optional[str]
    sell_order_id: Optional[str]
    status: str


class GridStatistics(BaseModel):
    total_trades: int
    buy_orders: int
    sell_orders: int
    active_orders: int
    profit: Decimal
    profit_percentage: Decimal
    total_fees: Decimal


class GridStatusResponse(APIResponse):
    grid_id: Optional[str]
    status: str
    message: Optional[str] = None
    config: Optional[dict] = None
    current_price: Optional[Decimal] = None
    runtime: Optional[str] = None
    statistics: Optional[GridStatistics] = None
    grids: Optional[List[GridLevelSnapshot]] = None


class GridHistoryItem(BaseModel):
    grid_id: str
    trading_pair: str
    start_time: datetime
    end_time: Optional[datetime]
    duration: str
    total_investment: Decimal
    total_trades: int
    profit: Decimal
    profit_percentage: Decimal
    status: str


class GridHistoryResponse(APIResponse):
    total: int
    page: int
    limit: int
    grids: List[GridHistoryItem]
