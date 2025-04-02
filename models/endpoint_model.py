"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field
from typing import Optional

class EndpointModel(BaseModel):
    
    api_name: str = Field(..., min_length=1, max_length=50)
    api_version: str = Field(..., min_length=1, max_length=10)
    endpoint_method: str = Field(...) 
    endpoint_uri: str = Field(..., min_length=1, max_length=255)

    api_id: Optional[str] = Field(None, min_length=1, max_length=255)
    endpoint_description: Optional[str] = Field(None, min_length=1, max_length=255)
    endpoint_id: Optional[str] = Field(None, min_length=1, max_length=255)

    class Config:
        arbitrary_types_allowed = True