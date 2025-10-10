from __future__ import annotations

from .base import ApplicationError


class ResourceNotFoundError(ApplicationError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="NOT_FOUND")
