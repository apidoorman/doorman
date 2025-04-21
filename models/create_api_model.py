"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field
from typing import List, Optional

class CreateApiModel(BaseModel): 
    
    api_name: str = Field(..., min_length=1, max_length=25, description="Name of the API", example="customer")
    api_version: str = Field(..., min_length=1, max_length=8, description="Version of the API", example="v1")
    api_description: str = Field(None, min_length=1, max_length=127, description="Description of the API", example="New customer onboarding API")
    api_allowed_roles: List[str] = Field(default_factory=list, description="Allowed user roles for the API", example=["admin", "user"])
    api_allowed_groups: List[str] = Field(default_factory=list, description="Allowed user groups for the API" , example=["admin", "client-1-group"])
    api_servers: List[str] = Field(default_factory=list, description="List of backend servers for the API", example=["http://localhost:8080", "http://localhost:8081"])
    api_type: str = Field(None, description="Type of the API. Valid values: 'REST'", example="REST")
    api_allowed_retry_count: int = Field(0, description="Number of allowed retries for the API", example=0)
    api_allowed_headers: Optional[List[str]] = Field(None, description="Allowed headers for the API", example=["Content-Type", "Authorization"])

    api_tokens_enabled: Optional[bool] = Field(False, description="Enable token-based authentication for the API", example=True)
    api_token_group: Optional[str] = Field(None, description="API token group for the API tokens", example="ai-group-1")
    
    api_id: Optional[str] = Field(None, description="Unique identifier for the API, auto-generated", example=None)
    api_path: Optional[str] = Field(None, description="Unique path for the API, auto-generated", example=None)

    class Config:
        arbitrary_types_allowed = True