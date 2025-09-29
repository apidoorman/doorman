"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field
from typing import Optional

class CreateRoleModel(BaseModel):
    
    role_name: str = Field(..., min_length=1, max_length=50, description="Name of the role", example="admin")
    role_description: Optional[str] = Field(None, max_length=255, description="Description of the role", example="Administrator role with full access")
    manage_users: bool = Field(False, description="Permission to manage users", example=True)
    manage_apis: bool = Field(False, description="Permission to manage APIs", example=True)
    manage_endpoints: bool = Field(False, description="Permission to manage endpoints", example=True)
    manage_groups: bool = Field(False, description="Permission to manage groups", example=True)
    manage_roles: bool = Field(False, description="Permission to manage roles", example=True)
    manage_routings: bool = Field(False, description="Permission to manage routings", example=True)
    manage_gateway: bool = Field(False, description="Permission to manage gateway", example=True)
    manage_subscriptions: bool = Field(False, description="Permission to manage subscriptions", example=True)
    manage_security: bool = Field(False, description="Permission to manage security settings", example=True)
    manage_credits: bool = Field(False, description="Permission to manage credits", example=True)
    manage_auth: bool = Field(False, description="Permission to manage auth (revoke tokens/disable users)", example=True)
    view_logs: bool = Field(False, description="Permission to view logs", example=True)
    export_logs: bool = Field(False, description="Permission to export logs", example=True)

    class Config:
        arbitrary_types_allowed = True
