# Testing

The active gateway and control plane test suite is entirely Rust-based.

## Prerequisites

- Rust 1.88 with `rustfmt` and `clippy`
- Node.js 20 for the dashboard build
- Docker for image and Compose validation

## Local checks

From the repository root:

```bash
make check
make web-build
```

The equivalent direct commands are:

```bash
cargo fmt --manifest-path gateway-rs/Cargo.toml --all -- --check
cargo clippy --manifest-path gateway-rs/Cargo.toml --locked --all-targets --all-features -- -D warnings
cargo test --manifest-path gateway-rs/Cargo.toml --locked
npm --prefix web-client ci
npm --prefix web-client run build
```

Rust integration tests use in-process upstream servers and do not require MongoDB or Redis. Storage and platform tests use the native in-memory backend. Checked-in parity fixtures preserve the pre-Rust public wire contract.

## Live smoke test

Start Doorman:

```bash
cp .env.demo .env
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build
```

In another terminal:

```bash
make smoke
```

## Shared-storage verification

Use the external profile when testing MongoDB/Redis behavior:

```bash
MEM_OR_EXTERNAL=REDIS docker compose --profile external up --build
make smoke
```

## Release evidence check

A release candidate must include a fresh zero-difference differential report, a
passing Python-versus-Rust performance report, and the log from the isolated
MongoDB/Redis suite. The final check is intentionally fail-closed:

```bash
ENV=production MEM_OR_EXTERNAL=REDIS \
HTTPS_ONLY=true CORS_STRICT=true LOCAL_HOST_IP_BYPASS=false \
DOORMAN_ADMIN_EMAIL=admin@example.com \
DOORMAN_ADMIN_PASSWORD='use-a-real-secret' \
JWT_SECRET_KEY='use-a-unique-signing-key' \
JWT_ISSUER=doorman-production JWT_AUDIENCE=doorman-clients \
ALLOWED_ORIGINS=https://admin.example.com \
DISCOVERY_ALLOWED_HOSTS=api.example.com \
MONGO_DB_HOSTS=mongo.example.com:27017 \
MONGO_DB_USER=doorman-release MONGO_DB_PASSWORD='use-a-real-mongo-secret' \
REDIS_HOST=redis.example.com REDIS_PASSWORD='use-a-real-redis-secret' \
PARITY_REPORT=release-evidence/differential.json \
PARITY_PERF_REPORT=release-evidence/performance.json \
EXTERNAL_STORAGE_LOG=release-evidence/external-storage.log \
RELEASE_OPERATIONS_REPORT=release-evidence/operations.json \
make release-check
```

Evidence defaults to a maximum age of 24 hours; set
`DOORMAN_RELEASE_EVIDENCE_MAX_AGE_HOURS` only when the release policy explicitly
allows a longer review window. Scheduled CI runs the external-storage suite and
retains its Compose logs for 14 days, including on failures.

The differential report is accepted only when it records the SHA-256 of the
checked-in `parity/differential/scenarios.json` and one result for each of its
scenarios plus the OpenAPI comparison. This prevents a partial or empty
zero-difference report from being used as release evidence.

`operations.json` is the signed-off record produced from the release runbook.
It must be a schema-version-1 JSON object with each of these fields set to
`{"passed": true}`: `image_smoke`, `restore_rehearsal`, `canary`, and
`rollback`. The checker rejects an incomplete or failed rehearsal record.

The performance report must come from `make parity-performance` using four
representative, policy-enabled candidate routes. Set `PARITY_PERF_SCENARIOS` to
a private JSON file containing named `rest`, `graphql`, `soap`, and `grpc`
entries. Each entry has `python_url`, `rust_url`, and an optional `request`
object (`method`, string-map `headers`, and string `body`), so POST-based
GraphQL, SOAP, and gRPC requests are measured faithfully. The benchmark never
writes request headers or bodies to its report. The release checker rejects a
health-only or incomplete performance report.

## Container checks

```bash
docker compose config
docker build -t doorman:local .
```
