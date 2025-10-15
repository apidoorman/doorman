import os
import pytest

@pytest.mark.asyncio
async def test_max_page_size_boundary_api_list(authed_client, monkeypatch):
    monkeypatch.setenv('MAX_PAGE_SIZE', '5')

    r_ok = await authed_client.get('/platform/api/all?page=1&page_size=5')
    assert r_ok.status_code == 200, r_ok.text

    r_bad = await authed_client.get('/platform/api/all?page=1&page_size=6')
    assert r_bad.status_code == 400, r_bad.text
    body = r_bad.json()
    assert 'error_message' in body

@pytest.mark.asyncio
async def test_max_page_size_boundary_users_list(authed_client, monkeypatch):
    monkeypatch.setenv('MAX_PAGE_SIZE', '3')

    r_ok = await authed_client.get('/platform/user/all?page=1&page_size=3')
    assert r_ok.status_code == 200, r_ok.text

    r_bad = await authed_client.get('/platform/user/all?page=1&page_size=4')
    assert r_bad.status_code == 400, r_bad.text

@pytest.mark.asyncio
async def test_invalid_page_values(authed_client, monkeypatch):
    monkeypatch.setenv('MAX_PAGE_SIZE', '10')

    r1 = await authed_client.get('/platform/role/all?page=0&page_size=5')
    assert r1.status_code == 400

    r2 = await authed_client.get('/platform/group/all?page=1&page_size=0')
    assert r2.status_code == 400

