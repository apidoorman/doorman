"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field


class UpdatePasswordModel(BaseModel):
    current_password: str | None = Field(
        None,
        min_length=6,
        max_length=128,
        description='Current password of the user',
        example='CurrentPassword123!',
    )
    old_password: str | None = Field(
        None,
        min_length=6,
        max_length=128,
        description='Legacy alias for current password',
        example='CurrentPassword123!',
    )
    new_password: str = Field(
        ...,
        min_length=6,
        max_length=36,
        description='New password of the user',
        example='NewPassword456!',
    )

    def provided_current_password(self) -> str | None:
        return self.current_password or self.old_password

    class Config:
        arbitrary_types_allowed = True
