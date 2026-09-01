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

## Python-to-Rust test coverage ledger

`test_coverage_ledger.json` is the generated, pinned inventory of every Python
test case in the frozen reference. `test_coverage_overrides.json` is the small,
reviewed source of truth for its disposition and exact Rust assertion mapping.
The format is documented by `test_coverage_ledger.schema.json`.

Each case is one of `covered`, `approved_changed`, `approved_obsolete`, or
`missing`. A case can be marked `covered` only with one or more Rust test IDs
whose assertions cover the Python case; a similarly named or broader test is
not sufficient. Approved changes and obsoletions require a rationale. Unlisted
cases intentionally generate as `missing`, so progress cannot be inferred.

After reviewing a case, update the override file and regenerate the ledger:

```bash
python3 scripts/generate_test_coverage_ledger.py --write
make parity-ledger
```

`make parity` and Rust CI verify that the checked-in ledger exactly matches the
pinned commit. The verification report includes counts by suite/domain and
status, allowing incremental migration work to target a concrete gap.

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
