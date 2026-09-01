"""
Tests for API key expiry in user credit documents.

Verifies:
- get_user_api_key returns the key when no expiry is set (backward compat)
- get_user_api_key returns None when the key has expired
- get_user_api_key returns the key when expiry is in the future
- rotate_api_key writes user_api_key_expires_at when expires_in_days is provided
- rotate_api_key does not write user_api_key_expires_at when expires_in_days is omitted
"""

from datetime import UTC, datetime, timedelta

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_credit_doc(username: str, group: str, key: str, expires_at=None) -> dict:
    entry = {
        'tier_name': 'basic',
        'available_credits': 10,
        'user_api_key': key,
    }
    if expires_at is not None:
        entry['user_api_key_expires_at'] = expires_at
    return {'username': username, 'users_credits': {group: entry}}


def _seed_sync(doc: dict):
    """Seed a credit document using the synchronous in-memory collection."""
    from utils.database import user_credit_collection as _sync_coll
    _sync_coll.delete_one({'username': doc['username']})
    _sync_coll.insert_one(doc)


# ---------------------------------------------------------------------------
# get_user_api_key — expiry behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_user_api_key_no_expiry_field():
    """Key with no expiry field should always be returned (backward compat)."""
    from utils.credit_util import get_user_api_key

    _seed_sync(_make_credit_doc('expiry_user_1', 'grp', 'plainkey'))

    result = await get_user_api_key('grp', 'expiry_user_1')
    # The key is not encrypted in the test doc, so decrypt_value returns None → raw fallback
    assert result == 'plainkey'


@pytest.mark.asyncio
async def test_get_user_api_key_not_yet_expired():
    """Key with a future expiry should be returned."""
    from utils.credit_util import get_user_api_key

    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    _seed_sync(_make_credit_doc('expiry_user_2', 'grp', 'validkey', expires_at=future))

    result = await get_user_api_key('grp', 'expiry_user_2')
    assert result == 'validkey'


@pytest.mark.asyncio
async def test_get_user_api_key_expired():
    """Key with a past expiry should return None."""
    from utils.credit_util import get_user_api_key

    past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    _seed_sync(_make_credit_doc('expiry_user_3', 'grp', 'expiredkey', expires_at=past))

    result = await get_user_api_key('grp', 'expiry_user_3')
    assert result is None


@pytest.mark.asyncio
async def test_get_user_api_key_expires_at_none():
    """Explicit None expiry should be treated the same as no expiry field."""
    from utils.credit_util import get_user_api_key

    _seed_sync(_make_credit_doc('expiry_user_4', 'grp', 'nonekey', expires_at=None))

    result = await get_user_api_key('grp', 'expiry_user_4')
    assert result == 'nonekey'


@pytest.mark.asyncio
async def test_get_user_api_key_no_group():
    """Passing None credit group should immediately return None."""
    from utils.credit_util import get_user_api_key

    result = await get_user_api_key(None, 'anyone')
    assert result is None


# ---------------------------------------------------------------------------
# rotate_api_key — expiry parameter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rotate_api_key_with_expiry(authed_client):
    """rotate_api_key with expires_in_days=30 should store expires_at ~30 days from now."""
    from services.credit_service import CreditService
    from utils.database import user_credit_collection as _sync_coll

    _sync_coll.delete_one({'username': 'rotate_expiry_user'})
    _sync_coll.insert_one({
        'username': 'rotate_expiry_user',
        'users_credits': {
            'testgroup': {'tier_name': 'basic', 'available_credits': 5, 'user_api_key': None}
        },
    })

    result = await CreditService.rotate_api_key(
        'rotate_expiry_user', 'testgroup', 'test-req', expires_in_days=30
    )
    assert result.get('status_code') == 200

    doc = _sync_coll.find_one({'username': 'rotate_expiry_user'})
    expires_raw = doc['users_credits']['testgroup'].get('user_api_key_expires_at')
    assert expires_raw is not None

    expires_dt = datetime.fromisoformat(str(expires_raw).replace('Z', '+00:00'))
    delta = expires_dt - datetime.now(UTC)
    assert 29 <= delta.days <= 30


@pytest.mark.asyncio
async def test_rotate_api_key_without_expiry(authed_client):
    """rotate_api_key without expires_in_days should not write user_api_key_expires_at."""
    from services.credit_service import CreditService
    from utils.database import user_credit_collection as _sync_coll

    _sync_coll.delete_one({'username': 'rotate_noexpiry_user'})
    _sync_coll.insert_one({
        'username': 'rotate_noexpiry_user',
        'users_credits': {
            'testgroup': {'tier_name': 'basic', 'available_credits': 5, 'user_api_key': None}
        },
    })

    result = await CreditService.rotate_api_key(
        'rotate_noexpiry_user', 'testgroup', 'test-req'
    )
    assert result.get('status_code') == 200

    doc = _sync_coll.find_one({'username': 'rotate_noexpiry_user'})
    assert 'user_api_key_expires_at' not in doc['users_credits']['testgroup']
