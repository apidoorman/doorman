import pytest


def _make_request(path: str, headers: dict | None = None):
    from starlette.requests import Request

    hdrs = []
    for k, v in (headers or {}).items():
        hdrs.append((k.lower().encode('latin-1'), str(v).encode('latin-1')))
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': path,
        'headers': hdrs,
        'query_string': b'',
        'client': ('testclient', 12345),
        'server': ('testserver', 80),
        'scheme': 'http',
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_subscription_required_rest_path_parsing(monkeypatch):
    import utils.subscription_util as su

    async def fake_auth(req):
        return {'sub': 'alice'}

    monkeypatch.setattr(su, 'auth_required', fake_auth)
    monkeypatch.setattr(
        su.doorman_cache,
        'get_cache',
        lambda name, key: {'apis': ['svc1/v1']}
        if (name, key) == ('user_subscription_cache', 'alice')
        else None,
    )

    req = _make_request('/api/rest/svc1/v1/resource')
    payload = await su.subscription_required(req)
    assert payload.get('sub') == 'alice'


@pytest.mark.asyncio
async def test_subscription_required_soap_path_parsing(monkeypatch):
    import utils.subscription_util as su

    async def fake_auth(req):
        return {'sub': 'alice'}

    monkeypatch.setattr(su, 'auth_required', fake_auth)
    monkeypatch.setattr(
        su.doorman_cache,
        'get_cache',
        lambda name, key: {'apis': ['svc2/v2']}
        if (name, key) == ('user_subscription_cache', 'alice')
        else None,
    )

    req = _make_request('/api/soap/svc2/v2/do')
    payload = await su.subscription_required(req)
    assert payload.get('sub') == 'alice'


@pytest.mark.asyncio
async def test_subscription_required_graphql_header_parsing(monkeypatch):
    import utils.subscription_util as su

    async def fake_auth(req):
        return {'sub': 'alice'}

    monkeypatch.setattr(su, 'auth_required', fake_auth)
    monkeypatch.setattr(
        su.doorman_cache,
        'get_cache',
        lambda name, key: {'apis': ['svc3/v3']}
        if (name, key) == ('user_subscription_cache', 'alice')
        else None,
    )

    req = _make_request('/api/graphql/svc3', headers={'X-API-Version': 'v3'})
    payload = await su.subscription_required(req)
    assert payload.get('sub') == 'alice'


@pytest.mark.asyncio
async def test_subscription_required_grpc_path_parsing(monkeypatch):
    import utils.subscription_util as su

    async def fake_auth(req):
        return {'sub': 'alice'}

    monkeypatch.setattr(su, 'auth_required', fake_auth)
    monkeypatch.setattr(
        su.doorman_cache,
        'get_cache',
        lambda name, key: {'apis': ['svc4/v4']}
        if (name, key) == ('user_subscription_cache', 'alice')
        else None,
    )

    req = _make_request('/api/grpc/svc4', headers={'X-API-Version': 'v4'})
    payload = await su.subscription_required(req)
    assert payload.get('sub') == 'alice'


@pytest.mark.asyncio
async def test_subscription_required_unknown_prefix_fallback(monkeypatch):
    import utils.subscription_util as su

    async def fake_auth(req):
        return {'sub': 'alice'}

    monkeypatch.setenv('PYTHONASYNCIODEBUG', '0')
    monkeypatch.setattr(su, 'auth_required', fake_auth)
    monkeypatch.setattr(
        su.doorman_cache,
        'get_cache',
        lambda name, key: {'apis': ['svc5/v5']}
        if (name, key) == ('user_subscription_cache', 'alice')
        else None,
    )

    req = _make_request('/api/other/svc5/v5/op')
    payload = await su.subscription_required(req)
    assert payload.get('sub') == 'alice'
