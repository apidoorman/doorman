from __future__ import annotations

import json
import re
from difflib import unified_diff
from copy import deepcopy
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

REQUEST_ID_TOKEN = "<request-id>"
ELAPSED_TOKEN = "<elapsed-ms>"

HEADER_ALLOWLIST = {
    "access-control-allow-credentials",
    "access-control-allow-headers",
    "access-control-allow-methods",
    "access-control-allow-origin",
    "content-type",
    "request_id",
    "vary",
    "x-request-id",
    "x-upstream-request-id",
}

DYNAMIC_BODY_KEYS = {
    "request_id",
    "x-request-id",
    "elapsed_ms",
    "elapsed_time",
    "gateway_time",
    "backend_time",
}

UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


class FixtureError(AssertionError):
    pass


class RecordingHTTPResponse:
    def __init__(self, status_code: int = 200, json_body: Any = None, text_body: str | None = None, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text_body if text_body is not None else ("" if json_body is not None else "OK")
        base_headers = {"Content-Type": "application/json" if json_body is not None else "text/plain"}
        if headers:
            base_headers.update(headers)
        self.headers = base_headers

    def json(self) -> Any:
        if self._json_body is None:
            return json.loads(self.text or "{}")
        return self._json_body


class RecordingAsyncClient:
    records: list[dict[str, Any]] = []
    routes: dict[str, list[str]] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> "RecordingAsyncClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    @classmethod
    def reset(cls) -> None:
        cls.records = []
        cls.routes = {}

    async def request(self, method: str, url: str, **kwargs: Any) -> RecordingHTTPResponse:
        method = method.upper()
        if method == "GET":
            return await self.get(url, **kwargs)
        if method == "POST":
            return await self.post(url, **kwargs)
        if method == "PUT":
            return await self.put(url, **kwargs)
        if method == "DELETE":
            return await self.delete(url, **kwargs)
        if method == "HEAD":
            return await self.get(url, **kwargs)
        if method == "PATCH":
            return await self.put(url, **kwargs)
        return RecordingHTTPResponse(405, json_body={"error": "Method not allowed"})

    async def get(self, url: str, params: Any = None, headers: dict[str, str] | None = None, **kwargs: Any) -> RecordingHTTPResponse:
        return self._record("GET", url, params=params, headers=headers)

    async def post(self, url: str, json: Any = None, params: Any = None, headers: dict[str, str] | None = None, content: Any = None, **kwargs: Any) -> RecordingHTTPResponse:
        return self._record("POST", url, params=params, headers=headers, body=_body(json, content))

    async def put(self, url: str, json: Any = None, params: Any = None, headers: dict[str, str] | None = None, content: Any = None, **kwargs: Any) -> RecordingHTTPResponse:
        return self._record("PUT", url, params=params, headers=headers, body=_body(json, content))

    async def delete(self, url: str, json: Any = None, params: Any = None, headers: dict[str, str] | None = None, content: Any = None, **kwargs: Any) -> RecordingHTTPResponse:
        return self._record("DELETE", url, params=params, headers=headers, body=_body(json, content))

    def _record(self, method: str, url: str, params: Any = None, headers: dict[str, str] | None = None, body: Any = None) -> RecordingHTTPResponse:
        params_dict = dict(params or {})
        headers_dict = dict(headers or {})
        record = {
            "method": method,
            "url": url,
            "params": normalize_value(params_dict),
            "headers": normalize_headers(headers_dict),
            "body": normalize_value(body),
        }
        self.records.append(record)
        return RecordingHTTPResponse(
            200,
            json_body={
                "method": method,
                "url": url,
                "params": params_dict,
                "headers": normalize_headers(headers_dict),
                "body": normalize_value(body),
                "ok": True,
            },
            headers={"X-Upstream": "yes", "X-Upstream-Request-ID": headers_dict.get("X-Request-ID", "")},
        )


def _body(json_body: Any, content: Any) -> Any:
    if json_body is not None:
        return json_body
    if isinstance(content, (bytes, bytearray)):
        return content.decode("utf-8")
    return content


def normalize_headers(headers: dict[str, Any] | None) -> dict[str, Any]:
    if not headers:
        return {}
    has_cors_origin = any(
        str(key).lower() == "access-control-allow-origin" and bool(str(value).strip())
        for key, value in headers.items()
    )
    normalized: dict[str, Any] = {}
    for key, value in headers.items():
        name = str(key).lower()
        if name not in HEADER_ALLOWLIST:
            continue
        if not str(value).strip():
            continue
        if name == "vary":
            tokens = [item.strip() for item in str(value).split(",")]
            stable_tokens = [
                item for item in tokens
                if item.lower() != "accept-encoding"
                and (item.lower() != "origin" or has_cors_origin)
            ]
            if not stable_tokens:
                continue
            value = ", ".join(stable_tokens)
        if name in {"x-request-id", "request_id", "x-upstream-request-id"} and value:
            normalized[name] = REQUEST_ID_TOKEN
        else:
            normalized[name] = normalize_value(value)
    return dict(sorted(normalized.items()))


def normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, inner in value.items():
            key_s = str(key)
            if key_s.lower() in DYNAMIC_BODY_KEYS:
                if "request" in key_s.lower() and isinstance(inner, str) and UUID_RE.search(inner):
                    out[key_s] = REQUEST_ID_TOKEN
                elif "request" not in key_s.lower():
                    out[key_s] = ELAPSED_TOKEN
                else:
                    out[key_s] = normalize_value(inner)
            else:
                out[key_s] = normalize_value(inner)
        return dict(sorted(out.items()))
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_value(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return UUID_RE.sub(REQUEST_ID_TOKEN, value)
    return value


async def response_contract(response: Any) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        try:
            body = response.json()
        except Exception:
            body = response.text
    else:
        body = response.text
    return {
        "status": response.status_code,
        "content_type": content_type.split(";")[0],
        "headers": normalize_headers(dict(response.headers)),
        "body": normalize_value(body),
    }


def scenario_fixture(
    *,
    name: str,
    description: str,
    tags: list[str],
    request: dict[str, Any],
    setup: dict[str, Any],
    response: dict[str, Any],
    upstream_requests: list[dict[str, Any]] | None = None,
    decisions: dict[str, Any] | None = None,
    state_changes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fixture = {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "description": description,
        "tags": tags,
        "request": normalize_value(request),
        "setup": normalize_value(setup),
        "expected": {
            "response": normalize_value(response),
            "upstream_requests": normalize_value(upstream_requests or []),
            "decisions": normalize_value(decisions or {}),
            "state_changes": normalize_value(state_changes or {}),
        },
    }
    validate_fixture(fixture)
    return fixture


def validate_fixture(fixture: dict[str, Any]) -> None:
    required_top = {"schema_version", "name", "description", "tags", "request", "setup", "expected"}
    missing = required_top - set(fixture)
    if missing:
        raise FixtureError(f"missing top-level fixture keys: {sorted(missing)}")
    if fixture["schema_version"] != SCHEMA_VERSION:
        raise FixtureError(f"unsupported schema_version: {fixture['schema_version']}")
    if not isinstance(fixture["tags"], list):
        raise FixtureError("tags must be a list")
    expected = fixture["expected"]
    for key in ("response", "upstream_requests", "decisions", "state_changes"):
        if key not in expected:
            raise FixtureError(f"missing expected.{key}")
    response = expected["response"]
    for key in ("status", "content_type", "headers", "body"):
        if key not in response:
            raise FixtureError(f"missing expected.response.{key}")
    if not isinstance(response["status"], int):
        raise FixtureError("expected.response.status must be an integer")


def fixture_path(fixtures_dir: Path, name: str) -> Path:
    return fixtures_dir / f"{name}.json"


def load_fixture(path: Path) -> dict[str, Any]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    validate_fixture(fixture)
    return fixture


def write_fixture(path: Path, fixture: dict[str, Any]) -> None:
    validate_fixture(fixture)
    path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def assert_fixture_matches(path: Path, fixture: dict[str, Any]) -> None:
    expected = load_fixture(path)
    actual = deepcopy(fixture)
    if actual != expected:
        expected_text = json.dumps(expected, indent=2, sort_keys=True).splitlines()
        actual_text = json.dumps(actual, indent=2, sort_keys=True).splitlines()
        diff = "\n".join(
            unified_diff(expected_text, actual_text, fromfile=str(path),
                         tofile=f"{fixture['name']} (actual)", lineterm="")
        )
        raise FixtureError(
            f"fixture drift for {fixture['name']}:\n{diff}\n"
            "run UPDATE_PARITY_CONTRACTS=1 pytest backend-services/tests/test_parity_contract_fixtures.py only after reviewing this diff"
        )
