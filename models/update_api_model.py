"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field
from typing import List, Optional

class UpdateApiModel(BaseModel): 
    
    api_name: Optional[str] = Field(None, min_length=1, max_length=25)
    api_version: Optional[str] = Field(None, min_length=1, max_length=2)
    api_description: Optional[str] = Field(None, min_length=1, max_length=127)
    api_allowed_roles: Optional[List[str]] = Field(None)
    api_allowed_groups: Optional[List[str]] = Field(None)
    api_servers: Optional[List[str]] = Field(None)
    api_type: Optional[str] = None
    api_id: Optional[str] = None
    api_path: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True