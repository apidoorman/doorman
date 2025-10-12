#!/usr/bin/env python3
"""
Capture CPU and event-loop lag statistics for a running Doorman process.

Writes a JSON file (perf-stats.json) alongside k6 results so compare_perf.py
can print these figures in the diff report.

Note: Loop lag is measured by this monitor's own asyncio loop as an
approximation of scheduler pressure on the host. It does not instrument the
server's internal loop directly, but correlates under shared host load.
"""

from __future__ import annotations
import argparse
import asyncio
import json
import os
import signal
import statistics
import sys
import time
from pathlib import Path

try:
    import psutil  # type: ignore
except Exception:
    psutil = None  # type: ignore


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, help="PID of the target process")
    ap.add_argument("--pidfile", type=str, default="backend-services/doorman.pid",
                    help="Path to PID file (used if --pid not provided)")
    ap.add_argument("--output", type=str, default="load-tests/perf-stats.json",
                    help="Output JSON path")
    ap.add_argument("--cpu-interval", type=float, default=0.5,
                    help="CPU sampling interval seconds")
    ap.add_argument("--lag-interval", type=float, default=0.05,
                    help="Loop lag sampling interval seconds")
    ap.add_argument("--timeout", type=float, default=0.0,
                    help="Optional timeout seconds; 0 = until process exits or SIGTERM")
    return ap.parse_args()


def read_pid(pid: int | None, pidfile: str) -> int | None:
    if pid:
        return pid
    try:
        with open(pidfile, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None


async def sample_cpu(proc: "psutil.Process", interval: float, stop: asyncio.Event, samples: list[float]):
    # Prime cpu_percent() baseline
    try:
        proc.cpu_percent(None)
    except Exception:
        pass
    while not stop.is_set():
        try:
            val = await asyncio.to_thread(proc.cpu_percent, interval)
            samples.append(float(val))
        except Exception:
            await asyncio.sleep(interval)
            continue


async def sample_loop_lag(interval: float, stop: asyncio.Event, lags_ms: list[float]):
    # Measure scheduling delay over requested interval
    next_ts = time.perf_counter() + interval
    while not stop.is_set():
        await asyncio.sleep(max(0.0, next_ts - time.perf_counter()))
        now = time.perf_counter()
        expected = next_ts
        lag = max(0.0, (now - expected) * 1000.0)  # ms
        lags_ms.append(lag)
        next_ts = expected + interval


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = int(max(0, min(len(values) - 1, round((p / 100.0) * (len(values) - 1)))))
    return float(values[k])


async def main() -> int:
    if psutil is None:
        print("psutil is not installed; CPU stats unavailable", file=sys.stderr)
        return 1

    args = parse_args()
    pid = read_pid(args.pid, args.pidfile)
    if not pid:
        print(f"No PID found (pidfile: {args.pidfile}). Is the server running?", file=sys.stderr)
        return 2

    try:
        proc = psutil.Process(pid)
    except Exception as e:
        print(f"Failed to attach to PID {pid}: {e}", file=sys.stderr)
        return 3

    stop = asyncio.Event()

    def _handle_sig(*_):
        stop.set()

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _handle_sig)
        except Exception:
            pass

    cpu_samples: list[float] = []
    lag_samples_ms: list[float] = []

    tasks = [
        asyncio.create_task(sample_cpu(proc, args.cpu_interval, stop, cpu_samples)),
        asyncio.create_task(sample_loop_lag(args.lag_interval, stop, lag_samples_ms)),
    ]

    start = time.time()
    try:
        while not stop.is_set():
            # Exit if target process is gone
            if not proc.is_running():
                break
            if args.timeout > 0 and (time.time() - start) >= args.timeout:
                break
            await asyncio.sleep(0.2)
    finally:
        stop.set()
        for t in tasks:
            try:
                await asyncio.wait_for(t, timeout=2.0)
            except Exception:
                pass

    out = {
        "cpu_percent_avg": round(statistics.fmean(cpu_samples), 2) if cpu_samples else 0.0,
        "cpu_percent_p95": round(percentile(cpu_samples, 95), 2) if cpu_samples else 0.0,
        "cpu_samples": len(cpu_samples),
        "loop_lag_ms_p95": round(percentile(lag_samples_ms, 95), 2) if lag_samples_ms else 0.0,
        "loop_lag_samples": len(lag_samples_ms),
    }

    try:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"Wrote perf stats: {out_path}")
    except Exception as e:
        print(f"Failed to write output: {e}", file=sys.stderr)
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

