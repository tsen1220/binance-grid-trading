from __future__ import annotations

from datetime import datetime, timedelta, UTC
from decimal import Decimal
from pathlib import Path
from typing import Generator, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.api import get_db
from backend.entities import Grid, GridStatus, Order, OrderSide, OrderStatus, OrderType, Trade, TradeSide
from backend.main import app
from backend.repositories import create_test_session

GRID_ID_PRIMARY = "11111111-1111-1111-1111-111111111111"
GRID_ID_SECONDARY = "22222222-2222-2222-2222-222222222222"

ORDER_ID_PRIMARY = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ORDER_ID_SECONDARY = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ORDER_ID_TERTIARY = "cccccccc-cccc-cccc-cccc-cccccccccccc"

TRADE_ID_PRIMARY = "dddddddd-dddd-dddd-dddd-dddddddddddd"
TRADE_ID_SECONDARY = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
TRADE_ID_TERTIARY = "ffffffff-ffff-ffff-ffff-ffffffffffff"

TRADE_ID_BATCH = [
    "20000000-0000-0000-0000-000000000001",
    "20000000-0000-0000-0000-000000000002",
    "20000000-0000-0000-0000-000000000003",
    "20000000-0000-0000-0000-000000000004",
    "20000000-0000-0000-0000-000000000005",
]


@pytest.fixture
def client(tmp_path: Path) -> Generator[Tuple[TestClient, sessionmaker], None, None]:
    db_path = tmp_path / "trade_test.db"
    session_factory, engine = create_test_session(f"sqlite:///{db_path}")

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


