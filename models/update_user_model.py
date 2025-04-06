"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

class UpdateUserModel(BaseModel):

    email: Optional[EmailStr] = Field(None)
    role: Optional[str] = Field(None, min_length=2, max_length=50)
    groups: Optional[List[str]] = Field(None)
    rate_limit: Optional[int] = Field(None, ge=0)
    rate_limit_duration: Optional[str] = Field(None, min_length=1, max_length=6)
    throttle: Optional[int] = Field(None, ge=0)
    throttle_duration: Optional[int] = Field(None, ge=0)
    whitelist: Optional[str] = Field(None, min_length=2, max_length=50)
    custom_attributes: Optional[dict] = Field(None)

    class Config:
        arbitrary_types_allowed = True