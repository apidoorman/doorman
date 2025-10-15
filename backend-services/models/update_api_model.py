"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pydantic import BaseModel, Field
from typing import List, Optional

class UpdateApiModel(BaseModel):

    api_name: Optional[str] = Field(None, min_length=1, max_length=25, description='Name of the API', example='customer')
    api_version: Optional[str] = Field(None, min_length=1, max_length=8, description='Version of the API', example='v1')
    api_description: Optional[str] = Field(None, min_length=1, max_length=127, description='Description of the API', example='New customer onboarding API')
    api_allowed_roles: Optional[List[str]] = Field(None, description='Allowed user roles for the API', example=['admin', 'user'])
    api_allowed_groups: Optional[List[str]] = Field(None, description='Allowed user groups for the API' , example=['admin', 'client-1-group'])
    api_servers: Optional[List[str]] = Field(None, description='List of backend servers for the API', example=['http://localhost:8080', 'http://localhost:8081'])
    api_type: Optional[str] = Field(None, description="Type of the API. Valid values: 'REST'", example='REST')
    api_authorization_field_swap: Optional[str]  = Field(None, description='Header to swap for backend authorization header', example='backend-auth-header')
    api_allowed_headers: Optional[List[str]] = Field(None, description='Allowed headers for the API', example=['Content-Type', 'Authorization'])
    api_allowed_retry_count: Optional[int] = Field(None, description='Number of allowed retries for the API', example=0)
    api_grpc_package: Optional[str] = Field(None, description='Optional gRPC Python package to use for this API (e.g., "my.pkg"). When set, overrides request package and default.', example='my.pkg')
    api_grpc_allowed_packages: Optional[List[str]] = Field(None, description='Allow-list of gRPC package/module base names (no dots). If set, requests must match one of these.', example=['customer_v1'])
    api_grpc_allowed_services: Optional[List[str]] = Field(None, description='Allow-list of gRPC service names (e.g., Greeter). If set, only these services are permitted.', example=['Greeter'])
    api_grpc_allowed_methods: Optional[List[str]] = Field(None, description='Allow-list of gRPC methods as Service.Method strings. If set, only these methods are permitted.', example=['Greeter.SayHello'])
    api_credits_enabled: Optional[bool] = Field(False, description='Enable credit-based authentication for the API', example=True)
    api_credit_group: Optional[str] = Field(None, description='API credit group for the API credits', example='ai-group-1')
    active: Optional[bool] = Field(None, description='Whether the API is active (enabled)')
    api_id: Optional[str] = Field(None, description='Unique identifier for the API, auto-generated', example=None)
    api_path: Optional[str] = Field(None, description='Unqiue path for the API, auto-generated', example=None)

    api_cors_allow_origins: Optional[List[str]] = Field(None, description="Allowed origins for CORS (e.g., ['http://localhost:3000']). Use ['*'] to allow all.")
    api_cors_allow_methods: Optional[List[str]] = Field(None, description="Allowed methods for CORS preflight (e.g., ['GET','POST','PUT','DELETE','OPTIONS'])")
    api_cors_allow_headers: Optional[List[str]] = Field(None, description="Allowed request headers for CORS preflight (e.g., ['Content-Type','Authorization'])")
    api_cors_allow_credentials: Optional[bool] = Field(None, description='Whether to include Access-Control-Allow-Credentials=true in responses')
    api_cors_expose_headers: Optional[List[str]] = Field(None, description='Response headers to expose to the browser via Access-Control-Expose-Headers')

    api_public: Optional[bool] = Field(None, description='If true, this API can be called without authentication or subscription')

    api_auth_required: Optional[bool] = Field(None, description='If true (default), JWT auth is required for this API when not public. If false, requests may be unauthenticated but must meet other checks as configured.')

    api_ip_mode: Optional[str] = Field(None, description="IP policy mode: 'allow_all' or 'whitelist'")
    api_ip_whitelist: Optional[List[str]] = Field(None, description='Allowed IPs/CIDRs when api_ip_mode=whitelist')
    api_ip_blacklist: Optional[List[str]] = Field(None, description='IPs/CIDRs denied regardless of mode')
    api_trust_x_forwarded_for: Optional[bool] = Field(None, description='Override: trust X-Forwarded-For for this API')

    class Config:
        arbitrary_types_allowed = True
