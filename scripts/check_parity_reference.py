#!/usr/bin/env python3
"""Validate the pinned Python oracle and checked-in compatibility artifacts."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main() -> int:
    reference = json.loads((ROOT / "parity/reference.json").read_text())
    commit = reference["commit"]
    resolved = git("rev-parse", reference["git_ref"]).decode().strip()
    if resolved != commit:
        raise SystemExit(f"parity ref moved: expected {commit}, got {resolved}")

    requirements = git("show", f"{commit}:backend-services/requirements.txt")
    digest = hashlib.sha256(requirements).hexdigest()
    if digest != reference["requirements_sha256"]:
        raise SystemExit("pinned Python requirements hash changed")

    paths = git("ls-tree", "-r", "--name-only", commit).decode().splitlines()
    unit_files = sum(
        path.startswith("backend-services/tests/test_") and path.endswith(".py")
        for path in paths
    )
    live_files = sum(
        path.startswith("backend-services/live-tests/test_") and path.endswith(".py")
        for path in paths
    )
    expected = reference["surface"]
    if (unit_files, live_files) != (
        expected["unit_test_files"],
        expected["live_test_files"],
    ):
        raise SystemExit("pinned Python test inventory changed")

    encoded = (ROOT / "parity/openapi/python-openapi.json.gz.b64").read_text().strip()
    contract = json.loads(gzip.decompress(base64.b64decode(encoded)))
    operation_names = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
    operations = sum(
        method in operation_names
        for path in contract["paths"].values()
        for method in path
    )
    parameters = sum(
        len(operation.get("parameters", []))
        for path in contract["paths"].values()
        for method, operation in path.items()
        if method in operation_names
    )
    observed = {
        "openapi_paths": len(contract["paths"]),
        "openapi_operations": operations,
        "openapi_schemas": len(contract["components"]["schemas"]),
        "openapi_parameters": parameters,
    }
    for key, value in observed.items():
        if value != expected[key]:
            raise SystemExit(f"{key} changed: expected {expected[key]}, got {value}")

    fixtures = sorted((ROOT / "parity/contracts/fixtures").glob("*.json"))
    harness = (ROOT / "gateway-rs/tests/parity_contracts.rs").read_text()
    if len(fixtures) != expected["frozen_contracts"]:
        raise SystemExit("frozen contract count changed without updating the ledger")
    missing = [fixture.stem for fixture in fixtures if f'"{fixture.stem}"' not in harness]
    if missing:
        raise SystemExit(f"frozen contracts not executed by Rust: {', '.join(missing)}")

    print(
        "parity reference verified:",
        f"commit={commit}",
        f"tests={unit_files + live_files}",
        f"operations={operations}",
        f"contracts={len(fixtures)}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
