from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import List

from backend.exceptions import ValidationError

getcontext().prec = 18


@dataclass(frozen=True)
class GridLevelPlan:
    level_index: int
    price: Decimal


@dataclass(frozen=True)
class GridCalculationResult:
    grid_spacing: Decimal
    investment_per_grid: Decimal
    levels: List[GridLevelPlan]


class GridStrategy:
    """Deterministic calculator for arithmetic grid trading parameters."""

    MIN_GRID_COUNT = 5
    MAX_GRID_COUNT = 100

    def __init__(self, trading_pair: str, upper_price: Decimal, lower_price: Decimal, grid_count: int, total_investment: Decimal, price_precision: int = 8) -> None:
        self.trading_pair = trading_pair
        self.upper_price = upper_price
        self.lower_price = lower_price
        self.grid_count = grid_count
        self.total_investment = total_investment
        self.price_precision = price_precision

        self._validate()

    def _validate(self) -> None:
        if self.upper_price <= self.lower_price:
            raise ValidationError("Upper price must be greater than lower price.")
        if not (self.MIN_GRID_COUNT <= self.grid_count <= self.MAX_GRID_COUNT):
            raise ValidationError(f"Grid count must be between {self.MIN_GRID_COUNT} and {self.MAX_GRID_COUNT}.")
        if self.total_investment <= Decimal("0"):
            raise ValidationError("Total investment must be greater than zero.")

    def calculate(self) -> GridCalculationResult:
        grid_spacing = (self.upper_price - self.lower_price) / Decimal(self.grid_count)
        investment_per_grid = self.total_investment / Decimal(self.grid_count)

        # Use dynamic precision for price
        price_quantize_str = f"0.{'0' * self.price_precision}"

        levels: List[GridLevelPlan] = []
        for index in range(self.grid_count + 1):
            price = self.lower_price + grid_spacing * Decimal(index)
            # Quantize price to match symbol precision
            price = price.quantize(Decimal(price_quantize_str))
            levels.append(GridLevelPlan(level_index=index + 1, price=price))

        return GridCalculationResult(
            grid_spacing=grid_spacing.quantize(Decimal(price_quantize_str)),
            investment_per_grid=investment_per_grid.quantize(Decimal("0.00000001")),
            levels=levels,
        )
