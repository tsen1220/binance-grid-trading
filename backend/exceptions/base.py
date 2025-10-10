from __future__ import annotations

from typing import Any, Dict, Optional


class ApplicationError(Exception):
    """Base class for domain-specific errors."""

    def __init__(self, message: str, *, error_code: str = "INTERNAL_ERROR", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
