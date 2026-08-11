#!/usr/bin/env python3
"""Compare deterministic public wire behavior between Python and Rust gateways."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


VOLATILE_KEYS = {
    "request_id",
    "x-request-id",
    "x-upstream-request-id",
    "timestamp",
    "created_at",
    "updated_at",
    "iat",
    "exp",
    "jti",
}
COMPARED_HEADERS = {
    "access-control-allow-credentials",
    "access-control-allow-headers",
    "access-control-allow-methods",
    "access-control-allow-origin",
    "allow",
    "content-encoding",
    "content-type",
    "grpc-encoding",
    "grpc-message",
    "grpc-status",
    "retry-after",
    "vary",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "x-request-id",
}


def normalize(value: Any, key: str = "") -> Any:
    if key.lower() in VOLATILE_KEYS:
        return "<volatile>"
    if isinstance(value, dict):
        return {item_key: normalize(item, item_key) for item_key, item in sorted(value.items())}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if key.lower() == "vary" and isinstance(value, str):
        return ", ".join(sorted(token.strip().lower() for token in value.split(",")))
    return value


def request(base_url: str, case: dict[str, Any]) -> dict[str, Any]:
    headers = dict(case.get("headers", {}))
    data = None
    if "json" in case:
        data = json.dumps(case["json"], separators=(",", ":")).encode()
        headers.setdefault("Content-Type", "application/json")
    elif "raw_body" in case:
        data = case["raw_body"].encode()
    outgoing = urllib.request.Request(
        base_url.rstrip("/") + case["path"],
        data=data,
        headers=headers,
        method=case.get("method", "GET"),
    )
    try:
        response = urllib.request.urlopen(outgoing, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    raw = response.read()
    content_type = response.headers.get_content_type()
    if content_type == "application/json":
        body: Any = json.loads(raw or b"null")
    else:
        body = raw.decode("utf-8", errors="replace")
    selected_headers = {
        name.lower(): value
        for name, value in response.headers.items()
        if name.lower() in COMPARED_HEADERS
    }
    return normalize(
        {
            "status": response.status,
            "headers": selected_headers,
            "body": body,
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-url", default="http://127.0.0.1:3102")
    parser.add_argument("--rust-url", default="http://127.0.0.1:3101")
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=Path("parity/differential/scenarios.json"),
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    scenarios = json.loads(args.scenarios.read_text())
    results: list[dict[str, Any]] = []
    for case in scenarios:
        python_result = request(args.python_url, case)
        rust_result = request(args.rust_url, case)
        results.append(
            {
                "name": case["name"],
                "match": python_result == rust_result,
                "python": python_result,
                "rust": rust_result,
            }
        )

    python_openapi = request(
        args.python_url, {"name": "openapi", "path": "/platform/openapi.json"}
    )
    rust_openapi = request(
        args.rust_url, {"name": "openapi", "path": "/platform/openapi.json"}
    )
    results.append(
        {
            "name": "openapi",
            "match": python_openapi == rust_openapi,
            "python": python_openapi,
            "rust": rust_openapi,
        }
    )

    report = {
        "schema_version": 1,
        "differences": sum(not result["match"] for result in results),
        "results": results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for result in results:
        print(f"{'PASS' if result['match'] else 'FAIL'} {result['name']}")
        if not result["match"]:
            print("  python:", json.dumps(result["python"], sort_keys=True))
            print("  rust:  ", json.dumps(result["rust"], sort_keys=True))
    print(f"differences={report['differences']}")
    return 1 if report["differences"] else 0


if __name__ == "__main__":
    sys.exit(main())
