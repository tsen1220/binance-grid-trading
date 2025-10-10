from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.config import settings
from backend.repositories import GridRepository
from backend.services import ConfigService
from backend.utils import format_timedelta


class SystemService:
    def __init__(self, session: Session, config_service: ConfigService) -> None:
        self.session = session
        self.config_service = config_service
        self.grid_repository = GridRepository(session)
        self._started_at = datetime.now(timezone.utc)

    def get_status(self) -> dict:
        active_grid = self.grid_repository.find_active_grid()
        try:
            client = self.config_service.create_client()
            binance_connected = client.test_connection()
            testnet_mode = client.testnet
        except Exception:
            binance_connected = False
            testnet_mode = False

        uptime = format_timedelta(datetime.now(timezone.utc) - self._started_at)
        return {
            "status": "running",
            "uptime": uptime,
            "active_grids": 1 if active_grid else 0,
            "binance_connected": binance_connected,
            "testnet_mode": testnet_mode,
            "version": settings.app.version,
        }

    def health(self) -> dict:
        return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}


__all__ = ["SystemService"]
