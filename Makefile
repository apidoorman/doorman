SHELL := /bin/bash

PORT ?= $(shell grep '^PORT=' .env 2>/dev/null | cut -d'=' -f2 || echo 3001)
ADMIN_EMAIL ?= $(shell grep '^DOORMAN_ADMIN_EMAIL=' .env 2>/dev/null | cut -d'=' -f2)
ADMIN_PASSWORD ?= $(shell grep '^DOORMAN_ADMIN_PASSWORD=' .env 2>/dev/null | cut -d'=' -f2)
BASE_URL ?= http://localhost:$(PORT)
GATEWAY_LOAD_BASE_URL ?= http://localhost:3001

.PHONY: check test unit unitq rust-test rust-clippy rust-fmt-check web-build parity parity-reference parity-ledger parity-contracts parity-differential parity-performance smoke preflight live liveq gateway-load clean clean-deep

check: rust-fmt-check rust-clippy test

parity: parity-reference parity-ledger parity-contracts

parity-reference:
	python3 scripts/check_parity_reference.py

parity-ledger:
	python3 scripts/generate_test_coverage_ledger.py --check

parity-contracts:
	cargo test --manifest-path gateway-rs/Cargo.toml --locked --test parity_contracts --test openapi_parity --test auth_rate_parity

parity-differential:
	python3 scripts/differential_parity.py \
		--python-url "$${PYTHON_PARITY_URL:-http://127.0.0.1:3102}" \
		--rust-url "$${RUST_PARITY_URL:-http://127.0.0.1:3101}" \
		--report "$${PARITY_REPORT:-parity-report.json}"

parity-performance:
	python3 scripts/benchmark_parity.py \
		--python-pid "$${PYTHON_PARITY_PID:?set PYTHON_PARITY_PID}" \
		--rust-pid "$${RUST_PARITY_PID:?set RUST_PARITY_PID}" \
		--report "$${PARITY_PERF_REPORT:-parity-performance.json}"

test unit unitq rust-test:
	cargo test --manifest-path gateway-rs/Cargo.toml --locked

rust-clippy:
	cargo clippy --manifest-path gateway-rs/Cargo.toml --locked --all-targets --all-features -- -D warnings

rust-fmt-check:
	cargo fmt --manifest-path gateway-rs/Cargo.toml --all -- --check

web-build:
	npm --prefix web-client ci
	npm --prefix web-client run build

smoke preflight live liveq:
	BASE_URL=$(BASE_URL) \
	DOORMAN_ADMIN_EMAIL=$(ADMIN_EMAIL) \
	DOORMAN_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
	bash scripts/preflight.sh

test-live-tcp:
	PATH="$(HOME)/.cargo/bin:$(PATH)" \
	LIVE_SERVER_URL=$(BASE_URL) \
	DOORMAN_ADMIN_EMAIL=$(ADMIN_EMAIL) \
	DOORMAN_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
	cargo test --test live_tcp_port_3001 --manifest-path gateway-rs/Cargo.toml -- --ignored --nocapture

gateway-load:
	BASE_URL=$(GATEWAY_LOAD_BASE_URL) bash scripts/run_perf_check.sh

clean:
	@echo "Cleaning Rust, web, and runtime artifacts..."
	@rm -rf gateway-rs/target web-client/.next
	@rm -f doorman.pid
	@echo "Done."

clean-deep: clean
	@echo "Removing generated runtime data..."
	@rm -rf data logs
	@echo "Done."
