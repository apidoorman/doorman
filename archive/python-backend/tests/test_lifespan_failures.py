import pytest


@pytest.mark.asyncio
async def test_production_guard_causes_startup_failure_direct(monkeypatch):
    monkeypatch.setenv('ENV', 'production')
    monkeypatch.setenv('HTTPS_ONLY', 'false')
    import pytest as _pytest

    from doorman import app_lifespan, doorman

    with _pytest.raises(RuntimeError):
        async with app_lifespan(doorman):
            pass


@pytest.mark.asyncio
async def test_lifespan_failure_raises_with_fresh_app_testclient(monkeypatch):
    monkeypatch.setenv('ENV', 'production')
    monkeypatch.setenv('HTTPS_ONLY', 'false')

    from fastapi import FastAPI

    from doorman import app_lifespan

    app = FastAPI(lifespan=app_lifespan)

    @app.get('/ping')
    async def ping():
        return {'ok': True}

    import pytest as _pytest
    from starlette.testclient import TestClient

    with _pytest.raises(RuntimeError):
        with TestClient(app) as client:
            client.get('/ping')
