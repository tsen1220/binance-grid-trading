from __future__ import annotations

from typing import Any, Dict, Optional

from .base import ApplicationError


class BinanceAPIError(ApplicationError):
    """Raised when Binance API returns an error."""

    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="BINANCE_API_ERROR", details=details)
