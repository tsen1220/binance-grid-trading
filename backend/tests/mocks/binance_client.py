from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from backend.core.binance_client import Balance, SymbolInfo


class MockBinanceClient:
    """Mock Binance client for testing."""

    _DEFAULT_BALANCES = (
        Balance(asset="USDT", free=Decimal("10000"), locked=Decimal("0")),
        Balance(asset="BTC", free=Decimal("0.05"), locked=Decimal("0")),
        Balance(asset="ETH", free=Decimal("1.5"), locked=Decimal("0")),
    )

    _DEFAULT_SYMBOLS = (
        SymbolInfo(
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            status="TRADING",
            min_qty=Decimal("0.0001"),
            min_notional=Decimal("10"),
            step_size=Decimal("0.000001"),
            tick_size=Decimal("0.01"),
            price_precision=2,
            qty_precision=6,
        ),
        SymbolInfo(
            symbol="ETHUSDT",
            base_asset="ETH",
            quote_asset="USDT",
            status="TRADING",
            min_qty=Decimal("0.001"),
            min_notional=Decimal("10"),
            step_size=Decimal("0.0001"),
            tick_size=Decimal("0.01"),
            price_precision=2,
            qty_precision=5,
        ),
    )

    _DEFAULT_PRICES = {
        "BTCUSDT": Decimal("45000"),
        "ETHUSDT": Decimal("2200"),
    }

    def __init__(
        self,
        api_key: Optional[str],
        api_secret: Optional[str],
        *,
        testnet: bool,
        binance_url: str,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.base_url = binance_url
        self._order_id_counter = 1000000
        self._orders: Dict[int, Dict[str, Any]] = {}

    def test_connection(self) -> bool:
        """Test connection - requires both API key and secret.

        Returns:
            True if both API key and secret are provided, False otherwise.
        """
        # Require both credentials, matching real BinanceClient behavior
        return bool(self.api_key and self.api_secret)

    def get_account_balances(self) -> List[Balance]:
        return list(self._DEFAULT_BALANCES)

    def get_supported_symbols(self, *, base_asset: Optional[str] = None, quote_asset: Optional[str] = None) -> List[SymbolInfo]:
        symbols = self._DEFAULT_SYMBOLS
        if base_asset:
            symbols = tuple(s for s in symbols if s.base_asset == base_asset)
        if quote_asset:
            symbols = tuple(s for s in symbols if s.quote_asset == quote_asset)
        return list(symbols)

    def get_symbol_price(self, symbol: str) -> Decimal:
        return self._DEFAULT_PRICES.get(symbol, Decimal("0"))

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        """Mock place order - returns a fake order ID."""
        order_id = self._order_id_counter
        self._order_id_counter += 1

        order = {
            "orderId": order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),
            "price": str(price) if price else None,
            "status": "NEW",
            "executedQty": "0",
        }
        self._orders[order_id] = order
        return order

    def query_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Mock query order - returns the stored order."""
        if order_id not in self._orders:
            raise ValueError(f"Order {order_id} not found")
        return self._orders[order_id]

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Mock cancel order - marks order as canceled."""
        if order_id not in self._orders:
            raise ValueError(f"Order {order_id} not found")
        self._orders[order_id]["status"] = "CANCELED"
        return self._orders[order_id]

    # WebSocket User Data Stream methods (for testing)
    def create_listen_key(self) -> str:
        """Mock create listen key."""
        return "mock_listen_key_12345"

    def keepalive_listen_key(self, listen_key: str) -> None:
        """Mock keepalive listen key."""
        pass

    def close_listen_key(self, listen_key: str) -> None:
        """Mock close listen key."""
        pass
