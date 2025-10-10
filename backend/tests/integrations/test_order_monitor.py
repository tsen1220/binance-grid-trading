from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Generator, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.api import get_db
from backend.entities import Grid, GridLevel, GridLevelStatus, GridStatus, Order, OrderSide, OrderStatus, OrderType
from backend.main import app
from backend.repositories import create_test_session
from backend.services import ConfigService
from backend.services.order_pairing_service import OrderPairingService
from backend.tests.mocks.binance_client import MockBinanceClient

GRID_ID_ALPHA = "11111111-1111-1111-1111-111111111111"
GRID_ID_BETA = "22222222-2222-2222-2222-222222222222"
GRID_ID_GAMMA = "33333333-3333-3333-3333-333333333333"

BUY_ORDER_ID_1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
BUY_ORDER_ID_2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
BUY_ORDER_ID_3 = "cccccccc-cccc-cccc-cccc-cccccccccccc"
BUY_ORDER_ID_4 = "dddddddd-dddd-dddd-dddd-dddddddddddd"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Tuple[TestClient, sessionmaker], None, None]:
    db_path = tmp_path / "order_monitor_test.db"
    session_factory, engine = create_test_session(f"sqlite:///{db_path}")

    # Mock BinanceClient
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


def test_order_monitor_creates_sell_order_when_buy_fills(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test that OrderPairingService creates a SELL order when a BUY order fills."""
    _test_client, session_factory = client

    session = session_factory()
    try:
        # Create a grid
        grid = Grid(
            id=GRID_ID_ALPHA,
            trading_pair="BTCUSDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_count=5,
            grid_spacing=Decimal("2500"),
            total_investment=Decimal("10000"),
            investment_per_grid=Decimal("2000"),
            status=GridStatus.RUNNING,
        )
        session.add(grid)

        # Create grid levels
        levels = [
            GridLevel(grid_id=GRID_ID_ALPHA, level_index=0, price=Decimal("40000"), status=GridLevelStatus.IDLE),
            GridLevel(grid_id=GRID_ID_ALPHA, level_index=1, price=Decimal("42500"), status=GridLevelStatus.IDLE),
            GridLevel(grid_id=GRID_ID_ALPHA, level_index=2, price=Decimal("45000"), status=GridLevelStatus.IDLE),
            GridLevel(grid_id=GRID_ID_ALPHA, level_index=3, price=Decimal("47500"), status=GridLevelStatus.IDLE),
            GridLevel(grid_id=GRID_ID_ALPHA, level_index=4, price=Decimal("50000"), status=GridLevelStatus.IDLE),
        ]
        session.add_all(levels)

        # Create a FILLED BUY order at level 1 ($42,500)
        buy_order = Order(
            id=BUY_ORDER_ID_1,
            grid_id=GRID_ID_ALPHA,
            grid_level=1,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("42500"),
            quantity=Decimal("0.047"),
            filled_quantity=Decimal("0.047"),
            status=OrderStatus.FILLED,
        )
        session.add(buy_order)
        session.commit()

        # Run the pairing service
        config_service = ConfigService()
        client = config_service.create_client()
        pairing_service = OrderPairingService(session, client)
        created_count = pairing_service.process_filled_buys_without_pair(GRID_ID_ALPHA)

        # Should create 1 SELL order
        assert created_count == 1

        # Verify SELL order was created at level 2 ($45,000)
        sell_orders = session.query(Order).filter(Order.side == OrderSide.SELL).all()
        assert len(sell_orders) == 1

        sell_order = sell_orders[0]
        assert sell_order.grid_level == 2
        assert sell_order.price == Decimal("45000")
        assert sell_order.quantity == Decimal("0.047")  # Same quantity as BUY
        assert sell_order.status == OrderStatus.NEW
        assert sell_order.paired_order_id == BUY_ORDER_ID_1  # Verify pairing

    finally:
        session.close()


def test_order_monitor_does_not_duplicate_sell_orders(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test that OrderPairingService doesn't create duplicate SELL orders when run multiple times."""
    _test_client, session_factory = client

    session = session_factory()
    try:
        # Create a grid
        grid = Grid(
            id=GRID_ID_BETA,
            trading_pair="BTCUSDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_count=3,
            grid_spacing=Decimal("5000"),
            total_investment=Decimal("10000"),
            investment_per_grid=Decimal("5000"),
            status=GridStatus.RUNNING,
        )
        session.add(grid)

        # Create grid levels
        levels = [
            GridLevel(grid_id=GRID_ID_BETA, level_index=0, price=Decimal("40000"), status=GridLevelStatus.IDLE),
            GridLevel(grid_id=GRID_ID_BETA, level_index=1, price=Decimal("45000"), status=GridLevelStatus.IDLE),
            GridLevel(grid_id=GRID_ID_BETA, level_index=2, price=Decimal("50000"), status=GridLevelStatus.IDLE),
        ]
        session.add_all(levels)

        # Create a FILLED BUY order at level 0
        buy_order = Order(
            id=BUY_ORDER_ID_2,
            grid_id=GRID_ID_BETA,
            grid_level=0,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.125"),
            filled_quantity=Decimal("0.125"),
            status=OrderStatus.FILLED,
        )
        session.add(buy_order)
        session.commit()

        # Run the pairing service - should create SELL at level 1
        config_service = ConfigService()
        client = config_service.create_client()
        pairing_service = OrderPairingService(session, client)
        created_count = pairing_service.process_filled_buys_without_pair(GRID_ID_BETA)
        assert created_count == 1

        # Verify SELL order was created at level 1
        sell_orders = session.query(Order).filter(Order.side == OrderSide.SELL).all()
        assert len(sell_orders) == 1
        assert sell_orders[0].grid_level == 1
        assert sell_orders[0].price == Decimal("45000")
        assert sell_orders[0].paired_order_id == BUY_ORDER_ID_2  # Verify pairing

        # Run the pairing service AGAIN - should NOT create duplicate
        created_count = pairing_service.process_filled_buys_without_pair(GRID_ID_BETA)
        assert created_count == 0

        # Verify still only 1 SELL order exists
        sell_orders = session.query(Order).filter(Order.side == OrderSide.SELL).all()
        assert len(sell_orders) == 1

        # Run one more time to be sure
        created_count = pairing_service.process_filled_buys_without_pair(GRID_ID_BETA)
        assert created_count == 0

        sell_orders = session.query(Order).filter(Order.side == OrderSide.SELL).all()
        assert len(sell_orders) == 1

    finally:
        session.close()


def test_order_monitor_does_not_recreate_sell_after_filled(client: Tuple[TestClient, sessionmaker]) -> None:
    """Test that OrderPairingService does NOT recreate SELL after it's FILLED.

    This test verifies the fix for the inventory tracking bug where a SELL
    would be recreated for the same BUY after the original SELL was filled,
    resulting in selling non-existent inventory.
    """
    _test_client, session_factory = client

    session = session_factory()
    try:
        # Create a grid
        grid = Grid(
            id=GRID_ID_GAMMA,
            trading_pair="BTCUSDT",
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_count=3,
            grid_spacing=Decimal("5000"),
            total_investment=Decimal("10000"),
            investment_per_grid=Decimal("5000"),
            status=GridStatus.RUNNING,
        )
        session.add(grid)

        # Create grid levels
        levels = [
            GridLevel(grid_id=GRID_ID_GAMMA, level_index=0, price=Decimal("40000"), status=GridLevelStatus.IDLE),
            GridLevel(grid_id=GRID_ID_GAMMA, level_index=1, price=Decimal("45000"), status=GridLevelStatus.IDLE),
            GridLevel(grid_id=GRID_ID_GAMMA, level_index=2, price=Decimal("50000"), status=GridLevelStatus.IDLE),
        ]
        session.add_all(levels)

        # Create a FILLED BUY order at level 0
        buy_order_1 = Order(
            id=BUY_ORDER_ID_3,
            grid_id=GRID_ID_GAMMA,
            grid_level=0,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.125"),
            filled_quantity=Decimal("0.125"),
            status=OrderStatus.FILLED,
        )
        session.add(buy_order_1)
        session.commit()

        # Run the pairing service - should create SELL at level 1
        config_service = ConfigService()
        client = config_service.create_client()
        pairing_service = OrderPairingService(session, client)
        created_count = pairing_service.process_filled_buys_without_pair(GRID_ID_GAMMA)
        assert created_count == 1

        # Verify SELL order was created at level 1 and paired to BUY
        sell_orders = session.query(Order).filter(Order.side == OrderSide.SELL).all()
        assert len(sell_orders) == 1
        sell_order_1 = sell_orders[0]
        assert sell_order_1.grid_level == 1
        assert sell_order_1.status == OrderStatus.NEW
        assert sell_order_1.paired_order_id == buy_order_1.id  # Verify pairing

        # Simulate the SELL order being filled
        sell_order_1.status = OrderStatus.FILLED
        sell_order_1.filled_quantity = sell_order_1.quantity
        session.commit()

        # Run the pairing service AGAIN - should NOT create another SELL
        # for the same BUY because inventory has already been sold
        created_count = pairing_service.process_filled_buys_without_pair(GRID_ID_GAMMA)
        assert created_count == 0

        # Verify still only 1 SELL order exists
        sell_orders = session.query(Order).filter(Order.side == OrderSide.SELL).all()
        assert len(sell_orders) == 1

        # Create another FILLED BUY order at level 0 (grid cycling)
        buy_order_2 = Order(
            id=BUY_ORDER_ID_4,
            grid_id=GRID_ID_GAMMA,
            grid_level=0,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.125"),
            filled_quantity=Decimal("0.125"),
            status=OrderStatus.FILLED,
        )
        session.add(buy_order_2)
        session.commit()

        # Run the pairing service - should create NEW SELL for the NEW BUY
        created_count = pairing_service.process_filled_buys_without_pair(GRID_ID_GAMMA)
        assert created_count == 1

        # Verify a new SELL order was created at level 1 for the new BUY
        sell_orders = session.query(Order).filter(Order.side == OrderSide.SELL).all()
        assert len(sell_orders) == 2  # One for first BUY (FILLED), one for second BUY (NEW)

        # Find the new SELL order
        new_sells = [sell for sell in sell_orders if sell.status == OrderStatus.NEW]
        assert len(new_sells) == 1
        assert new_sells[0].grid_level == 1
        assert new_sells[0].price == Decimal("45000")
        assert new_sells[0].paired_order_id == buy_order_2.id  # Paired to second BUY

    finally:
        session.close()
