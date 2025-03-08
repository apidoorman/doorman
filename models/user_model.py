"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

class UserModel(BaseModel):

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(..., min_length=2, max_length=50)
    groups: List[str] = Field(default_factory=list)
    rate_limit: Optional[int] = Field(None, ge=0)
    rate_limit_duration: Optional[int] = Field(None, ge=0)
    throttle: Optional[int] = Field(None, ge=0)
    throttle_duration: Optional[int] = Field(None, ge=0)
    whitelist: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True