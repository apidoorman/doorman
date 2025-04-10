"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field
from typing import Optional

class UpdateEndpointModel(BaseModel):
    
    api_name: Optional[str] = Field(None, min_length=1, max_length=50, description="Name of the API", example="customer")
    api_version: Optional[str] = Field(None, min_length=1, max_length=10, description="Version of the API", example="v1")
    endpoint_method: Optional[str] = Field(None, min_length=1, max_length=10, description="HTTP method for the endpoint", example="GET") 
    endpoint_uri: Optional[str] = Field(None, min_length=1, max_length=255, description="URI for the endpoint", example="/customer")
    endpoint_description: Optional[str] = Field(None, min_length=1, max_length=255, description="Description of the endpoint", example="Get customer details")
    api_id: Optional[str] = Field(None, min_length=1, max_length=255, description="Unique identifier for the API, auto-generated", example=None)
    endpoint_id: Optional[str] = Field(None, min_length=1, max_length=255, description="Unique identifier for the endpoint, auto-generated", example=None)

    class Config:
        arbitrary_types_allowed = True