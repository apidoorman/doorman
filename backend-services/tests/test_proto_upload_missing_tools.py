import pytest


@pytest.mark.skip(reason="Test requires complex import mocking that causes test suite to hang. Proto upload error handling is covered by other proto tests.")
@pytest.mark.asyncio
async def test_proto_upload_succeeds_or_fails_gracefully(authed_client):
    """Test proto upload with real gateway logic - succeeds if grpcio-tools installed, fails gracefully if not."""
    api_name, api_version = 'xproto', 'v1'
    
    # Create API for proto upload
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'gRPC test',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['grpc://localhost:9'],
            'api_type': 'gRPC',
            'api_allowed_retry_count': 0,
        },
    )

    proto_content = b"syntax = \"proto3\"; package xproto_v1; service S { rpc M (A) returns (B) {} } message A { string n = 1; } message B { string m = 1; }"
    files = {'proto_file': ('svc.proto', proto_content, 'application/octet-stream')}
    r = await authed_client.post(f'/platform/proto/{api_name}/{api_version}', files=files)
    
    # Either succeeds (if grpcio-tools is installed) or fails with clear error message
    if r.status_code == 200:
        # Proto uploaded successfully
        body = r.json()
        assert 'message' in body or 'response' in body
    else:
        # Should fail gracefully with clear error message if tools missing
        assert r.status_code in (400, 500)
        body = r.json().get('response', r.json())
        msg = body.get('error_message') or body.get('message') or ''
        # Verify error message is informative (not a generic crash)
        assert len(msg) > 0, 'Error message should not be empty'
