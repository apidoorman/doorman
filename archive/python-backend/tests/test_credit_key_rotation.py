from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_credit_key_rotation_logic_resolves_header_and_keys():
    from utils.credit_util import get_credit_api_header
    from utils.database import credit_def_collection

    group = 'rotgrp'
    credit_def_collection.delete_one({'api_credit_group': group})
    # Insert with rotation in the future
    credit_def_collection.insert_one(
        {
            'api_credit_group': group,
            'api_key_header': 'x-api-key',
            'api_key': 'old-key',
            'api_key_new': 'new-key',
            'api_key_rotation_expires': datetime.now(UTC) + timedelta(hours=1),
        }
    )

    hdr = await get_credit_api_header(group)
    assert hdr and hdr[0] == 'x-api-key'
    assert isinstance(hdr[1], list)
    assert hdr[1][0] == 'old-key' and hdr[1][1] == 'new-key'

    # After rotation expiry, only new key should be returned
    credit_def_collection.update_one(
        {'api_credit_group': group},
        {'$set': {'api_key_rotation_expires': datetime.now(UTC) - timedelta(seconds=1)}},
    )
    hdr2 = await get_credit_api_header(group)
    assert hdr2 and hdr2[0] == 'x-api-key'
    assert hdr2[1] == 'new-key'
