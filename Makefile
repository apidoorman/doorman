SHELL := /bin/bash

# Configurable envs (can override on CLI)
BASE_URL ?= http://localhost:5001
ADMIN_EMAIL ?= admin@localhost
ADMIN_PASSWORD ?= password1

.PHONY: unit unitq live liveq smoke soak preflight

unit:
	cd backend-services && pytest

unitq:
	cd backend-services && pytest -q

live:
	cd backend-services/live-tests && \
	  DOORMAN_BASE_URL=$(BASE_URL) \
	  DOORMAN_ADMIN_EMAIL=$(ADMIN_EMAIL) \
	  DOORMAN_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
	  pytest

liveq:
	cd backend-services/live-tests && \
	  DOORMAN_BASE_URL=$(BASE_URL) \
	  DOORMAN_ADMIN_EMAIL=$(ADMIN_EMAIL) \
	  DOORMAN_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
	  pytest -q

# Lightweight readiness + platform smoke (optionally gateway if SMOKE_UPSTREAM_URL provided)
smoke preflight:
	BASE_URL=$(BASE_URL) \
	STARTUP_ADMIN_EMAIL=$(ADMIN_EMAIL) \
	STARTUP_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
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
	BASE_URL=$(BASE_URL) STARTUP_ADMIN_EMAIL=$(ADMIN_EMAIL) STARTUP_ADMIN_PASSWORD=$(ADMIN_PASSWORD) \
	 bash scripts/coverage_all.sh
