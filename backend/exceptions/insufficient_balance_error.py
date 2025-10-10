from __future__ import annotations

from .base import ApplicationError


class InsufficientBalanceError(ApplicationError):
    """Raised when account balance is insufficient for an operation."""

    def __init__(self, message: str, *, required: float, available: float, asset: str) -> None:
        details = {"required": required, "available": available, "asset": asset}
        super().__init__(message, error_code="INSUFFICIENT_BALANCE", details=details)
