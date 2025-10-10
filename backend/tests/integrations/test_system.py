from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Generator, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.api import get_db
from backend.config import settings as default_settings
from backend.entities import Grid, GridStatus
from backend.main import app
from backend.repositories import create_test_session
from backend.tests.mocks.binance_client import MockBinanceClient

TEST_API_SECRET = "test-api-secret"

GRID_ID_PRIMARY = "11111111-1111-1111-1111-111111111111"
GRID_ID_SECONDARY = "22222222-2222-2222-2222-222222222222"


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
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Tuple[TestClient, sessionmaker], None, None]:
    db_path = tmp_path / "system_test.db"
    session_factory, engine = create_test_session(f"sqlite:///{db_path}")

    monkeypatch.setattr("backend.repositories.database.init_db", lambda: None)
    monkeypatch.setattr("backend.repositories.init_db", lambda: None)
    monkeypatch.setattr("backend.core.binance_client.BinanceClient", MockBinanceClient)
    monkeypatch.setattr("backend.services.config_service.BinanceClient", MockBinanceClient)

    def override_get_db() -> Generator[Session, None, None]:
        session: Session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client, session_factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_health_check(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, _session_factory = client

    response = test_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_system_status_without_config(client: Tuple[TestClient, sessionmaker], monkeypatch: pytest.MonkeyPatch) -> None:
    test_client, _session_factory = client

    _override_settings(monkeypatch, api_key=None, api_secret=None)

    response = test_client.get("/api/v1/system/status")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "running"
    assert "uptime" in data
    assert data["active_grids"] == 0
    assert data["binance_connected"] is False
    assert data["testnet_mode"] is True
    assert "version" in data


def test_system_status_with_config(client: Tuple[TestClient, sessionmaker], monkeypatch: pytest.MonkeyPatch) -> None:
    test_client, _session_factory = client

    _override_settings(monkeypatch, api_key="test-key", api_secret=TEST_API_SECRET, testnet=True)

    response = test_client.get("/api/v1/system/status")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "running"
    assert "uptime" in data
    assert data["active_grids"] == 0
    assert data["binance_connected"] is True
    assert data["testnet_mode"] is True
    assert "version" in data


def test_system_status_with_active_grid(client: Tuple[TestClient, sessionmaker], monkeypatch: pytest.MonkeyPatch) -> None:
    test_client, session_factory = client

    _override_settings(monkeypatch, api_key="test-key", api_secret=TEST_API_SECRET, testnet=False)

    session = session_factory()
    try:
        grid = Grid(
            id=GRID_ID_PRIMARY,
            trading_pair="BTCUSDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_count=10,
            grid_spacing=Decimal("1000"),
            total_investment=Decimal("10000"),
            investment_per_grid=Decimal("1000"),
            status=GridStatus.RUNNING,
        )
        session.add(grid)
        session.commit()
    finally:
        session.close()

    response = test_client.get("/api/v1/system/status")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "running"
    assert data["active_grids"] == 1
    assert data["binance_connected"] is True
    assert data["testnet_mode"] is False


def test_system_status_with_multiple_stopped_grids(
    client: Tuple[TestClient, sessionmaker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, session_factory = client

    _override_settings(monkeypatch, api_key="test-key", api_secret=TEST_API_SECRET, testnet=True)

    session = session_factory()
    try:
        grid1 = Grid(
            id=GRID_ID_PRIMARY,
            trading_pair="BTCUSDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_count=10,
            grid_spacing=Decimal("1000"),
            total_investment=Decimal("10000"),
            investment_per_grid=Decimal("1000"),
            status=GridStatus.STOPPED,
        )
        grid2 = Grid(
            id=GRID_ID_SECONDARY,
            trading_pair="ETHUSDT",
            upper_price=Decimal("3000"),
            lower_price=Decimal("2000"),
            grid_count=10,
            grid_spacing=Decimal("100"),
            total_investment=Decimal("5000"),
            investment_per_grid=Decimal("500"),
            status=GridStatus.COMPLETED,
        )
        session.add_all([grid1, grid2])
        session.commit()
    finally:
        session.close()

    response = test_client.get("/api/v1/system/status")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["active_grids"] == 0


def test_system_status_uptime_format(client: Tuple[TestClient, sessionmaker], monkeypatch: pytest.MonkeyPatch) -> None:
    test_client, _session_factory = client

    _override_settings(monkeypatch, api_key="test-key", api_secret=TEST_API_SECRET, testnet=True)

    response = test_client.get("/api/v1/system/status")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["uptime"], str)
    assert len(data["uptime"]) > 0
