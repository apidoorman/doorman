import json

from services.logging_service import LoggingService


def test_rust_gateway_json_log_fields_are_queryable():
    record = {
        "time": "2026-08-05T12:34:56Z",
        "name": "doorman.gateway.rust",
        "level": "WARNING",
        "message": "gateway request completed",
        "request_id": "17fb42df-aaba-4ed8-a0d7-a20de7159880",
        "type": "gateway",
        "user": "alice",
        "api": "rest:orders:v1",
        "endpoint": "/orders/42",
        "method": "GET",
        "status_code": 429,
        "response_time": 12.5,
        "ip_address": "192.0.2.10",
    }

    parsed = LoggingService()._parse_log_line(json.dumps(record))

    assert parsed is not None
    for field in (
        "request_id",
        "type",
        "user",
        "api",
        "endpoint",
        "method",
        "status_code",
        "response_time",
        "ip_address",
    ):
        assert parsed[field] == record[field]
