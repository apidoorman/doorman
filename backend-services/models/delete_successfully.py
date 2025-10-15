"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field

class ResponseMessage(BaseModel):

    message: str = Field(None, description='The response message', example='API Deleted Successfully')

    class Config:
        arbitrary_types_allowed = True