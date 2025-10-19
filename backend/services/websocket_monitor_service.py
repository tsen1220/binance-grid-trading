"""WebSocket service for real-time order monitoring."""

from __future__ import annotations

import asyncio
import json
import logging
from decimal import Decimal
from typing import Optional

import websockets
from websockets.asyncio.client import ClientConnection

from backend.entities import GridStatus, OrderSide, OrderStatus, TradeSide
from backend.repositories import get_session
from backend.services import ConfigService
from backend.services.order_pairing_service import OrderPairingService
from backend.utils import utcnow

logger = logging.getLogger(__name__)


class WebSocketMonitorService:
    """Monitors orders via Binance WebSocket User Data Stream."""

    def __init__(self, config_service: ConfigService) -> None:
        self.config_service = config_service
        self.websocket: Optional[ClientConnection] = None
        self.listen_key: Optional[str] = None
        self.running = False
        self.keepalive_task: Optional[asyncio.Task] = None
        self.monitor_task: Optional[asyncio.Task] = None
        self.reconnect_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()  # Lock to prevent concurrent operations

    async def start(self) -> None:
        """Start WebSocket monitoring."""
        async with self._lock:
            if self.running:
                logger.warning("WebSocket monitor is already running")
                return

            try:
                # Create Binance client and get listen key
                client = self.config_service.create_client()
                self.listen_key = client.create_listen_key()
                logger.info(f"Created listen key: {self.listen_key}")

                # Get WebSocket URL from config
                from backend.config import settings

                ws_base_url = settings.binance.websocket_url
                ws_url = f"{ws_base_url}/ws/{self.listen_key}"

                # Connect to WebSocket
                self.websocket = await websockets.connect(ws_url)
                logger.info(f"Connected to WebSocket: {ws_url}")

                self.running = True

                # Start keepalive task (ping every 30 minutes)
                self.keepalive_task = asyncio.create_task(self._keepalive_loop())

                # Start monitoring task with auto-reconnect
                self.monitor_task = asyncio.create_task(self._monitor_with_reconnect())

            except Exception as e:
                logger.error(f"Failed to start WebSocket monitor: {e}", exc_info=True)
                await self._cleanup()
                raise

    async def stop(self) -> None:
        """Stop WebSocket monitoring."""
        logger.info("Stopping WebSocket monitor...")
        self.running = False
        await self._cleanup()
        logger.info("WebSocket monitor stopped")

    async def _cleanup(self) -> None:
        """Clean up resources (websocket, tasks, listen key)."""
        # Cancel tasks
        if self.keepalive_task:
            self.keepalive_task.cancel()
            try:
                await self.keepalive_task
            except asyncio.CancelledError:
                pass
            self.keepalive_task = None

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
            self.monitor_task = None

        # Close WebSocket connection
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None

        # Close listen key
        if self.listen_key:
            try:
                client = self.config_service.create_client()
                client.close_listen_key(self.listen_key)
                logger.info(f"Closed listen key: {self.listen_key}")
            except Exception as e:
                logger.error(f"Failed to close listen key: {e}")
            self.listen_key = None

    async def _monitor_with_reconnect(self) -> None:
        """Monitor loop with automatic reconnection on disconnect."""
        reconnect_delay = 5  # seconds

        while self.running:
            try:
                # Run the monitor loop (this will block until disconnect)
                await self._monitor_loop()

                # If we exit the loop and still running, reconnect
                if self.running:
                    logger.warning(f"Monitor loop exited, reconnecting in {reconnect_delay} seconds...")
                    await asyncio.sleep(reconnect_delay)
                    await self._reconnect()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor with reconnect: {e}", exc_info=True)
                if self.running:
                    await asyncio.sleep(reconnect_delay)

    async def _keepalive_loop(self) -> None:
        """Keep the listen key alive by pinging every 30 minutes."""
        while self.running:
            try:
                # Wait 30 minutes
                await asyncio.sleep(30 * 60)

                if self.listen_key and self.running:
                    client = self.config_service.create_client()
                    client.keepalive_listen_key(self.listen_key)
                    logger.debug("Listen key keepalive successful")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Keepalive error: {e}", exc_info=True)

    async def _monitor_loop(self) -> None:
        """Monitor WebSocket messages and process order updates."""
        while self.running and self.websocket:
            try:
                # Wait for message from WebSocket
                message = await self.websocket.recv()
                data = json.loads(message)

                # Process the message
                await self._process_message(data)

            except asyncio.CancelledError:
                break
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                # Don't call reconnect directly - exit loop and let it be handled externally
                # This prevents multiple concurrent recv() calls
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                # Don't continue the loop on error to avoid rapid error loops
                await asyncio.sleep(1)

    async def _reconnect(self) -> None:
        """Reconnect to WebSocket after connection loss.

        This creates a new WebSocket connection with a new listen key.
        Should only be called from _monitor_with_reconnect().
        """
        async with self._lock:
            try:
                logger.info("Reconnecting to WebSocket...")

                # Close old websocket if exists
                if self.websocket:
                    try:
                        await self.websocket.close()
                    except Exception:
                        pass
                    self.websocket = None

                # Close old listen key if exists
                if self.listen_key:
                    try:
                        client = self.config_service.create_client()
                        client.close_listen_key(self.listen_key)
                    except Exception as e:
                        logger.error(f"Failed to close old listen key: {e}")
                    self.listen_key = None

                # Create new connection
                client = self.config_service.create_client()
                self.listen_key = client.create_listen_key()
                logger.info(f"Created new listen key: {self.listen_key}")

                from backend.config import settings
                ws_base_url = settings.binance.websocket_url
                ws_url = f"{ws_base_url}/ws/{self.listen_key}"

                self.websocket = await websockets.connect(ws_url)
                logger.info(f"Reconnected to WebSocket: {ws_url}")

            except Exception as e:
                logger.error(f"Reconnection failed: {e}", exc_info=True)
                raise

    async def _process_message(self, data: dict) -> None:
        """Process incoming WebSocket message.

        Args:
            data: Parsed JSON message from WebSocket
        """
        event_type = data.get("e")

        if event_type == "executionReport":
            # Order update event
            await self._handle_execution_report(data)
        elif event_type == "listenKeyExpired":
            # Listen key expired, stop monitoring
            logger.warning("Listen key expired, stopping monitor...")
            self.running = False
        else:
            # Log other event types for debugging
            logger.debug(f"Received event: {event_type}")

    async def _handle_execution_report(self, data: dict) -> None:
        """Handle executionReport event (order update).

        Directly updates order from WebSocket data without querying Binance REST API.

        Args:
            data: Execution report data from WebSocket

        Event payload example:
        {
            "e": "executionReport",
            "E": 1499405658658,
            "s": "ETHBTC",
            "c": "client_order_id",
            "S": "BUY",
            "o": "LIMIT",
            "f": "GTC",
            "q": "1.00000000",
            "p": "0.10264410",
            "X": "FILLED",
            "x": "TRADE",
            "i": 4293153,
            "l": "0.00000000",
            "z": "1.00000000",
            "L": "0.00000000",
            "n": "0",
            "T": 1499405658657,
            ...
        }
        """
        try:
            symbol = data.get("s")
            order_status = data.get("X")  # Current order status (NEW, FILLED, etc.)
            execution_type = data.get("x")  # Execution type (NEW, CANCELED, TRADE, etc.)
            binance_order_id = str(data.get("i"))
            filled_qty = Decimal(data.get("z", "0"))  # Cumulative filled quantity

            logger.info(
                f"Order update: symbol={symbol}, "
                f"binance_order_id={binance_order_id}, "
                f"status={order_status}, "
                f"execution_type={execution_type}, "
                f"filled_qty={filled_qty}"
            )

            # Only process meaningful status changes
            if order_status not in ("FILLED", "PARTIALLY_FILLED", "CANCELED"):
                return

            session = next(get_session())
            try:
                # Import here to avoid circular dependency
                from backend.repositories import GridRepository, OrderRepository, TradeRepository

                grid_repo = GridRepository(session)
                order_repo = OrderRepository(session)
                trade_repo = TradeRepository(session)

                # Find the order by binance_order_id
                order = order_repo.find_by_binance_order_id(binance_order_id)
                if not order:
                    logger.warning(f"Order not found for binance_order_id: {binance_order_id}")
                    return

                grid_id = order.grid_id

                # Check if the grid is still running
                grid = grid_repo.find(grid_id)
                if not grid or grid.status != GridStatus.RUNNING:
                    logger.debug(f"Grid {grid_id} is not running (status={grid.status if grid else 'None'}), skipping order processing")
                    return

                # Update order status directly from WebSocket data (no REST API call!)
                old_status = order.status
                new_status = None

                if order_status == "FILLED":
                    new_status = OrderStatus.FILLED
                    order.filled_quantity = filled_qty
                    order.filled_at = utcnow()
                elif order_status == "PARTIALLY_FILLED":
                    new_status = OrderStatus.PARTIALLY_FILLED
                    order.filled_quantity = filled_qty
                elif order_status == "CANCELED":
                    new_status = OrderStatus.CANCELLED

                # Only update if status changed
                if new_status and old_status != new_status:
                    order.status = new_status
                    session.commit()
                    logger.info(f"Order {order.id} status updated: {old_status} → {new_status}")

                    # Create Trade record for newly filled orders
                    if new_status == OrderStatus.FILLED and old_status != OrderStatus.FILLED:
                        trade_side = TradeSide.BUY if order.side == OrderSide.BUY else TradeSide.SELL
                        quote_quantity = Decimal(order.price) * filled_qty

                        trade_repo.create(
                            {
                                "grid_id": order.grid_id,
                                "order_id": order.id,
                                "symbol": order.symbol,
                                "side": trade_side,
                                "price": order.price,
                                "quantity": filled_qty,
                                "quote_quantity": quote_quantity,
                                "commission": Decimal(data.get("n", "0")) if data.get("n") else None,
                                "commission_asset": data.get("N"),
                                "timestamp": utcnow(),
                                "is_maker": data.get("m", False),
                            }
                        )
                        session.commit()
                        logger.info(f"Created trade record for order {order.id}")

                        # If this is a filled BUY order, create paired SELL order
                        if order.side == OrderSide.BUY:
                            client = self.config_service.create_client()
                            pairing_service = OrderPairingService(session, client)
                            if pairing_service.create_paired_sell_order(order):
                                logger.info(f"Created paired SELL order for BUY order {order.id}")

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error handling execution report: {e}", exc_info=True)
