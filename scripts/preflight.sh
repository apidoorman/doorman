#!/usr/bin/env bash
set -euo pipefail

# Preflight checks for Doorman gateway
# - Verifies liveness/readiness, metrics reachable
# - Authenticates as admin
# - Optionally smokes REST/SOAP/GraphQL gateway if SMOKE_* upstream URLs are provided
#
# Env:
#   BASE_URL (default http://localhost:5001)
#   STARTUP_ADMIN_EMAIL, STARTUP_ADMIN_PASSWORD (required)
#   SMOKE_REST_UPSTREAM (optional, e.g., http://httpbin.org)
#   SMOKE_SOAP_UPSTREAM (optional)
#   SMOKE_GQL_UPSTREAM  (optional)

BASE_URL="${BASE_URL:-http://localhost:5001}"
EMAIL="${STARTUP_ADMIN_EMAIL:-}"
PASSWORD="${STARTUP_ADMIN_PASSWORD:-}"

if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
  echo "[preflight] ERROR: STARTUP_ADMIN_EMAIL and STARTUP_ADMIN_PASSWORD must be set" >&2
  exit 1
fi

echo "[preflight] Base URL: $BASE_URL"

PASS=0
FAIL=0
WARN=0
note_pass(){ echo "  OK"; PASS=$((PASS+1)); }
note_fail(){ echo "  FAIL: $1" >&2; FAIL=$((FAIL+1)); }
note_warn(){ echo "  WARN: $1" >&2; WARN=$((WARN+1)); }

echo "[1/8] Liveness/readiness"
if curl -fsS "$BASE_URL/platform/monitor/liveness" | jq -e '.status=="alive"' >/dev/null; then note_pass; else note_fail "liveness"; fi
if curl -fsS "$BASE_URL/platform/monitor/readiness" | jq -e '.status=="ready" or .status=="degraded"' >/dev/null; then note_pass; else note_fail "readiness"; fi

echo "[2/8] Login as admin"
COOKIE_JAR="$(mktemp)" ; trap 'rm -f "$COOKIE_JAR"' EXIT
curl -fsS -c "$COOKIE_JAR" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  "$BASE_URL/platform/authorization" >/dev/null
note_pass

echo "[3/8] Metrics endpoint (authenticated)"
if curl -fsS -b "$COOKIE_JAR" "$BASE_URL/platform/monitor/metrics" >/dev/null; then note_pass; else note_fail "metrics"; fi

echo "[4/8] Request-ID headers present"
# Capture headers for liveness call
HDRS="$(mktemp)"; trap 'rm -f "$COOKIE_JAR" "$HDRS"' EXIT
if curl -fsS -D "$HDRS" "$BASE_URL/platform/monitor/liveness" -o /dev/null; then
  if grep -i -q '^X-Request-ID:' "$HDRS" && grep -i -q '^request_id:' "$HDRS"; then
    note_pass
  else
    note_fail "missing request id headers"
  fi
else
  note_fail "request id probe"
fi

ts() { date +%s; }

# Helper to create minimal API and endpoint and subscribe admin
create_api_and_endpoint() {
  local api_name=$1 ver=$2 method=$3 uri=$4 upstream=$5
  curl -fsS -b "$COOKIE_JAR" -H 'Content-Type: application/json' -X POST \
    -d "{\"api_name\":\"$api_name\",\"api_version\":\"$ver\",\"api_description\":\"pf\",\"api_allowed_roles\":[\"admin\"],\"api_allowed_groups\":[\"ALL\"],\"api_servers\":[\"$upstream\"],\"api_type\":\"REST\",\"api_allowed_retry_count\":0}" \
    "$BASE_URL/platform/api" >/dev/null
  curl -fsS -b "$COOKIE_JAR" -H 'Content-Type: application/json' -X POST \
    -d "{\"api_name\":\"$api_name\",\"api_version\":\"$ver\",\"endpoint_method\":\"$method\",\"endpoint_uri\":\"$uri\",\"endpoint_description\":\"pf\"}" \
    "$BASE_URL/platform/endpoint" >/dev/null
  curl -fsS -b "$COOKIE_JAR" -H 'Content-Type: application/json' -X POST \
    -d "{\"username\":\"admin\",\"api_name\":\"$api_name\",\"api_version\":\"$ver\"}" \
    "$BASE_URL/platform/subscription/subscribe" >/dev/null
}

