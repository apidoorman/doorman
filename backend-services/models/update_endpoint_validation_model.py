"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field

from models.validation_schema_model import ValidationSchema

class UpdateEndpointValidationModel(BaseModel):

    validation_enabled: bool = Field(..., description='Whether the validation is enabled', example=True)
    validation_schema: ValidationSchema = Field(..., description='The schema to validate the endpoint against', example={})

    class Config:
        arbitrary_types_allowed = True