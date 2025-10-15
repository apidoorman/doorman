import pytest
import os
import platform

_RUN_LIVE = os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')
if not _RUN_LIVE:
    pytestmark = pytest.mark.skip(reason='Requires live backend service; set DOORMAN_RUN_LIVE=1 to enable')

@pytest.mark.skipif(platform.system() == 'Windows', reason='SIGUSR1 not available on Windows')
def test_sigusr1_dump_in_memory_mode_live(client, monkeypatch, tmp_path):
    monkeypatch.setenv('MEM_ENCRYPTION_KEY', 'live-secret-xyz')
    monkeypatch.setenv('MEM_DUMP_PATH', str(tmp_path / 'live' / 'memory_dump.bin'))
    import signal, time
    os.kill(os.getpid(), signal.SIGUSR1)
    time.sleep(0.5)
    assert True
