from pydantic import BaseModel, Field
from typing import Optional

class ResponseModel(BaseModel):
    status_code: int = Field(None)

    response: Optional[dict] = Field(None)
    message: Optional[str] = Field(None, min_length=1, max_length=255)

    error_code: Optional[str] = Field(None, min_length=1, max_length=255)
    error_message: Optional[str] = Field(None, min_length=1, max_length=255)

