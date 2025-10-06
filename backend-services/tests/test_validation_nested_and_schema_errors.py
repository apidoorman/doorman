import pytest

from tests.test_gateway_routing_limits import _FakeAsyncClient


async def _setup(client, api='vtest', ver='v1', method='POST', uri='/data'):
    from conftest import create_api, create_endpoint, subscribe_self
    await create_api(client, api, ver)
    await create_endpoint(client, api, ver, method, uri)
    await subscribe_self(client, api, ver)
    g = await client.get(f'/platform/endpoint/{method}/{api}/{ver}{uri}')
    assert g.status_code == 200
    eid = g.json().get('endpoint_id') or g.json().get('response', {}).get('endpoint_id')
    return api, ver, uri, eid


async def _apply_schema(client, eid, schema_dict):
    payload = {'endpoint_id': eid, 'validation_enabled': True, 'validation_schema': schema_dict}
    r = await client.post('/platform/endpoint/endpoint/validation', json=payload)
    assert r.status_code in (200, 201, 400)


@pytest.mark.asyncio
async def test_validation_nested_object_paths_valid(monkeypatch, authed_client):
    api, ver, uri, eid = await _setup(authed_client, api='vnest', uri='/ok1')
    # Use nested_schema on object type
    schema = {
        'validation_schema': {
            'user': {
                'required': True,
                'type': 'object',
                'nested_schema': {
                    'name': {'required': True, 'type': 'string', 'min': 2}
                }
            }
        }
    }
    await _apply_schema(authed_client, eid, schema)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.post(f'/api/rest/{api}/{ver}{uri}', json={'user': {'name': 'John'}})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_validation_array_items_valid(monkeypatch, authed_client):
    api, ver, uri, eid = await _setup(authed_client, api='varr1', uri='/ok2')
    schema = {
        'validation_schema': {
            'tags': {'required': True, 'type': 'array', 'min': 1, 'array_items': {'type': 'string', 'min': 2, 'required': True}}
        }
    }
    await _apply_schema(authed_client, eid, schema)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.post(f'/api/rest/{api}/{ver}{uri}', json={'tags': ['ab', 'cd']})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_validation_array_items_invalid_type(monkeypatch, authed_client):
    api, ver, uri, eid = await _setup(authed_client, api='varr2', uri='/bad1')
    schema = {
        'validation_schema': {
            'tags': {'required': True, 'type': 'array', 'array_items': {'type': 'string', 'required': True}}
        }
    }
    await _apply_schema(authed_client, eid, schema)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.post(f'/api/rest/{api}/{ver}{uri}', json={'tags': [1, 2]})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_validation_required_field_missing(monkeypatch, authed_client):
    api, ver, uri, eid = await _setup(authed_client, api='vreq', uri='/bad2')
    schema = {'validation_schema': {'profile.age': {'required': True, 'type': 'number'}}}
    await _apply_schema(authed_client, eid, schema)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.post(f'/api/rest/{api}/{ver}{uri}', json={'profile': {}})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_validation_enum_restrictions(monkeypatch, authed_client):
    api, ver, uri, eid = await _setup(authed_client, api='venum', uri='/bad3')
    schema = {'validation_schema': {'status': {'required': True, 'type': 'string', 'enum': ['NEW', 'OPEN']}}}
    await _apply_schema(authed_client, eid, schema)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    bad = await authed_client.post(f'/api/rest/{api}/{ver}{uri}', json={'status': 'CLOSED'})
    assert bad.status_code == 400
    ok = await authed_client.post(f'/api/rest/{api}/{ver}{uri}', json={'status': 'OPEN'})
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_validation_custom_validator_success(monkeypatch, authed_client):
    api, ver, uri, eid = await _setup(authed_client, api='vcust1', uri='/ok3')
    from utils.validation_util import validation_util, ValidationError
    def is_upper(value, vdef):
        if not isinstance(value, str) or not value.isupper():
            raise ValidationError('Not upper', 'code')
    validation_util.register_custom_validator('isUpper', is_upper)
    schema = {'validation_schema': {'code': {'required': True, 'type': 'string', 'custom_validator': 'isUpper'}}}
    await _apply_schema(authed_client, eid, schema)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.post(f'/api/rest/{api}/{ver}{uri}', json={'code': 'ABC'})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_validation_custom_validator_failure(monkeypatch, authed_client):
    api, ver, uri, eid = await _setup(authed_client, api='vcust2', uri='/bad4')
    from utils.validation_util import validation_util, ValidationError
    def is_upper(value, vdef):
        if not isinstance(value, str) or not value.isupper():
            raise ValidationError('Not upper', 'code')
    validation_util.register_custom_validator('isUpper2', is_upper)
    schema = {'validation_schema': {'code': {'required': True, 'type': 'string', 'custom_validator': 'isUpper2'}}}
    await _apply_schema(authed_client, eid, schema)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.post(f'/api/rest/{api}/{ver}{uri}', json={'code': 'Abc'})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_validation_invalid_field_path_raises_schema_error(monkeypatch, authed_client):
    api, ver, uri, eid = await _setup(authed_client, api='vbadpath', uri='/bad5')
    # Invalid path 'user..name' should cause a 400 when validation is attempted
    schema = {'validation_schema': {'user..name': {'required': True, 'type': 'string'}}}
    await _apply_schema(authed_client, eid, schema)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.post(f'/api/rest/{api}/{ver}{uri}', json={'user': {'name': 'ok'}})
    assert r.status_code == 400

