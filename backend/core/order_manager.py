from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, ROUND_DOWN
from typing import List, Optional

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

    def __init__(
        self,
        investment_per_grid: Decimal,
        qty_precision: int = 8,
        price_precision: int = 8,
        step_size: Optional[Decimal] = None,
        tick_size: Optional[Decimal] = None,
        min_qty: Optional[Decimal] = None,
    ) -> None:
        self.investment_per_grid = investment_per_grid
        self.qty_precision = qty_precision
        self.price_precision = price_precision
        self.step_size = step_size
        self.tick_size = tick_size
        self.min_qty = min_qty

    def generate_orders(self, levels: List[GridLevelPlan]) -> List[OrderPlan]:
        """Generate initial BUY orders for grid trading.

        Dynamic pairing strategy:
        - Start with BUY orders at lower price levels
        - When a BUY fills, create a SELL order at a higher price
        - This avoids self-trading and manages capital efficiently
        """
        if len(levels) < 2:
            return []

        orders: List[OrderPlan] = []
        # Only generate BUY orders at lower levels (exclude highest level)
        for level in levels[:-1]:
            price = self._quantize_price(level.price)
            quantity = self._calculate_quantity(price)
            orders.append(OrderPlan(level_index=level.level_index, side=OrderSide.BUY, price=price, quantity=quantity))

        return orders

    def create_paired_sell_order(
        self, buy_level_index: int, buy_price: Decimal, buy_quantity: Decimal, levels: List[GridLevelPlan]
    ) -> Optional[OrderPlan]:
        """Create a SELL order paired with a filled BUY order.

        Args:
            buy_level_index: The level index where the BUY order was filled
            buy_price: The price at which the BUY was filled
            buy_quantity: The quantity that was bought
            levels: All grid levels

        Returns:
            OrderPlan for SELL order at next higher level, or None if no higher level exists
        """
        # Find the next higher level
        next_level = next((lvl for lvl in levels if lvl.level_index > buy_level_index), None)

        if not next_level:
            # No higher level available (buy was at top level)
            return None

        # Create SELL order at the next higher price
        price = self._quantize_price(next_level.price)
        return OrderPlan(level_index=next_level.level_index, side=OrderSide.SELL, price=price, quantity=buy_quantity)

    def _calculate_quantity(self, price: Decimal) -> Decimal:
        try:
            quantity = self.investment_per_grid / price
        except DivisionByZero as exc:  # pragma: no cover - safety guard
            raise ValueError("Price must be greater than zero for quantity calculation") from exc
        quantity = self._quantize_quantity(quantity)
        if self.min_qty and self.min_qty > 0 and quantity < self.min_qty:
            raise ValueError("Calculated quantity is below the exchange minimum quantity")
        return quantity

    def _quantize_quantity(self, quantity: Decimal) -> Decimal:
        if self.step_size and self.step_size > 0:
            step = self.step_size
            steps = (quantity / step).to_integral_value(rounding=ROUND_DOWN)
            quantity = steps * step

        quantize_str = f"0.{'0' * self.qty_precision}"
        quantity = quantity.quantize(Decimal(quantize_str), rounding=ROUND_DOWN)

        if quantity <= 0:
            raise ValueError("Calculated quantity is zero after applying symbol constraints")

        return quantity

    def _quantize_price(self, price: Decimal) -> Decimal:
        if self.tick_size and self.tick_size > 0:
            return price.quantize(self.tick_size, rounding=ROUND_DOWN)

        quantize_str = f"0.{'0' * self.price_precision}"
        return price.quantize(Decimal(quantize_str), rounding=ROUND_DOWN)
