from __future__ import annotations

from pathlib import Path
from typing import Generator, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.api import get_db
from backend.entities import ApiConfig
from backend.main import app
from backend.repositories import create_test_session


@pytest.fixture
def client(tmp_path: Path) -> Generator[Tuple[TestClient, sessionmaker], None, None]:
    db_path = tmp_path / "config_test.db"
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


def test_configure_binance_persists_credentials(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, session_factory = client
    payload = {
        "api_key": "test-key",
        "api_secret": "test-secret",
        "testnet": False,
    }

    response = test_client.post("/api/v1/config/binance", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "success": True,
        "message": "Binance API credentials configured successfully",
        "testnet": False,
    }

    session = session_factory()
    try:
        config = session.scalars(select(ApiConfig)).one()
    finally:
        session.close()

    assert config.api_key == payload["api_key"]
    assert config.api_secret == payload["api_secret"]
    assert config.testnet is payload["testnet"]


def test_test_connection_uses_persisted_credentials(client: Tuple[TestClient, sessionmaker]) -> None:
    test_client, _session_factory = client
    payload = {
        "api_key": "another-key",
        "api_secret": "another-secret",
        "testnet": True,
    }

    configure_response = test_client.post("/api/v1/config/binance", json=payload)
    assert configure_response.status_code == 200

    response = test_client.get("/api/v1/config/test-connection")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "success": True,
        "connected": True,
        "account_type": "SPOT",
        "can_trade": True,
    }
