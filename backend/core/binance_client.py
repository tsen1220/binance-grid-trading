from __future__ import annotations

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Balance:
    asset: str
    free: Decimal
    locked: Decimal


@dataclass(frozen=True)
class SymbolInfo:
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


class BinanceClient:
    """Binance API client with HMAC-SHA256 signature support."""

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

    def _sign_request(self, params: Dict[str, Any]) -> str:
        """Sign request parameters using HMAC-SHA256."""
        if not self.api_secret:
            raise ValueError("API secret not provided")

        query_string = urlencode(params, doseq=True)
        signature = hmac.new(self.api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        return signature

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key
        return headers

    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Any:
        """Make HTTP request to Binance API."""
        url = f"{self.base_url}{endpoint}"
        params = params or {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign_request(params)

        headers = self._build_headers()

        with httpx.Client() as client:
            if method == "GET":
                response = client.get(url, params=params, headers=headers, timeout=10.0)
            elif method == "POST":
                response = client.post(url, params=params, headers=headers, timeout=10.0)
            elif method == "PUT":
                response = client.put(url, params=params, headers=headers, timeout=10.0)
            elif method == "DELETE":
                response = client.delete(url, params=params, headers=headers, timeout=10.0)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

    def test_connection(self) -> bool:
        """Test API connection and credentials.

        Returns:
            True if both network connectivity and authenticated access work.
            False if API credentials are missing or any connection test fails.
        """
        try:
            # Require API credentials for trading operations
            if not self.api_key or not self.api_secret:
                logger.error("API key and secret are required for trading operations")
                return False

            # Test network connectivity
            self._request("GET", "/api/v3/ping")

            # Test authenticated access (actual trading capability)
            self._request("GET", "/api/v3/account", signed=True)

            return True
        except Exception as exc:
            logger.error(f"Binance connection test failed: {exc}", exc_info=True)
            return False

    def get_account_balances(self) -> List[Balance]:
        """Get account balances."""
        try:
            data = self._request("GET", "/api/v3/account", signed=True)
            balances = []
            for item in data.get("balances", []):
                free = Decimal(item["free"])
                locked = Decimal(item["locked"])
                # Only include assets with non-zero balance
                if free > 0 or locked > 0:
                    balances.append(Balance(asset=item["asset"], free=free, locked=locked))
            return balances
        except Exception:
            # Return empty list on error
            return []

    def get_supported_symbols(self, *, base_asset: Optional[str] = None, quote_asset: Optional[str] = None) -> List[SymbolInfo]:
        """Get trading symbols information."""
        try:
            data = self._request("GET", "/api/v3/exchangeInfo")
            symbols = []

            for item in data.get("symbols", []):
                # Filter by base asset if specified
                if base_asset and item["baseAsset"] != base_asset:
                    continue

                # Filter by quote asset if specified
                if quote_asset and item["quoteAsset"] != quote_asset:
                    continue

                # Only include trading symbols
                if item["status"] != "TRADING":
                    continue

                # Extract LOT_SIZE, PRICE_FILTER and MIN_NOTIONAL filters
                min_qty = Decimal("0")
                min_notional = Decimal("0")
                step_size = Decimal("0")
                tick_size = Decimal("0")
                for filter_item in item.get("filters", []):
                    if filter_item["filterType"] == "LOT_SIZE":
                        min_qty = Decimal(filter_item["minQty"])
                        step_size = Decimal(filter_item.get("stepSize", "0"))
                    elif filter_item["filterType"] == "NOTIONAL":
                        min_notional = Decimal(filter_item.get("minNotional", "0"))
                    elif filter_item["filterType"] == "PRICE_FILTER":
                        tick_size = Decimal(filter_item.get("tickSize", "0"))

                symbols.append(
                    SymbolInfo(
                        symbol=item["symbol"],
                        base_asset=item["baseAsset"],
                        quote_asset=item["quoteAsset"],
                        status=item["status"],
                        min_qty=min_qty,
                        min_notional=min_notional,
                        step_size=step_size,
                        tick_size=tick_size,
                        price_precision=item["quotePrecision"],
                        qty_precision=item["baseAssetPrecision"],
                    )
                )

            return symbols
        except Exception:
            return []

    def get_symbol_price(self, symbol: str) -> Decimal:
        """Get current symbol price."""
        try:
            data = self._request("GET", "/api/v3/ticker/price", params={"symbol": symbol})
            return Decimal(data["price"])
        except Exception:
            return Decimal("0")

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        """Place an order on Binance.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            order_type: "LIMIT" or "MARKET"
            quantity: Order quantity
            price: Order price (required for LIMIT orders)
            time_in_force: Time in force (GTC, IOC, FOK)

        Returns:
            Order response from Binance
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),
        }

        if order_type == "LIMIT":
            if price is None:
                raise ValueError("Price is required for LIMIT orders")
            params["price"] = str(price)
            params["timeInForce"] = time_in_force

        return self._request("POST", "/api/v3/order", params=params, signed=True)

    def query_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Query order status.

        Args:
            symbol: Trading pair
            order_id: Binance order ID

        Returns:
            Order details from Binance
        """
        params = {
            "symbol": symbol,
            "orderId": order_id,
        }
        return self._request("GET", "/api/v3/order", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an order.

        Args:
            symbol: Trading pair
            order_id: Binance order ID

        Returns:
            Cancellation response from Binance
        """
        params = {
            "symbol": symbol,
            "orderId": order_id,
        }
        return self._request("DELETE", "/api/v3/order", params=params, signed=True)

    def create_listen_key(self) -> str:
        """Create a listen key for User Data Stream.

        Returns:
            Listen key string
        """
        response = self._request("POST", "/api/v3/userDataStream", signed=False)
        return response["listenKey"]

    def keepalive_listen_key(self, listen_key: str) -> None:
        """Keep alive a listen key for User Data Stream.

        Args:
            listen_key: The listen key to keep alive
        """
        params = {"listenKey": listen_key}
        self._request("PUT", "/api/v3/userDataStream", params=params, signed=False)

    def close_listen_key(self, listen_key: str) -> None:
        """Close a listen key for User Data Stream.

        Args:
            listen_key: The listen key to close
        """
        params = {"listenKey": listen_key}
        self._request("DELETE", "/api/v3/userDataStream", params=params, signed=False)
