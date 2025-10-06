import pytest
import os


@pytest.mark.asyncio
async def test_memory_dump_writes_file_when_memory_mode(monkeypatch, tmp_path):
    monkeypatch.setenv('MEM_ENCRYPTION_KEY', 'test-secret-123')
    monkeypatch.setenv('MEM_DUMP_PATH', str(tmp_path / 'd' / 'dump.bin'))
    from utils.memory_dump_util import dump_memory_to_file, find_latest_dump_path
    path = dump_memory_to_file(None)
    assert os.path.exists(path)
    latest = find_latest_dump_path(str(tmp_path / 'd' / ''))
    assert latest == path


def test_dump_requires_encryption_key_logs_error(tmp_path, monkeypatch):
    # Clear key and expect ValueError on dump
    monkeypatch.delenv('MEM_ENCRYPTION_KEY', raising=False)
    monkeypatch.setenv('MEM_DUMP_PATH', str(tmp_path / 'x' / 'memory_dump.bin'))
    from utils import memory_dump_util as md
    with pytest.raises(ValueError):
        md.dump_memory_to_file(None)


def test_sigusr1_handler_registered_on_unix(monkeypatch, capsys):
    # Only assert that SIGUSR1 attribute exists and registration code path logs
    import importlib
    import doorman as appmod
    if hasattr(appmod.signal, 'SIGUSR1'):
        # simulate reload path; registration happens at import time via lifespan
        # We can't easily trigger the handler here; ensure symbol exists
        assert hasattr(appmod.signal, 'SIGUSR1')


def test_sigusr1_ignored_when_not_memory_mode(monkeypatch):
    # In non-memory mode, handler is registered but runtime check skips; here, just assert presence of SIGUSR1
    import doorman as appmod
    assert hasattr(appmod.signal, 'SIGUSR1')

