import pytest


@pytest.mark.asyncio
async def test_platform_cors_no_duplicate_access_control_allow_origin(monkeypatch, authed_client):
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://ok.example')
    r = await authed_client.get('/platform/user/me', headers={'Origin': 'http://ok.example'})
    assert r.status_code == 200
    acao = r.headers.get('Access-Control-Allow-Origin') or r.headers.get(
        'access-control-allow-origin'
    )
    assert acao == 'http://ok.example'
    assert ',' not in acao
