import os
import pytest


@pytest.mark.asyncio
async def test_admin_seed_fields_memory_mode(monkeypatch):
    # Ensure memory mode and deterministic admin creds
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    monkeypatch.setenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev')
    monkeypatch.setenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars')

    from utils import database as dbmod
    # Reinitialize collections to ensure seed runs
    dbmod.database.initialize_collections()

    from utils.database import user_collection, role_collection, group_collection, _build_admin_seed_doc
    admin = user_collection.find_one({'username': 'admin'})
    assert admin is not None, 'Admin user should be seeded'

    # Expected keys from canonical seed helper
    expected_keys = set(_build_admin_seed_doc('x@example.com', 'hash').keys())
    doc_keys = set(admin.keys())
    assert expected_keys.issubset(doc_keys), f'Missing keys: {expected_keys - doc_keys}'
    # In-memory will include an _id key
    assert '_id' in doc_keys

    # Password handling: should be hashed and verify
    from utils import password_util
    assert password_util.verify_password(os.environ['DOORMAN_ADMIN_PASSWORD'], admin.get('password'))

    # Groups/roles parity
    assert set(admin.get('groups') or []) >= {'ALL', 'admin'}
    role = role_collection.find_one({'role_name': 'admin'})
    assert role is not None
    # Core capabilities expected on admin role
    for cap in (
        'manage_users','manage_apis','manage_endpoints','manage_groups','manage_roles',
        'manage_routings','manage_gateway','manage_subscriptions','manage_credits','manage_auth','manage_security','view_logs'
    ):
        assert role.get(cap) is True, f'Missing admin capability: {cap}'
    grp_admin = group_collection.find_one({'group_name': 'admin'})
    grp_all = group_collection.find_one({'group_name': 'ALL'})
    assert grp_admin is not None and grp_all is not None


def test_admin_seed_helper_is_canonical():
    # Helper itself encodes the canonical set of fields for both modes
    from utils.database import _build_admin_seed_doc
    doc = _build_admin_seed_doc('a@b.c', 'hash')
    # Ensure required fields exist and have expected default values/types
    assert doc['username'] == 'admin'
    assert doc['role'] == 'admin'
    assert doc['ui_access'] is True
    assert doc['active'] is True
    assert doc['rate_limit_duration'] == 1
    assert doc['rate_limit_duration_type'] == 'second'
    assert doc['throttle_duration'] == 1
    assert doc['throttle_duration_type'] == 'second'
    assert doc['throttle_wait_duration'] == 0
    assert doc['throttle_wait_duration_type'] == 'second'
    assert doc['throttle_queue_limit'] == 1
    assert set(doc['groups']) == {'ALL', 'admin'}

