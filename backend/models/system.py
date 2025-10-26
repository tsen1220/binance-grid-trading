from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .base import APIResponse


class WebSocketStatus(BaseModel):
    """WebSocket connection status details."""

    running: bool
    is_connected: bool
    connected_at: Optional[float] = None
    last_message_at: Optional[float] = None
    reconnect_count: int = 0
    uptime: Optional[float] = None


class SystemStatusResponse(APIResponse):
    status: str
    uptime: str
    active_grids: int
    binance_connected: bool
    testnet_mode: bool
    version: str
    websocket: WebSocketStatus


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
