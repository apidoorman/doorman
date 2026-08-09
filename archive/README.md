# Python backend archive

This directory preserves the pre-Rust backend, its tests, and migration tooling for historical contract review.

It is not an executable fallback:

- no active build, entrypoint, Compose service, CI job, or Make target imports it;
- the directory is excluded from Docker build contexts;
- all production gateway and `/platform/*` behavior is implemented by `gateway-rs`;
- fixes must be made in Rust, not in this archive.

The archived source may be removed after the Rust parity window closes and retained contract fixtures are no longer needed for review.
