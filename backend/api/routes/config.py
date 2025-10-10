from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api import get_config_service
from backend.models import BinanceConfigRequest, BinanceConfigResponse, TestConnectionResponse
from backend.services import ConfigService

router = APIRouter(prefix="/config", tags=["config"])


@router.post("/binance", response_model=BinanceConfigResponse)
def configure_binance(request: BinanceConfigRequest, service: ConfigService = Depends(get_config_service)) -> BinanceConfigResponse:
    config = service.configure_binance(api_key=request.api_key, api_secret=request.api_secret, testnet=request.testnet)
    return BinanceConfigResponse(success=True, message="Binance API credentials configured successfully", testnet=config.testnet)


@router.get("/test-connection", response_model=TestConnectionResponse)
def test_connection(service: ConfigService = Depends(get_config_service)) -> TestConnectionResponse:
    connected = service.test_connection()
    return TestConnectionResponse(success=True, connected=connected, can_trade=connected)
