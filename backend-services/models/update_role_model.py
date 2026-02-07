"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field


class UpdateRoleModel(BaseModel):
    role_name: str | None = Field(
        None, min_length=1, max_length=50, description='Name of the role', example='admin'
    )
    role_description: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description='Description of the role',
        example='Administrator role with full access',
    )
    manage_users: bool | None = Field(None, description='Permission to manage users', example=True)
    manage_apis: bool | None = Field(None, description='Permission to manage APIs', example=True)
    manage_endpoints: bool | None = Field(
        None, description='Permission to manage endpoints', example=True
    )
    manage_groups: bool | None = Field(
        None, description='Permission to manage groups', example=True
    )
    manage_roles: bool | None = Field(None, description='Permission to manage roles', example=True)
    manage_routings: bool | None = Field(
        None, description='Permission to manage routings', example=True
    )
    manage_gateway: bool | None = Field(
        None, description='Permission to manage gateway', example=True
    )
    manage_subscriptions: bool | None = Field(
        None, description='Permission to manage subscriptions', example=True
    )
    manage_security: bool | None = Field(
        None, description='Permission to manage security settings', example=True
    )
    manage_tiers: bool | None = Field(
        None, description='Permission to manage pricing tiers', example=True
    )
    manage_rate_limits: bool | None = Field(
        None, description='Permission to manage rate limiting rules', example=True
    )
    manage_credits: bool | None = Field(
        None, description='Permission to manage credits', example=True
    )
    manage_auth: bool | None = Field(
        None, description='Permission to manage auth (revoke tokens/disable users)', example=True
    )
    view_analytics: bool | None = Field(
        None, description='Permission to view analytics dashboard', example=True
    )
    view_builder_tables: bool | None = Field(
        None, description='Permission to explore tables', example=True
    )
    view_logs: bool | None = Field(None, description='Permission to view logs', example=True)
    export_logs: bool | None = Field(None, description='Permission to export logs', example=True)

    class Config:
        arbitrary_types_allowed = True
