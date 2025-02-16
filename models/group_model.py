"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

class GroupModel:

    def __init__ (self, group_name = None, group_description = None, api_access = None):
        self.group_name = group_name
        self.group_description = group_description
        self.api_access = api_access

    def validate_endpoint_creation(self):
        missing = []
        if not self.group_name: missing.append("group_name")
        if not self.group_description: missing.append("group_description")
        if not self.api_access: missing.append("api_access")
        if missing:
            raise ValueError(f"Missing required field(s): {', '.join(missing)}")