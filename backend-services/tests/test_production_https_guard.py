import pytest


@pytest.mark.asyncio
async def test_production_without_https_flags_fails_startup(monkeypatch):
    monkeypatch.setenv('ENV', 'production')
    monkeypatch.setenv('HTTPS_ONLY', 'false')

    import pytest as _pytest

    from doorman import app_lifespan, doorman

    with _pytest.raises(RuntimeError):
        async with app_lifespan(doorman):
            pass


@pytest.mark.asyncio
async def test_production_with_https_only_succeeds(monkeypatch):
    monkeypatch.setenv('ENV', 'production')
    monkeypatch.setenv('HTTPS_ONLY', 'true')

    from httpx import AsyncClient

    from doorman import doorman

    client = AsyncClient(app=doorman, base_url='http://testserver')
    r = await client.get('/platform/monitor/liveness')
    assert r.status_code == 200
