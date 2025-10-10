from __future__ import annotations

from typing import Any, Dict, Optional

from .base import ApplicationError


class ValidationError(ApplicationError):
    """Raised when input validation fails."""

    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="INVALID_PARAMETERS", details=details)
