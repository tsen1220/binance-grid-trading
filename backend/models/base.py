from typing import Optional

from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    success: bool = True


class APIErrorResponse(APIResponse):
    success: bool = False
    error: str
    error_code: str = Field(default="INTERNAL_ERROR")
    details: Optional[dict] = None
