import pytest


@pytest.mark.asyncio
async def test_credit_definition_masking(authed_client):
    group = 'maskgroup'
    create = await authed_client.post(
        '/platform/credit',
        json={
            'api_credit_group': group,
            'api_key': 'VERY-SECRET-KEY',
            'api_key_header': 'x-api-key',
            'credit_tiers': [
                {
                    'tier_name': 'default',
                    'credits': 5,
                    'input_limit': 0,
                    'output_limit': 0,
                    'reset_frequency': 'monthly',
                }
            ],
        },
    )
    assert create.status_code in (200, 201), create.text

    r = await authed_client.get(f'/platform/credit/defs/{group}')
    assert r.status_code == 200, r.text
    body = r.json().get('response', r.json())

    # Masking rules
    assert body.get('api_credit_group') == group
    assert body.get('api_key_header') == 'x-api-key'
    assert body.get('api_key_present') is True
    # Under no circumstance should the API key material be returned
    assert 'api_key' not in body
