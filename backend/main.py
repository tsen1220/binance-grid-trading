from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.api import account, config, grid, order, symbols, system, trade
from backend.config import settings
from backend.utils import (
    ApplicationError,
    BinanceAPIError,
    ConflictError,
    InsufficientBalanceError,
    ResourceNotFoundError,
    UnauthorizedError,
    ValidationError,
    init_db,
)

app = FastAPI(title=settings.app.name, version=settings.app.version)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.exception_handler(ApplicationError)
async def handle_application_error(request: Request, exc: ApplicationError) -> JSONResponse:
    status_map = {
        ValidationError: 400,
        UnauthorizedError: 401,
        ResourceNotFoundError: 404,
        ConflictError: 409,
        InsufficientBalanceError: 422,
        BinanceAPIError: 503,
    }
    status = status_map.get(type(exc), 500)
    body = {
        "success": False,
        "error": str(exc),
        "error_code": exc.error_code,
        "details": exc.details,
    }
    return JSONResponse(status_code=status, content=body)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover - safeguard
    body = {
        "success": False,
        "error": "Internal server error",
        "error_code": "INTERNAL_ERROR",
        "details": {},
    }
    return JSONResponse(status_code=500, content=body)


app.include_router(config.router, prefix="/api/v1")
app.include_router(account.router, prefix="/api/v1")
app.include_router(symbols.router, prefix="/api/v1")
app.include_router(grid.router, prefix="/api/v1")
app.include_router(order.router, prefix="/api/v1")
app.include_router(trade.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")


@app.get("/")
def root() -> dict:
    return {"success": True, "message": settings.app.name, "version": settings.app.version}
