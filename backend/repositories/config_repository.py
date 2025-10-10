from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.entities import ApiConfig


class ConfigRepository:
    """Persistence for Binance API configuration."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_latest(self) -> Optional[ApiConfig]:
        stmt = select(ApiConfig).order_by(ApiConfig.updated_at.desc()).limit(1)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def save(self, api_key: str, api_secret: str, testnet: bool) -> ApiConfig:
        existing = self.get_latest()
        if existing:
            existing.api_key = api_key
            existing.api_secret = api_secret
            existing.testnet = testnet
            self.session.add(existing)
            self.session.flush()
            return existing

        config = ApiConfig(api_key=api_key, api_secret=api_secret, testnet=testnet)
        self.session.add(config)
        self.session.flush()
        return config
