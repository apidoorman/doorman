"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from pydantic import BaseModel, Field
from typing import Optional


class CreateVaultEntryModel(BaseModel):
    """Model for creating a new vault entry."""
    
    key_name: str = Field(
        ..., 
        min_length=1, 
        max_length=255, 
        description='Unique name for the vault key',
        example='api_key_production'
    )
    
    value: str = Field(
        ..., 
        min_length=1, 
        description='The secret value to encrypt and store',
        example='sk_live_abc123xyz789'
    )
    
    description: Optional[str] = Field(
        None,
        max_length=500,
        description='Optional description of what this key is used for',
        example='Production API key for payment gateway'
    )

    class Config:
        arbitrary_types_allowed = True
