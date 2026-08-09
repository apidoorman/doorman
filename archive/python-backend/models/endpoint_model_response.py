"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field


class EndpointModelResponse(BaseModel):
    api_name: str | None = Field(
        None, min_length=1, max_length=50, description='Name of the API', example='customer'
    )
    api_version: str | None = Field(
        None, min_length=1, max_length=10, description='Version of the API', example='v1'
    )
    endpoint_method: str | None = Field(
        None, min_length=1, max_length=10, description='HTTP method for the endpoint', example='GET'
    )
    endpoint_uri: str | None = Field(
        None, min_length=1, max_length=255, description='URI for the endpoint', example='/customer'
    )
    endpoint_description: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description='Description of the endpoint',
        example='Get customer details',
    )
    endpoint_servers: list[str] | None = Field(
        None,
        description='Optional list of backend servers for this endpoint (overrides API servers)',
        example=['http://localhost:8082', 'http://localhost:8083'],
    )
    api_id: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description='Unique identifier for the API, auto-generated',
        example=None,
    )
    endpoint_id: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description='Unique identifier for the endpoint, auto-generated',
        example=None,
    )

    class Config:
        arbitrary_types_allowed = True
