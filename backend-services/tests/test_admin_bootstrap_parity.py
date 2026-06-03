import os

import pytest


@pytest.mark.asyncio
async def test_admin_seed_fields_memory_mode(monkeypatch):
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    monkeypatch.setenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev')
    monkeypatch.setenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars')

    from utils import database as dbmod

    dbmod.database.initialize_collections()

    from utils.database import (
        _build_admin_seed_doc,
        group_collection,
        role_collection,
        user_collection,
    )

    admin = user_collection.find_one({'username': 'admin'})
    assert admin is not None, 'Admin user should be seeded'

    expected_keys = set(_build_admin_seed_doc('x@example.com', 'hash').keys())
    doc_keys = set(admin.keys())
    assert expected_keys.issubset(doc_keys), f'Missing keys: {expected_keys - doc_keys}'
    assert '_id' in doc_keys

    from utils import password_util

    assert password_util.verify_password(
        os.environ['DOORMAN_ADMIN_PASSWORD'], admin.get('password')
    )

    assert set(admin.get('groups') or []) >= {'ALL', 'admin'}
    role = role_collection.find_one({'role_name': 'admin'})
    assert role is not None
    for cap in (
        'manage_users',
        'manage_apis',
        'manage_endpoints',
        'manage_groups',
        'manage_roles',
        'manage_routings',
        'manage_gateway',
        'manage_subscriptions',
        'manage_credits',
        'manage_auth',
        'manage_security',
        'view_logs',
    ):
        assert role.get(cap) is True, f'Missing admin capability: {cap}'
    grp_admin = group_collection.find_one({'group_name': 'admin'})
    grp_all = group_collection.find_one({'group_name': 'ALL'})
    assert grp_admin is not None and grp_all is not None


def test_admin_seed_helper_is_canonical():
    from utils.database import _build_admin_seed_doc

    doc = _build_admin_seed_doc('a@b.c', 'hash')
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


def test_admin_seed_fields_mongo_branch_creates_default_groups(monkeypatch):
    monkeypatch.setenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev')
    monkeypatch.setenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars')

    from utils.database import Database

    class _FakeResult:
        acknowledged = True
        modified_count = 1

    class _FakeCollection:
        def __init__(self):
            self.docs = []

        def find_one(self, query):
            for doc in self.docs:
                if all(doc.get(k) == v for k, v in query.items()):
                    return dict(doc)
            return None

        def insert_one(self, doc):
            self.docs.append(dict(doc))
            return _FakeResult()

        def update_one(self, query, update):
            for i, doc in enumerate(self.docs):
                if all(doc.get(k) == v for k, v in query.items()):
                    updated = dict(doc)
                    updated.update(update.get('$set', {}))
                    self.docs[i] = updated
                    break
            return _FakeResult()

    class _FakeMongoDB:
        def __init__(self):
            self._collections = {}
            for name in (
                'users',
                'apis',
                'endpoints',
                'groups',
                'roles',
                'subscriptions',
                'routings',
                'credit_defs',
                'user_credits',
                'endpoint_validations',
                'settings',
                'revocations',
                'vault_entries',
                'api_builder_tables',
                'tiers',
                'user_tier_assignments',
            ):
                self.create_collection(name)

        def list_collection_names(self):
            return list(self._collections.keys())

        def create_collection(self, name):
            coll = self._collections.get(name)
            if coll is None:
                coll = _FakeCollection()
                self._collections[name] = coll
                setattr(self, name, coll)
            return coll

    db = object.__new__(Database)
    db.memory_only = False
    db.db_existed = False
    db.db = _FakeMongoDB()

    Database.initialize_collections(db)

    grp_admin = db.db.groups.find_one({'group_name': 'admin'})
    grp_all = db.db.groups.find_one({'group_name': 'ALL'})

    assert grp_admin is not None
    assert grp_all is not None
