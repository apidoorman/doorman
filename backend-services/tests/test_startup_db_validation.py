import ast
import asyncio
import os
from pathlib import Path

import pytest


def _load_validate_database_connections():
    doorman_path = Path(__file__).resolve().parents[1] / 'doorman.py'
    source = doorman_path.read_text(encoding='utf-8')
    module = ast.parse(source, filename=str(doorman_path))
    func = next(
        node
        for node in module.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'validate_database_connections'
    )
    isolated_module = ast.Module(body=[func], type_ignores=[])
    ast.fix_missing_locations(isolated_module)

    class _Logger:
        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

    namespace = {
        'asyncio': asyncio,
        'os': os,
        'gateway_logger': _Logger(),
    }
    exec(compile(isolated_module, str(doorman_path), 'exec'), namespace)
    return namespace['validate_database_connections']


@pytest.mark.asyncio
async def test_validate_database_connections_uses_async_user_collection(monkeypatch):
    import utils.database_async as db_async

    class _AsyncCollection:
        def __init__(self):
            self.called = False

        async def find_one(self, query):
            self.called = True
            return {'_id': 'ok'}

    fake_collection = _AsyncCollection()
    monkeypatch.setattr(db_async, 'user_collection', fake_collection)
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
    monkeypatch.delenv('REDIS_HOST', raising=False)

    validate_database_connections = _load_validate_database_connections()
    await validate_database_connections()

    assert fake_collection.called is True
