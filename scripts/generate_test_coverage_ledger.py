#!/usr/bin/env python3
"""Generate and validate the pinned Python-to-Rust test coverage ledger."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "parity/reference.json"
OVERRIDES_PATH = ROOT / "parity/test_coverage_overrides.json"
LEDGER_PATH = ROOT / "parity/test_coverage_ledger.json"
VALID_STATUSES = {"covered", "approved_changed", "approved_obsolete", "missing"}

DOMAIN_ALIASES = {
    "api": "platform/api",
    "auth": "platform/authorization",
    "authorization": "platform/authorization",
    "bandwidth": "gateway/bandwidth",
    "cache": "gateway/cache",
    "compression": "gateway/compression",
    "config": "platform/config",
    "cors": "gateway/cors",
    "credit": "platform/credit",
    "endpoint": "platform/endpoint",
    "endpoints": "platform/endpoint",
    "gateway": "gateway/general",
    "graphql": "gateway/graphql",
    "grpc": "gateway/grpc",
    "group": "platform/group",
    "health": "operations/health",
    "hot": "platform/hot-reload",
    "ip": "gateway/ip-policy",
    "jwt": "platform/authorization",
    "logging": "platform/logging",
    "memory": "platform/memory",
    "metrics": "operations/metrics",
    "monitor": "operations/monitor",
    "quota": "platform/quota",
    "rate": "platform/rate-limits",
    "rest": "gateway/rest",
    "role": "platform/role",
    "routing": "platform/routing",
    "security": "platform/security",
    "soap": "gateway/soap",
    "subscription": "platform/subscription",
    "tier": "platform/tier",
    "tools": "platform/tools",
    "user": "platform/user",
    "validation": "gateway/validation",
    "vault": "platform/vault",
}


def git_text(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def iter_test_nodes(nodes: list[ast.stmt], parents: tuple[str, ...] = ()) -> Iterator[tuple[str, int]]:
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            yield "::".join((*parents, node.name)), node.lineno
        elif isinstance(node, ast.ClassDef):
            yield from iter_test_nodes(node.body, (*parents, node.name))


def pinned_test_paths(commit: str) -> list[str]:
    paths = git_text(
        "ls-tree",
        "-r",
        "--name-only",
        commit,
        "--",
        "backend-services/tests",
        "backend-services/live-tests",
    ).splitlines()
    return sorted(
        path
        for path in paths
        if Path(path).name.startswith("test_") and path.endswith(".py")
    )


def domain_for(path: str) -> str:
    suite = "live" if path.startswith("backend-services/live-tests/") else "unit"
    stem = Path(path).stem.removeprefix("test_")
    tokens = (token for token in stem.split("_") if not token.isdigit())
    domain_key = next((token for token in tokens if token in DOMAIN_ALIASES), "other")
    return f"{suite}/{DOMAIN_ALIASES.get(domain_key, 'other')}"


def load_overrides() -> dict[str, dict[str, Any]]:
    data = json.loads(OVERRIDES_PATH.read_text())
    if data.get("schema_version") != 1 or not isinstance(data.get("entries"), dict):
        raise ValueError("test coverage overrides must contain schema_version=1 and entries")
    return data["entries"]


def validate_override(test_id: str, override: dict[str, Any]) -> None:
    status = override.get("status")
    if status not in VALID_STATUSES:
        raise ValueError(f"{test_id}: invalid status {status!r}")
    rust_tests = override.get("rust_tests", [])
    if status == "covered" and not rust_tests:
        raise ValueError(f"{test_id}: covered entries require assertion-level rust_tests")
    if status.startswith("approved_") and not override.get("rationale"):
        raise ValueError(f"{test_id}: approved entries require rationale")
    if not isinstance(rust_tests, list) or not all(isinstance(item, str) for item in rust_tests):
        raise ValueError(f"{test_id}: rust_tests must be a list of strings")


def build_ledger() -> dict[str, Any]:
    reference = json.loads(REFERENCE_PATH.read_text())
    commit = reference["commit"]
    overrides = load_overrides()
    entries: list[dict[str, Any]] = []

    for path in pinned_test_paths(commit):
        source = git_text("show", f"{commit}:{path}")
        module = ast.parse(source, filename=path)
        suite = "live" if path.startswith("backend-services/live-tests/") else "unit"
        for test_name, line in iter_test_nodes(module.body):
            test_id = f"{path}::{test_name}"
            override = overrides.pop(test_id, None)
            if override is None:
                override = {"status": "missing", "rust_tests": [], "notes": "Unreviewed."}
            validate_override(test_id, override)
            entries.append(
                {
                    "id": test_id,
                    "source": {"path": path, "line": line, "suite": suite},
                    "domain": domain_for(path),
                    "status": override["status"],
                    "rust_tests": override.get("rust_tests", []),
                    "notes": override.get("notes", ""),
                    **({"rationale": override["rationale"]} if "rationale" in override else {}),
                }
            )

    if overrides:
        unknown = ", ".join(sorted(overrides))
        raise ValueError(f"overrides refer to tests absent from the pinned reference: {unknown}")

    status_counts = Counter(entry["status"] for entry in entries)
    domain_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for entry in entries:
        domain_counts[entry["domain"]][entry["status"]] += 1

    return {
        "schema_version": 1,
        "reference": {"git_ref": reference["git_ref"], "commit": commit},
        "generation": {
            "command": "python3 scripts/generate_test_coverage_ledger.py --write",
            "status_values": sorted(VALID_STATUSES),
        },
        "summary": {
            "total_test_cases": len(entries),
            "status_counts": dict(sorted(status_counts.items())),
            "domain_status_counts": {
                domain: dict(sorted(counts.items())) for domain, counts in sorted(domain_counts.items())
            },
        },
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="regenerate the checked-in ledger")
    mode.add_argument("--check", action="store_true", help="verify the checked-in ledger is current")
    args = parser.parse_args()

    try:
        ledger = build_ledger()
    except (OSError, ValueError, subprocess.CalledProcessError, SyntaxError) as error:
        print(f"test coverage ledger error: {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(ledger, indent=2, sort_keys=True) + "\n"
    if args.write:
        LEDGER_PATH.write_text(rendered)
        print(f"wrote {LEDGER_PATH.relative_to(ROOT)} with {ledger['summary']['total_test_cases']} tests")
        return 0

    if not LEDGER_PATH.exists() or LEDGER_PATH.read_text() != rendered:
        print("test coverage ledger is stale; run python3 scripts/generate_test_coverage_ledger.py --write", file=sys.stderr)
        return 1

    summary = ledger["summary"]
    print(
        "test coverage ledger verified:",
        f"tests={summary['total_test_cases']}",
        " ".join(f"{status}={count}" for status, count in summary["status_counts"].items()),
    )
    for domain, counts in summary["domain_status_counts"].items():
        print(f"  {domain}: " + " ".join(f"{status}={count}" for status, count in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
