from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.repositories import get_session
from backend.services import (
    ConfigService,
    GridService,
    OrderService,
    SystemService,
    TradeService,
)

if TYPE_CHECKING:
    from backend.services import WebSocketMonitorService


def get_db() -> Session:
    yield from get_session()


def get_config_service() -> ConfigService:
    return ConfigService()


def get_grid_service(db: Session = Depends(get_db), config_service: ConfigService = Depends(get_config_service)) -> GridService:
    return GridService(db, config_service)


def get_order_service(db: Session = Depends(get_db), config_service: ConfigService = Depends(get_config_service)) -> OrderService:
    return OrderService(db, config_service)


def get_trade_service(db: Session = Depends(get_db)) -> TradeService:
    return TradeService(db)


def get_ws_monitor() -> WebSocketMonitorService | None:
    """Get the global WebSocket monitor instance."""
    from backend.main import get_ws_monitor as _get_ws_monitor

    return _get_ws_monitor()


def get_system_service(
    db: Session = Depends(get_db),
    config_service: ConfigService = Depends(get_config_service),
    ws_monitor: WebSocketMonitorService | None = Depends(get_ws_monitor),
) -> SystemService:
    return SystemService(db, config_service, ws_monitor)
