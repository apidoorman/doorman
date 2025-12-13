def test_memory_dump_via_route_live(client, tmp_path):
    dest = str(tmp_path / 'live' / 'memory_dump.bin')
    r = client.post('/platform/memory/dump', json={'path': dest})
    # Expect success when server is in MEM mode with MEM_ENCRYPTION_KEY set
    # 400 is expected when not in memory mode or encryption key not set
    assert r.status_code in (200, 400), r.text
    if r.status_code == 200:
        body = r.json()
        # Response structure: {response: {response: {path: ...}}} or {response: {path: ...}}
        resp = body.get('response', body)
        if isinstance(resp, dict):
            inner = resp.get('response', resp)
            path = inner.get('path') if isinstance(inner, dict) else None
        else:
            path = None
        assert isinstance(path, str) and len(path) > 0, f'Expected path in response: {body}'
