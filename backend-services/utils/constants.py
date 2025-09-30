class Headers:
    REQUEST_ID = 'request_id'

class Defaults:
    PAGE = 1
    PAGE_SIZE = 10
    MAX_MULTIPART_SIZE_BYTES_ENV = 'MAX_MULTIPART_SIZE_BYTES'
    MAX_MULTIPART_SIZE_BYTES_DEFAULT = 5_242_880

class Roles:
    MANAGE_USERS = 'manage_users'
    MANAGE_APIS = 'manage_apis'
    MANAGE_GROUPS = 'manage_groups'
    MANAGE_ENDPOINTS = 'manage_endpoints'
    VIEW_LOGS = 'view_logs'
    EXPORT_LOGS = 'export_logs'
    MANAGE_ROLES = 'manage_roles'

class ErrorCodes:
    UNEXPECTED = 'GTW999'
    HTTP_EXCEPTION = 'GTW998'
    GRPC_GENERATION_FAILED = 'GTW012'
    PATH_VALIDATION = 'GTW013'
    API_NOT_FOUND = 'API002'
    AUTH_REQUIRED = 'AUTH001'
    REQUEST_TOO_LARGE = 'REQ002'
    REQUEST_FILE_TYPE = 'REQ003'

class Messages:
    UNEXPECTED = 'An unexpected error occurred'
    FILE_TOO_LARGE = 'Uploaded file too large'
    ONLY_PROTO_ALLOWED = 'Only .proto files are allowed'
    PERMISSION_MANAGE_APIS = 'User does not have permission to manage APIs'
    GRPC_GEN_FAILED = 'Failed to generate gRPC code'
