from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.core import BinanceClient
from backend.entities import ApiConfig
from backend.repositories import ConfigRepository
from backend.utils import UnauthorizedError


class ConfigService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ConfigRepository(session)

    def configure_binance(self, *, api_key: str, api_secret: str, testnet: bool) -> ApiConfig:
        config = self.repository.save(api_key=api_key, api_secret=api_secret, testnet=testnet)
        self.session.commit()
        return config

    def get_active_config(self) -> ApiConfig:
        config = self.repository.get_latest()
        if not config:
            raise UnauthorizedError("Binance API credentials are not configured")
        return config

    def create_client(self) -> BinanceClient:
        config = self.get_active_config()
        return BinanceClient(api_key=config.api_key, api_secret=config.api_secret, testnet=config.testnet)

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

    def get_symbols(self, *, quote_asset: Optional[str] = None) -> list:
        client = self.create_client()
        symbols = client.get_supported_symbols(quote_asset=quote_asset)
        return [
            {
                "symbol": item.symbol,
                "base_asset": item.base_asset,
                "quote_asset": item.quote_asset,
                "status": item.status,
                "min_qty": str(item.min_qty),
                "min_notional": str(item.min_notional),
                "price_precision": item.price_precision,
                "qty_precision": item.qty_precision,
            }
            for item in symbols
        ]
