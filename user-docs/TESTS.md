Doorman Test Runs
=================

This guide shows how to run the different test suites: unit/integration tests, live tests (against a running server), and load tests.

Prerequisites
-------------
- Python 3.11+ with `pip`.
- From repo root: `pip install -r backend-services/requirements.txt`
- Many tests run in memory mode by default (no external services). Live tests and load tests require a running server.

Unit/Integration Tests (in-process)
-----------------------------------
- Run all backend tests:
  - pytest -q backend-services/tests
- Run a single file or test:
  - pytest -q backend-services/tests/test_security.py
  - pytest -q backend-services/tests -k gateway_validation
- With coverage:
  - pytest -q backend-services/tests --cov=backend-services --cov-report=term-missing

Notes
- The test harness sets safe defaults (e.g., memory DB, relaxed rate limits).
- If you need to force memory mode explicitly: `MEM_OR_EXTERNAL=MEM pytest -q backend-services/tests`

Live Tests (end-to-end against a running server)
-----------------------------------------------
These tests hit a real Doorman instance via HTTP. Start Doorman separately, then point tests at it.

1) Start Doorman locally (example memory mode):
   - PORT=8000 THREADS=1 MEM_OR_EXTERNAL=MEM \
     DOORMAN_ADMIN_PASSWORD='test-only-password-12chars' \
     JWT_SECRET_KEY='local-dev-jwt-secret-key-please-change' \
     python backend-services/doorman.py start

2) Run live tests with base URL and admin creds:
   - DOORMAN_BASE_URL=http://localhost:8000 \
     DOORMAN_ADMIN_EMAIL=admin@doorman.dev \
     DOORMAN_ADMIN_PASSWORD='test-only-password-12chars' \
     pytest -q backend-services/live-tests

3) Optional flags to focus areas:
   - pytest -q backend-services/live-tests --grpc
   - pytest -q backend-services/live-tests --graph

Notes
- Live tests expect `/api/health` to be healthy before starting.
- Some tests spin up local echo servers internally (see `live-tests/servers.py`); no manual setup is needed.
- Stop the server when done: `python backend-services/doorman.py stop`

Load Tests (k6 preferred, Locust optional)
-----------------------------------------
Run against a running Doorman instance. k6 script writes a JSON summary; helper scripts compare against a baseline to detect regressions.

- k6 quick run (BASE_URL defaults to http://localhost:8000):
  - k6 run load-tests/k6-load-test.js --env BASE_URL=http://localhost:8000

- End-to-end perf check with regression gating:
  - BASE_URL=http://localhost:8000 bash scripts/run_perf_check.sh
  - First time: create a baseline from a known-good run:
    - mkdir -p load-tests/baseline
    - cp load-tests/k6-summary.json load-tests/baseline/k6-summary.json

- Compare two summaries manually:
  - python3 scripts/compare_perf.py load-tests/k6-summary.json load-tests/baseline/k6-summary.json

- Locust (optional):
  - locust -f load-tests/locust-load-test.py --host=http://localhost:8000 --headless \
    --users 50 --spawn-rate 5 --run-time 5m

Useful Scripts
--------------
- Smoke/preflight:
  - bash scripts/smoke.sh
  - bash scripts/preflight.sh
- Coverage helper:
  - bash scripts/coverage_all.sh

Troubleshooting
---------------
- Port/health: Ensure your server’s `PORT` matches `DOORMAN_BASE_URL`.
- Auth: Admin password must match the one you started Doorman with.
- k6 missing: Install from https://k6.io/docs/get-started/installation/
- Baseline not found: Create one per the Load Tests section above.

