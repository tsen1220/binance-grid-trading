from __future__ import annotations

from .base import ApplicationError


class UnauthorizedError(ApplicationError):
    """Raised when API credentials are not configured or invalid."""

    def __init__(self, message: str = "API key not configured") -> None:
        super().__init__(message, error_code="UNAUTHORIZED")
