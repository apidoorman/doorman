These are optional developer shims that used to live at the repo root.

- `test_ip_filter_platform.py` and `test_platform_expanded.py` allow running select backend tests via their shim paths.
- `conftest.py` mirrors backend test fixtures for the shims.
- `sitecustomize.py` mirrors logging redaction behavior for ad-hoc runs; primary copies exist under `backend-services/` and `backend-services/tests/`.

They are not required for normal test execution. Use `make unit` or run `pytest` from `backend-services/`.

