from __future__ import annotations

import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from backend.core import GridEngine, GridStrategy
from backend.entities import Grid, GridLevelStatus, GridStatus, OrderSide, OrderStatus, OrderType
from backend.exceptions import (
    ConflictError,
    InsufficientBalanceError,
    ResourceNotFoundError,
    UnauthorizedError,
    ValidationError,
)
from backend.models import GridConfig, GridHistoryItem, GridStatistics, GridStatusResponse
from backend.repositories import (
    GridLevelRepository,
    GridRepository,
    OrderRepository,
    TradeRepository,
)
from backend.entities import TradeSide
from backend.services import ConfigService
from backend.utils import format_timedelta, utcnow

logger = logging.getLogger(__name__)


class GridService:
    def __init__(self, session: Session, config_service: ConfigService) -> None:
        self.session = session
        self.config_service = config_service
        self.grid_repository = GridRepository(session)
        self.level_repository = GridLevelRepository(session)
        self.order_repository = OrderRepository(session)
        self.trade_repository = TradeRepository(session)

    def start_grid(self, config: GridConfig) -> Tuple[Grid, Dict[str, Decimal], int]:
        if self.grid_repository.find_active_grid():
            raise ConflictError("Grid trading already running", error_code="GRID_ALREADY_RUNNING")

        client = self.config_service.create_client()

        # Fetch symbol rules to get precision requirements
        symbols = client.get_supported_symbols()
        symbol_info = next((s for s in symbols if s.symbol == config.trading_pair), None)
        if not symbol_info:
            raise ValidationError(f"Trading pair {config.trading_pair} not found or not supported")

        # Risk Control: Price validation
        current_price = client.get_symbol_price(config.trading_pair)
        if current_price > 0:
            # Ensure current price is within grid bounds with reasonable buffer
            price_buffer_percentage = Decimal("0.5")  # 50% buffer
            acceptable_lower = config.lower_price * (Decimal("1") - price_buffer_percentage)
            acceptable_upper = config.upper_price * (Decimal("1") + price_buffer_percentage)

            if current_price < acceptable_lower or current_price > acceptable_upper:
                logger.warning(
                    f"Current price {current_price} is outside grid bounds "
                    f"[{config.lower_price}, {config.upper_price}] with {price_buffer_percentage * 100}% buffer"
                )
                raise ValidationError(
                    f"Current market price ({current_price}) is too far from your grid range. "
                    f"Please adjust your grid bounds to be closer to current market price."
                )

        # Use symbol's precision requirements
        qty_precision = symbol_info.qty_precision
        price_precision = symbol_info.price_precision
        step_size = symbol_info.step_size
        tick_size = symbol_info.tick_size
        min_qty = symbol_info.min_qty

        strategy = GridStrategy(
            trading_pair=config.trading_pair,
            upper_price=config.upper_price,
            lower_price=config.lower_price,
            grid_count=config.grid_count,
            total_investment=config.total_investment,
            price_precision=price_precision,
        )
        calculation = strategy.calculate()
        engine = GridEngine(client)

        # Dynamic pairing strategy: Only BUY orders are created initially
        # SELL orders are created automatically when BUY orders fill
        # So we only need to verify USDT balance for BUY orders
        required_investment = config.total_investment

        # Risk Control: Maximum investment limit
        MAX_INVESTMENT_USDT = Decimal("100000")  # $100,000 max per grid
        if required_investment > MAX_INVESTMENT_USDT:
            raise ValidationError(
                f"Total investment ({required_investment} USDT) exceeds maximum allowed ({MAX_INVESTMENT_USDT} USDT). "
                f"Please reduce your investment amount or increase the limit if you're certain."
            )

        balances = {balance.asset: balance.free for balance in client.get_account_balances()}
        available = balances.get("USDT", Decimal("0"))
        if available < required_investment:
            raise InsufficientBalanceError(
                "Insufficient USDT balance for BUY orders.",
                required=float(required_investment),
                available=float(available),
                asset="USDT",
            )

        grid = self.grid_repository.create(
            {
                "trading_pair": config.trading_pair,
                "upper_price": config.upper_price,
                "lower_price": config.lower_price,
                "grid_count": config.grid_count,
                "grid_spacing": calculation.grid_spacing,
                "total_investment": config.total_investment,
                "investment_per_grid": calculation.investment_per_grid,
                "status": GridStatus.RUNNING,
                "started_at": utcnow(),
            }
        )

        level_payloads = [
            {
                "grid_id": grid.id,
                "level_index": level.level_index,
                "price": level.price,
                "status": GridLevelStatus.IDLE,
            }
            for level in calculation.levels
        ]
        self.level_repository.create_many(level_payloads)

        try:
            initialization = engine.initialize(
                calculation,
                qty_precision=qty_precision,
                price_precision=price_precision,
                step_size=step_size,
                tick_size=tick_size,
                min_qty=min_qty,
            )
        except ValueError as exc:
            self.session.rollback()
            raise ValidationError(str(exc)) from exc

        # Place orders on Binance and save to database
        order_payloads = []
        for plan in initialization.orders:
            try:
                # Place order on Binance
                binance_response = client.place_order(
                    symbol=config.trading_pair,
                    side=plan.side.value,
                    order_type="LIMIT",
                    quantity=plan.quantity,
                    price=plan.price,
                )

                # Save order to database with Binance order ID
                order_payloads.append(
                    {
                        "grid_id": grid.id,
                        "grid_level": plan.level_index,
                        "symbol": config.trading_pair,
                        "side": plan.side,
                        "type": OrderType.LIMIT,
                        "price": plan.price,
                        "quantity": plan.quantity,
                        "filled_quantity": Decimal("0"),
                        "status": OrderStatus.NEW,
                        "binance_order_id": str(binance_response["orderId"]),
                    }
                )
            except Exception as e:
                # Rollback grid creation if order placement fails
                self.session.rollback()
                raise ValidationError(f"Failed to place order at level {plan.level_index}: {str(e)}")

        if order_payloads:
            self.order_repository.create_many(order_payloads)

        self.session.commit()

        return grid, {
            "grid_spacing": calculation.grid_spacing,
            "investment_per_grid": calculation.investment_per_grid,
            "total_investment": config.total_investment,
        }, len(order_payloads)

    def stop_grid(self, grid_id: str, *, cancel_orders: bool) -> Tuple[Grid, int]:
        grid = self.grid_repository.find(grid_id)
        if not grid:
            raise ResourceNotFoundError(f"Grid {grid_id} not found")

        grid.status = GridStatus.STOPPED
        grid.stopped_at = utcnow()

        cancelled = 0
        if cancel_orders:
            pending_orders = self.order_repository.get_pending_orders(grid_id=grid_id)
            client = self.config_service.create_client()

            for order in pending_orders:
                # Cancel order on Binance if it has a Binance order ID
                if order.binance_order_id:
                    try:
                        client.cancel_order(symbol=order.symbol, order_id=int(order.binance_order_id))
                    except Exception as e:
                        # Log error but continue with other orders
                        logger.error(f"Error cancelling order {order.id} on Binance: {e}", exc_info=True)
                        continue

                # Update order status in database
                order.status = OrderStatus.CANCELLED
                cancelled += 1

        self.session.commit()
        return grid, cancelled

    def _calculate_profit(self, grid_id: str) -> Tuple[Decimal, Decimal, Decimal]:
        """Calculate profit for a grid.

        Args:
            grid_id: The grid ID to calculate profit for

        Returns:
            Tuple of (profit, profit_percentage, total_fees)
        """
        trades = self.trade_repository.get(filters={"grid_id": grid_id})

        buy_cost = Decimal("0")
        sell_revenue = Decimal("0")
        total_fees = Decimal("0")

        for trade in trades:
            amount = Decimal(trade.price) * Decimal(trade.quantity)
            if trade.side == TradeSide.BUY:
                buy_cost += amount
            elif trade.side == TradeSide.SELL:
                sell_revenue += amount

            if trade.commission:
                total_fees += Decimal(trade.commission)

        profit = sell_revenue - buy_cost
        profit_percentage = (profit / buy_cost * Decimal("100")) if buy_cost > 0 else Decimal("0")

        return profit, profit_percentage, total_fees

    def get_status(self, *, grid_id: Optional[str] = None) -> GridStatusResponse:
        grid: Optional[Grid]
        if grid_id:
            grid = self.grid_repository.find(grid_id)
        else:
            grid = self.grid_repository.find_active_grid()

        if not grid:
            return GridStatusResponse(success=True, status="stopped", message="No active grid trading found", grid_id=None)

        levels = self.level_repository.get_by_grid_id(grid.id)
        orders, _ = self.order_repository.get_orders(page=1, limit=1000, grid_id=grid.id)
        total_trades = self.trade_repository.count(filters={"grid_id": grid.id})

        buy_orders = len([order for order in orders if order.side == OrderSide.BUY])
        sell_orders = len([order for order in orders if order.side == OrderSide.SELL])
        active_orders = len([order for order in orders if order.status in {OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED}])

        runtime = None
        if grid.started_at:
            delta = (grid.stopped_at or utcnow()) - grid.started_at
            runtime = format_timedelta(delta)

        config_snapshot = {
            "trading_pair": grid.trading_pair,
            "upper_price": Decimal(grid.upper_price),
            "lower_price": Decimal(grid.lower_price),
            "grid_count": grid.grid_count,
            "grid_spacing": Decimal(grid.grid_spacing),
            "investment_per_grid": Decimal(grid.investment_per_grid),
            "total_investment": Decimal(grid.total_investment),
        }

        level_snapshots = [
            {
                "grid_level": level.level_index,
                "price": Decimal(level.price),
                "buy_order_id": next((order.id for order in orders if order.grid_level == level.level_index and order.side == OrderSide.BUY), None),
                "sell_order_id": next((order.id for order in orders if order.grid_level == level.level_index and order.side == OrderSide.SELL), None),
                "status": level.status.value,
            }
            for level in levels
        ]

        try:
            client = self.config_service.create_client()
            current_price = client.get_symbol_price(grid.trading_pair)
        except UnauthorizedError:
            current_price = None

        # Calculate profit based on actual trades
        profit, profit_percentage, total_fees = self._calculate_profit(grid.id)

        statistics = GridStatistics(
            total_trades=total_trades,
            buy_orders=buy_orders,
            sell_orders=sell_orders,
            active_orders=active_orders,
            profit=profit,
            profit_percentage=profit_percentage,
            total_fees=total_fees,
        )

        return GridStatusResponse(
            success=True,
            grid_id=grid.id,
            status=grid.status.value,
            config=config_snapshot,
            current_price=current_price,
            runtime=runtime,
            statistics=statistics,
            grids=level_snapshots,
        )

    def get_histories(self, *, page: int, limit: int) -> Tuple[list[GridHistoryItem], int]:
        grids, total = self.grid_repository.get_histories(page=page, limit=limit)
        history_items = []
        for grid in grids:
            duration = None
            if grid.started_at and grid.stopped_at:
                duration = format_timedelta(grid.stopped_at - grid.started_at)

            # Calculate profit for each grid
            profit, profit_percentage, _ = self._calculate_profit(grid.id)
            total_trades = self.trade_repository.count(filters={"grid_id": grid.id})

            history_items.append(
                GridHistoryItem(
                    grid_id=grid.id,
                    trading_pair=grid.trading_pair,
                    start_time=grid.started_at,
                    end_time=grid.stopped_at,
                    duration=duration or "0s",
                    total_investment=Decimal(grid.total_investment),
                    total_trades=total_trades,
                    profit=profit,
                    profit_percentage=profit_percentage,
                    status=grid.status.value,
                )
            )
        return history_items, total
