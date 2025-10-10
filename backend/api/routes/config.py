from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api import get_config_service
from backend.models import TestConnectionResponse
from backend.services import ConfigService

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/test-connection", response_model=TestConnectionResponse)
def test_connection(service: ConfigService = Depends(get_config_service)) -> TestConnectionResponse:
    connected = service.test_connection()
    return TestConnectionResponse(success=True, connected=connected, can_trade=connected)
