# External imports
import os
import re
import pytest


def _collect_set_cookie_headers(resp):
    try:
        # httpx.Headers supports get_list
        return resp.headers.get_list('set-cookie')
    except Exception:
        raw = resp.headers.get('set-cookie') or ''
        return [h.strip() for h in raw.split(',') if 'Expires=' not in h] or ([raw] if raw else [])


def _find_cookie_lines(lines, name):
    name_l = name.lower() + '='
    return [l for l in lines if name_l in l.lower()]


@pytest.mark.asyncio
async def test_default_samesite_strict_and_secure_false(monkeypatch, client):
    monkeypatch.delenv('COOKIE_SAMESITE', raising=False)
    monkeypatch.setenv('HTTPS_ONLY', 'false')
    monkeypatch.setenv('HTTPS_ENABLED', 'false')

    r = await client.post('/platform/authorization', json={'email': os.environ['STARTUP_ADMIN_EMAIL'], 'password': os.environ['STARTUP_ADMIN_PASSWORD']})
    assert r.status_code == 200
    cookies = _collect_set_cookie_headers(r)
    atk = _find_cookie_lines(cookies, 'access_token_cookie')
    csrf = _find_cookie_lines(cookies, 'csrf_token')
    assert atk and csrf
    def has_attr(lines, pattern):
        return any(re.search(pattern, l, flags=re.I) for l in lines)
    assert has_attr(atk, r"samesite\s*=\s*strict")
    assert has_attr(csrf, r"samesite\s*=\s*strict")
    assert not has_attr(atk, r";\s*secure(\s*;|$)")
    assert not has_attr(csrf, r";\s*secure(\s*;|$)")


@pytest.mark.asyncio
async def test_cookies_samesite_lax_override(monkeypatch, client):
    monkeypatch.setenv('COOKIE_SAMESITE', 'Lax')
    monkeypatch.setenv('HTTPS_ONLY', 'false')
    monkeypatch.setenv('HTTPS_ENABLED', 'false')

    r = await client.post('/platform/authorization', json={'email': os.environ['STARTUP_ADMIN_EMAIL'], 'password': os.environ['STARTUP_ADMIN_PASSWORD']})
    assert r.status_code == 200
    cookies = _collect_set_cookie_headers(r)
    atk = _find_cookie_lines(cookies, 'access_token_cookie')
    csrf = _find_cookie_lines(cookies, 'csrf_token')
    assert atk and csrf
    def has_attr(lines, pattern):
        return any(re.search(pattern, l, flags=re.I) for l in lines)
    assert has_attr(atk, r"samesite\s*=\s*lax")
    assert has_attr(csrf, r"samesite\s*=\s*lax")


@pytest.mark.asyncio
async def test_secure_flag_toggles_with_https(monkeypatch, client):
    # HTTPS off → no Secure
    monkeypatch.setenv('COOKIE_SAMESITE', 'None')
    monkeypatch.setenv('HTTPS_ONLY', 'false')
    monkeypatch.setenv('HTTPS_ENABLED', 'false')
    r1 = await client.post('/platform/authorization', json={'email': os.environ['STARTUP_ADMIN_EMAIL'], 'password': os.environ['STARTUP_ADMIN_PASSWORD']})
    assert r1.status_code == 200
    cookies1 = _collect_set_cookie_headers(r1)
    atk1 = _find_cookie_lines(cookies1, 'access_token_cookie')
    csrf1 = _find_cookie_lines(cookies1, 'csrf_token')
    def has_attr(lines, pattern):
        return any(re.search(pattern, l, flags=re.I) for l in lines)
    assert not has_attr(atk1, r";\s*secure(\s*;|$)")
    assert not has_attr(csrf1, r";\s*secure(\s*;|$)")

    # HTTPS on → Secure present
    monkeypatch.setenv('HTTPS_ONLY', 'true')
    r2 = await client.post('/platform/authorization', json={'email': os.environ['STARTUP_ADMIN_EMAIL'], 'password': os.environ['STARTUP_ADMIN_PASSWORD']})
    assert r2.status_code == 200
    cookies2 = _collect_set_cookie_headers(r2)
    atk2 = _find_cookie_lines(cookies2, 'access_token_cookie')
    csrf2 = _find_cookie_lines(cookies2, 'csrf_token')
    assert has_attr(atk2, r";\s*secure(\s*;|$)")
    assert has_attr(csrf2, r";\s*secure(\s*;|$)")

