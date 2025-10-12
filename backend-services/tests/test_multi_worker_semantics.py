import pytest


@pytest.mark.asyncio
async def test_mem_multi_worker_guard_raises(monkeypatch):
    # MEM mode with multiple workers must fail due to non-shared revocation
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    monkeypatch.setenv('THREADS', '2')
    from doorman import validate_token_revocation_config

    with pytest.raises(RuntimeError):
        validate_token_revocation_config()


@pytest.mark.asyncio
async def test_mem_single_worker_allowed(monkeypatch):
    # MEM mode with single worker is allowed
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    monkeypatch.setenv('THREADS', '1')
    from doorman import validate_token_revocation_config

    # Should not raise
    validate_token_revocation_config()


@pytest.mark.asyncio
async def test_redis_multi_worker_allowed(monkeypatch):
    # REDIS mode with multiple workers is allowed (shared revocation)
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'REDIS')
    monkeypatch.setenv('THREADS', '4')
    from doorman import validate_token_revocation_config

    # Should not raise
    validate_token_revocation_config()

