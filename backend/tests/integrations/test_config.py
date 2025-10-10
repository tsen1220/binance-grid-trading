from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.config import settings as default_settings
from backend.main import app
from backend.tests.mocks.binance_client import MockBinanceClient


def _override_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    api_key: str | None,
    api_secret: str | None,
    testnet: bool = True,
) -> None:
    """Replace runtime settings with in-memory credentials for tests."""
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


def test_test_connection_requires_credentials(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _override_settings(monkeypatch, api_key=None, api_secret=None)

    response = client.get("/api/v1/config/test-connection")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "success": True,
        "message": None,
        "connected": False,
        "account_type": "SPOT",
        "can_trade": False,
    }


def test_test_connection_with_configured_credentials(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _override_settings(monkeypatch, api_key="test-key", api_secret="test-secret", testnet=True)

    response = client.get("/api/v1/config/test-connection")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "success": True,
        "message": None,
        "connected": True,
        "account_type": "SPOT",
        "can_trade": True,
    }
