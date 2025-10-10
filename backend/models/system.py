from datetime import datetime

from pydantic import BaseModel

from .base import APIResponse


class SystemStatusResponse(APIResponse):
    status: str
    uptime: str
    active_grids: int
    binance_connected: bool
    testnet_mode: bool
    version: str


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
