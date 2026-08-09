"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field


class ApiModelResponse(BaseModel):
    api_name: str | None = Field(
        None, min_length=1, max_length=25, description='Name of the API', example='customer'
    )
    api_version: str | None = Field(
        None, min_length=1, max_length=8, description='Version of the API', example='v1'
    )
    api_description: str | None = Field(
        None,
        max_length=127,
        description='Description of the API',
        example='New customer onboarding API',
    )
    api_allowed_roles: list[str] | None = Field(
        None, description='Allowed user roles for the API', example=['admin', 'user']
    )
    api_allowed_groups: list[str] | None = Field(
        None, description='Allowed user groups for the API', example=['admin', 'client-1-group']
    )
    api_servers: list[str] | None = Field(
        None,
        description='List of backend servers for the API',
        example=['http://localhost:8080', 'http://localhost:8081'],
    )
    api_type: str | None = Field(
        None, description="Type of the API. Valid values: 'REST'", example='REST'
    )
    api_authorization_field_swap: str | None = Field(
        None,
        description='Header to swap for backend authorization header',
        example='backend-auth-header',
    )
    api_allowed_headers: list[str] | None = Field(
        None, description='Allowed headers for the API', example=['Content-Type', 'Authorization']
    )
    api_allowed_retry_count: int | None = Field(
        None, description='Number of allowed retries for the API', example=0
    )
    api_credits_enabled: bool | None = Field(
        False, description='Enable credit-based authentication for the API', example=True
    )
    api_credit_group: str | None = Field(
        None, description='API credit group for the API credits', example='ai-group-1'
    )
    api_id: str | None = Field(
        None,
        description='Unique identifier for the API, auto-generated',
        example='c3eda315-545a-4fef-a831-7e45e2f68987',
    )
    api_path: str | None = Field(
        None, description='Unqiue path for the API, auto-generated', example='/customer/v1'
    )

    class Config:
        arbitrary_types_allowed = True
