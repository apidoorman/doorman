import os
import pytest
import asyncio
import logging
from io import StringIO

@pytest.mark.asyncio
async def test_graceful_shutdown_allows_inflight_completion(monkeypatch):
    from services.user_service import UserService
    original = UserService.check_password_return_user

    async def _slow_check(email, password):
        await asyncio.sleep(0.3)
        return await original(email, password)

    monkeypatch.setattr(UserService, 'check_password_return_user', _slow_check)

    logger = logging.getLogger('doorman.gateway')
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)

    try:
        from doorman import doorman, app_lifespan
        from httpx import AsyncClient

        async with app_lifespan(doorman):
            client = AsyncClient(app=doorman, base_url='http://testserver')
            creds = {
                'email': os.environ.get('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
                'password': os.environ.get('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
            }
            req_task = asyncio.create_task(client.post('/platform/authorization', json=creds))
            await asyncio.sleep(0.05)

        resp = await req_task
        assert resp.status_code in (200, 400), resp.text

        logs = stream.getvalue()
        assert 'Starting graceful shutdown' in logs
        assert 'Waiting for in-flight requests to complete' in logs
    finally:
        logger.removeHandler(handler)

