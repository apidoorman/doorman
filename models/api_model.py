"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field
from typing import List, Optional

class ApiModel(BaseModel): 
    
    api_name: str = Field(..., min_length=1, max_length=25)
    api_version: str = Field(..., min_length=1, max_length=2)
    api_description: str = Field(None, min_length=1, max_length=127)
    api_allowed_roles: List[str] = Field(default_factory=list)
    api_allowed_groups: List[str] = Field(default_factory=list)
    api_servers: List[str] = Field(default_factory=list)
    api_type: str = None
    
    api_id: Optional[str] = None
    api_path: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True