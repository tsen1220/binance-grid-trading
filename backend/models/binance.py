from decimal import Decimal
from typing import List

from pydantic import BaseModel

from .base import APIResponse


class TestConnectionResponse(APIResponse):
    connected: bool
    account_type: str = "SPOT"
    can_trade: bool = True


class BalanceItem(BaseModel):
    asset: str
    free: Decimal
    locked: Decimal


class BalanceResponse(APIResponse):
    balances: List[BalanceItem]


class SymbolItem(BaseModel):
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    min_qty: Decimal
    min_notional: Decimal
    step_size: Decimal
    tick_size: Decimal
    price_precision: int
    qty_precision: int


class SymbolsResponse(APIResponse):
    symbols: List[SymbolItem]
