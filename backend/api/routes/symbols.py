from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api import get_config_service
from backend.models import SymbolsResponse
from backend.services import ConfigService

router = APIRouter(prefix="/symbols", tags=["symbols"])


@router.get("", response_model=SymbolsResponse)
def list_symbols(
    base_asset: str | None = Query(default=None, description="Filter by base asset"),
    quote_asset: str | None = Query(default=None, description="Filter by quote asset"),
    service: ConfigService = Depends(get_config_service),
) -> SymbolsResponse:
    symbols = service.get_symbols(base_asset=base_asset, quote_asset=quote_asset)
    return SymbolsResponse(success=True, symbols=symbols)
