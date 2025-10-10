from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List

from backend.core import BinanceClient, GridCalculationResult, OrderManager, OrderPlan


@dataclass(frozen=True)
class GridInitializationResult:
    orders: List[OrderPlan]
    started_at: datetime


class GridEngine:
    """Coordinates strategy output with Binance client interactions."""

    def __init__(self, client: BinanceClient) -> None:
        self.client = client

    def initialize(self, calculation: GridCalculationResult) -> GridInitializationResult:
        order_manager = OrderManager(calculation.investment_per_grid)
        orders = order_manager.generate_orders(calculation.levels)
        return GridInitializationResult(orders=orders, started_at=datetime.utcnow())

    def test_balance(self, required: Decimal, asset: str = "USDT") -> bool:
        balances = {balance.asset: balance.free for balance in self.client.get_account_balances()}
        return balances.get(asset, Decimal("0")) >= required
