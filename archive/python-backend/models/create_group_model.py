"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field


class CreateGroupModel(BaseModel):
    group_name: str = Field(
        ..., min_length=1, max_length=50, description='Name of the group', example='client-1-group'
    )

    group_description: str | None = Field(
        None, max_length=255, description='Description of the group', example='Group for client 1'
    )
    api_access: list[str] | None = Field(
        default_factory=list,
        description='List of APIs the group can access',
        example=['customer/v1'],
    )

    class Config:
        arbitrary_types_allowed = True
