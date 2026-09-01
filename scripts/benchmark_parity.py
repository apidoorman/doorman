#!/usr/bin/env python3
"""Run a repeatable Python-versus-Rust no-regression benchmark."""

from __future__ import annotations

import argparse
import json
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


def one_request(url: str) -> tuple[float, bool]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            response.read()
            success = 200 <= response.status < 400
    except Exception:
        success = False
    return (time.perf_counter() - started) * 1000.0, success


def trial(url: str, pid: int, requests: int, concurrency: int) -> dict[str, float]:
    stop = threading.Event()
    samples: list[int] = []

    def sample_memory() -> None:
        while not stop.wait(0.01):
            samples.append(rss_bytes(pid))

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(lambda _: one_request(url), range(requests)))
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
    args = parser.parse_args()

    for url in (args.python_url, args.rust_url):
        for _ in range(25):
            one_request(url)

    measured: dict[str, list[dict[str, float]]] = {"python": [], "rust": []}
    targets = {
        "python": (args.python_url, args.python_pid),
        "rust": (args.rust_url, args.rust_pid),
    }
    for index in range(args.trials):
        order = ("python", "rust") if index % 2 == 0 else ("rust", "python")
        for name in order:
            url, pid = targets[name]
            measured[name].append(trial(url, pid, args.requests, args.concurrency))

    summary = {name: aggregate(results) for name, results in measured.items()}
    python = summary["python"]
    rust = summary["rust"]
    tolerance = args.tolerance
    failures: list[str] = []
    if rust["throughput_rps"] < python["throughput_rps"] * (1.0 - tolerance):
        failures.append("throughput regressed by more than the allowed tolerance")
    if rust["p95_latency_ms"] > python["p95_latency_ms"] * (1.0 + tolerance):
        failures.append("p95 latency regressed by more than the allowed tolerance")
    if rust["peak_rss_bytes"] > python["peak_rss_bytes"] * (1.0 + tolerance):
        failures.append("peak RSS regressed by more than the allowed tolerance")
    if rust["error_rate"] > python["error_rate"]:
        failures.append("error rate is higher than Python")

    report: dict[str, Any] = {
        "schema_version": 1,
        "trials": args.trials,
        "requests_per_trial": args.requests,
        "concurrency": args.concurrency,
        "tolerance": tolerance,
        "summary": summary,
        "measurements": measured,
        "failures": failures,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: Rust is within the 5% no-regression performance gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
