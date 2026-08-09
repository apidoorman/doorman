SHELL := /bin/bash

PORT ?= $(shell grep '^PORT=' .env 2>/dev/null | cut -d'=' -f2 || echo 3001)
ADMIN_EMAIL ?= $(shell grep '^DOORMAN_ADMIN_EMAIL=' .env 2>/dev/null | cut -d'=' -f2)
ADMIN_PASSWORD ?= $(shell grep '^DOORMAN_ADMIN_PASSWORD=' .env 2>/dev/null | cut -d'=' -f2)
BASE_URL ?= http://localhost:$(PORT)
GATEWAY_LOAD_BASE_URL ?= http://localhost:3001

.PHONY: check test unit unitq rust-test rust-clippy rust-fmt-check web-build smoke preflight live liveq gateway-load clean clean-deep

check: rust-fmt-check rust-clippy test

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
	cargo test --test live_tcp_port_3001 --manifest-path gateway-rs/Cargo.toml -- --nocapture

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
