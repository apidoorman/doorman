"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field


class UpdatePasswordModel(BaseModel):
    new_password: str = Field(
        ...,
        min_length=6,
        max_length=36,
        description='New password of the user',
        example='NewPassword456!',
    )

    class Config:
        arbitrary_types_allowed = True
