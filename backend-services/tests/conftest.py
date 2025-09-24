"""
Pytest configuration for backend-services tests.

Ensures the backend-services directory is on sys.path so imports like
`from utils...` resolve correctly when tests run from the repo root in CI.
"""

import os
import sys

_HERE = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

