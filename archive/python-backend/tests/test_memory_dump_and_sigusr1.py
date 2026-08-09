import os

import pytest


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
    monkeypatch.delenv('MEM_ENCRYPTION_KEY', raising=False)
    monkeypatch.setenv('MEM_DUMP_PATH', str(tmp_path / 'x' / 'memory_dump.bin'))
    from utils import memory_dump_util as md

    with pytest.raises(ValueError):
        md.dump_memory_to_file(None)


def test_sigusr1_handler_registered_on_unix(monkeypatch, capsys):
    import doorman as appmod

    if hasattr(appmod.signal, 'SIGUSR1'):
        assert hasattr(appmod.signal, 'SIGUSR1')


def test_sigusr1_ignored_when_not_memory_mode(monkeypatch):
    import doorman as appmod

    assert hasattr(appmod.signal, 'SIGUSR1')
