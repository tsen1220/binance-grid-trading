from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from backend.api import get_order_service
from backend.models import OrdersResponse
from backend.services import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=OrdersResponse)
def get_orders(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    grid_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    service: OrderService = Depends(get_order_service),
) -> OrdersResponse:
    orders, total = service.get_orders(page=page, limit=limit, grid_id=grid_id, status=status)
    return OrdersResponse(success=True, total=total, page=page, limit=limit, orders=orders)


@router.delete("/{order_id}", response_model=dict)
def cancel_order(order_id: str = Path(..., description="Order identifier"), service: OrderService = Depends(get_order_service)) -> dict:
    order = service.cancel_order(order_id)
    return {
        "success": True,
        "message": "Order cancelled successfully",
        "order_id": order.id,
    }
