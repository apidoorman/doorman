"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from typing import List
from pydantic import BaseModel, Field

class CreditTierModel(BaseModel):
    tier_name: str = Field(..., min_length=1, max_length=50, description="Name of the credit tier", example="basic")
    credits: int = Field(..., description="Number of credits per reset", example=50)
    input_limit: int = Field(..., description="Input limit for paid credits (text or context)", example=150)
    output_limit: int = Field(..., description="Output limit for paid credits (text or context)", example=150)
    reset_frequency: str = Field(..., description="Frequency of paid credit reset", example="monthly")

    class Config:
        arbitrary_types_allowed = True

class CreditModel(BaseModel):

    api_credit_group: str = Field(..., min_length=1, max_length=50, description="API group for the credits", example="ai-group-1")
    api_key: str = Field(..., description="API key for the credit tier", example="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    api_key_header: str = Field(..., description="Header the API key should be sent in", example="x-api-key")
    credit_tiers: List[CreditTierModel] = Field(..., min_items=1, description="Credit tiers information")
    
    class Config:
        arbitrary_types_allowed = True

