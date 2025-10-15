"""
Root-level pytest configuration shim.

Allows running tests from backend-services/tests using root-level nodeids
like `pytest -v test_ip_filter_platform.py::test_...` by dynamically
loading the backend-services test fixtures into this module's namespace.
"""

import os
import sys
import runpy

def _path(*parts: str) -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), *parts))

_BS_DIR = _path('backend-services')
if _BS_DIR not in sys.path:
    sys.path.insert(0, _BS_DIR)

def _load_backend_services_conftest():
    """Execute backend-services/tests/conftest.py and copy its fixtures here.

    This makes its fixtures visible to pytest when collecting root-level tests.
    """
    bs_conftest = _path('backend-services', 'tests', 'conftest.py')
    if not os.path.exists(bs_conftest):
        return
    ns = runpy.run_path(bs_conftest)
    g = globals()
    for k, v in ns.items():
        if k in ('__name__', '__file__', '__package__', '__loader__', '__spec__'):
            continue
        g.setdefault(k, v)

_load_backend_services_conftest()

