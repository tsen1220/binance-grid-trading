from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.config import settings as default_settings
from backend.main import app
from backend.tests.mocks.binance_client import MockBinanceClient

TEST_API_SECRET = "test-api-secret"


def _override_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    api_key: str | None,
    api_secret: str | None,
    testnet: bool = True,
) -> None:
    new_binance = replace(default_settings.binance, api_key=api_key, api_secret=api_secret, testnet=testnet)
    new_settings = replace(default_settings, binance=new_binance)

    for target in (
        "backend.config.config.settings",
        "backend.config.settings",
        "backend.services.config_service.settings",
        "backend.services.system_service.settings",
    ):
        monkeypatch.setattr(target, new_settings, raising=False)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("backend.repositories.database.init_db", lambda: None)
    monkeypatch.setattr("backend.repositories.init_db", lambda: None)
    monkeypatch.setattr("backend.core.binance_client.BinanceClient", MockBinanceClient)
    monkeypatch.setattr("backend.services.config_service.BinanceClient", MockBinanceClient)

    with TestClient(app) as test_client:
        yield test_client


def test_list_symbols_without_config(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _override_settings(monkeypatch, api_key=None, api_secret=None)

    response = client.get("/api/v1/symbols")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["symbols"]) >= 2


def test_list_symbols_returns_all_symbols(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _override_settings(monkeypatch, api_key="test-key", api_secret=TEST_API_SECRET, testnet=True)

    response = client.get("/api/v1/symbols")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "symbols" in data
    assert len(data["symbols"]) >= 2  # Mock client returns BTCUSDT and ETHUSDT

    symbol = data["symbols"][0]
    assert "symbol" in symbol
    assert "base_asset" in symbol
    assert "quote_asset" in symbol
    assert "status" in symbol
    assert "min_qty" in symbol
    assert "min_notional" in symbol
    assert "step_size" in symbol
    assert "tick_size" in symbol
    assert "price_precision" in symbol
    assert "qty_precision" in symbol


def test_list_symbols_includes_btcusdt(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _override_settings(monkeypatch, api_key="test-key", api_secret=TEST_API_SECRET, testnet=True)

    response = client.get("/api/v1/symbols")

    assert response.status_code == 200
    data = response.json()
    btcusdt = next((s for s in data["symbols"] if s["symbol"] == "BTCUSDT"), None)
    assert btcusdt is not None
    assert btcusdt["base_asset"] == "BTC"
    assert btcusdt["quote_asset"] == "USDT"
    assert btcusdt["status"] == "TRADING"
    assert float(btcusdt["min_qty"]) > 0
    assert float(btcusdt["min_notional"]) > 0
    assert float(btcusdt["step_size"]) > 0
    assert float(btcusdt["tick_size"]) > 0
    assert btcusdt["price_precision"] >= 0
    assert btcusdt["qty_precision"] >= 0


def test_list_symbols_filter_by_quote_asset_usdt(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _override_settings(monkeypatch, api_key="test-key", api_secret=TEST_API_SECRET, testnet=True)

    response = client.get("/api/v1/symbols?quote_asset=USDT")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["symbols"]) >= 2
    for symbol in data["symbols"]:
        assert symbol["quote_asset"] == "USDT"


def test_list_symbols_filter_by_quote_asset_btc(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _override_settings(monkeypatch, api_key="test-key", api_secret=TEST_API_SECRET, testnet=True)

    response = client.get("/api/v1/symbols?quote_asset=BTC")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["symbols"]) == 0  # Mock client has no BTC quote symbols


def test_list_symbols_with_testnet_false(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _override_settings(monkeypatch, api_key="test-key", api_secret=TEST_API_SECRET, testnet=False)

    response = client.get("/api/v1/symbols")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["symbols"]) >= 2


def test_list_symbols_returns_decimal_values(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _override_settings(monkeypatch, api_key="test-key", api_secret=TEST_API_SECRET, testnet=True)

    response = client.get("/api/v1/symbols")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["symbols"]) > 0

    symbol = data["symbols"][0]
    assert isinstance(symbol["min_qty"], str)
    assert isinstance(symbol["min_notional"], str)
    assert isinstance(symbol["step_size"], str)
    assert isinstance(symbol["tick_size"], str)
    assert isinstance(symbol["price_precision"], int)
    assert isinstance(symbol["qty_precision"], int)
