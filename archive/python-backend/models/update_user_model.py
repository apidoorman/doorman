"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field


class UpdateUserModel(BaseModel):
    username: str | None = Field(
        None, min_length=3, max_length=50, description='Username of the user', example='john_doe'
    )
    email: str | None = Field(
        None,
        min_length=3,
        max_length=127,
        description='Email of the user (no strict format validation)',
        example='john@mail.com',
    )
    password: str | None = Field(
        None,
        min_length=6,
        max_length=50,
        description='Password of the user',
        example='SecurePassword@123',
    )
    role: str | None = Field(
        None, min_length=2, max_length=50, description='Role of the user', example='admin'
    )
    groups: list[str] | None = Field(
        None, description='List of groups the user belongs to', example=['client-1-group']
    )
    rate_limit_duration: int | None = Field(
        None, ge=0, description='Rate limit for the user', example=100
    )
    rate_limit_duration_type: str | None = Field(
        None, min_length=1, max_length=7, description='Duration for the rate limit', example='hour'
    )
    rate_limit_enabled: bool | None = Field(
        None, description='Whether rate limiting is enabled for this user', example=True
    )
    throttle_duration: int | None = Field(
        None, ge=0, description='Throttle limit for the user', example=10
    )
    throttle_duration_type: str | None = Field(
        None,
        min_length=1,
        max_length=7,
        description='Duration for the throttle limit',
        example='second',
    )
    throttle_wait_duration: int | None = Field(
        None, ge=0, description='Wait time for the throttle limit', example=5
    )
    throttle_wait_duration_type: str | None = Field(
        None,
        min_length=1,
        max_length=7,
        description='Wait duration for the throttle limit',
        example='seconds',
    )
    throttle_queue_limit: int | None = Field(
        None, ge=0, description='Throttle queue limit for the user', example=10
    )
    throttle_enabled: bool | None = Field(
        None, description='Whether throttling is enabled for this user', example=True
    )
    custom_attributes: dict | None = Field(
        None, description='Custom attributes for the user', example={'custom_key': 'custom_value'}
    )
    bandwidth_limit_bytes: int | None = Field(
        None,
        ge=0,
        description='Maximum bandwidth allowed within the window (bytes)',
        example=1073741824,
    )
    bandwidth_limit_window: str | None = Field(
        None,
        min_length=1,
        max_length=10,
        description='Bandwidth window unit (second/minute/hour/day/month)',
        example='day',
    )
    bandwidth_limit_enabled: bool | None = Field(
        None,
        description='Whether bandwidth limit enforcement is enabled for this user',
        example=True,
    )
    active: bool | None = Field(None, description='Active status of the user', example=True)
    ui_access: bool | None = Field(None, description='UI access for the user', example=False)

    class Config:
        arbitrary_types_allowed = True
