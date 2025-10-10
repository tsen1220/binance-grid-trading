from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api import get_grid_service
from backend.models import (
    GridHistoryResponse,
    GridStartRequest,
    GridStartResponse,
    GridStatusResponse,
    GridStopRequest,
    GridStopResponse,
)
from backend.services import GridService

router = APIRouter(prefix="/grid", tags=["grid"])


@router.post("/start", response_model=GridStartResponse)
def start_grid(request: GridStartRequest, service: GridService = Depends(get_grid_service)) -> GridStartResponse:
    grid, metrics, initial_orders = service.start_grid(request)
    config_payload = {
        "trading_pair": grid.trading_pair,
        "upper_price": float(request.upper_price),
        "lower_price": float(request.lower_price),
        "grid_count": request.grid_count,
        "grid_spacing": float(metrics["grid_spacing"]),
        "investment_per_grid": float(metrics["investment_per_grid"]),
        "total_investment": float(metrics["total_investment"]),
    }
    return GridStartResponse(
        success=True,
        grid_id=grid.id,
        message="Grid trading started successfully",
        config=config_payload,
        initial_orders=initial_orders,
    )


@router.post("/stop", response_model=GridStopResponse)
def stop_grid(request: GridStopRequest, service: GridService = Depends(get_grid_service)) -> GridStopResponse:
    grid, cancelled = service.stop_grid(request.grid_id, cancel_orders=request.cancel_orders)
    final_status = {
        "total_trades": 0,
        "profit": 0.0,
        "profit_percentage": 0.0,
    }
    return GridStopResponse(
        success=True,
        message="Grid trading stopped successfully",
        cancelled_orders=cancelled,
        final_status=final_status,
    )


@router.get("/status", response_model=GridStatusResponse)
def get_status(grid_id: str | None = Query(default=None), service: GridService = Depends(get_grid_service)) -> GridStatusResponse:
    return service.get_status(grid_id=grid_id)


@router.get("/history", response_model=GridHistoryResponse)
def get_history(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    service: GridService = Depends(get_grid_service),
) -> GridHistoryResponse:
    history_items, total = service.get_history(page=page, limit=limit)
    return GridHistoryResponse(success=True, total=total, page=page, limit=limit, grids=history_items)
