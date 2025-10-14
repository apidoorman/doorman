"""
Root-level test shim for backend-services/tests/test_ip_filter_platform.py

Enables running:
  pytest -v test_ip_filter_platform.py::test_...
from the repository root.
"""

import os
import sys
import runpy


def _path(*parts: str) -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), *parts))


# Ensure backend-services is importable for utils/* imports used by tests
_BS_DIR = _path('backend-services')
if _BS_DIR not in sys.path:
    sys.path.insert(0, _BS_DIR)


def _load_tests():
    src = _path('backend-services', 'tests', 'test_ip_filter_platform.py')
    if not os.path.exists(src):
        raise SystemExit(f"Upstream test file not found: {src}")
    ns = runpy.run_path(src)
    g = globals()
    # Merge everything so pytest can collect tests and helpers
    for k, v in ns.items():
        if k in ('__name__', '__file__', '__package__', '__loader__', '__spec__'):
            continue
        g.setdefault(k, v)


_load_tests()

