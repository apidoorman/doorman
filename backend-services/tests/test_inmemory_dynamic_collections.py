from utils.database import InMemoryDB


def test_dump_and_load_include_dynamic_collections():
    db = InMemoryDB()

    table_registry = db.create_collection('api_builder_tables')
    table_registry.insert_one(
        {
            '_id': 'tbl-1',
            'table_name': 'Products',
            'collection_name': 'crud_data_products',
            'schema': {'name': {'type': 'string', 'required': True}},
        }
    )

    products = db.create_collection('crud_data_products')
    products.insert_one({'_id': 'p-1', 'name': 'Laptop'})

    snapshot = db.dump_data()
    assert 'api_builder_tables' in snapshot
    assert 'crud_data_products' in snapshot
    assert snapshot['api_builder_tables'][0]['table_name'] == 'Products'

    restored = InMemoryDB()
    restored.load_data(snapshot)
    assert 'api_builder_tables' in restored.list_collection_names()
    assert 'crud_data_products' in restored.list_collection_names()

    restored_registry = restored.create_collection('api_builder_tables')
    restored_products = restored.create_collection('crud_data_products')
    assert restored_registry.find_one({'_id': 'tbl-1'}) is not None
    assert restored_products.find_one({'_id': 'p-1'}) is not None

