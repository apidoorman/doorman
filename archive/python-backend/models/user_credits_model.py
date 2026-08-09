"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from pydantic import BaseModel, Field


class UserCreditInformationModel(BaseModel):
    tier_name: str = Field(
        ..., min_length=1, max_length=50, description='Name of the credit tier', example='basic'
    )
    available_credits: int = Field(..., description='Number of available credits', example=50)

    reset_date: str | None = Field(
        None, description='Date when paid credits are reset', example='2023-10-01'
    )
    user_api_key: str | None = Field(
        None,
        description='User specific API key for the credit tier',
        example='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    )

    class Config:
        arbitrary_types_allowed = True


class UserCreditModel(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description='Username of credits owner',
        example='client-1',
    )
    users_credits: dict[str, UserCreditInformationModel] = Field(
        ..., description='Credits information. Key is the credit group name'
    )

    class Config:
        arbitrary_types_allowed = True
