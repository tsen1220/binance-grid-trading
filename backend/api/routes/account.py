from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api import get_config_service
from backend.models import BalanceResponse
from backend.services import ConfigService

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/balance", response_model=BalanceResponse)
def get_balance(service: ConfigService = Depends(get_config_service)) -> BalanceResponse:
    balances = service.get_balances()
    return BalanceResponse(success=True, balances=balances)
