"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

class ApiModel:
    
    def __init__ (self, api_name = None, api_version = None, api_description = None, api_servers = None, api_type = None):
        self.api_name = api_name
        self.api_version = api_version
        self.api_description = api_description
        self.api_servers = api_servers
        self.api_type = api_type

    def validate(self):
        required_errors = self.validate_required_api_creation()
        length_errors = self.validate_length_api_creation()
        errors = []
        if required_errors:
            errors.append(required_errors)
        if length_errors:
            errors.append(length_errors)
        if errors:
            raise ValueError(errors)

    def validate_required_api_creation(self):
        missing = []
        if not self.api_name: missing.append("api_name")
        if not self.api_version: missing.append("api_version")
        if not self.api_description: missing.append("api_description")
        if not self.api_servers: missing.append("api_servers")
        if missing:
            return (f"Missing required field(s): {', '.join(missing)}")
    
    def validate_length_api_creation(self):
        length_errors = []
        if len(self.api_name) < 1 or len(self.api_name) > 25: length_errors.append("1 < api_name < 26")
        if len(self.api_version) < 1 or len(self.api_version) > 2: length_errors.append("1 < api_version < 3")
        if len(self.api_description) < 1 or len(self.api_description) > 127: length_errors.append("1 < api_description < 128")
        if len(self.api_servers) < 1 or len(self.api_servers) > 9: length_errors.append("1 < api_servers < 10")
        if length_errors:
            return (f"Length requirement(s) not met in: {', '.join(length_errors)}")