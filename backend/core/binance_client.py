from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Optional


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
    price_precision: int
    qty_precision: int


class BinanceClient:
    """Lightweight wrapper that can be swapped with a real Binance SDK implementation."""

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
            price_precision=2,
            qty_precision=5,
        ),
    )

    _DEFAULT_PRICES = {
        "BTCUSDT": Decimal("45000"),
        "ETHUSDT": Decimal("2200"),
    }

    def __init__(self, api_key: Optional[str], api_secret: Optional[str], *, testnet: bool = True) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

    def test_connection(self) -> bool:
        # In stub mode, a connection is considered valid when credentials exist.
        return bool(self.api_key and self.api_secret)

    def get_account_balances(self) -> List[Balance]:
        return list(self._DEFAULT_BALANCES)

    def get_supported_symbols(self, *, quote_asset: Optional[str] = None) -> List[SymbolInfo]:
        symbols: Iterable[SymbolInfo] = self._DEFAULT_SYMBOLS
        if quote_asset:
            symbols = [s for s in symbols if s.quote_asset == quote_asset]
        return list(symbols)

    def get_symbol_price(self, symbol: str) -> Decimal:
        return self._DEFAULT_PRICES.get(symbol, Decimal("0"))
