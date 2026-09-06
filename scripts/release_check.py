#!/usr/bin/env python3
"""Validate the evidence and production configuration required for a release.

This deliberately does not build or deploy anything.  It is the final, fail-closed
evidence check to run after the release commands have generated their reports.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REQUIRED_ENVIRONMENT = {
    "ENV": {"production"},
    "MEM_OR_EXTERNAL": {"redis", "external"},
    "HTTPS_ONLY": {"true"},
    "CORS_STRICT": {"true"},
    "LOCAL_HOST_IP_BYPASS": {"false"},
}
REQUIRED_VALUES = (
    "DOORMAN_ADMIN_EMAIL",
    "DOORMAN_ADMIN_PASSWORD",
    "JWT_SECRET_KEY",
    "JWT_ISSUER",
    "JWT_AUDIENCE",
    "ALLOWED_ORIGINS",
    "DISCOVERY_ALLOWED_HOSTS",
    "MONGO_DB_HOSTS",
    "MONGO_DB_USER",
    "MONGO_DB_PASSWORD",
    "REDIS_HOST",
    "REDIS_PASSWORD",
    "PARITY_REPORT",
    "PARITY_PERF_REPORT",
    "EXTERNAL_STORAGE_LOG",
    "RELEASE_OPERATIONS_REPORT",
)
PLACEHOLDERS = {"", "please-change-me", "changeme", "change-me", "example", "todo"}
REQUIRED_PERFORMANCE_PROFILES = ("rest", "graphql", "soap", "grpc")
PERFORMANCE_METRICS = (
    "throughput_rps",
    "p95_latency_ms",
    "error_rate",
    "peak_rss_bytes",
)


def fail(message: str) -> None:
    raise ValueError(message)


def required_environment() -> None:
    for name, allowed in REQUIRED_ENVIRONMENT.items():
        value = os.environ.get(name, "").strip().lower()
        if value not in allowed:
            fail(f"{name} must be one of {', '.join(sorted(allowed))}")
    for name in REQUIRED_VALUES:
        value = os.environ.get(name, "").strip()
        if value.lower() in PLACEHOLDERS:
            fail(f"{name} must be set to a non-placeholder value")
    for name in ("DOORMAN_ADMIN_PASSWORD", "JWT_SECRET_KEY", "MONGO_DB_PASSWORD", "REDIS_PASSWORD"):
        if len(os.environ[name].strip()) < 16:
            fail(f"{name} must be at least 16 characters")


def report_path(name: str) -> Path:
    path = Path(os.environ[name]).expanduser()
    if not path.is_file() or path.stat().st_size == 0:
        fail(f"{name} must point to a non-empty report file: {path}")
    max_age = float(os.environ.get("DOORMAN_RELEASE_EVIDENCE_MAX_AGE_HOURS", "24"))
    if max_age <= 0:
        fail("DOORMAN_RELEASE_EVIDENCE_MAX_AGE_HOURS must be greater than zero")
    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > max_age * 3600:
        fail(f"{name} is older than the allowed evidence age ({max_age:g} hours): {path}")
    return path


def load_report(name: str) -> dict[str, Any]:
    path = report_path(name)
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"{name} is not valid JSON: {error}")
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        fail(f"{name} must be a schema_version 1 JSON report")
    return value


def validate_reports() -> None:
    differential = load_report("PARITY_REPORT")
    if differential.get("differences") != 0 or not isinstance(differential.get("results"), list):
        fail("PARITY_REPORT must contain zero unapproved differences and a results list")
    scenario_path = Path(__file__).resolve().parents[1] / "parity/differential/scenarios.json"
    expected_hash = hashlib.sha256(scenario_path.read_bytes()).hexdigest()
    if differential.get("scenario_manifest_sha256") != expected_hash:
        fail("PARITY_REPORT must be generated from the checked-in differential scenario manifest")
    expected_scenarios = {
        case["name"] for case in json.loads(scenario_path.read_text())
    } | {"openapi"}
    actual_scenarios = {
        result.get("name") for result in differential["results"] if isinstance(result, dict)
    }
    if actual_scenarios != expected_scenarios:
        fail("PARITY_REPORT must contain one result for every differential scenario")

    performance = load_report("PARITY_PERF_REPORT")
    profiles = performance.get("profiles")
    if performance.get("failures") != [] or not isinstance(profiles, dict):
        fail("PARITY_PERF_REPORT must contain an empty failures list and profiles")
    missing_profiles = [name for name in REQUIRED_PERFORMANCE_PROFILES if name not in profiles]
    if missing_profiles:
        fail(
            "PARITY_PERF_REPORT must cover REST, GraphQL, SOAP, and gRPC; "
            f"missing: {', '.join(missing_profiles)}"
        )
    for profile_name in REQUIRED_PERFORMANCE_PROFILES:
        profile = profiles[profile_name]
        summary = profile.get("summary") if isinstance(profile, dict) else None
        if not isinstance(summary, dict):
            fail(f"PARITY_PERF_REPORT profile {profile_name} must contain a summary")
        for implementation in ("python", "rust"):
            metrics = summary.get(implementation)
            if not isinstance(metrics, dict) or any(
                not isinstance(metrics.get(metric), (int, float))
                or metrics[metric] < 0
                for metric in PERFORMANCE_METRICS
            ):
                fail(
                    "PARITY_PERF_REPORT profile "
                    f"{profile_name} must contain non-negative {implementation} metrics"
                )

    report_path("EXTERNAL_STORAGE_LOG")

    operations = load_report("RELEASE_OPERATIONS_REPORT")
    required_operations = ("image_smoke", "restore_rehearsal", "canary", "rollback")
    for operation in required_operations:
        evidence = operations.get(operation)
        if not isinstance(evidence, dict) or evidence.get("passed") is not True:
            fail(
                "RELEASE_OPERATIONS_REPORT must record a passing "
                f"{operation} rehearsal"
            )


def run_generated_checks(repo_root: Path) -> None:
    for command in (
        [sys.executable, "scripts/check_parity_reference.py"],
        [sys.executable, "scripts/generate_test_coverage_ledger.py", "--check"],
    ):
        completed = subprocess.run(command, cwd=repo_root, check=False)
        if completed.returncode != 0:
            fail(f"generated parity check failed: {' '.join(command)}")


def main() -> int:
    try:
        required_environment()
        validate_reports()
        run_generated_checks(Path(__file__).resolve().parents[1])
    except ValueError as error:
        print(f"release evidence check failed: {error}", file=sys.stderr)
        return 1
    print("release evidence check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
