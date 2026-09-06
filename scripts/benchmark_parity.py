#!/usr/bin/env python3
"""Run a repeatable Python-versus-Rust no-regression benchmark."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


def rss_bytes(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    return values[min(len(values) - 1, int(len(values) * fraction))]


def one_request(url: str, request: dict[str, Any]) -> tuple[float, bool]:
    started = time.perf_counter()
    try:
        body = request.get("body")
        data = body.encode() if isinstance(body, str) else None
        outgoing = urllib.request.Request(
            url,
            data=data,
            headers=request["headers"],
            method=request["method"],
        )
        with urllib.request.urlopen(outgoing, timeout=5) as response:
            response.read()
            success = 200 <= response.status < 400
    except Exception:
        success = False
    return (time.perf_counter() - started) * 1000.0, success


def trial(
    url: str, request: dict[str, Any], pid: int, requests: int, concurrency: int
) -> dict[str, float]:
    stop = threading.Event()
    samples: list[int] = []

    def sample_memory() -> None:
        while not stop.wait(0.01):
            samples.append(rss_bytes(pid))

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(
            executor.map(lambda _: one_request(url, request), range(requests))
        )
    elapsed = time.perf_counter() - started
    stop.set()
    sampler.join(timeout=1)
    latencies = [latency for latency, _ in results]
    errors = sum(not success for _, success in results)
    return {
        "throughput_rps": requests / elapsed,
        "p95_latency_ms": percentile(latencies, 0.95),
        "error_rate": errors / requests,
        "peak_rss_bytes": float(max(samples, default=rss_bytes(pid))),
    }


def aggregate(results: list[dict[str, float]]) -> dict[str, float]:
    return {
        key: statistics.median(result[key] for result in results)
        for key in results[0]
    }


def normalize_scenario(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("each scenario must be a JSON object")
    name = value.get("name")
    python_url = value.get("python_url")
    rust_url = value.get("rust_url")
    if not all(isinstance(item, str) for item in (name, python_url, rust_url)):
        raise ValueError("each scenario requires string name, python_url, and rust_url")
    request = value.get("request", {})
    if not isinstance(request, dict):
        raise ValueError(f"{name}: request must be an object")
    method = request.get("method", "GET")
    headers = request.get("headers", {})
    body = request.get("body")
    if not isinstance(method, str) or not method.isalpha():
        raise ValueError(f"{name}: request method must be alphabetic")
    if not isinstance(headers, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in headers.items()
    ):
        raise ValueError(f"{name}: request headers must be a string map")
    if body is not None and not isinstance(body, str):
        raise ValueError(f"{name}: request body must be a string")
    return {
        "name": name,
        "python_url": python_url,
        "rust_url": rust_url,
        "request": {"method": method.upper(), "headers": headers, "body": body},
    }


def validate_scenarios(scenarios: list[dict[str, Any]]) -> None:
    names: set[str] = set()
    for scenario in scenarios:
        name = scenario["name"]
        python_url = scenario["python_url"]
        rust_url = scenario["rust_url"]
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
            raise ValueError(
                "scenario names must use lowercase letters, digits, underscores, or hyphens"
            )
        if name in names:
            raise ValueError(f"duplicate scenario name: {name}")
        if not python_url.startswith(("http://", "https://")):
            raise ValueError(f"{name}: Python URL must use http or https")
        if not rust_url.startswith(("http://", "https://")):
            raise ValueError(f"{name}: Rust URL must use http or https")
        names.add(name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-url", default="http://127.0.0.1:3102/api/health")
    parser.add_argument("--rust-url", default="http://127.0.0.1:3101/api/health")
    parser.add_argument("--python-pid", type=int, required=True)
    parser.add_argument("--rust-pid", type=int, required=True)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--tolerance", type=float, default=0.05)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--scenario",
        nargs=3,
        action="append",
        default=[],
        metavar=("NAME", "PYTHON_URL", "RUST_URL"),
        help="named protocol profile; repeat for rest, graphql, soap, and grpc",
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        help="JSON scenario array with request method, headers, and body per profile",
    )
    args = parser.parse_args()
    if args.trials < 1 or args.requests < 1 or args.concurrency < 1:
        parser.error("trials, requests, and concurrency must each be at least one")
    if not 0 <= args.tolerance < 1:
        parser.error("tolerance must be at least zero and less than one")

    try:
        if args.scenarios:
            scenarios = [normalize_scenario(value) for value in json.loads(args.scenarios.read_text())]
        else:
            shortcuts = args.scenario or [["health", args.python_url, args.rust_url]]
            scenarios = [
                normalize_scenario(
                    {"name": name, "python_url": python_url, "rust_url": rust_url}
                )
                for name, python_url, rust_url in shortcuts
            ]
        validate_scenarios(scenarios)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))

    profiles: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for scenario in scenarios:
        profile_name = scenario["name"]
        python_url = scenario["python_url"]
        rust_url = scenario["rust_url"]
        request = scenario["request"]
        for url in (python_url, rust_url):
            for _ in range(25):
                one_request(url, request)

        measured: dict[str, list[dict[str, float]]] = {"python": [], "rust": []}
        targets = {
            "python": (python_url, args.python_pid),
            "rust": (rust_url, args.rust_pid),
        }
        for index in range(args.trials):
            order = ("python", "rust") if index % 2 == 0 else ("rust", "python")
            for implementation in order:
                url, pid = targets[implementation]
                measured[implementation].append(
                    trial(url, request, pid, args.requests, args.concurrency)
                )

        summary = {name: aggregate(results) for name, results in measured.items()}
        profiles[profile_name] = {"summary": summary, "measurements": measured}
        python = summary["python"]
        rust = summary["rust"]
        tolerance = args.tolerance
        if rust["throughput_rps"] < python["throughput_rps"] * (1.0 - tolerance):
            failures.append(f"{profile_name}: throughput regressed by more than the allowed tolerance")
        if rust["p95_latency_ms"] > python["p95_latency_ms"] * (1.0 + tolerance):
            failures.append(f"{profile_name}: p95 latency regressed by more than the allowed tolerance")
        if rust["peak_rss_bytes"] > python["peak_rss_bytes"] * (1.0 + tolerance):
            failures.append(f"{profile_name}: peak RSS regressed by more than the allowed tolerance")
        if rust["error_rate"] > python["error_rate"]:
            failures.append(f"{profile_name}: error rate is higher than Python")

    report: dict[str, Any] = {
        "schema_version": 1,
        "trials": args.trials,
        "requests_per_trial": args.requests,
        "concurrency": args.concurrency,
        "tolerance": args.tolerance,
        "profiles": profiles,
        "failures": failures,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(profiles, indent=2, sort_keys=True))
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"PASS: Rust is within the {args.tolerance:.0%} no-regression performance gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
