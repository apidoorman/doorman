import pytest

@pytest.mark.asyncio
async def test_mem_multi_worker_guard_raises(monkeypatch):
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    monkeypatch.setenv('THREADS', '2')
    from doorman import validate_token_revocation_config

    with pytest.raises(RuntimeError):
        validate_token_revocation_config()

@pytest.mark.asyncio
async def test_mem_single_worker_allowed(monkeypatch):
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    monkeypatch.setenv('THREADS', '1')
    from doorman import validate_token_revocation_config

    validate_token_revocation_config()

@pytest.mark.asyncio
async def test_redis_multi_worker_allowed(monkeypatch):
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'REDIS')
    monkeypatch.setenv('THREADS', '4')
    from doorman import validate_token_revocation_config

    validate_token_revocation_config()

