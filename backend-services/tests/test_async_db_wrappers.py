import pytest

from utils.async_db import db_delete_one, db_find_one, db_insert_one, db_update_one
from utils.database_async import async_database


@pytest.mark.asyncio
async def test_async_wrappers_with_inmemory_async_collections():
    coll = async_database.db.tiers  # AsyncInMemoryCollection

    # Insert
    await db_insert_one(coll, {'tier_id': 't1', 'name': 'Tier 1'})
    doc = await db_find_one(coll, {'tier_id': 't1'})
    assert doc and doc.get('name') == 'Tier 1'

    # Update
    await db_update_one(coll, {'tier_id': 't1'}, {'$set': {'name': 'Tier One'}})
    doc2 = await db_find_one(coll, {'tier_id': 't1'})
    assert doc2 and doc2.get('name') == 'Tier One'

    # Delete
    await db_delete_one(coll, {'tier_id': 't1'})
    assert await db_find_one(coll, {'tier_id': 't1'}) is None


class _SyncColl:
    def __init__(self):
        self._docs = []

    def find_one(self, q):
        for d in self._docs:
            match = all(d.get(k) == v for k, v in q.items())
            if match:
                return dict(d)
        return None

    def insert_one(self, doc):
        self._docs.append(dict(doc))

        class R:
            acknowledged = True
            inserted_id = 'x'

        return R()

    def update_one(self, q, upd):
        for i, d in enumerate(self._docs):
            if all(d.get(k) == v for k, v in q.items()):
                setv = upd.get('$set', {})
                nd = dict(d)
                nd.update(setv)
                self._docs[i] = nd

                class R:
                    acknowledged = True
                    modified_count = 1

                return R()

        class R2:
            acknowledged = True
            modified_count = 0

        return R2()

    def delete_one(self, q):
        for i, d in enumerate(self._docs):
            if all(d.get(k) == v for k, v in q.items()):
                del self._docs[i]

                class R:
                    acknowledged = True
                    deleted_count = 1

                return R()

        class R2:
            acknowledged = True
            deleted_count = 0

        return R2()


@pytest.mark.asyncio
async def test_async_wrappers_fallback_to_thread_for_sync_collections():
    coll = _SyncColl()
    await db_insert_one(coll, {'k': 1, 'v': 'a'})
    d = await db_find_one(coll, {'k': 1})
    assert d and d['v'] == 'a'
    await db_update_one(coll, {'k': 1}, {'$set': {'v': 'b'}})
    d2 = await db_find_one(coll, {'k': 1})
    assert d2 and d2['v'] == 'b'
    await db_delete_one(coll, {'k': 1})
    assert await db_find_one(coll, {'k': 1}) is None
