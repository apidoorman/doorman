"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from typing import Optional
from pydantic import BaseModel, Field


class CreateApiModel(BaseModel):
    api_name: str = Field(
        ..., min_length=1, max_length=64, description='Name of the API', example='customer'
    )
    api_version: str = Field(
        ..., min_length=1, max_length=8, description='Version of the API', example='v1'
    )
    api_description: str | None = Field(
        None,
        max_length=127,
        description='Description of the API',
        example='New customer onboarding API',
    )
    api_allowed_roles: list[str] = Field(
        default_factory=list,
        description='Allowed user roles for the API',
        example=['admin', 'user'],
    )
    api_allowed_groups: list[str] = Field(
        default_factory=list,
        description='Allowed user groups for the API',
        example=['admin', 'client-1-group'],
    )
    api_servers: list[str] = Field(
        default_factory=list,
        description='List of backend servers for the API',
        example=['http://localhost:8080', 'http://localhost:8081'],
    )
    api_type: str | None = Field(
        None, description="Type of the API. Valid values: 'REST', 'SOAP', 'GRAPHQL', 'GRPC'", example='REST'
    )
    api_allowed_retry_count: int = Field(
        0, description='Number of allowed retries for the API', example=0
    )
    api_grpc_package: str | None = Field(
        None,
        description='Optional gRPC Python package to use for this API (e.g., "my.pkg"). When set, overrides request package and default.',
        example='my.pkg',
    )
    api_grpc_allowed_packages: list[str] | None = Field(
        None,
        description='Allow-list of gRPC package/module base names (no dots). If set, requests must match one of these.',
        example=['customer_v1'],
    )
    api_grpc_allowed_services: list[str] | None = Field(
        None,
        description='Allow-list of gRPC service names (e.g., Greeter). If set, only these services are permitted.',
        example=['Greeter'],
    )
    api_grpc_allowed_methods: list[str] | None = Field(
        None,
        description='Allow-list of gRPC methods as Service.Method strings. If set, only these methods are permitted.',
        example=['Greeter.SayHello'],
    )

    api_authorization_field_swap: str | None = Field(
        None,
        description='Header to swap for backend authorization header',
        example='backend-auth-header',
    )
    api_allowed_headers: list[str] | None = Field(
        None, description='Allowed headers for the API', example=['Content-Type', 'Authorization']
    )
    api_credits_enabled: bool | None = Field(
        False, description='Enable credit-based authentication for the API', example=True
    )
    api_credit_group: str | None = Field(
        None, description='API credit group for the API credits', example='ai-group-1'
    )
    active: bool | None = Field(
        True, description='Whether the API is active (enabled)', example=True
    )

    api_cors_allow_origins: list[str] | None = Field(
        None,
        description="Allowed origins for CORS (e.g., ['http://localhost:3000']). Use ['*'] to allow all.",
    )
    api_cors_allow_methods: list[str] | None = Field(
        None,
        description="Allowed methods for CORS preflight (e.g., ['GET','POST','PUT','DELETE','OPTIONS'])",
    )
    api_cors_allow_headers: list[str] | None = Field(
        None,
        description="Allowed request headers for CORS preflight (e.g., ['Content-Type','Authorization'])",
    )
    api_cors_allow_credentials: bool | None = Field(
        False, description='Whether to include Access-Control-Allow-Credentials=true in responses'
    )
    api_cors_expose_headers: list[str] | None = Field(
        None,
        description='Response headers to expose to the browser via Access-Control-Expose-Headers',
    )

    api_public: bool | None = Field(
        False, description='If true, this API can be called without authentication or subscription'
    )

    api_auth_required: bool | None = Field(
        True,
        description='If true (default), JWT auth is required for this API when not public. If false, requests may be unauthenticated but must meet other checks as configured.',
    )

    api_id: str | None = Field(
        None, description='Unique identifier for the API, auto-generated', example=None
    )
    api_path: str | None = Field(
        None, description='Unique path for the API, auto-generated', example=None
    )

    api_ip_mode: str | None = Field(
        'allow_all', description="IP policy mode: 'allow_all' or 'whitelist'"
    )
    api_ip_whitelist: list[str] | None = Field(
        None, description='Allowed IPs/CIDRs when api_ip_mode=whitelist'
    )
    api_ip_blacklist: list[str] | None = Field(
        None, description='IPs/CIDRs denied regardless of mode'
    )
    api_trust_x_forwarded_for: bool | None = Field(
        None, description='Override: trust X-Forwarded-For for this API'
    )

    # Request/Response Transformation
    api_request_transform: dict | None = Field(
        None,
        description='Request transformation config. Supports headers, body (JSONPath), query transforms.',
        example={
            'request': {
                'headers': {'add': {'X-Custom': 'value'}, 'remove': ['X-Internal']},
                'body': {'set': {'$.source': 'doorman'}},
            }
        },
    )
    api_response_transform: dict | None = Field(
        None,
        description='Response transformation config. Supports headers, body (JSONPath), status mapping.',
        example={
            'response': {
                'headers': {'add': {'X-Gateway': 'doorman'}},
                'body': {'wrap': 'data'},
                'status_map': {'500': 502},
            }
        },
    )

    # OpenAPI Auto-Discovery
    api_openapi_url: str | None = Field(
        None,
        description='URL path to fetch OpenAPI spec from upstream (e.g., /openapi.json, /swagger.json)',
        example='/openapi.json',
    )
    api_openapi_auto_discover: bool | None = Field(
        False,
        description='If true, automatically discover and sync endpoints from upstream OpenAPI spec',
    )

    # SOAP/WSDL Configuration
    api_wsdl_url: str | None = Field(
        None,
        description='URL to fetch WSDL from upstream (e.g., /service?wsdl)',
        example='/CustomerService?wsdl',
    )
    api_soap_version: str | None = Field(
        None,
        description='SOAP version: "1.1" or "1.2". If not set, auto-detects from envelope.',
        example='1.1',
    )
    api_ws_security: dict | None = Field(
        None,
        description='WS-Security configuration for SOAP requests',
        example={
            'username': 'service_user',
            'password_type': 'PasswordText',
            'add_timestamp': True,
            'timestamp_ttl_seconds': 300,
        },
    )

    # GraphQL Configuration
    api_graphql_max_depth: int | None = Field(
        None,
        description='Maximum allowed query depth for GraphQL queries (default: 10, 0 = disabled)',
        example=10,
    )
    api_graphql_schema_url: str | None = Field(
        None,
        description='GraphQL endpoint path for introspection (default: /graphql)',
        example='/graphql',
    )
    api_graphql_subscriptions: bool | None = Field(
        False,
        description='Enable WebSocket subscription proxy for this API',
    )

    # gRPC Configuration
    api_grpc_web_enabled: bool | None = Field(
        False,
        description='Enable gRPC-Web proxy for browser clients',
    )
    api_grpc_reflection_url: str | None = Field(
        None,
        description='Upstream URL for gRPC Server Reflection (if different from base URL)',
    )

    api_is_crud: bool | None = Field(
        False,
        description='If true, this API is a CRUD builder API and stores data in Doorman database',
    )
    api_crud_collection: str | None = Field(
        None,
        description='Dynamic collection name for custom CRUD data',
        example='crud_data_my_collection',
    )
    api_crud_schema: Optional[dict] = Field(
        None,
        description="Schema definition for CRUD validation. Dict of field_name -> rules.",
        example={
            "name": {"type": "string", "required": True, "min_length": 3},
            "age": {"type": "number", "min_value": 0}
        }
    )

    class Config:
        arbitrary_types_allowed = True
