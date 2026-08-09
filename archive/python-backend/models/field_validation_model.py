"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class FieldValidation(BaseModel):
    required: bool = Field(..., description='Whether the field is required')
    type: str = Field(
        ..., description='Expected data type (string, number, boolean, array, object)'
    )
    min: int | float | None = Field(
        None, description='Minimum value for numbers or minimum length for strings/arrays'
    )
    max: int | float | None = Field(
        None, description='Maximum value for numbers or maximum length for strings/arrays'
    )
    pattern: str | None = Field(None, description='Regex pattern for string validation')
    enum: list[Any] | None = Field(None, description='List of allowed values')
    format: str | None = Field(
        None, description='Format validation (email, url, date, datetime, uuid, etc.)'
    )
    custom_validator: str | None = Field(None, description='Custom validation function name')
    nested_schema: dict[str, 'FieldValidation'] | None = Field(
        None, description='Validation schema for nested objects'
    )
    array_items: Optional['FieldValidation'] = Field(
        None, description='Validation schema for array items'
    )
