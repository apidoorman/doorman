"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

# Internal Imports
from models.api_model import ApiModel

class EndpointModel:

    def __init__ (self, api_name = None, api_version = None, endpoint_method = None, endpoint_uri = None):
        self.api_name = api_name
        self.api_version = api_version
        self.endpoint_method = endpoint_method
        self.endpoint_uri = endpoint_uri

    def validate_endpoint_creation(self):
        missing = []
        if not self.api_name: missing.append("api_name")
        if not self.api_version: missing.append("api_version")
        if not self.endpoint_method: missing.append("endpoint_method")
        if not self.endpoint_uri: missing.append("endpoint_uri")
        if missing:
            raise ValueError(f"Missing required field(s): {', '.join(missing)}")