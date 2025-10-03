def test_config_export_import_roundtrip(client):
    # Export all
    r = client.get('/platform/config/export/all')
    assert r.status_code == 200
    payload = r.json().get('response', r.json())
    assert isinstance(payload, dict)
    # Import back the same payload (should be idempotent)
    r = client.post('/platform/config/import', json=payload)
    assert r.status_code == 200
    data = r.json().get('response', r.json())
    assert 'imported' in data
import pytest
pytestmark = [pytest.mark.config]
