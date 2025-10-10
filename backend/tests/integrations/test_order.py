from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Generator, Tuple
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.api import get_db
from backend.entities import Grid, GridStatus, Order, OrderSide, OrderStatus, OrderType
from backend.main import app
from backend.repositories import create_test_session


@pytest.fixture
def client(tmp_path: Path) -> Generator[Tuple[TestClient, sessionmaker], None, None]:
    db_path = tmp_path / "order_test.db"
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


def test_get_orders_empty(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, _session_factory = client

    response = test_client.get("/api/v1/orders")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["limit"] == 20
    assert data["orders"] == []


def test_get_orders_with_data(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client

    # Create test data
    grid_id = str(uuid4())
    order_new_id = str(uuid4())
    order_filled_id = str(uuid4())
    session = session_factory()
    try:
        grid = Grid(
            id=grid_id,
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
            id=order_new_id,
            grid_id=grid_id,
            grid_level=1,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            filled_quantity=Decimal("0"),
            status=OrderStatus.NEW,
        )
        order2 = Order(
            id=order_filled_id,
            grid_id=grid_id,
            grid_level=2,
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            type=OrderType.LIMIT,
            price=Decimal("41000"),
            quantity=Decimal("0.025"),
            filled_quantity=Decimal("0.025"),
            status=OrderStatus.FILLED,
        )
        session.add_all([order1, order2])
        session.commit()
    finally:
        session.close()

    response = test_client.get("/api/v1/orders")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 2
    assert len(data["orders"]) == 2
    assert data["orders"][0]["id"] == order_filled_id  # Ordered by created_at desc
    assert data["orders"][1]["id"] == order_new_id


def test_get_orders_with_pagination(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client

    # Create test data
    grid_id = str(uuid4())
    session = session_factory()
    try:
        grid = Grid(
            id=grid_id,
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

        # Create 5 orders
        order_ids = [str(uuid4()) for _ in range(5)]
        for i in range(5):
            order = Order(
                id=order_ids[i],
                grid_id=grid_id,
                grid_level=i + 1,
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                price=Decimal("40000") + Decimal(i * 1000),
                quantity=Decimal("0.025"),
                filled_quantity=Decimal("0"),
                status=OrderStatus.NEW,
            )
            session.add(order)
        session.commit()
    finally:
        session.close()

    # Test first page with limit 2
    response = test_client.get("/api/v1/orders?page=1&limit=2")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["limit"] == 2
    assert len(data["orders"]) == 2
    assert data["orders"][0]["id"] in order_ids
    assert data["orders"][1]["id"] in order_ids

    # Test second page
    response = test_client.get("/api/v1/orders?page=2&limit=2")

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert len(data["orders"]) == 2


def test_get_orders_filter_by_grid_id(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client

    # Create test data with two grids
    grid_primary_id = str(uuid4())
    grid_secondary_id = str(uuid4())
    session = session_factory()
    try:
        grid1 = Grid(
            id=grid_primary_id,
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
            id=grid_secondary_id,
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
            id=str(uuid4()),
            grid_id=grid_primary_id,
            grid_level=1,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            filled_quantity=Decimal("0"),
            status=OrderStatus.NEW,
        )
        order2 = Order(
            id=str(uuid4()),
            grid_id=grid_secondary_id,
            grid_level=1,
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("2000"),
            quantity=Decimal("0.25"),
            filled_quantity=Decimal("0"),
            status=OrderStatus.NEW,
        )
        session.add_all([order1, order2])
        session.commit()
    finally:
        session.close()

    response = test_client.get(f"/api/v1/orders?grid_id={grid_primary_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 1
    assert len(data["orders"]) == 1
    assert data["orders"][0]["grid_id"] == grid_primary_id


def test_get_orders_filter_by_status(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client

    # Create test data
    grid_id = str(uuid4())
    filled_order_id = str(uuid4())
    session = session_factory()
    try:
        grid = Grid(
            id=grid_id,
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
            id=str(uuid4()),
            grid_id=grid_id,
            grid_level=1,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            filled_quantity=Decimal("0"),
            status=OrderStatus.NEW,
        )
        order2 = Order(
            id=filled_order_id,
            grid_id=grid_id,
            grid_level=2,
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            type=OrderType.LIMIT,
            price=Decimal("41000"),
            quantity=Decimal("0.025"),
            filled_quantity=Decimal("0.025"),
            status=OrderStatus.FILLED,
        )
        session.add_all([order1, order2])
        session.commit()
    finally:
        session.close()

    response = test_client.get("/api/v1/orders?status=filled")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 1
    assert len(data["orders"]) == 1
    assert data["orders"][0]["status"] == OrderStatus.FILLED.value
    assert data["orders"][0]["id"] == filled_order_id


def test_get_orders_invalid_status(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, _session_factory = client

    response = test_client.get("/api/v1/orders?status=invalid_status")

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "Unsupported order status" in data["error"]


def test_cancel_order_success(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client

    # Create test data
    grid_id = str(uuid4())
    order_id = str(uuid4())
    session = session_factory()
    try:
        grid = Grid(
            id=grid_id,
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
            id=order_id,
            grid_id=grid_id,
            grid_level=1,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=Decimal("40000"),
            quantity=Decimal("0.025"),
            filled_quantity=Decimal("0"),
            status=OrderStatus.NEW,
        )
        session.add(order)
        session.commit()
    finally:
        session.close()

    response = test_client.delete(f"/api/v1/orders/{order_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Order cancelled successfully"
    assert data["order_id"] == order_id

    # Verify order status was updated
    session = session_factory()
    try:
        from sqlalchemy import select

        order = session.execute(select(Order).where(Order.id == order_id)).scalar_one()
        assert order.status == OrderStatus.CANCELLED
    finally:
        session.close()


def test_cancel_order_not_found(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, _session_factory = client

    response = test_client.delete("/api/v1/orders/nonexistent-order")

    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert "not found" in data["error"]
