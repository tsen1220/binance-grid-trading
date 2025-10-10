"""Service for creating paired SELL orders when BUY orders fill."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session

from backend.core import BinanceClient, GridLevelPlan, OrderManager
from backend.entities import Order, OrderSide, OrderStatus, OrderType
from backend.repositories import GridLevelRepository, GridRepository, OrderRepository

logger = logging.getLogger(__name__)


class OrderPairingService:
    """Handles creation of paired SELL orders for filled BUY orders."""

    def __init__(self, session: Session, client: BinanceClient) -> None:
        self.session = session
        self.client = client
        self.grid_repository = GridRepository(session)
        self.level_repository = GridLevelRepository(session)
        self.order_repository = OrderRepository(session)

    def create_paired_sell_order(self, buy_order: Order) -> bool:
        """Create a paired SELL order for a filled BUY order.

        Args:
            buy_order: The filled BUY order

        Returns:
            True if SELL order was created, False otherwise
        """
        if buy_order.side != OrderSide.BUY:
            logger.warning(f"Order {buy_order.id} is not a BUY order, skipping pairing")
            return False

        if buy_order.status != OrderStatus.FILLED:
            logger.warning(f"Order {buy_order.id} is not FILLED, skipping pairing")
            return False

        # Check if already paired
        from sqlalchemy import select
        stmt = select(Order).where(Order.paired_order_id == buy_order.id)
        existing_pair = self.session.execute(stmt).scalar_one_or_none()
        if existing_pair:
            logger.debug(f"BUY order {buy_order.id} already has paired SELL order")
            return False

        # Get grid info
        grid = self.grid_repository.find(buy_order.grid_id)
        if not grid:
            logger.error(f"Grid {buy_order.grid_id} not found")
            return False

        # Fetch symbol rules to get precision requirements
        symbols = self.client.get_supported_symbols()
        symbol_info = next((s for s in symbols if s.symbol == grid.trading_pair), None)
        if not symbol_info:
            logger.error(f"Symbol info not found for {grid.trading_pair}")
            return False

        # Get all grid levels to find the next higher level
        levels = self.level_repository.get_by_grid_id(buy_order.grid_id)
        grid_level_plans = [
            GridLevelPlan(level_index=level.level_index, price=Decimal(level.price)) for level in levels
        ]

        # Calculate paired SELL order
        order_manager = OrderManager(
            Decimal(grid.investment_per_grid),
            qty_precision=symbol_info.qty_precision,
            price_precision=symbol_info.price_precision,
            step_size=symbol_info.step_size,
            tick_size=symbol_info.tick_size,
            min_qty=symbol_info.min_qty,
        )
        sell_plan = order_manager.create_paired_sell_order(
            buy_level_index=buy_order.grid_level,
            buy_price=Decimal(buy_order.price),
            buy_quantity=Decimal(buy_order.filled_quantity),
            levels=grid_level_plans,
        )

        if not sell_plan:
            logger.debug(f"No higher level available for BUY order {buy_order.id} (at top level)")
            return False

        try:
            # Place SELL order on Binance
            binance_response = self.client.place_order(
                symbol=grid.trading_pair,
                side=sell_plan.side.value,
                order_type="LIMIT",
                quantity=sell_plan.quantity,
                price=sell_plan.price,
            )

            # Create the SELL order in database
            self.order_repository.create(
                {
                    "grid_id": buy_order.grid_id,
                    "grid_level": sell_plan.level_index,
                    "symbol": grid.trading_pair,
                    "side": sell_plan.side,
                    "type": OrderType.LIMIT,
                    "price": sell_plan.price,
                    "quantity": sell_plan.quantity,
                    "filled_quantity": Decimal("0"),
                    "status": OrderStatus.NEW,
                    "paired_order_id": buy_order.id,
                    "binance_order_id": str(binance_response["orderId"]),
                }
            )
            self.session.commit()
            logger.info(f"Created paired SELL order for BUY order {buy_order.id}")
            return True

        except Exception as e:
            logger.error(f"Error creating SELL order for BUY {buy_order.id}: {e}", exc_info=True)
            self.session.rollback()
            return False

    def process_filled_buys_without_pair(self, grid_id: str) -> int:
        """Process all filled BUY orders that don't have paired SELL orders yet.

        Args:
            grid_id: The grid to process

        Returns:
            Number of SELL orders created
        """
        buy_orders = self.order_repository.find_filled_buys_without_pair(grid_id=grid_id)
        created_count = 0

        for buy_order in buy_orders:
            if self.create_paired_sell_order(buy_order):
                created_count += 1

        return created_count
