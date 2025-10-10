from __future__ import annotations

from typing import Optional

from backend.config import settings
from backend.core import BinanceClient
from backend.exceptions import UnauthorizedError


class ConfigService:
    def __init__(self) -> None:
        return

    def create_client(self) -> BinanceClient:
        return BinanceClient(
            api_key=settings.binance.api_key,
            api_secret=settings.binance.api_secret,
            testnet=settings.binance.testnet,
            binance_url=settings.binance.binance_url,
        )

    def test_connection(self) -> bool:
        client = self.create_client()
        return client.test_connection()

    def get_balances(self) -> list:
        client = self.create_client()
        balances = client.get_account_balances()
        return [
            {
                "asset": balance.asset,
                "free": str(balance.free),
                "locked": str(balance.locked),
            }
            for balance in balances
        ]

    def get_symbols(self, *, base_asset: Optional[str] = None, quote_asset: Optional[str] = None) -> list:
        client = self.create_client()
        symbols = client.get_supported_symbols(base_asset=base_asset, quote_asset=quote_asset)
        return [
            {
                "symbol": item.symbol,
                "base_asset": item.base_asset,
                "quote_asset": item.quote_asset,
                "status": item.status,
                "min_qty": str(item.min_qty),
                "min_notional": str(item.min_notional),
                "step_size": str(item.step_size),
                "tick_size": str(item.tick_size),
                "price_precision": item.price_precision,
                "qty_precision": item.qty_precision,
            }
            for item in symbols
        ]
