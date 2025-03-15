"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field
from typing import List, Optional

class GroupModel(BaseModel):
    
    group_name: str = Field(..., min_length=1, max_length=50)
    
    group_description: Optional[str] = Field(None, min_length=1, max_length=255)
    api_access: Optional[List[str]] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True