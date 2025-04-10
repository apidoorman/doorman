"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

class CreateUserModel(BaseModel):

    username: str = Field(..., min_length=3, max_length=50, description="Username of the user", example="john_doe")
    email: EmailStr = Field(..., description="Email of the user", example="john@mail.com")
    password: str = Field(..., min_length=16, max_length=50, description="Password of the user", example="SecurePassword@123")
    role: str = Field(..., min_length=2, max_length=50, description="Role of the user", example="admin")
    groups: List[str] = Field(default_factory=list, description="List of groups the user belongs to", example=["client-1-group"])
    
    rate_limit_duration: Optional[int] = Field(None, ge=0, description="Rate limit for the user", example=100)
    rate_limit_duration_type: Optional[str] = Field(None, min_length=1, max_length=7, description="Duration for the rate limit", example="hour")
    throttle_duration: Optional[int] = Field(None, ge=0, description="Throttle limit for the user", example=10)
    throttle_duration_type: Optional[str] = Field(None, min_length=1, max_length=7,  description="Duration for the throttle limit", example="second")
    throttle_wait_duration: Optional[int] = Field(None, ge=0, description="Wait time for the throttle limit", example=5)
    throttle_wait_duration_type: Optional[str] = Field(None, min_length=1, max_length=7, description="Wait duration for the throttle limit", example="seconds")
    throttle_queue_limit: Optional[int] = Field(None, ge=0, description="Throttle queue limit for the user", example=10)
    custom_attributes: Optional[dict] = Field(None, description="Custom attributes for the user", example={"custom_key": "custom_value"})

    class Config:
        arbitrary_types_allowed = True