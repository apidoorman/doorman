"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

class RequestModel:

    def __init__ (self, method = None, path = None, headers = None, json = None, args = None, user = None):
        self.method = method
        self.path = path
        self.headers = headers
        self.json = json
        self.args = args
        self.user = user