from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, DivisionByZero
from typing import List

from backend.entities import OrderSide
from backend.core import GridLevelPlan


@dataclass(frozen=True)
class OrderPlan:
    level_index: int
    side: OrderSide
    price: Decimal
    quantity: Decimal


class OrderManager:
    """Responsible for translating grid levels into actionable order plans."""

    def __init__(self, investment_per_grid: Decimal) -> None:
        self.investment_per_grid = investment_per_grid

    def generate_orders(self, levels: List[GridLevelPlan]) -> List[OrderPlan]:
        if len(levels) < 2:
            return []

        orders: List[OrderPlan] = []
        for level in levels[:-1]:
            quantity = self._calculate_quantity(level.price)
            orders.append(OrderPlan(level_index=level.level_index, side=OrderSide.BUY, price=level.price, quantity=quantity))

        for level in levels[1:]:
            quantity = self._calculate_quantity(level.price)
            orders.append(OrderPlan(level_index=level.level_index, side=OrderSide.SELL, price=level.price, quantity=quantity))

        return orders

    def _calculate_quantity(self, price: Decimal) -> Decimal:
        try:
            quantity = self.investment_per_grid / price
        except DivisionByZero as exc:  # pragma: no cover - safety guard
            raise ValueError("Price must be greater than zero for quantity calculation") from exc
        return quantity.quantize(Decimal("0.00000001"))
