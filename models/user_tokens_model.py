"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class UserTokenInformationModel(BaseModel):
    tier_name: str = Field(..., min_length=1, max_length=50, description="Name of the token tier", example="basic")
    reset_date: Optional[str] = Field(None, description="Date when paid tokens are reset", example="2023-10-01")
    available_tokens: int = Field(..., description="Number of available tokens", example=50)
    
    class Config:
        arbitrary_types_allowed = True

class UserTokenModel(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username of tokens owner", example="client-1")
    users_tokens: Dict[str, UserTokenInformationModel] = Field(..., min_items=1, description="Tokens information. Key is the token group name")
    
    class Config:
        arbitrary_types_allowed = True

