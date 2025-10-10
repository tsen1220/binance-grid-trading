from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Generator, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.api import get_db
from backend.config import settings as default_settings
from backend.entities import Grid, GridStatus, Order, OrderSide, OrderStatus, Trade
from backend.main import app
from backend.repositories import create_test_session
from backend.tests.mocks.binance_client import MockBinanceClient


# Shared mock client instance to preserve order state across test steps
_shared_mock_client: MockBinanceClient | None = None


class PersistentMockBinanceClient(MockBinanceClient):
    """Mock Binance client that persists orders across instances."""

    def __init__(self, api_key: str | None, api_secret: str | None, *, testnet: bool, binance_url: str) -> None:
        global _shared_mock_client
        super().__init__(api_key, api_secret, testnet=testnet, binance_url=binance_url)
        if _shared_mock_client is not None:
            # Reuse shared state
            self._orders = _shared_mock_client._orders
            self._order_id_counter = _shared_mock_client._order_id_counter
        _shared_mock_client = self


def _configure_test_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure test Binance credentials via settings override."""
    new_binance = replace(
        default_settings.binance,
        api_key="test_key",
        api_secret="test_secret",
        testnet=True,
    )
    new_settings = replace(default_settings, binance=new_binance)

    for target in (
        "backend.config.config.settings",
        "backend.config.settings",
        "backend.services.config_service.settings",
        "backend.services.grid_service.settings",
    ):
        monkeypatch.setattr(target, new_settings, raising=False)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Tuple[TestClient, sessionmaker], None, None]:
    global _shared_mock_client
    _shared_mock_client = None  # Reset for each test

    db_path = tmp_path / "grid_test.db"
    session_factory, engine = create_test_session(f"sqlite:///{db_path}")

    # Configure test credentials
    _configure_test_credentials(monkeypatch)

    # Mock BinanceClient with persistent state
    monkeypatch.setattr("backend.core.binance_client.BinanceClient", PersistentMockBinanceClient)
    monkeypatch.setattr("backend.services.config_service.BinanceClient", PersistentMockBinanceClient)

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


def test_start_grid_success(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test successfully starting a grid trading session."""
    test_client, session_factory = client

    # Start grid (credentials already configured via fixture)
    response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 50000,
            "lower_price": 40000,
            "grid_count": 5,
            "total_investment": 1000,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "grid_id" in data
    assert data["config"]["trading_pair"] == "BTCUSDT"
    assert data["config"]["grid_count"] == 5
    assert data["initial_orders"] == 5  # 5 BUY orders (excluding top level)

    # Verify grid was created in database
    session = session_factory()
    try:
        grid = session.query(Grid).filter(Grid.id == data["grid_id"]).first()
        assert grid is not None
        assert grid.status == GridStatus.RUNNING
        assert grid.trading_pair == "BTCUSDT"
        assert grid.grid_count == 5

        # Verify orders were created
        orders = session.query(Order).filter(Order.grid_id == grid.id).all()
        assert len(orders) == 5
        assert all(order.side == OrderSide.BUY for order in orders)
        assert all(order.status == OrderStatus.NEW for order in orders)
        assert all(order.binance_order_id is not None for order in orders)
    finally:
        session.close()


def test_start_grid_insufficient_balance(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test starting a grid with insufficient USDT balance."""
    test_client, _ = client

    # Try to start grid with investment exceeding balance (mock has 10000 USDT)
    response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 50000,
            "lower_price": 40000,
            "grid_count": 5,
            "total_investment": 20000,  # Exceeds mock balance
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "insufficient" in data["error"].lower()


def test_start_grid_already_running(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test starting a grid when another grid is already running."""
    test_client, _ = client

    # Start first grid
    response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 50000,
            "lower_price": 40000,
            "grid_count": 5,
            "total_investment": 1000,
        },
    )
    assert response.status_code == 200

    # Try to start second grid
    response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "ETHUSDT",
            "upper_price": 3000,
            "lower_price": 2000,
            "grid_count": 5,
            "total_investment": 1000,
        },
    )
    assert response.status_code == 409
    data = response.json()
    assert data["success"] is False
    assert "already running" in data["error"].lower()


