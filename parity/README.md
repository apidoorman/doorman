# Gateway Parity Harness

This directory holds deterministic inputs shared by the Python reference gateway
and the Rust gateway. Scenarios must start from isolated, identical database and
Redis fixtures and compare wire output, upstream requests, decision traces, and
state transitions.
