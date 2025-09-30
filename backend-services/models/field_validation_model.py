"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

# External imports
from typing import List, Union, Optional, Dict, Any
from pydantic import BaseModel, Field

class FieldValidation(BaseModel):
    required: bool = Field(..., description='Whether the field is required')
    type: str = Field(..., description='Expected data type (string, number, boolean, array, object)')
    min: Optional[Union[int, float]] = Field(None, description='Minimum value for numbers or minimum length for strings/arrays')
    max: Optional[Union[int, float]] = Field(None, description='Maximum value for numbers or maximum length for strings/arrays')
    pattern: Optional[str] = Field(None, description='Regex pattern for string validation')
    enum: Optional[List[Any]] = Field(None, description='List of allowed values')
    format: Optional[str] = Field(None, description='Format validation (email, url, date, datetime, uuid, etc.)')
    custom_validator: Optional[str] = Field(None, description='Custom validation function name')
    nested_schema: Optional[Dict[str, 'FieldValidation']] = Field(None, description='Validation schema for nested objects')
    array_items: Optional['FieldValidation'] = Field(None, description='Validation schema for array items')