# Gateway Parity Harness

This directory holds deterministic inputs shared by the Python reference gateway
and the Rust gateway. Scenarios must start from isolated, identical database and
Redis fixtures and compare wire output, upstream requests, decision traces, and
state transitions.

## Contract Fixtures

- `contracts/schema.json` documents the fixture format.
- `contracts/fixtures/*.json` are checked-in Python goldens for canonical
  `/api/*` behavior.
- `python/contract_capture.py` contains normalization, validation, and fake
  upstream capture helpers used by the backend parity tests.

Validate fixtures:

```bash
make parity-contracts
```

Regenerate fixtures intentionally after a reviewed Python contract change:

```bash
make parity-contracts-update
```
