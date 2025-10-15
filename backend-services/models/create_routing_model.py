"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field
from typing import Optional

class CreateRoutingModel(BaseModel):

    routing_name: str = Field(..., min_length=1, max_length=50, description='Name of the routing', example='customer-routing')
    routing_servers : list[str] = Field(..., min_items=1, description='List of backend servers for the routing', example=['http://localhost:8080', 'http://localhost:8081'])
    routing_description: str = Field(None, min_length=1, max_length=255, description='Description of the routing', example='Routing for customer API')

    client_key: Optional[str] = Field(None, min_length=1, max_length=50, description='Client key for the routing', example='client-1')
    server_index: Optional[int] = Field(0, ge=0, description='Index of the server to route to', example=0)

    class Config:
        arbitrary_types_allowed = True