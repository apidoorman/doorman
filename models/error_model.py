from pydantic import BaseModel, Field
from typing import Optional

class ErrorModel(BaseModel):
    error_code: int = Field(..., ge=1000, le=9999)
    error_message: str = Field(..., min_length=1, max_length=255)
    error_description: Optional[str] = Field(None, min_length=1, max_length=255)