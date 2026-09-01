from starlette.requests import Request

from middleware.tier_rate_limit_middleware import TierRateLimitMiddleware


async def _empty_app(scope, receive, send):
    return None


def _request(path: str) -> Request:
    return Request(
        {
            'type': 'http',
            'method': 'GET',
            'path': path,
            'headers': [],
            'query_string': b'',
            'server': ('testserver', 80),
            'scheme': 'http',
            'client': ('127.0.0.1', 12345),
        }
    )


def test_tier_rate_limit_skips_gateway_admin_and_health_paths():
    middleware = TierRateLimitMiddleware(_empty_app)

    assert middleware._should_skip(_request('/api/caches'))
    assert middleware._should_skip(_request('/api/health'))
