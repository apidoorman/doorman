# External imports
import json
import asyncio
import pytest


@pytest.mark.asyncio
async def test_load_settings_from_file_in_memory_mode(tmp_path, monkeypatch):
    # Ensure memory-only mode and a clean slate
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    from utils import security_settings_util as ssu
    # Point module to our temp settings file before load
    settings_path = tmp_path / 'sec_settings.json'
    monkeypatch.setattr(ssu, 'SETTINGS_FILE', str(settings_path), raising=False)
    from utils.security_settings_util import load_settings, get_cached_settings
    from utils.security_settings_util import _get_collection  # type: ignore

    coll = _get_collection()
    try:
        coll.delete_one({'type': 'security_settings'})
    except Exception:
        pass

    # Prepare a settings file with some values
    file_obj = {
        'type': 'security_settings',
        'trust_x_forwarded_for': True,
        'xff_trusted_proxies': ['10.0.0.1/32'],
        'enable_auto_save': True,
        'auto_save_frequency_seconds': 120,
        'dump_path': str(tmp_path / 'dump.bin'),
        'ip_whitelist': ['203.0.113.1'],
        'allow_localhost_bypass': True,
    }
    settings_path.write_text(json.dumps(file_obj), encoding='utf-8')
    # Clear cache to ensure fresh merge
    ssu._CACHE.clear()

    loaded = await load_settings()
    cached = get_cached_settings()

    # Assert file values took effect (merged with defaults)
    assert loaded.get('trust_x_forwarded_for') is True
    assert cached.get('xff_trusted_proxies') == ['10.0.0.1/32']
    assert cached.get('enable_auto_save') is True
    assert int(cached.get('auto_save_frequency_seconds')) == 120
    assert cached.get('dump_path') == str(tmp_path / 'dump.bin')
    assert cached.get('ip_whitelist') == ['203.0.113.1']
    assert cached.get('allow_localhost_bypass') is True


@pytest.mark.asyncio
async def test_save_settings_writes_file_and_autosave_triggers_dump(tmp_path, monkeypatch):
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    from utils import security_settings_util as ssu

    # Point persistence to a temp file
    sec_file = tmp_path / 'sec.json'
    monkeypatch.setattr(ssu, 'SETTINGS_FILE', str(sec_file), raising=False)

    # Spy on dump_memory_to_file to confirm autosave loop triggers immediately
    calls = {'count': 0, 'last_path': None}
    def _fake_dump(path_hint):
        calls['count'] += 1
        calls['last_path'] = path_hint
        return str(tmp_path / 'dump.bin')
    monkeypatch.setattr(ssu, 'dump_memory_to_file', _fake_dump)

    # Start a baseline task to ensure restart occurs
    await ssu.start_auto_save_task()
    prev_task = getattr(ssu, '_AUTO_TASK', None)

    # Enable autosave via save_settings (also writes settings file and restarts task)
    result = await ssu.save_settings({
        'enable_auto_save': True,
        'auto_save_frequency_seconds': 90,
        'dump_path': str(tmp_path / 'wanted_dump.bin'),
    })

    # Give the restarted loop a tick to run first iteration
    await asyncio.sleep(0)

    # Assertions
    assert sec_file.exists() and sec_file.read_text().strip() != ''
    new_task = getattr(ssu, '_AUTO_TASK', None)
    assert new_task is not None and new_task != prev_task
    assert calls['count'] >= 1
    assert calls['last_path'] == str(tmp_path / 'wanted_dump.bin')
    assert bool(result.get('enable_auto_save')) is True
    assert int(result.get('auto_save_frequency_seconds')) == 90

    # Cleanup
    await ssu.stop_auto_save_task()
