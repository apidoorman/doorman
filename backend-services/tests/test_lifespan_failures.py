# External imports
import pytest


@pytest.mark.asyncio
async def test_production_guard_causes_startup_failure_direct(monkeypatch):
    # Production without HTTPS flags must fail during lifespan
    monkeypatch.setenv('ENV', 'production')
    monkeypatch.setenv('HTTPS_ONLY', 'false')
    monkeypatch.setenv('HTTPS_ENABLED', 'false')
    from doorman import app_lifespan, doorman
    import pytest as _pytest
    with _pytest.raises(RuntimeError):
        async with app_lifespan(doorman):
            pass


@pytest.mark.asyncio
async def test_lifespan_failure_raises_with_fresh_app_testclient(monkeypatch):
    # Use a fresh app and Starlette TestClient; startup failure should raise
    monkeypatch.setenv('ENV', 'production')
    monkeypatch.setenv('HTTPS_ONLY', 'false')
    monkeypatch.setenv('HTTPS_ENABLED', 'false')

    from fastapi import FastAPI
    from doorman import app_lifespan
    app = FastAPI(lifespan=app_lifespan)

    @app.get('/ping')
    async def ping():
        return {'ok': True}

    from starlette.testclient import TestClient
    import pytest as _pytest
    with _pytest.raises(RuntimeError):
        with TestClient(app) as client:
            client.get('/ping')
