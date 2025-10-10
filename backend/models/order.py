from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.entities import OrderSide, OrderStatus, OrderType

from .base import APIResponse


class OrderItem(BaseModel):
    order_id: str = Field(alias="id")
    grid_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    grid_level: int
    price: Decimal
    quantity: Decimal
    filled_quantity: Decimal
    status: OrderStatus
    created_at: datetime
    filled_at: Optional[datetime]
    commission: Optional[Decimal]
    commission_asset: Optional[str]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class OrdersResponse(APIResponse):
    total: int
    page: int
    limit: int
    orders: List[OrderItem]
