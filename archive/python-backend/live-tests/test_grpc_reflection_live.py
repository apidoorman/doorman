import os
import time

import pytest

pytestmark = [pytest.mark.grpc, pytest.mark.public]


def test_grpc_reflection_no_proto(client):
    name, ver = f'grpc-refl-{int(time.time())}', 'v1'

    # Create API without uploading any proto to force reflection or failure path
    r = client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'gRPC reflection test',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['grpcs://grpcb.in:9001'],
            'api_type': 'GRPC',
            'api_allowed_retry_count': 0,
            'active': True,
            'api_grpc_package': 'grpcbin',
            'api_public': True,
        },
    )
    assert r.status_code in (200, 201), r.text

    r = client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/grpc',
            'endpoint_description': 'grpc',
        },
    )
    assert r.status_code in (200, 201), r.text

    try:
        body = {'method': 'GRPCBin.Empty', 'message': {}}
        res = client.post(f'/api/grpc/{name}', json=body, headers={'X-API-Version': ver})
        # If reflection is enabled on Doorman, require a successful 200 response.
        # Otherwise, accept any non-auth failure outcome to confirm reachability.
        if os.getenv('DOORMAN_ENABLE_GRPC_REFLECTION', '').lower() in ('1', 'true', 'yes'):
            assert res.status_code == 200, res.text
        else:
            assert res.status_code not in (401, 403), res.text
    finally:
        try:
            client.delete(f'/platform/endpoint/POST/{name}/{ver}/grpc')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{name}/{ver}')
        except Exception:
            pass
