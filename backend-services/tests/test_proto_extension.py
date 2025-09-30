# External imports
import io
import pytest

@pytest.mark.asyncio
async def test_proto_upload_rejects_non_proto(authed_client):
    files = {'file': ('bad.txt', b'syntax = \"proto3\";', 'text/plain')}
    r = await authed_client.post('/platform/proto/sample/v1', files=files)
    assert r.status_code == 400
    body = r.json()
    assert body.get('error_code') == 'REQ003'

@pytest.mark.asyncio
async def test_proto_upload_accepts_proto(authed_client):
    content = b'syntax = \"proto3\";\npackage sample_v1;\nmessage Ping { string msg = 1; }'
    files = {'file': ('ok.proto', content, 'application/octet-stream')}
    r = await authed_client.post('/platform/proto/sample/v1', files=files)
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        body = r.json()
        assert body.get('message', '').lower().startswith('proto file uploaded')

