"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field

from models.field_validation_model import FieldValidation


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

    validation_schema: dict[str, FieldValidation] = Field(
        ...,
        description='The schema to validate the endpoint against',
        example={
            'user.name': {'required': True, 'type': 'string', 'min': 2, 'max': 50},
            'user.age': {'required': True, 'type': 'number', 'min': 0, 'max': 120},
        },
    )
