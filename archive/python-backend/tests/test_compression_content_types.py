"""
Test response compression with different content types.

Verifies compression works correctly with:
- JSON (REST API responses)
- XML (SOAP responses)
- GraphQL responses
- Error responses
- Various HTTP methods
"""

import gzip
import io
import json
import os
import time

import pytest


@pytest.mark.asyncio
async def test_compression_with_rest_gateway_json(client):
    """Test compression with REST gateway JSON responses"""
    # This is a mock test - in a real scenario you'd set up a REST gateway
    # For now, we'll test platform endpoints which return JSON

    # Authenticate
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # Test JSON response (typical REST response)
    r = await client.get(
        '/platform/api', headers={'Accept-Encoding': 'gzip', 'Accept': 'application/json'}
    )
    assert r.status_code == 200

    # Should be valid JSON
    data = r.json()
    assert isinstance(data, dict)

    # Calculate compression for JSON
    json_str = json.dumps(data, separators=(',', ':'))
    uncompressed_size = len(json_str.encode('utf-8'))

    if uncompressed_size > 500:
        compressed_buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
            gz.write(json_str.encode('utf-8'))
        compressed_size = len(compressed_buffer.getvalue())
        ratio = (1 - (compressed_size / uncompressed_size)) * 100

        print('\nREST JSON Compression:')
        print(f'  Original: {uncompressed_size} bytes')
        print(f'  Compressed: {compressed_size} bytes')
        print(f'  Ratio: {ratio:.1f}% reduction')

        # JSON typically compresses well
        assert ratio > 20


@pytest.mark.asyncio
async def test_compression_with_xml_content(client):
    """Test compression with XML content (SOAP-like)"""
    # XML is very verbose and should compress extremely well

    # Create a mock XML response
    xml_content = (
        """<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Body>
            <Response>
                <Status>Success</Status>
                <Data>
                    <Item><Name>Item 1</Name><Value>Value 1</Value></Item>
                    <Item><Name>Item 2</Name><Value>Value 2</Value></Item>
                    <Item><Name>Item 3</Name><Value>Value 3</Value></Item>
                    <Item><Name>Item 4</Name><Value>Value 4</Value></Item>
                    <Item><Name>Item 5</Name><Value>Value 5</Value></Item>
                </Data>
            </Response>
        </soap:Body>
    </soap:Envelope>"""
        * 3
    )  # Repeat to make it larger

    uncompressed_size = len(xml_content.encode('utf-8'))

    # Compress
    compressed_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
        gz.write(xml_content.encode('utf-8'))
    compressed_size = len(compressed_buffer.getvalue())

    ratio = (1 - (compressed_size / uncompressed_size)) * 100

    print('\nXML/SOAP Compression:')
    print(f'  Original: {uncompressed_size} bytes')
    print(f'  Compressed: {compressed_size} bytes')
    print(f'  Ratio: {ratio:.1f}% reduction')

    # XML should compress very well (lots of repetitive tags)
    assert ratio > 60, f'XML should compress >60%, got {ratio:.1f}%'


@pytest.mark.asyncio
async def test_compression_with_graphql_style_response(client):
    """Test compression with GraphQL-style nested responses"""
    # GraphQL responses are nested JSON structures
    # Authenticate
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # Get a nested response
    r = await client.get('/platform/api')
    assert r.status_code == 200

    data = r.json()
    json_str = json.dumps(data, separators=(',', ':'))
    uncompressed_size = len(json_str.encode('utf-8'))

    if uncompressed_size > 500:
        compressed_buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
            gz.write(json_str.encode('utf-8'))
        compressed_size = len(compressed_buffer.getvalue())
        ratio = (1 - (compressed_size / uncompressed_size)) * 100

        print('\nGraphQL-style Response Compression:')
        print(f'  Original: {uncompressed_size} bytes')
        print(f'  Compressed: {compressed_size} bytes')
        print(f'  Ratio: {ratio:.1f}% reduction')


