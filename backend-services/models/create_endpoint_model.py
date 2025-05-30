"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field
from typing import Optional

class CreateEndpointModel(BaseModel):
    
    api_name: str = Field(..., min_length=1, max_length=50, description="Name of the API", example="customer")
    api_version: str = Field(..., min_length=1, max_length=10, description="Version of the API", example="v1")
    endpoint_method: str = Field(..., min_length=1, max_length=10, description="HTTP method for the endpoint", example="GET") 
    endpoint_uri: str = Field(..., min_length=1, max_length=255, description="URI for the endpoint", example="/customer")
    endpoint_description: str = Field(..., min_length=1, max_length=255, description="Description of the endpoint", example="Get customer details")
    
    api_id: Optional[str] = Field(None, description="Unique identifier for the API, auto-generated", example=None)
    endpoint_id: Optional[str] = Field(None, description="Unique identifier for the endpoint, auto-generated", example=None)

    class Config:
        arbitrary_types_allowed = True