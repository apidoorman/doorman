"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from pydantic import BaseModel, Field


class UpdateVaultEntryModel(BaseModel):
    """Model for updating a vault entry. Only description can be updated, not the value."""

    description: str | None = Field(
        None,
        max_length=500,
        description='Updated description of what this key is used for',
        example='Production API key for payment gateway - updated',
    )

    class Config:
        arbitrary_types_allowed = True