def test_stop_grid_success(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test successfully stopping a grid trading session."""
    test_client, session_factory = client

    # Start grid
    start_response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 50000,
            "lower_price": 40000,
            "grid_count": 5,
            "total_investment": 1000,
        },
    )
    grid_id = start_response.json()["grid_id"]

    # Stop grid without cancelling orders
    response = test_client.post(
        "/api/v1/grid/stop",
        json={"grid_id": grid_id, "cancel_orders": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["cancelled_orders"] == 0

    # Verify grid was stopped in database
    session = session_factory()
    try:
        grid = session.query(Grid).filter(Grid.id == grid_id).first()
        assert grid is not None
        assert grid.status == GridStatus.STOPPED
        assert grid.stopped_at is not None

        # Verify orders are still NEW (not cancelled)
        orders = session.query(Order).filter(Order.grid_id == grid_id).all()
        assert all(order.status == OrderStatus.NEW for order in orders)
    finally:
        session.close()


def test_stop_grid_with_cancel_orders(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test stopping a grid and cancelling all pending orders."""
    test_client, session_factory = client

    # Start grid
    start_response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 50000,
            "lower_price": 40000,
            "grid_count": 5,
            "total_investment": 1000,
        },
    )
    grid_id = start_response.json()["grid_id"]

    # Stop grid and cancel orders
    response = test_client.post(
        "/api/v1/grid/stop",
        json={"grid_id": grid_id, "cancel_orders": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["cancelled_orders"] == 5  # All 5 BUY orders

    # Verify orders were cancelled in database
    session = session_factory()
    try:
        orders = session.query(Order).filter(Order.grid_id == grid_id).all()
        assert all(order.status == OrderStatus.CANCELLED for order in orders)
    finally:
        session.close()


def test_get_status_active_grid(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test getting status of an active grid."""
    test_client, _ = client

    # Start grid
    start_response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 50000,
            "lower_price": 40000,
            "grid_count": 5,
            "total_investment": 1000,
        },
    )
    grid_id = start_response.json()["grid_id"]

    # Get status
    response = test_client.get(f"/api/v1/grid/status?grid_id={grid_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["grid_id"] == grid_id
    assert data["status"] == "running"
    assert data["config"]["trading_pair"] == "BTCUSDT"
    assert data["statistics"]["buy_orders"] == 5
    assert data["statistics"]["sell_orders"] == 0
    assert data["statistics"]["active_orders"] == 5
    assert len(data["grids"]) == 6  # 6 levels (0-5)


def test_get_status_no_grid(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test getting status when no grid is running."""
    test_client, _ = client

    # Get status without starting grid
    response = test_client.get("/api/v1/grid/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "stopped"
    assert data["grid_id"] is None


def test_get_history(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test getting grid trading history."""
    test_client, _ = client

    # Start and stop first grid
    start_response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 50000,
            "lower_price": 40000,
            "grid_count": 5,
            "total_investment": 1000,
        },
    )
    grid_id_1 = start_response.json()["grid_id"]
    test_client.post("/api/v1/grid/stop", json={"grid_id": grid_id_1, "cancel_orders": True})

    # Start and stop second grid
    start_response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 48000,
            "lower_price": 42000,
            "grid_count": 10,
            "total_investment": 2000,
        },
    )
    grid_id_2 = start_response.json()["grid_id"]
    test_client.post("/api/v1/grid/stop", json={"grid_id": grid_id_2, "cancel_orders": True})

    # Get history
    response = test_client.get("/api/v1/grid/history?page=1&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 2
    assert len(data["grids"]) == 2
    assert all(grid["status"] == "stopped" for grid in data["grids"])


def test_invalid_grid_parameters(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test starting grid with invalid parameters."""
    test_client, _ = client

    # Test upper_price <= lower_price
    response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 40000,
            "lower_price": 50000,  # Invalid: lower > upper
            "grid_count": 5,
            "total_investment": 1000,
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False

    # Test invalid grid_count (too low) - Pydantic validation returns 422
    response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 50000,
            "lower_price": 40000,
            "grid_count": 2,  # Invalid: below minimum (5)
            "total_investment": 1000,
        },
    )
    assert response.status_code in {400, 422}  # Either is acceptable

    # Test invalid grid_count (too high)
    response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 50000,
            "lower_price": 40000,
            "grid_count": 150,  # Invalid: above maximum (100)
            "total_investment": 1000,
        },
    )
    assert response.status_code in {400, 422}

    # Test zero investment
    response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 50000,
            "lower_price": 40000,
            "grid_count": 5,
            "total_investment": 0,  # Invalid: must be > 0
        },
    )
    assert response.status_code in {400, 422}


def test_full_grid_trading_flow_with_filled_order(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test complete grid trading flow with simulated order fills."""
    test_client, session_factory = client

    # Start grid
    start_response = test_client.post(
        "/api/v1/grid/start",
        json={
            "trading_pair": "BTCUSDT",
            "upper_price": 50000,
            "lower_price": 40000,
            "grid_count": 5,
            "total_investment": 1000,
        },
    )
    assert start_response.status_code == 200
    grid_id = start_response.json()["grid_id"]

    # Verify initial state
    session = session_factory()
    try:
        buy_orders = (
            session.query(Order).filter(Order.grid_id == grid_id, Order.side == OrderSide.BUY).all()
        )
        assert len(buy_orders) == 5
        assert all(order.status == OrderStatus.NEW for order in buy_orders)

        # Simulate first BUY order being filled
        first_buy = buy_orders[0]
        first_buy.status = OrderStatus.FILLED
        first_buy.filled_quantity = first_buy.quantity
        session.commit()

        # In production, WebSocket would automatically create paired SELL
        # In tests, we need to manually trigger the pairing logic
        from backend.services import ConfigService
        from backend.services.order_pairing_service import OrderPairingService

        config_service = ConfigService()
        client = config_service.create_client()
        pairing_service = OrderPairingService(session, client)
        pairing_service.create_paired_sell_order(first_buy)
        session.commit()

    finally:
        session.close()

    # Verify SELL order was created for the filled BUY
    session = session_factory()
    try:
        sell_orders = (
            session.query(Order).filter(Order.grid_id == grid_id, Order.side == OrderSide.SELL).all()
        )
        assert len(sell_orders) == 1  # One SELL order created

        # Verify the SELL order is paired with the BUY order
        sell_order = sell_orders[0]
        assert sell_order.paired_order_id == first_buy.id
        assert sell_order.status == OrderStatus.NEW
    finally:
        session.close()

    # Stop grid
    stop_response = test_client.post(
        "/api/v1/grid/stop",
        json={"grid_id": grid_id, "cancel_orders": True},
    )
    assert stop_response.status_code == 200

    # Verify grid is stopped
    session = session_factory()
    try:
        grid = session.query(Grid).filter(Grid.id == grid_id).first()
        assert grid.status == GridStatus.STOPPED
        assert grid.stopped_at is not None
    finally:
        session.close()
