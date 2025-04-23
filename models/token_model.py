"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from typing import List
from pydantic import BaseModel, Field

class TokenTierModel(BaseModel):
    tier_name: str = Field(..., min_length=1, max_length=50, description="Name of the token tier", example="basic")
    tokens: int = Field(..., description="Number of tokens per reset", example=50)
    input_limit: int = Field(..., description="Input imit for paid tokens (text or context)", example=150)
    output_limit: int = Field(..., description="Output limit for paid tokens (text or context)", example=150)
    reset_frequency: str = Field(..., description="Frequency of paid token reset", example="monthly")

    class Config:
        arbitrary_types_allowed = True

class TokenModel(BaseModel):

    api_token_group: str = Field(..., min_length=1, max_length=50, description="API group for the tokens", example="ai-group-1")
    api_key: str = Field(..., description="API key for the token tier", example="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    api_key_header: str = Field(..., description="Header the API key should be sent in", example="x-api-key")
    token_tiers: List[TokenTierModel] = Field(..., min_items=1, description="Token tiers information")
    
    class Config:
        arbitrary_types_allowed = True

