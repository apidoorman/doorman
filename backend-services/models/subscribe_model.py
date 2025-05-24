"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field

class SubscribeModel(BaseModel):

    username: str = Field(..., min_length=3, max_length=50, description="Username of the subscriber", example="client-1")
    api_name: str = Field(..., min_length=3, max_length=50, description="Name of the API to subscribe to", example="customer")
    api_version: str = Field(..., min_length=1, max_length=5, description="Version of the API to subscribe to", example="v1")

    class Config:
        arbitrary_types_allowed = True