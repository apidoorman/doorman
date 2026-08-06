SHELL := /bin/bash

# Read configuration from .env files
PORT ?= $(shell grep '^PORT=' backend-services/.env 2>/dev/null | cut -d'=' -f2 || grep '^PORT=' .env 2>/dev/null | cut -d'=' -f2 || echo 3001)
ADMIN_EMAIL ?= $(shell grep '^DOORMAN_ADMIN_EMAIL=' backend-services/.env 2>/dev/null | cut -d'=' -f2 || grep '^DOORMAN_ADMIN_EMAIL=' .env 2>/dev/null | cut -d'=' -f2)
ADMIN_PASSWORD ?= $(shell grep '^DOORMAN_ADMIN_PASSWORD=' backend-services/.env 2>/dev/null | cut -d'=' -f2 || grep '^DOORMAN_ADMIN_PASSWORD=' .env 2>/dev/null | cut -d'=' -f2)

# Construct BASE_URL from PORT (can still override on CLI).
# Always http:// — HTTPS_ONLY is a server-side cookie/CSRF setting;
# the server itself listens on plain HTTP (TLS terminated at reverse proxy).
BASE_URL ?= http://localhost:$(PORT)
GATEWAY_LOAD_BASE_URL ?= http://localhost:3001

# Set to 1 when running tests against Doorman in Docker (affects test server host references)
DOORMAN_IN_DOCKER ?= 0

.PHONY: unit unitq live liveq live-docker liveq-docker smoke soak preflight

unit:
	cd backend-services && pytest

unitq:
	cd backend-services && pytest -q

live:
	cd backend-services/live-tests && \
	  DOORMAN_BASE_URL=$(BASE_URL) \
	  DOORMAN_ADMIN_EMAIL=$(ADMIN_EMAIL) \
	  DOORMAN_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
	  DOORMAN_IN_DOCKER=$(DOORMAN_IN_DOCKER) \
	  pytest

liveq:
	cd backend-services/live-tests && \
	  DOORMAN_BASE_URL=$(BASE_URL) \
	  DOORMAN_ADMIN_EMAIL=$(ADMIN_EMAIL) \
	  DOORMAN_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
	  DOORMAN_IN_DOCKER=$(DOORMAN_IN_DOCKER) \
	  pytest -q

# Run live tests against Doorman running in Docker
live-docker:
	cd backend-services/live-tests && \
	  DOORMAN_BASE_URL=$(BASE_URL) \
	  DOORMAN_ADMIN_EMAIL=$(ADMIN_EMAIL) \
	  DOORMAN_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
	  DOORMAN_IN_DOCKER=1 \
	  pytest

liveq-docker:
	cd backend-services/live-tests && \
	  DOORMAN_BASE_URL=$(BASE_URL) \
	  DOORMAN_ADMIN_EMAIL=$(ADMIN_EMAIL) \
	  DOORMAN_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
	  DOORMAN_IN_DOCKER=1 \
	  pytest -q

# Lightweight readiness + platform smoke (optionally gateway if SMOKE_UPSTREAM_URL provided)
smoke preflight:
	BASE_URL=$(BASE_URL) \
	DOORMAN_ADMIN_EMAIL=$(ADMIN_EMAIL) \
	DOORMAN_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
	 bash scripts/preflight.sh

# Placeholder: requires k6/locust. Provide your own script path via SOAK_SCRIPT.
soak:
	@echo "Define SOAK_SCRIPT and ARGS to run your soak tool, e.g.:" ; \
	 echo "  SOAK_SCRIPT=scripts/k6-rest-smoke.js ARGS='-d 1h -u 200' make soak" ; \
	 if [[ -n "$(SOAK_SCRIPT)" ]]; then \
	   k6 run $(ARGS) $(SOAK_SCRIPT) ; \
	 else \
	   echo "No SOAK_SCRIPT provided" ; \
	 fi

.PHONY: coverage-unit coverage-html coverage-all

coverage-unit:
	cd backend-services && \
	  coverage run -m pytest && \
	  coverage report -m

coverage-html:
	cd backend-services && \
	  coverage run -m pytest && \
	  coverage html -d coverage_html && \
	  echo "HTML report at backend-services/coverage_html/index.html"

# Runs server under coverage (parallel mode), executes live-tests, then combines
coverage-all:
	BASE_URL=$(BASE_URL) DOORMAN_ADMIN_EMAIL=$(ADMIN_EMAIL) DOORMAN_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
	 bash scripts/coverage_all.sh

.PHONY: clean clean-deep

# Remove common local build/test artifacts without touching dependencies
clean:
	@echo "Cleaning caches and runtime artifacts..."
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} + || true
	@find . -type d -name ".pytest_cache" -prune -exec rm -rf {} + || true
	@find . -type f -name "*.py[co]" -delete || true
	@find . -type f -name ".DS_Store" -delete || true
	@rm -rf backend-services/platform-logs/*.log backend-services/doorman.pid doorman.pid uvicorn.pid || true
	@rm -rf web-client/.next || true
	@rm -rf gateway-rs/target || true
	@rm -f pytest_backend_verbose.log || true
	@echo "Done."

# Deeper cleanup that also removes generated dev artifacts
clean-deep: clean
	@echo "Removing generated dev artifacts..."
	@rm -rf generated backend-services/generated || true
	@echo "Done."

.PHONY: rust-test rust-clippy rust-fmt-check parity parity-rust parity-python-reference parity-contracts parity-contracts-update gateway-load

rust-test:
	cargo test --manifest-path gateway-rs/Cargo.toml --locked

rust-clippy:
	cargo clippy --manifest-path gateway-rs/Cargo.toml --locked --all-targets --all-features -- -D warnings

rust-fmt-check:
	cargo fmt --manifest-path gateway-rs/Cargo.toml --all -- --check

parity: rust-test parity-rust parity-python-reference parity-contracts

parity-rust:
	cargo test --manifest-path gateway-rs/Cargo.toml --locked --tests

parity-python-reference:
	cd backend-services && pytest -q \
	  tests/test_rest_methods_and_405.py \
	  tests/test_rest_header_and_response_parsing.py \
	  tests/test_request_id_propagation.py \
	  tests/test_soap_gateway_content_types.py \
	  tests/test_graphql_error_flow_and_status.py \
	  tests/test_grpc_streaming_and_metadata.py

parity-contracts:
	cd backend-services && pytest -q tests/test_parity_contract_fixtures.py

parity-contracts-update:
	cd backend-services && UPDATE_PARITY_CONTRACTS=1 pytest -q tests/test_parity_contract_fixtures.py

gateway-load:
	BASE_URL=$(GATEWAY_LOAD_BASE_URL) bash scripts/run_perf_check.sh
