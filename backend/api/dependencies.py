from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.services import (
    ConfigService,
    GridService,
    OrderService,
    SystemService,
    TradeService,
)
from backend.utils import get_session


def get_db() -> Session:
    yield from get_session()


def get_config_service(db: Session = Depends(get_db)) -> ConfigService:
    return ConfigService(db)


def get_grid_service(db: Session = Depends(get_db), config_service: ConfigService = Depends(get_config_service)) -> GridService:
    return GridService(db, config_service)


def get_order_service(db: Session = Depends(get_db)) -> OrderService:
    return OrderService(db)


def get_trade_service(db: Session = Depends(get_db)) -> TradeService:
    return TradeService(db)


def get_system_service(db: Session = Depends(get_db), config_service: ConfigService = Depends(get_config_service)) -> SystemService:
    return SystemService(db, config_service)
