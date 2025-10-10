from __future__ import annotations

from .base import ApplicationError


class ConflictError(ApplicationError):
    """Raised when an operation conflicts with current system state."""

    def __init__(self, message: str, *, error_code: str = "CONFLICT") -> None:
        super().__init__(message, error_code=error_code)
