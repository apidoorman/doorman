"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field
from typing import Optional

class RoleModel(BaseModel):
    
    role_name: str = Field(..., min_length=1, max_length=50)
    role_description: Optional[str] = Field(None, min_length=1, max_length=255)
    manage_users: bool = False
    manage_apis: bool = False
    manage_endpoints: bool = False
    manage_groups: bool = False
    manage_roles: bool = False

    class Config:
        arbitrary_types_allowed = True