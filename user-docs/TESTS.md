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

Rust integration tests use in-process upstream servers and do not require MongoDB or Redis. Storage and platform tests use the native in-memory backend. Checked-in parity fixtures preserve the pre-migration public wire contract.

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

## Container checks

```bash
docker compose config
docker build -t doorman:local .
```

The former Python suites are retained only as migration reference under `archive/python-backend/`; they are excluded from CI and runtime images.