delete_api_and_endpoint() {
  local api_name=$1 ver=$2 method=$3 uri=$4
  # best-effort cleanup
  curl -fsS -b "$COOKIE_JAR" -X DELETE "$BASE_URL/platform/endpoint/$method/$api_name/$ver${uri}" >/dev/null || true
  curl -fsS -b "$COOKIE_JAR" -X DELETE "$BASE_URL/platform/api/$api_name/$ver" >/dev/null || true
}

REST_UP="${SMOKE_REST_UPSTREAM:-}"
SOAP_UP="${SMOKE_SOAP_UPSTREAM:-}"
GQL_UP="${SMOKE_GQL_UPSTREAM:-}"

if [[ -n "$REST_UP" ]]; then
  echo "[5/8] REST gateway smoke"
  name="pfrest-$(ts)" ; ver="v1"
  create_api_and_endpoint "$name" "$ver" GET "/get" "$REST_UP"
  curl -fsS -b "$COOKIE_JAR" "$BASE_URL/api/rest/$name/$ver/get" >/dev/null
  delete_api_and_endpoint "$name" "$ver" GET "/get"
  note_pass
else
  echo "[5/8] REST gateway smoke skipped (set SMOKE_REST_UPSTREAM)"
fi

if [[ -n "$GQL_UP" ]]; then
  echo "[6/8] GraphQL gateway smoke"
  name="pfgql-$(ts)" ; ver="v1"
  create_api_and_endpoint "$name" "$ver" POST "/graphql" "$GQL_UP"
  curl -fsS -b "$COOKIE_JAR" -H 'Content-Type: application/json' \
    -d '{"query":"{ __typename }"}' \
    -H "X-API-Version: $ver" \
    "$BASE_URL/api/graphql/$name" >/dev/null
  delete_api_and_endpoint "$name" "$ver" POST "/graphql"
  note_pass
else
  echo "[6/8] GraphQL gateway smoke skipped (set SMOKE_GQL_UPSTREAM)"
fi

if [[ -n "$SOAP_UP" ]]; then
  echo "[7/8] SOAP gateway smoke"
  name="pfsoap-$(ts)" ; ver="v1"
  create_api_and_endpoint "$name" "$ver" POST "/post" "$SOAP_UP"
  envelope='<?xml version="1.0" encoding="UTF-8"?><Envelope><Body><Ping/></Body></Envelope>'
  curl -fsS -b "$COOKIE_JAR" -H 'Content-Type: application/xml' \
    -d "$envelope" \
    "$BASE_URL/api/soap/$name/$ver/post" >/dev/null
  delete_api_and_endpoint "$name" "$ver" POST "/post"
  note_pass
else
  echo "[7/8] SOAP gateway smoke skipped (set SMOKE_SOAP_UPSTREAM)"
fi

echo "[8/8] XFF/trusted proxies sanity"
# This is a best-effort check: verifies settings and header echo via client_ip_xff
XFF_JSON="$(curl -fsS -b "$COOKIE_JAR" "$BASE_URL/platform/security/settings" || echo '{}')"
TRUST_XFF=$(echo "$XFF_JSON" | jq -r '.trust_x_forwarded_for // false')
TPROX_LEN=$(echo "$XFF_JSON" | jq -r '.xff_trusted_proxies | length // 0')
if [[ "$TRUST_XFF" == "true" && "$TPROX_LEN" -gt 0 ]]; then
  # Send an XFF and ensure server captured it in client_ip_xff field
  SIM_IP=${SIM_XFF_IP:-203.0.113.99}
  XFF_ECHO=$(curl -fsS -H "X-Forwarded-For: $SIM_IP" -b "$COOKIE_JAR" "$BASE_URL/platform/security/settings" | jq -r '.client_ip_xff // ""')
  if [[ "$XFF_ECHO" == "$SIM_IP" ]]; then note_pass; else note_warn "XFF header not observed (check proxy trust/source)"; fi
else
  note_warn "XFF trust disabled or no trusted proxies configured"
fi

echo "[preflight] Summary: PASS=$PASS WARN=$WARN FAIL=$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
