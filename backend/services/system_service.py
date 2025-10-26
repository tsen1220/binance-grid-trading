from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from backend.config import settings
from backend.repositories import GridRepository
from backend.services import ConfigService
from backend.utils import format_timedelta

if TYPE_CHECKING:
    from backend.services import WebSocketMonitorService


class SystemService:
    def __init__(
        self,
        session: Session,
        config_service: ConfigService,
        ws_monitor: Optional[WebSocketMonitorService] = None,
    ) -> None:
        self.session = session
        self.config_service = config_service
        self.grid_repository = GridRepository(session)
        self._started_at = datetime.now(timezone.utc)
        self.ws_monitor = ws_monitor

    def get_status(self) -> dict:
        active_grid = self.grid_repository.find_active_grid()
        try:
            client = self.config_service.create_client()
            binance_connected = client.test_connection()
            testnet_mode = client.testnet
        except Exception:
            binance_connected = False
            testnet_mode = False

        # Get WebSocket status if monitor is available
        ws_status = {
            "running": False,
            "is_connected": False,
            "connected_at": None,
            "last_message_at": None,
            "reconnect_count": 0,
            "uptime": None,
        }
        if self.ws_monitor:
            ws_status = self.ws_monitor.get_status()

        uptime = format_timedelta(datetime.now(timezone.utc) - self._started_at)
        return {
            "status": "running",
            "uptime": uptime,
            "active_grids": 1 if active_grid else 0,
            "binance_connected": binance_connected,
            "testnet_mode": testnet_mode,
            "version": settings.app.version,
            "websocket": ws_status,
        }

    def health(self) -> dict:
        return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}


__all__ = ["SystemService"]
