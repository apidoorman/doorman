"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field

class SubscribeModel(BaseModel):

    username: str = Field(..., min_length=3, max_length=50)
    api_name: str = Field(..., min_length=3, max_length=50)
    api_version: str = Field(..., min_length=1, max_length=5)

    class Config:
        arbitrary_types_allowed = True