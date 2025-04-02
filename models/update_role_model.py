"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field
from typing import Optional

class UpdateRoleModel(BaseModel):
    
    role_name: Optional[str] = Field(None, min_length=1, max_length=50)
    role_description: Optional[str] = Field(None, min_length=1, max_length=255)
    manage_users: Optional[bool] = Field(None)
    manage_apis: Optional[bool] = Field(None)
    manage_endpoints: Optional[bool] = Field(None)
    manage_groups: Optional[bool] = Field(None)
    manage_roles: Optional[bool] = Field(None)

    class Config:
        arbitrary_types_allowed = True