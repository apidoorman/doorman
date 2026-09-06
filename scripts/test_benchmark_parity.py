#!/usr/bin/env python3
"""Focused input-validation tests for the protocol performance benchmark."""

from __future__ import annotations

import unittest

from scripts.benchmark_parity import normalize_scenario, validate_scenarios


class BenchmarkScenarioTests(unittest.TestCase):
    def test_post_protocol_scenario_accepts_headers_and_body(self) -> None:
        scenario = normalize_scenario(
            {
                "name": "graphql",
                "python_url": "http://127.0.0.1:3102/api/graphql/demo",
                "rust_url": "http://127.0.0.1:3101/api/graphql/demo",
                "request": {
                    "method": "post",
                    "headers": {"Content-Type": "application/json"},
                    "body": '{"query":"{ __typename }"}',
                },
            }
        )
        validate_scenarios([scenario])
        self.assertEqual(scenario["request"]["method"], "POST")

    def test_scenarios_reject_secret_bearing_or_ambiguous_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "headers"):
            normalize_scenario(
                {
                    "name": "grpc",
                    "python_url": "http://python.example.test",
                    "rust_url": "http://rust.example.test",
                    "request": {"headers": {"Authorization": 7}},
                }
            )
        rest = normalize_scenario(
            {
                "name": "rest",
                "python_url": "http://python.example.test",
                "rust_url": "http://rust.example.test",
            }
        )
        duplicate = {**rest}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_scenarios([rest, duplicate])


if __name__ == "__main__":
    unittest.main()
