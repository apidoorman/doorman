"""
Pytest configuration shim for developer test shims.

Executes backend-services/tests/conftest.py and exposes its fixtures
in this module's namespace for the shim tests in this folder.
"""

import os
import sys
import runpy


def _path(*parts: str) -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', *parts))


_BS_DIR = _path('backend-services')
if _BS_DIR not in sys.path:
    sys.path.insert(0, _BS_DIR)


def _load_backend_services_conftest():
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

