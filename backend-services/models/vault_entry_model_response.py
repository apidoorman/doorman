"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from pydantic import BaseModel, Field
from typing import Optional


class VaultEntryModelResponse(BaseModel):
    """Response model for vault entry. Value is never returned."""
    
    key_name: str = Field(
        ..., 
        description='Name of the vault key',
        example='api_key_production'
    )
    
    username: str = Field(
        ...,
        description='Username of the vault entry owner',
        example='john_doe'
    )
    
    description: Optional[str] = Field(
        None,
        description='Description of what this key is used for',
        example='Production API key for payment gateway'
    )
    
    created_at: Optional[str] = Field(
        None,
        description='Timestamp when the entry was created',
        example='2024-11-22T10:15:30Z'
    )
    
    updated_at: Optional[str] = Field(
        None,
        description='Timestamp when the entry was last updated',
        example='2024-11-22T10:15:30Z'
    )

    class Config:
        arbitrary_types_allowed = True