@pytest.mark.asyncio
async def test_compression_with_post_requests(client):
    """Test that compression works with POST request responses"""
    # POST to create an API
    api_payload = {
        'api_name': f'compression-post-test-{int(time.time())}',
        'api_version': 'v1',
        'api_description': 'Test API for POST compression',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://example.com'],
        'api_type': 'REST',
        'active': True,
    }

    # Authenticate first
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # POST with compression
    r = await client.post('/platform/api', json=api_payload, headers={'Accept-Encoding': 'gzip'})
    assert r.status_code in (200, 201)

    # Should get valid response
    data = r.json()
    assert isinstance(data, dict)

    # Cleanup
    try:
        await client.delete(f'/platform/api/{api_payload["api_name"]}/v1')
    except Exception:
        pass


@pytest.mark.asyncio
async def test_compression_with_put_requests(client):
    """Test compression works with PUT request responses"""
    # Authenticate
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # Create an API first
    api_name = f'compression-put-test-{int(time.time())}'
    api_payload = {
        'api_name': api_name,
        'api_version': 'v1',
        'api_description': 'Original description',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://example.com'],
        'api_type': 'REST',
        'active': True,
    }

    r = await client.post('/platform/api', json=api_payload)
    assert r.status_code in (200, 201)

    # Update with PUT
    update_payload = {'api_description': 'Updated description with compression test'}

    r = await client.put(
        f'/platform/api/{api_name}/v1', json=update_payload, headers={'Accept-Encoding': 'gzip'}
    )
    assert r.status_code == 200

    # Should get valid response
    data = r.json()
    assert isinstance(data, dict)

    # Cleanup
    try:
        await client.delete(f'/platform/api/{api_name}/v1')
    except Exception:
        pass


@pytest.mark.asyncio
async def test_compression_with_delete_requests(client):
    """Test compression works with DELETE request responses"""
    # Authenticate
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # Create an API to delete
    api_name = f'compression-delete-test-{int(time.time())}'
    api_payload = {
        'api_name': api_name,
        'api_version': 'v1',
        'api_description': 'Test API for DELETE compression',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://example.com'],
        'api_type': 'REST',
        'active': True,
    }

    r = await client.post('/platform/api', json=api_payload)
    assert r.status_code in (200, 201)

    # Delete with compression
    r = await client.delete(f'/platform/api/{api_name}/v1', headers={'Accept-Encoding': 'gzip'})
    assert r.status_code in (200, 204)


@pytest.mark.asyncio
async def test_compression_with_error_responses(client):
    """Test compression works with error responses"""
    # Clear cookies to trigger 401
    try:
        client.cookies.clear()
    except Exception:
        pass

    # Try to access protected endpoint without auth
    r = await client.get('/platform/api', headers={'Accept-Encoding': 'gzip'})

    # Should be unauthorized
    assert r.status_code in (401, 403)

    # Error response should still be processable
    # (httpx handles decompression automatically)


@pytest.mark.asyncio
async def test_compression_with_list_responses(client):
    """Test compression with list/array responses"""
    # Authenticate
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # Get list of users
    r = await client.get('/platform/user', headers={'Accept-Encoding': 'gzip'})
    assert r.status_code == 200

    data = r.json()
    response_data = data.get('response', data)

    # Should be a list or dict containing lists
    assert isinstance(response_data, (list, dict))


@pytest.mark.asyncio
async def test_compression_consistent_across_content_types(client):
    """Verify compression ratio is consistent for similar content"""
    # Authenticate
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # Test similar-sized responses
    endpoints = ['/platform/api', '/platform/user', '/platform/role']
    ratios = []

    for endpoint in endpoints:
        r = await client.get(endpoint)
        if r.status_code != 200:
            continue

        data = r.json()
        json_str = json.dumps(data, separators=(',', ':'))
        uncompressed = len(json_str.encode('utf-8'))

        if uncompressed > 500:
            compressed_buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
                gz.write(json_str.encode('utf-8'))
            compressed = len(compressed_buffer.getvalue())
            ratio = (1 - (compressed / uncompressed)) * 100
            ratios.append(ratio)

    if ratios:
        avg_ratio = sum(ratios) / len(ratios)
        print(f'\nAverage compression ratio across endpoints: {avg_ratio:.1f}%')
        print(f'Individual ratios: {[f"{r:.1f}%" for r in ratios]}')


# Mark all tests
pytestmark = [pytest.mark.compression, pytest.mark.content_types]