def test_get_trades_empty(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, _session_factory = client

    response = test_client.get("/api/v1/trades")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["limit"] == 20
    assert data["trades"] == []


def test_get_trades_with_data(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client

    # Create test data
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

        order = Order(
            id=ORDER_ID_PRIMARY,
            grid_id=GRID_ID_PRIMARY,
            grid_level=1,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            filled_quantity=Decimal("0.025"),
            status=OrderStatus.FILLED,
        )
        session.add(order)

        trade1 = Trade(
            id=TRADE_ID_PRIMARY,
            grid_id=GRID_ID_PRIMARY,
            order_id=ORDER_ID_PRIMARY,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            quote_quantity=Decimal("1000"),
            commission=Decimal("0.00025"),
            commission_asset="BTC",
            is_maker=True,
        )
        trade2 = Trade(
            id=TRADE_ID_SECONDARY,
            grid_id=GRID_ID_PRIMARY,
            order_id=ORDER_ID_PRIMARY,
            symbol="BTCUSDT",
            side=TradeSide.SELL,
            price=Decimal("41000"),
            quantity=Decimal("0.025"),
            quote_quantity=Decimal("1025"),
            commission=Decimal("1.025"),
            commission_asset="USDT",
            is_maker=False,
        )
        session.add_all([trade1, trade2])
        session.commit()
    finally:
        session.close()

    response = test_client.get("/api/v1/trades")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 2
    assert len(data["trades"]) == 2
    # Trades are ordered by timestamp desc
    assert data["trades"][0]["id"] == TRADE_ID_SECONDARY
    assert data["trades"][1]["id"] == TRADE_ID_PRIMARY


def test_get_trades_with_pagination(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client

    # Create test data
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

        order = Order(
            id=ORDER_ID_PRIMARY,
            grid_id=GRID_ID_PRIMARY,
            grid_level=1,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.125"),
            filled_quantity=Decimal("0.125"),
            status=OrderStatus.FILLED,
        )
        session.add(order)

        # Create 5 trades
        for i in range(5):
            trade = Trade(
                id=TRADE_ID_BATCH[i],
                grid_id=GRID_ID_PRIMARY,
                order_id=ORDER_ID_PRIMARY,
                symbol="BTCUSDT",
                side=TradeSide.BUY,
                price=Decimal("40000") + Decimal(i * 100),
                quantity=Decimal("0.025"),
                quote_quantity=Decimal("1000") + Decimal(i * 100),
                is_maker=True,
            )
            session.add(trade)
        session.commit()
    finally:
        session.close()

    # Test first page with limit 2
    response = test_client.get("/api/v1/trades?page=1&limit=2")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["limit"] == 2
    assert len(data["trades"]) == 2

    # Test second page
    response = test_client.get("/api/v1/trades?page=2&limit=2")

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert len(data["trades"]) == 2


def test_get_trades_filter_by_grid_id(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client

    # Create test data with two grids
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
            status=GridStatus.RUNNING,
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
            status=GridStatus.RUNNING,
        )
        session.add_all([grid1, grid2])

        order1 = Order(
            id=ORDER_ID_PRIMARY,
            grid_id=GRID_ID_PRIMARY,
            grid_level=1,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            filled_quantity=Decimal("0.025"),
            status=OrderStatus.FILLED,
        )
        order2 = Order(
            id=ORDER_ID_SECONDARY,
            grid_id=GRID_ID_SECONDARY,
            grid_level=1,
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("2000"),
            quantity=Decimal("0.25"),
            filled_quantity=Decimal("0.25"),
            status=OrderStatus.FILLED,
        )
        session.add_all([order1, order2])

        trade1 = Trade(
            id=TRADE_ID_PRIMARY,
            grid_id=GRID_ID_PRIMARY,
            order_id=ORDER_ID_PRIMARY,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            quote_quantity=Decimal("1000"),
            is_maker=True,
        )
        trade2 = Trade(
            id=TRADE_ID_SECONDARY,
            grid_id=GRID_ID_SECONDARY,
            order_id=ORDER_ID_SECONDARY,
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            price=Decimal("2000"),
            quantity=Decimal("0.25"),
            quote_quantity=Decimal("500"),
            is_maker=True,
        )
        session.add_all([trade1, trade2])
        session.commit()
    finally:
        session.close()

    response = test_client.get(f"/api/v1/trades?grid_id={GRID_ID_PRIMARY}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 1
    assert len(data["trades"]) == 1
    assert data["trades"][0]["grid_id"] == GRID_ID_PRIMARY


def test_get_trades_filter_by_symbol(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client

    # Create test data
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

        order1 = Order(
            id=ORDER_ID_PRIMARY,
            grid_id=GRID_ID_PRIMARY,
            grid_level=1,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            filled_quantity=Decimal("0.025"),
            status=OrderStatus.FILLED,
        )
        order2 = Order(
            id=ORDER_ID_SECONDARY,
            grid_id=GRID_ID_PRIMARY,
            grid_level=2,
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("2000"),
            quantity=Decimal("0.25"),
            filled_quantity=Decimal("0.25"),
            status=OrderStatus.FILLED,
        )
        session.add_all([order1, order2])

        trade1 = Trade(
            id=TRADE_ID_PRIMARY,
            grid_id=GRID_ID_PRIMARY,
            order_id=ORDER_ID_PRIMARY,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            quote_quantity=Decimal("1000"),
            is_maker=True,
        )
        trade2 = Trade(
            id=TRADE_ID_SECONDARY,
            grid_id=GRID_ID_PRIMARY,
            order_id=ORDER_ID_SECONDARY,
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            price=Decimal("2000"),
            quantity=Decimal("0.25"),
            quote_quantity=Decimal("500"),
            is_maker=True,
        )
        session.add_all([trade1, trade2])
        session.commit()
    finally:
        session.close()

    response = test_client.get("/api/v1/trades?symbol=BTCUSDT")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 1
    assert len(data["trades"]) == 1
    assert data["trades"][0]["symbol"] == "BTCUSDT"


def test_get_trades_filter_by_date_range(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client

    # Create test data with different timestamps
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

        order = Order(
            id=ORDER_ID_PRIMARY,
            grid_id=GRID_ID_PRIMARY,
            grid_level=1,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.075"),
            filled_quantity=Decimal("0.075"),
            status=OrderStatus.FILLED,
        )
        session.add(order)

        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        trade1 = Trade(
            id=TRADE_ID_PRIMARY,
            grid_id=GRID_ID_PRIMARY,
            order_id=ORDER_ID_PRIMARY,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            quote_quantity=Decimal("1000"),
            timestamp=two_days_ago,
            is_maker=True,
        )
        trade2 = Trade(
            id=TRADE_ID_SECONDARY,
            grid_id=GRID_ID_PRIMARY,
            order_id=ORDER_ID_PRIMARY,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            price=Decimal("40100"),
            quantity=Decimal("0.025"),
            quote_quantity=Decimal("1002.5"),
            timestamp=yesterday,
            is_maker=True,
        )
        trade3 = Trade(
            id=TRADE_ID_TERTIARY,
            grid_id=GRID_ID_PRIMARY,
            order_id=ORDER_ID_PRIMARY,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            price=Decimal("40200"),
            quantity=Decimal("0.025"),
            quote_quantity=Decimal("1005"),
            timestamp=now,
            is_maker=True,
        )
        session.add_all([trade1, trade2, trade3])
        session.commit()
    finally:
        session.close()

    # Filter by start_date (use URL-encoded datetime)
    import urllib.parse
    start_date = (datetime.now(UTC) - timedelta(days=1, hours=1)).isoformat()
    start_date_encoded = urllib.parse.quote(start_date)
    response = test_client.get(f"/api/v1/trades?start_date={start_date_encoded}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 2  # trade2 and trade3

    # Filter by end_date
    end_date = (datetime.now(UTC) - timedelta(days=1, hours=-1)).isoformat()
    end_date_encoded = urllib.parse.quote(end_date)
    response = test_client.get(f"/api/v1/trades?end_date={end_date_encoded}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 2  # trade1 and trade2

    # Filter by date range
    start = (datetime.now(UTC) - timedelta(days=1, hours=1)).isoformat()
    end = (datetime.now(UTC) - timedelta(hours=-1)).isoformat()
    start_encoded = urllib.parse.quote(start)
    end_encoded = urllib.parse.quote(end)
    response = test_client.get(f"/api/v1/trades?start_date={start_encoded}&end_date={end_encoded}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 2  # trade2 and trade3


def test_get_trades_multiple_filters(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client

    # Create test data with two grids and multiple symbols
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
            status=GridStatus.RUNNING,
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
            status=GridStatus.RUNNING,
        )
        session.add_all([grid1, grid2])

        order1 = Order(
            id=ORDER_ID_PRIMARY,
            grid_id=GRID_ID_PRIMARY,
            grid_level=1,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            filled_quantity=Decimal("0.025"),
            status=OrderStatus.FILLED,
        )
        order2 = Order(
            id=ORDER_ID_SECONDARY,
            grid_id=GRID_ID_SECONDARY,
            grid_level=1,
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("2000"),
            quantity=Decimal("0.25"),
            filled_quantity=Decimal("0.25"),
            status=OrderStatus.FILLED,
        )
        order3 = Order(
            id=ORDER_ID_TERTIARY,
            grid_id=GRID_ID_PRIMARY,
            grid_level=2,
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("2100"),
            quantity=Decimal("0.25"),
            filled_quantity=Decimal("0.25"),
            status=OrderStatus.FILLED,
        )
        session.add_all([order1, order2, order3])

        trade1 = Trade(
            id=TRADE_ID_PRIMARY,
            grid_id=GRID_ID_PRIMARY,
            order_id=ORDER_ID_PRIMARY,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            quote_quantity=Decimal("1000"),
            is_maker=True,
        )
        trade2 = Trade(
            id=TRADE_ID_SECONDARY,
            grid_id=GRID_ID_SECONDARY,
            order_id=ORDER_ID_SECONDARY,
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            price=Decimal("2000"),
            quantity=Decimal("0.25"),
            quote_quantity=Decimal("500"),
            is_maker=True,
        )
        trade3 = Trade(
            id=TRADE_ID_TERTIARY,
            grid_id=GRID_ID_PRIMARY,
            order_id=ORDER_ID_TERTIARY,
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            price=Decimal("2100"),
            quantity=Decimal("0.25"),
            quote_quantity=Decimal("525"),
            is_maker=True,
        )
        session.add_all([trade1, trade2, trade3])
        session.commit()
    finally:
        session.close()

    # Filter by grid_id and symbol
    response = test_client.get(f"/api/v1/trades?grid_id={GRID_ID_PRIMARY}&symbol=ETHUSDT")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 1
    assert len(data["trades"]) == 1
    assert data["trades"][0]["grid_id"] == GRID_ID_PRIMARY
    assert data["trades"][0]["symbol"] == "ETHUSDT"
