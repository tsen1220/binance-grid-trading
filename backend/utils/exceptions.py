from __future__ import annotations

from typing import Any, Dict, Optional


class ApplicationError(Exception):
    """Base class for domain-specific errors."""

    def __init__(self, message: str, *, error_code: str = "INTERNAL_ERROR", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class ValidationError(ApplicationError):
    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="INVALID_PARAMETERS", details=details)


class UnauthorizedError(ApplicationError):
    def __init__(self, message: str = "API key not configured") -> None:
        super().__init__(message, error_code="UNAUTHORIZED")


class ResourceNotFoundError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="NOT_FOUND")


class ConflictError(ApplicationError):
    def __init__(self, message: str, *, error_code: str = "CONFLICT") -> None:
        super().__init__(message, error_code=error_code)


class InsufficientBalanceError(ApplicationError):
    def __init__(self, message: str, *, required: float, available: float, asset: str) -> None:
        details = {"required": required, "available": available, "asset": asset}
        super().__init__(message, error_code="INSUFFICIENT_BALANCE", details=details)


class BinanceAPIError(ApplicationError):
    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="BINANCE_API_ERROR", details=details)
