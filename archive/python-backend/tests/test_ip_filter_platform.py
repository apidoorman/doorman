import json

import pytest


async def _ensure_manage_security(authed_client):
    await authed_client.put('/platform/role/admin', json={'manage_security': True})


async def _update_security(authed_client, settings: dict, headers: dict | None = None):
    await _ensure_manage_security(authed_client)
    r = await authed_client.put('/platform/security/settings', json=settings, headers=headers or {})
    assert r.status_code == 200, r.text
    return r


@pytest.mark.asyncio
async def test_global_whitelist_blocks_non_whitelisted_with_trusted_proxy(
    monkeypatch, authed_client, client
):
    await _update_security(
        authed_client,
        settings={
            'trust_x_forwarded_for': True,
            'xff_trusted_proxies': ['127.0.0.1'],
            'ip_whitelist': ['198.51.100.10'],
            'ip_blacklist': [],
            'allow_localhost_bypass': False,
        },
    )

    try:
        r = await client.get(
            '/platform/monitor/liveness', headers={'X-Forwarded-For': '203.0.113.10'}
        )
        assert r.status_code == 403
        body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        assert (body.get('error_code') or body.get('response', {}).get('error_code')) == 'SEC010'
    finally:
        await _update_security(
            authed_client,
            settings={
                'ip_whitelist': [],
                'ip_blacklist': [],
                'trust_x_forwarded_for': False,
                'xff_trusted_proxies': [],
            },
            headers={'X-Forwarded-For': '198.51.100.10'},
        )


@pytest.mark.asyncio
async def test_global_blacklist_blocks_with_trusted_proxy(monkeypatch, authed_client, client):
    await _update_security(
        authed_client,
        settings={
            'trust_x_forwarded_for': True,
            'xff_trusted_proxies': ['127.0.0.1'],
            'ip_whitelist': [],
            'ip_blacklist': ['203.0.113.10'],
            'allow_localhost_bypass': False,
        },
    )

    try:
        r = await client.get(
            '/platform/monitor/liveness', headers={'X-Forwarded-For': '203.0.113.10'}
        )
        assert r.status_code == 403
        body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        assert (body.get('error_code') or body.get('response', {}).get('error_code')) == 'SEC011'
    finally:
        await _update_security(
            authed_client,
            settings={
                'ip_whitelist': [],
                'ip_blacklist': [],
                'trust_x_forwarded_for': False,
                'xff_trusted_proxies': [],
            },
            headers={'X-Forwarded-For': '198.51.100.10'},
        )


@pytest.mark.asyncio
async def test_xff_ignored_when_proxy_not_trusted(monkeypatch, authed_client, client):
    await _update_security(
        authed_client,
        settings={
            'trust_x_forwarded_for': True,
            'xff_trusted_proxies': ['10.0.0.1'],
            'ip_whitelist': ['198.51.100.10'],
            'ip_blacklist': [],
            'allow_localhost_bypass': False,
        },
    )

    try:
        r = await client.get(
            '/platform/monitor/liveness', headers={'X-Forwarded-For': '198.51.100.10'}
        )
        assert r.status_code == 403
        body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        assert (body.get('error_code') or body.get('response', {}).get('error_code')) == 'SEC010'
    finally:
        monkeypatch.setenv('LOCAL_HOST_IP_BYPASS', 'true')
        try:
            await _update_security(
                authed_client,
                settings={
                    'ip_whitelist': [],
                    'ip_blacklist': [],
                    'trust_x_forwarded_for': False,
                    'xff_trusted_proxies': [],
                    'allow_localhost_bypass': False,
                },
            )
        finally:
            monkeypatch.delenv('LOCAL_HOST_IP_BYPASS', raising=False)


@pytest.mark.asyncio
async def test_localhost_bypass_enabled_allows_without_forwarding_headers(
    monkeypatch, authed_client, client
):
    await _update_security(
        authed_client,
        settings={
            'trust_x_forwarded_for': False,
            'ip_whitelist': ['198.51.100.10'],
            'ip_blacklist': [],
            'allow_localhost_bypass': True,
        },
    )

    try:
        r = await client.get('/platform/monitor/liveness')
        assert r.status_code == 200
    finally:
        await _update_security(
            authed_client,
            settings={
                'ip_whitelist': [],
                'ip_blacklist': [],
                'trust_x_forwarded_for': False,
                'xff_trusted_proxies': [],
                'allow_localhost_bypass': False,
            },
        )


@pytest.mark.asyncio
async def test_localhost_bypass_disabled_blocks_without_forwarding_headers(
    monkeypatch, authed_client, client
):
    monkeypatch.setenv('LOCAL_HOST_IP_BYPASS', 'false')

    await _update_security(
        authed_client,
        settings={
            'trust_x_forwarded_for': False,
            'ip_whitelist': ['198.51.100.10'],
            'ip_blacklist': [],
            'allow_localhost_bypass': False,
        },
    )

    try:
        r = await client.get('/platform/monitor/liveness')
        assert r.status_code == 403
        body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        assert (body.get('error_code') or body.get('response', {}).get('error_code')) == 'SEC010'
    finally:
        monkeypatch.setenv('LOCAL_HOST_IP_BYPASS', 'true')
        try:
            await _update_security(
                authed_client,
                settings={
                    'ip_whitelist': [],
                    'ip_blacklist': [],
                    'trust_x_forwarded_for': False,
                    'xff_trusted_proxies': [],
                },
            )
        finally:
            monkeypatch.delenv('LOCAL_HOST_IP_BYPASS', raising=False)


class _AuditSpy:
    def __init__(self):
        self.calls = []

    def info(self, msg):
        self.calls.append(msg)


@pytest.mark.asyncio
async def test_audit_logged_on_global_deny(monkeypatch, authed_client, client):
    import utils.audit_util as au

    orig = au._logger
    spy = _AuditSpy()
    au._logger = spy
    try:
        await _update_security(
            authed_client,
            settings={
                'trust_x_forwarded_for': True,
                'xff_trusted_proxies': ['127.0.0.1'],
                'ip_whitelist': ['198.51.100.10'],
                'ip_blacklist': [],
                'allow_localhost_bypass': False,
            },
        )

        r = await client.get(
            '/platform/monitor/liveness', headers={'X-Forwarded-For': '203.0.113.10'}
        )
        assert r.status_code == 403
        assert any('ip.global_deny' in str(c) for c in spy.calls)
        parsed = [json.loads(c) for c in spy.calls if isinstance(c, str)]
        assert any(ev.get('action') == 'ip.global_deny' for ev in parsed)
    finally:
        au._logger = orig
        await _update_security(
            authed_client,
            settings={
                'ip_whitelist': [],
                'ip_blacklist': [],
                'trust_x_forwarded_for': False,
                'xff_trusted_proxies': [],
            },
            headers={'X-Forwarded-For': '198.51.100.10'},
        )
