"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

class RoleModel:

    def __init__ (self, role_name = None, role_description = None, manage_users = None, manage_apis = None, manage_endpoints = None, manage_groups = None, manage_roles = None):
        self.role_name = role_name
        self.role_description = role_description
        self.manage_users = manage_users
        self.manage_apis = manage_apis
        self.manage_endpoints = manage_endpoints
        self.manage_groups = manage_groups
        self.manage_roles = manage_roles

    def validate_api_creation(self):
        missing = []
        if not self.role_name: missing.append("role_name")
        if not self.role_description: missing.append("role_description")
        if not self.manage_users: missing.append("manage_users")
        if not self.manage_apis: missing.append("manage_apis")
        if not self.manage_endpoints: missing.append("manage_endpoints")
        if not self.manage_groups: missing.append("manage_groups")
        if not self.manage_roles: missing.append("manage_roles")
        if missing:
            raise ValueError(f"Missing required field(s): {', '.join(missing)}")