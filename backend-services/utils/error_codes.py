"""
Centralized Error Code Registry

This module provides a single source of truth for all error codes used across Doorman.
Using constants ensures consistency and makes it easier to search/refactor error codes.

Usage:
    from utils.error_codes import ErrorCode

    raise HTTPException(
        status_code=401,
        detail={
            'error_code': ErrorCode.AUTH_INVALID_CREDENTIALS,
            'message': 'Invalid username or password'
        }
    )

    # Or with ResponseModel
    return ResponseModel(
        status_code=404,
        error_code=ErrorCode.USER_NOT_FOUND,
        error_message='User not found'
    ).dict()
"""


class ErrorCode:
    """
    Centralized error code constants.

    Naming Convention:
        - Format: CATEGORY_DESCRIPTION = 'PREFIX###'
        - Categories: AUTH, USER, API, ENDPOINT, GATEWAY, etc.
        - Prefixes: AUTH, USR, API, END, GTW, etc.
        - Numbers: Sequential within category

    Example:
        AUTH_INVALID_CREDENTIALS = 'AUTH001'
        USER_NOT_FOUND = 'USR002'
    """

    # ========================================================================
    # Authentication & Authorization Errors (AUTH001-AUTH999)
    # ========================================================================
    AUTH_MISSING_CREDENTIALS = 'AUTH001'  # Missing email or password
    AUTH_INVALID_CREDENTIALS = 'AUTH002'  # Invalid email or password
    AUTH_TOKEN_INVALID = 'AUTH003'  # Invalid or expired token
    AUTH_TOKEN_MISSING = 'AUTH004'  # Authorization token missing
    AUTH_TOKEN_EXPIRED = 'AUTH005'  # Token has expired
    AUTH_USER_INACTIVE = 'AUTH007'  # User account is not active
    AUTH_UNEXPECTED_ERROR = 'AUTH900'  # Unexpected authentication error

    # ========================================================================
    # User Management Errors (USR001-USR999)
    # ========================================================================
    USR_ALREADY_EXISTS = 'USR001'  # Username or email already exists
    USR_NOT_FOUND = 'USR002'  # User not found
    USR_DELETE_FAILED = 'USR003'  # Unable to delete user
    USR_UPDATE_FAILED = 'USR004'  # Unable to update user
    USR_WEAK_PASSWORD = 'USR005'  # Password does not meet requirements
    USR_UNAUTHORIZED_ACCESS = 'USR006'  # User lacks permission
    USR_INVALID_OPERATION = 'USR007'  # Invalid operation for user
    USR_PERMISSION_DENIED = 'USR008'  # Insufficient permissions
    USR_USERNAME_INVALID = 'USR013'  # Invalid username format
    USR_EMAIL_INVALID = 'USR015'  # Invalid email format
    USR_TOO_MANY_ATTRIBUTES = 'USR016'  # Maximum custom attributes exceeded

    # ========================================================================
    # API Management Errors (API001-API999)
    # ========================================================================
    API_ALREADY_EXISTS = 'API001'  # API already exists
    API_CREATE_FAILED = 'API002'  # Unable to create API
    API_NOT_FOUND = 'API003'  # API not found
    API_UPDATE_NAME_FORBIDDEN = 'API005'  # API name/version cannot be changed
    API_NO_DATA_TO_UPDATE = 'API006'  # No update data provided
    API_PERMISSION_DENIED = 'API007'  # Insufficient permissions
    API_INVALID_REQUEST = 'API008'  # Invalid API request
    API_PROTO_INVALID = 'API009'  # Invalid protobuf definition
    API_PUBLIC_CREDITS_CONFLICT = 'API013'  # Public API cannot have credits

    # ========================================================================
    # Endpoint Management Errors (END001-END999)
    # ========================================================================
    END_ALREADY_EXISTS = 'END001'  # Endpoint already exists
    END_CREATE_FAILED = 'END002'  # Unable to create endpoint
    END_NOT_FOUND = 'END003'  # Endpoint not found
    END_UPDATE_FAILED = 'END004'  # Unable to update endpoint
    END_DELETE_FAILED = 'END005'  # Unable to delete endpoint
    END_INVALID_TYPE = 'END006'  # Invalid endpoint type
    END_VALIDATION_FAILED = 'END007'  # Endpoint validation failed
    END_SERVERS_REQUIRED = 'END008'  # Endpoint servers required
    END_CIRCULAR_DEPENDENCY = 'END009'  # Circular dependency detected
    END_PERMISSION_DENIED = 'END010'  # Insufficient permissions
    END_INVALID_REQUEST = 'END011'  # Invalid endpoint request
    END_MISSING_PROTO = 'END012'  # Missing protobuf definition
    END_PATH_CONFLICT = 'END013'  # Endpoint path conflict
    END_METHOD_CONFLICT = 'END014'  # HTTP method conflict
    END_SERVER_INVALID = 'END015'  # Invalid server configuration
    END_TIMEOUT_INVALID = 'END016'  # Invalid timeout value
    END_RETRIES_INVALID = 'END017'  # Invalid retry configuration
    END_HEADERS_INVALID = 'END018'  # Invalid headers configuration
    END_BODY_TRANSFORM_INVALID = 'END019'  # Invalid body transformation
    END_RESPONSE_TRANSFORM_INVALID = 'END020'  # Invalid response transformation
    END_LOAD_BALANCER_INVALID = 'END021'  # Invalid load balancer config
    END_CIRCUIT_BREAKER_INVALID = 'END022'  # Invalid circuit breaker config
    END_RATE_LIMIT_INVALID = 'END023'  # Invalid rate limit config

    # ========================================================================
    # Role Management Errors (ROLE001-ROLE999)
    # ========================================================================
    ROLE_ALREADY_EXISTS = 'ROLE001'  # Role already exists
    ROLE_CREATE_FAILED = 'ROLE002'  # Unable to create role
    ROLE_NOT_FOUND = 'ROLE004'  # Role not found
    ROLE_NAME_IMMUTABLE = 'ROLE005'  # Role name cannot be changed
    ROLE_UPDATE_FAILED = 'ROLE006'  # Unable to update role
    ROLE_NO_DATA_TO_UPDATE = 'ROLE007'  # No update data provided
    ROLE_DELETE_FAILED = 'ROLE008'  # Unable to delete role
    ROLE_PERMISSION_DENIED = 'ROLE009'  # Insufficient permissions for role
    ROLE_INVALID_REQUEST = 'ROLE010'  # Invalid role request
    ROLE_IN_USE = 'ROLE011'  # Role is in use, cannot delete
    ROLE_PERMISSION_INVALID = 'ROLE013'  # Invalid permission
    ROLE_NAME_INVALID = 'ROLE014'  # Invalid role name format
    ROLE_RESERVED_NAME = 'ROLE015'  # Role name is reserved
    ROLE_DESCRIPTION_REQUIRED = 'ROLE016'  # Role description required

    # ========================================================================
    # Group Management Errors (GRP001-GRP999)
    # ========================================================================
    GRP_ALREADY_EXISTS = 'GRP001'  # Group already exists
    GRP_CREATE_FAILED = 'GRP002'  # Unable to create group
    GRP_NOT_FOUND = 'GRP003'  # Group not found
    GRP_UPDATE_FAILED = 'GRP004'  # Unable to update group
    GRP_DELETE_FAILED = 'GRP005'  # Unable to delete group
    GRP_NAME_IMMUTABLE = 'GRP006'  # Group name cannot be changed
    GRP_NO_DATA_TO_UPDATE = 'GRP007'  # No update data provided
    GRP_PERMISSION_DENIED = 'GRP008'  # Insufficient permissions
    GRP_INVALID_REQUEST = 'GRP009'  # Invalid group request
    GRP_IN_USE = 'GRP010'  # Group in use, cannot delete

    # ========================================================================
    # Subscription Management Errors (SUB001-SUB999)
    # ========================================================================
    SUB_INVALID_API = 'SUB003'  # Invalid API for subscription
    SUB_ALREADY_EXISTS = 'SUB004'  # Subscription already exists
    SUB_NOT_FOUND = 'SUB005'  # Subscription not found
    SUB_CREATE_FAILED = 'SUB006'  # Unable to create subscription
    SUB_PERMISSION_DENIED = 'SUB007'  # Insufficient permissions
    SUB_INVALID_REQUEST = 'SUB008'  # Invalid subscription request
    SUB_DELETE_FAILED = 'SUB009'  # Unable to delete subscription

    # ========================================================================
    # Routing Errors (RTG001-RTG999)
    # ========================================================================
    RTG_ALREADY_EXISTS = 'RTG001'  # Routing already exists
    RTG_CREATE_FAILED = 'RTG002'  # Unable to create routing
    RTG_NOT_FOUND = 'RTG004'  # Routing not found
    RTG_UPDATE_FAILED = 'RTG005'  # Unable to update routing
    RTG_DELETE_FAILED = 'RTG006'  # Unable to delete routing
    RTG_NO_DATA_TO_UPDATE = 'RTG007'  # No update data provided
    RTG_NAME_IMMUTABLE = 'RTG008'  # Routing name cannot be changed
    RTG_PERMISSION_DENIED = 'RTG009'  # Insufficient permissions
    RTG_INVALID_REQUEST = 'RTG010'  # Invalid routing request
    RTG_PRIORITY_CONFLICT = 'RTG011'  # Routing priority conflict
    RTG_PATH_INVALID = 'RTG012'  # Invalid routing path
    RTG_CONDITION_INVALID = 'RTG013'  # Invalid routing condition

    # ========================================================================
    # Credit System Errors (CRD001-CRD999)
    # ========================================================================
    CRD_GROUP_EXISTS = 'CRD001'  # Credit group already exists
    CRD_CREATE_FAILED = 'CRD002'  # Unable to create credit definition
    CRD_GROUP_IMMUTABLE = 'CRD003'  # Credit group name cannot be changed
    CRD_NOT_FOUND = 'CRD004'  # Credit definition not found
    CRD_UPDATE_FAILED = 'CRD005'  # Unable to update credit definition
    CRD_NO_DATA_TO_UPDATE = 'CRD006'  # No update data provided
    CRD_DELETE_NOT_FOUND = 'CRD007'  # Credit definition not found for deletion
    CRD_DELETE_FAILED = 'CRD008'  # Unable to delete credit definition
    CRD_GROUP_NAME_REQUIRED = 'CRD009'  # Credit group name required
    CRD_API_KEY_REQUIRED = 'CRD010'  # API key and header required
    CRD_DATABASE_ERROR = 'CRD011'  # Database error (create)
    CRD_DATABASE_ERROR_UPDATE = 'CRD012'  # Database error (update)
    CRD_DATABASE_ERROR_DELETE = 'CRD013'  # Database error (delete)
    CRD_USERNAME_MISMATCH = 'CRD014'  # Username mismatch in request
    CRD_USER_CREDITS_ERROR = 'CRD015'  # Error saving user credits
    CRD_GET_ALL_ERROR = 'CRD016'  # Error retrieving all credits
    CRD_USER_NOT_FOUND = 'CRD017'  # User credits not found
    CRD_GET_USER_ERROR = 'CRD018'  # Error retrieving user credits
    CRD_LIST_ERROR = 'CRD020'  # Error listing credit definitions
    CRD_FETCH_ERROR = 'CRD021'  # Error fetching credit definition
    CRD_RETRIEVE_ERROR = 'CRD022'  # Error retrieving credit definition

    # ========================================================================
    # Gateway Errors (GTW001-GTW999)
    # ========================================================================
    GTW_UPSTREAM_ERROR = 'GTW001'  # Upstream service error
    GTW_TIMEOUT = 'GTW002'  # Gateway timeout
    GTW_NO_AVAILABLE_SERVERS = 'GTW003'  # No available servers
    GTW_INVALID_REQUEST = 'GTW004'  # Invalid gateway request
    GTW_RATE_LIMIT_EXCEEDED = 'GTW005'  # Rate limit exceeded
    GTW_SERVICE_UNAVAILABLE = 'GTW006'  # Service unavailable
    GTW_AUTHENTICATION_REQUIRED = 'GTW007'  # Authentication required
    GTW_SUBSCRIPTION_REQUIRED = 'GTW008'  # Subscription required
    GTW_CIRCUIT_BREAKER_OPEN = 'GTW010'  # Circuit breaker open
    GTW_INVALID_ENDPOINT = 'GTW011'  # Invalid endpoint configuration
    GTW_PROTO_DECODE_ERROR = 'GTW013'  # Protobuf decode error
    GTW_UNEXPECTED_ERROR = 'GTW999'  # Unexpected gateway error

    # ========================================================================
    # Configuration Errors (CFG001-CFG999)
    # ========================================================================
    CFG_PERMISSION_DENIED = 'CFG001'  # Insufficient config permissions
    CFG_API_PERMISSION_DENIED = 'CFG002'  # Insufficient API config permissions
    CFG_ENDPOINT_PERMISSION_DENIED = 'CFG003'  # Insufficient endpoint permissions
    CFG_GROUP_PERMISSION_DENIED = 'CFG004'  # Insufficient group permissions
    CFG_ROLE_PERMISSION_DENIED = 'CFG005'  # Insufficient role permissions
    CFG_ROUTING_PERMISSION_DENIED = 'CFG006'  # Insufficient routing permissions
    CFG_SUBSCRIPTION_PERMISSION_DENIED = 'CFG007'  # Insufficient subscription permissions
    CFG_NOT_FOUND = 'CFG404'  # Configuration item not found

    # ========================================================================
    # Security Errors (SEC001-SEC999)
    # ========================================================================
    SEC_PERMISSION_DENIED = 'SEC001'  # Insufficient security permissions
    SEC_UPDATE_FAILED = 'SEC002'  # Security settings update failed
    SEC_INVALID_IP = 'SEC003'  # Invalid IP address or CIDR
    SEC_INVALID_SETTING = 'SEC004'  # Invalid security setting
    SEC_PROTECTED_SETTING = 'SEC005'  # Protected security setting

    # ========================================================================
    # Logging Errors (LOG001-LOG999)
    # ========================================================================
    LOG_PERMISSION_DENIED = 'LOG001'  # Insufficient logging permissions
    LOG_INVALID_LEVEL = 'LOG002'  # Invalid log level
    LOG_UPDATE_FAILED = 'LOG003'  # Log level update failed
    LOG_QUERY_FAILED = 'LOG004'  # Log query failed
    LOG_EXPORT_FAILED = 'LOG005'  # Log export failed

    # ========================================================================
    # Monitoring Errors (MON001-MON999)
    # ========================================================================
    MON_PERMISSION_DENIED = 'MON001'  # Insufficient monitoring permissions
    MON_QUERY_FAILED = 'MON002'  # Monitoring query failed
    MON_UNEXPECTED_ERROR = 'MON003'  # Unexpected monitoring error

    # ========================================================================
    # Memory/Storage Errors (MEM001-MEM999)
    # ========================================================================
    MEM_PERMISSION_DENIED = 'MEM001'  # Insufficient memory management permissions
    MEM_DUMP_FAILED = 'MEM002'  # Memory dump failed
    MEM_OPERATION_FAILED = 'MEM003'  # Memory operation failed

    # ========================================================================
    # Demo/Tools Errors (DEMO001-DEMO999, TLS001-TLS999)
    # ========================================================================
    DEMO_ALREADY_SEEDED = 'DEMO001'  # Demo data already seeded
    DEMO_SEED_FAILED = 'DEMO999'  # Demo data seed failed
    TLS_PERMISSION_DENIED = 'TLS001'  # Insufficient tools permissions
    TLS_UNEXPECTED_ERROR = 'TLS999'  # Unexpected tools error

    # ========================================================================
    # General/System Errors (GEN001-GEN999, ISE001-ISE999)
    # ========================================================================
    GEN_INVALID_REQUEST = 'GEN001'  # Invalid request format
    GEN_VALIDATION_ERROR = 'GEN002'  # Validation error
    ISE_INTERNAL_ERROR = 'ISE001'  # Internal server error

    # ========================================================================
    # Request Validation Errors (REQ001-REQ999, VAL001-VAL999)
    # ========================================================================
    REQ_BODY_TOO_LARGE = 'REQ001'  # Request body too large
    VAL_INVALID_JSON = 'VAL001'  # Invalid JSON format
    JWT_DECODE_ERROR = 'JWT001'  # JWT decode error

    # ========================================================================
    # Rate Limiting Errors
    # ========================================================================
    RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED'  # IP-based rate limit exceeded


# Alias for backward compatibility
class ErrorCodes(ErrorCode):
    """Deprecated: Use ErrorCode instead."""
    pass
