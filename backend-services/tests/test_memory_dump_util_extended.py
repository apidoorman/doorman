import os
import time
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_dump_file_naming_and_dir_creation(monkeypatch, tmp_path):
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    monkeypatch.setenv('MEM_ENCRYPTION_KEY', 'unit-test-key-12345')

    from utils.memory_dump_util import dump_memory_to_file, find_latest_dump_path

    hint_file = tmp_path / 'custom' / 'mydump.bin'
    dump_path = dump_memory_to_file(str(hint_file))
    assert Path(dump_path).exists()

    assert Path(dump_path).name.startswith('mydump-') and dump_path.endswith('.bin')

    latest = find_latest_dump_path(str(tmp_path / 'custom' / 'mydump.bin'))
    assert latest == dump_path


@pytest.mark.asyncio
async def test_dump_with_directory_hint_uses_default_stem(monkeypatch, tmp_path):
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    monkeypatch.setenv('MEM_ENCRYPTION_KEY', 'unit-test-key-99999')

    from utils.memory_dump_util import dump_memory_to_file

    d = tmp_path / 'onlydir'
    d.mkdir(parents=True, exist_ok=True)
    dump_path = dump_memory_to_file(str(d))
    assert Path(dump_path).exists()
    assert Path(dump_path).name.startswith('memory_dump-')


def test_find_latest_prefers_newest_by_stem(tmp_path):
    from utils.memory_dump_util import find_latest_dump_path

    d = tmp_path / 'dumps'
    d.mkdir(parents=True, exist_ok=True)
    a = d / 'memory_dump-20200101T000000Z.bin'
    b = d / 'memory_dump-20300101T000000Z.bin'
    a.write_bytes(b'a')
    b.write_bytes(b'b')

    now = time.time()
    os.utime(a, (now - 1000, now - 1000))
    os.utime(b, (now, now))

    latest = find_latest_dump_path(str(d / 'memory_dump.bin'))
    assert latest and latest.endswith(b.name)


def test_find_latest_ignores_other_stems_when_dir_hint(tmp_path):
    from utils.memory_dump_util import find_latest_dump_path

    d = tmp_path / 'store'
    d.mkdir(parents=True, exist_ok=True)
    x = d / 'memory_dump-20220101T000000Z.bin'
    y = d / 'otherstem-20990101T000000Z.bin'
    x.write_bytes(b'x')
    y.write_bytes(b'y')

    os.utime(x, None)
    os.utime(y, (time.time() + 1000, time.time() + 1000))

    latest = find_latest_dump_path(str(d))
    assert latest and Path(latest).name.startswith('memory_dump-')


def test_find_latest_uses_default_when_no_hint(monkeypatch, tmp_path):
    import utils.memory_dump_util as md

    base = tmp_path / 'default'
    base.mkdir(parents=True, exist_ok=True)

    md.DEFAULT_DUMP_PATH = str(base / 'memory_dump.bin')

    a = base / 'memory_dump-20000101T000000Z.bin'
    b = base / 'memory_dump-20500101T000000Z.bin'
    a.write_bytes(b'a')
    b.write_bytes(b'b')
    os.utime(a, (time.time() - 1000, time.time() - 1000))
    os.utime(b, None)

    latest = md.find_latest_dump_path(None)
    assert latest and latest.endswith(b.name)


def test_encrypt_decrypt_roundtrip(monkeypatch):
    import utils.memory_dump_util as md

    key = 'roundtrip-key-123'
    pt = b'hello world'
    blob = md._encrypt_blob(pt, key)
    assert blob.startswith(b'DMP1')
    out = md._decrypt_blob(blob, key)
    assert out == pt


def test_encrypt_requires_sufficient_key(monkeypatch):
    import utils.memory_dump_util as md

    with pytest.raises(ValueError):
        md._encrypt_blob(b'data', 'short')


@pytest.mark.asyncio
async def test_dump_and_restore_roundtrip_with_bytes(monkeypatch, tmp_path):
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    monkeypatch.setenv('MEM_ENCRYPTION_KEY', 'unit-test-key-abcde')
    monkeypatch.setenv('MEM_DUMP_PATH', str(tmp_path / 'mem' / 'memory_dump.bin'))

    import utils.memory_dump_util as md
    from utils.database import database

    database.db.settings.insert_one(
        {'_id': 'cfg', 'blob': b'\x00\x01', 'tuple': (1, 2, 3), 'aset': {'a', 'b'}}
    )

    dump_path = md.dump_memory_to_file(None)
    assert Path(dump_path).exists()

    database.db.settings._docs.clear()
    assert database.db.settings.count_documents({}) == 0
    info = md.restore_memory_from_file(md.find_latest_dump_path(str(tmp_path / 'mem')))
    assert info['version'] == 1
    restored = database.db.settings.find_one({'_id': 'cfg'})
    assert isinstance(restored.get('blob'), (bytes, bytearray))
    assert set(restored.get('aset')) == {'a', 'b'}
    assert list(restored.get('tuple')) == [1, 2, 3]


def test_restore_nonexistent_file_raises(tmp_path):
    import utils.memory_dump_util as md

    with pytest.raises(FileNotFoundError):
        md.restore_memory_from_file(str(tmp_path / 'nope.bin'))


@pytest.mark.asyncio
async def test_dump_fails_with_short_key(monkeypatch, tmp_path):
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    monkeypatch.setenv('MEM_ENCRYPTION_KEY', 'short')
    monkeypatch.setenv('MEM_DUMP_PATH', str(tmp_path / 'd' / 'dump.bin'))

    from utils.memory_dump_util import dump_memory_to_file

    with pytest.raises(ValueError):
        _ = dump_memory_to_file(None)
