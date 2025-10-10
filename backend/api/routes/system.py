from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api import get_system_service
from backend.models import HealthResponse, SystemStatusResponse
from backend.services import SystemService

router = APIRouter(tags=["system"])


@router.get("/system/status", response_model=SystemStatusResponse)
def system_status(service: SystemService = Depends(get_system_service)) -> SystemStatusResponse:
    status = service.get_status()
    return SystemStatusResponse(success=True, **status)


@router.get("/health", response_model=HealthResponse)
def health_check(service: SystemService = Depends(get_system_service)) -> HealthResponse:
    return HealthResponse(**service.health())
