#!/usr/bin/env python3
"""Focused regression tests for the fail-closed release evidence checker."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK = REPO_ROOT / "scripts" / "release_check.py"


class ReleaseCheckTests(unittest.TestCase):
    def base_environment(self, evidence: Path) -> dict[str, str]:
        differential = evidence / "differential.json"
        scenario_path = REPO_ROOT / "parity" / "differential" / "scenarios.json"
        scenario_names = [case["name"] for case in json.loads(scenario_path.read_text())]
        differential.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "scenario_manifest_sha256": hashlib.sha256(scenario_path.read_bytes()).hexdigest(),
                    "differences": 0,
                    "results": [{"name": name} for name in [*scenario_names, "openapi"]],
                }
            )
        )
        performance = evidence / "performance.json"
        performance.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "failures": [],
                    "profiles": {
                        profile: {
                            "summary": {
                                "python": {
                                    "throughput_rps": 1,
                                    "p95_latency_ms": 1,
                                    "error_rate": 0,
                                    "peak_rss_bytes": 1,
                                },
                                "rust": {
                                    "throughput_rps": 1,
                                    "p95_latency_ms": 1,
                                    "error_rate": 0,
                                    "peak_rss_bytes": 1,
                                },
                            }
                        }
                        for profile in ("rest", "graphql", "soap", "grpc")
                    },
                }
            )
        )
        external_log = evidence / "external.log"
        external_log.write_text("external storage suite passed\n")
        operations = evidence / "operations.json"
        operations.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "image_smoke": {"passed": True},
                    "restore_rehearsal": {"passed": True},
                    "canary": {"passed": True},
                    "rollback": {"passed": True},
                }
            )
        )
        return {
            **os.environ,
            "ENV": "production",
            "MEM_OR_EXTERNAL": "REDIS",
            "HTTPS_ONLY": "true",
            "CORS_STRICT": "true",
            "LOCAL_HOST_IP_BYPASS": "false",
            "DOORMAN_ADMIN_EMAIL": "admin@example.test",
            "DOORMAN_ADMIN_PASSWORD": "not-a-placeholder-password",
            "JWT_SECRET_KEY": "a-unique-long-secret-key",
            "JWT_ISSUER": "doorman-release",
            "JWT_AUDIENCE": "doorman-clients",
            "ALLOWED_ORIGINS": "https://admin.example.test",
            "DISCOVERY_ALLOWED_HOSTS": "api.example.test",
            "MONGO_DB_HOSTS": "mongo.example.test:27017",
            "MONGO_DB_USER": "doorman-release-user",
            "MONGO_DB_PASSWORD": "mongo-release-password",
            "REDIS_HOST": "redis.example.test",
            "REDIS_PASSWORD": "redis-release-password",
            "PARITY_REPORT": str(differential),
            "PARITY_PERF_REPORT": str(performance),
            "EXTERNAL_STORAGE_LOG": str(external_log),
            "RELEASE_OPERATIONS_REPORT": str(operations),
        }

    def run_check(self, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECK)],
            cwd=REPO_ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_accepts_current_evidence_and_rejects_missing_or_failed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = self.base_environment(Path(directory))
            self.assertEqual(self.run_check(environment).returncode, 0)

            environment.pop("JWT_SECRET_KEY")
            self.assertNotEqual(self.run_check(environment).returncode, 0)

            environment = self.base_environment(Path(directory))
            Path(environment["PARITY_REPORT"]).write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "scenario_manifest_sha256": hashlib.sha256(
                            (REPO_ROOT / "parity" / "differential" / "scenarios.json").read_bytes()
                        ).hexdigest(),
                        "differences": 1,
                        "results": [],
                    }
                )
            )
            self.assertNotEqual(self.run_check(environment).returncode, 0)

            environment = self.base_environment(Path(directory))
            Path(environment["RELEASE_OPERATIONS_REPORT"]).write_text(
                json.dumps({"schema_version": 1, "image_smoke": {"passed": True}})
            )
            self.assertNotEqual(self.run_check(environment).returncode, 0)

            environment = self.base_environment(Path(directory))
            performance = json.loads(Path(environment["PARITY_PERF_REPORT"]).read_text())
            del performance["profiles"]["grpc"]
            Path(environment["PARITY_PERF_REPORT"]).write_text(json.dumps(performance))
            self.assertNotEqual(self.run_check(environment).returncode, 0)

            environment = self.base_environment(Path(directory))
            environment["HTTPS_ONLY"] = "false"
            self.assertNotEqual(self.run_check(environment).returncode, 0)

            environment = self.base_environment(Path(directory))
            differential = json.loads(Path(environment["PARITY_REPORT"]).read_text())
            differential["scenario_manifest_sha256"] = "0" * 64
            Path(environment["PARITY_REPORT"]).write_text(json.dumps(differential))
            self.assertNotEqual(self.run_check(environment).returncode, 0)


if __name__ == "__main__":
    unittest.main()
