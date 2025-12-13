import uuid

import pytest

from utils.database import endpoint_collection, endpoint_validation_collection


def _mk_endpoint(api_name: str, api_version: str, method: str, uri: str) -> dict:
    eid = str(uuid.uuid4())
    doc = {
        'endpoint_id': eid,
        'api_id': f'{api_name}-{api_version}',
        'api_name': api_name,
        'api_version': api_version,
        'endpoint_method': method,
        'endpoint_uri': uri,
        'endpoint_description': f'{method} {uri}',
        'active': True,
    }
    endpoint_collection.insert_one(doc)
    return doc


def _run_audit() -> list[str]:
    failures: list[str] = []
    for vdoc in endpoint_validation_collection.find({'validation_enabled': True}):
        eid = vdoc.get('endpoint_id')
        ep = endpoint_collection.find_one({'endpoint_id': eid})
        if not ep:
            failures.append(f'Validation references missing endpoint: {eid}')
            continue
        schema = vdoc.get('validation_schema')
        if not isinstance(schema, dict) or not schema:
            failures.append(
                f'Enabled validation missing schema for endpoint {ep.get("endpoint_method")} {ep.get("api_name")}/{ep.get("api_version")} {ep.get("endpoint_uri")} (id={eid})'
            )
    return failures


@pytest.mark.asyncio
async def test_validator_activation_audit_passes():
    e_rest = _mk_endpoint('customers', 'v1', 'POST', '/create')
    e_graphql = _mk_endpoint('graphqlsvc', 'v1', 'POST', '/graphql')
    e_grpc = _mk_endpoint('grpcsvc', 'v1', 'POST', '/grpc')
    _mk_endpoint('soapsvc', 'v1', 'POST', '/soap')

    endpoint_validation_collection.insert_one(
        {
            'endpoint_id': e_rest['endpoint_id'],
            'validation_enabled': True,
            'validation_schema': {'payload.name': {'required': True, 'type': 'string', 'min': 1}},
        }
    )
    endpoint_validation_collection.insert_one(
        {
            'endpoint_id': e_graphql['endpoint_id'],
            'validation_enabled': True,
            'validation_schema': {'input.query': {'required': True, 'type': 'string', 'min': 1}},
        }
    )
    endpoint_validation_collection.insert_one(
        {
            'endpoint_id': e_grpc['endpoint_id'],
            'validation_enabled': True,
            'validation_schema': {'message.name': {'required': True, 'type': 'string', 'min': 1}},
        }
    )

    failures = _run_audit()
    assert not failures, '\n'.join(failures)


@pytest.mark.asyncio
async def test_validator_activation_audit_detects_missing_schema():
    e = _mk_endpoint('soapsvc2', 'v1', 'POST', '/soap')
    endpoint_validation_collection.insert_one(
        {'endpoint_id': e['endpoint_id'], 'validation_enabled': True}
    )
    failures = _run_audit()
    assert failures and any('missing schema' in f for f in failures)
