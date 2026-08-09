"""
Shim for backend-services/tests/test_platform_expanded.py

Allows running from repo root:
  pytest -v scripts/test-shims/test_platform_expanded.py::test_security_and_memory_dump_restore
"""

import os
import sys
import runpy


def _path(*parts: str) -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', *parts))


_BS_DIR = _path('backend-services')
if _BS_DIR not in sys.path:
    sys.path.insert(0, _BS_DIR)


def _load_tests():
    src = _path('backend-services', 'tests', 'test_platform_expanded.py')
    if not os.path.exists(src):
        raise SystemExit(f"Upstream test file not found: {src}")
    ns = runpy.run_path(src)
    g = globals()
    for k, v in ns.items():
        if k in ('__name__', '__file__', '__package__', '__loader__', '__spec__'):
            continue
        g.setdefault(k, v)


_load_tests()

