import os
import pytest

pytestmark = [pytest.mark.security]


def test_memory_dump_restore_conditionally(client):
    mem_mode = os.environ.get('MEM_OR_EXTERNAL', os.environ.get('MEM_OR_REDIS', 'MEM')).upper() == 'MEM'
    key = os.environ.get('MEM_ENCRYPTION_KEY')
    if not mem_mode or not key:
        pytest.skip('Memory dump/restore only in memory mode with MEM_ENCRYPTION_KEY set')
    # Dump
    r = client.post('/platform/memory/dump', json={})
    assert r.status_code == 200
    path = (r.json().get('response') or {}).get('path')
    assert path
    # Restore
    r = client.post('/platform/memory/restore', json={'path': path})
    assert r.status_code == 200

