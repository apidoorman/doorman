"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field
from typing import Optional

class RoutingModel(BaseModel):
    
    routing_name: str = Field(..., min_length=1, max_length=50)
    routing_servers : list[str] = Field(..., min_items=1)
    
    routing_description: Optional[str] = Field(None, min_length=1, max_length=255)
    client_key: Optional[str] = Field(None, min_length=1, max_length=50)
    server_index: Optional[int] = Field(None, ge=0)

    class Config:
        arbitrary_types_allowed = True