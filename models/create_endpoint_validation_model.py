"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from typing import List, Union, Optional, Dict, Any
from pydantic import BaseModel, Field

class FieldValidation(BaseModel):
    required: bool = Field(..., description="Whether the field is required")
    type: str = Field(..., description="Expected data type (string, number, boolean, array, object)")
    min: Optional[Union[int, float]] = Field(None, description="Minimum value for numbers or minimum length for strings/arrays")
    max: Optional[Union[int, float]] = Field(None, description="Maximum value for numbers or maximum length for strings/arrays")
    pattern: Optional[str] = Field(None, description="Regex pattern for string validation")
    enum: Optional[List[Any]] = Field(None, description="List of allowed values")
    format: Optional[str] = Field(None, description="Format validation (email, url, date, datetime, uuid, etc.)")
    custom_validator: Optional[str] = Field(None, description="Custom validation function name")
    nested_schema: Optional[Dict[str, 'FieldValidation']] = Field(None, description="Validation schema for nested objects")
    array_items: Optional['FieldValidation'] = Field(None, description="Validation schema for array items")

class ValidationSchema(BaseModel):
    """Validation schema for endpoint request/response validation.
    
    The schema is a dictionary where:
    - Keys are field paths (e.g., "user.name", "items[0].price")
    - Values are FieldValidation objects containing validation rules
    
    Example:
    {
        "user.name": {
            "required": true,
            "type": "string",
            "min": 2,
            "max": 50
        },
        "user.age": {
            "required": true,
            "type": "number",
            "min": 0,
            "max": 120
        },
        "user.email": {
            "required": true,
            "type": "string",
            "format": "email"
        },
        "items": {
            "required": true,
            "type": "array",
            "min": 1,
            "array_items": {
                "type": "object",
                "nested_schema": {
                    "id": {
                        "required": true,
                        "type": "string",
                        "format": "uuid"
                    },
                    "quantity": {
                        "required": true,
                        "type": "number",
                        "min": 1
                    }
                }
            }
        }
    }
    """
    validation_schema: Dict[str, FieldValidation] = Field(
        ...,
        description="The schema to validate the endpoint against",
        example={
            "user.name": {
                "required": True,
                "type": "string",
                "min": 2,
                "max": 50
            },
            "user.age": {
                "required": True,
                "type": "number",
                "min": 0,
                "max": 120
            }
        }
    )

class CreateEndpointValidationModel(BaseModel):
    
    endpoint_id: str = Field(..., description="Unique identifier for the endpoint, auto-generated", example="1299f720-e619-4628-b584-48a6570026cf")
    validation_enabled: bool = Field(..., description="Whether the validation is enabled", example=True)
    validation_schema: ValidationSchema = Field(..., description="The schema to validate the endpoint against", example={})

    class Config:
        arbitrary_types_allowed = True