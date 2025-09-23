"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pydantic import BaseModel, Field

class UpdatePasswordModel(BaseModel):

    old_password: str = Field(..., min_length=6, max_length=36)
    new_password: str = Field(..., min_length=6, max_length=36)

    class Config:
        arbitrary_types_allowed = True