Doorman Live Tests (E2E)

Purpose
- End-to-end tests that exercise a running Doorman backend via HTTP.
- Covers auth, user onboarding, credit defs/usage, REST and SOAP gateway.
- Includes optional GraphQL and gRPC gateway tests (skipped unless deps are present).

Important
- These tests require a live Doorman backend running and reachable.
- They do NOT spin the Doorman app; they only spin lightweight upstream mock servers locally.

Quick Start
- Ensure Doorman backend is running and accessible.
- Export required environment variables:
  - DOORMAN_BASE_URL: e.g. http://localhost:5001
  - DOORMAN_ADMIN_EMAIL: admin login email
  - DOORMAN_ADMIN_PASSWORD: admin password
  - Optional for HTTPS: set correct COOKIE_DOMAIN and CORS in backend to allow cookies.
- Optional feature flags (enable extra tests if deps exist):
  - DOORMAN_TEST_GRAPHQL=1 (requires ariadne, starlette/uvicorn, graphql-core)
  - DOORMAN_TEST_GRPC=1 (requires grpcio, grpcio-tools)

Install deps (example)
  pip install requests

Optional deps for extended coverage
  pip install ariadne uvicorn starlette graphql-core grpcio grpcio-tools

Run
  cd backend-services/live-tests
  pytest -q

Notes
- Tests will automatically fetch/set CSRF token from cookies when needed.
- Upstream mock servers are started on ephemeral ports per test module and torn down afterward.
- gRPC tests upload a .proto via Doorman’s proto endpoint and generate stubs server-side.
- GraphQL tests perform introspection; ensure optional deps are installed.
