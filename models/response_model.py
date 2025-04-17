from pydantic import BaseModel, Field
from typing import Optional, Union

class ResponseModel(BaseModel):
    status_code: int = Field(None)

    response_headers: Optional[dict] = Field(None)

    response: Optional[Union[dict, list]] = Field(None)
    message: Optional[str] = Field(None, min_length=1, max_length=255)

    error_code: Optional[str] = Field(None, min_length=1, max_length=255)
    error_message: Optional[str] = Field(None, min_length=1, max_length=255)

