import pytest


@pytest.mark.asyncio
async def test_tools_chaos_toggle_and_stats(authed_client):
    # Baseline stats
    st0 = await authed_client.get('/platform/tools/chaos/stats')
    assert st0.status_code == 200

    # Enable redis outage (response reflects enabled state)
    r1 = await authed_client.post(
        '/platform/tools/chaos/toggle', json={'backend': 'redis', 'enabled': True}
    )
    assert r1.status_code == 200
    en = r1.json().get('response', r1.json())
    assert en.get('enabled') is True

    # Immediately disable to avoid auth failures on subsequent calls
    # Disable using internal util to avoid auth during outage
    from utils import chaos_util as _cu

    _cu.enable('redis', False)

    # Stats should reflect disabled
    st2 = await authed_client.get('/platform/tools/chaos/stats')
    assert st2.status_code == 200
    body2 = st2.json().get('response', st2.json())
    assert body2.get('redis_outage') is False

    # Invalid backend -> 400
    bad = await authed_client.post(
        '/platform/tools/chaos/toggle', json={'backend': 'notabackend', 'enabled': True}
    )
    assert bad.status_code == 400
