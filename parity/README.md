# Gateway Contract Fixtures

This directory holds the frozen public wire contracts captured before the Rust
cutover. The Rust integration suite uses them to detect accidental compatibility
regressions.

## Contract Fixtures

- `contracts/schema.json` documents the fixture format.
- `contracts/fixtures/*.json` are checked-in goldens for canonical
  `/api/*` behavior.
- `schemas/decision-trace.schema.json` documents retained decision traces.

Run the Rust contract comparisons with the rest of the gateway suite:

```bash
make test
```

The Python oracle is pinned in `reference.json`. Verify the commit, dependency
hash, OpenAPI inventory, test-file inventory, and fixture coverage with:

```bash
make parity-reference
```

With the pinned Python server on port 3102 and Rust on port 3101, run the
zero-difference public-wire comparison with:

```bash
make parity-differential
```

The differential runner exits non-zero for any unclassified difference and can
write a machine-readable report through `PARITY_REPORT`.

Contract comparison normalizes only volatile fields such as request IDs and
timestamps. Meaningful wire headers, including compression, gRPC status/encoding,
cookies, and rate-limit headers, remain part of the contract.
