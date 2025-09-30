"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

# External imports
from pydantic import BaseModel, Field

# Internal imports
from models.validation_schema_model import ValidationSchema

class CreateEndpointValidationModel(BaseModel):

    endpoint_id: str = Field(..., description='Unique identifier for the endpoint, auto-generated', example='1299f720-e619-4628-b584-48a6570026cf')
    validation_enabled: bool = Field(..., description='Whether the validation is enabled', example=True)
    validation_schema: ValidationSchema = Field(..., description='The schema to validate the endpoint against', example={})

    class Config:
        arbitrary_types_allowed = True