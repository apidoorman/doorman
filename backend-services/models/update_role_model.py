"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field
from typing import Optional

class UpdateRoleModel(BaseModel):

    role_name: Optional[str] = Field(None, min_length=1, max_length=50, description='Name of the role', example='admin')
    role_description: Optional[str] = Field(None, min_length=1, max_length=255, description='Description of the role', example='Administrator role with full access')
    manage_users: Optional[bool] = Field(None, description='Permission to manage users', example=True)
    manage_apis: Optional[bool] = Field(None, description='Permission to manage APIs', example=True)
    manage_endpoints: Optional[bool] = Field(None, description='Permission to manage endpoints', example=True)
    manage_groups: Optional[bool] = Field(None, description='Permission to manage groups', example=True)
    manage_roles: Optional[bool] = Field(None, description='Permission to manage roles', example=True)
    manage_routings: Optional[bool] = Field(None, description='Permission to manage routings', example=True)
    manage_gateway: Optional[bool] = Field(None, description='Permission to manage gateway', example=True)
    manage_subscriptions: Optional[bool] = Field(None, description='Permission to manage subscriptions', example=True)
    manage_security: Optional[bool] = Field(None, description='Permission to manage security settings', example=True)
    manage_credits: Optional[bool] = Field(None, description='Permission to manage credits', example=True)
    manage_auth: Optional[bool] = Field(None, description='Permission to manage auth (revoke tokens/disable users)', example=True)
    view_logs: Optional[bool] = Field(None, description='Permission to view logs', example=True)
    export_logs: Optional[bool] = Field(None, description='Permission to export logs', example=True)

    class Config:
        arbitrary_types_allowed = True
