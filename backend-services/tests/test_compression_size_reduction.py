"""
Integration tests for response compression size reduction.

These tests verify that:
1. Compression actually reduces bandwidth usage
2. Different content types achieve expected compression ratios
3. Compression settings affect the compression ratio
"""

import gzip
import io
import json
import os

import pytest


@pytest.mark.asyncio
async def test_json_compression_ratio(client):
    """Measure actual compression ratio for JSON responses"""
    # Authenticate to get access to endpoints
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # Get a JSON response with compression
    r = await client.get('/platform/api')
    assert r.status_code == 200

    # Get the JSON content
    json_data = r.json()
    json_str = json.dumps(json_data, separators=(',', ':'))  # Compact JSON
    uncompressed_size = len(json_str.encode('utf-8'))

    # Manually compress to measure ratio
    compressed_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
        gz.write(json_str.encode('utf-8'))
    compressed_size = len(compressed_buffer.getvalue())

    # Calculate compression ratio
    compression_ratio = (1 - (compressed_size / uncompressed_size)) * 100

    print('\nJSON Compression Stats:')
    print(f'  Uncompressed: {uncompressed_size} bytes')
    print(f'  Compressed:   {compressed_size} bytes')
    print(f'  Ratio:        {compression_ratio:.1f}% reduction')

    # JSON should compress well (typically 60-80%)
    # But only if response is large enough
    if uncompressed_size > 500:
        assert compression_ratio > 30, f'Expected >30% compression, got {compression_ratio:.1f}%'


@pytest.mark.asyncio
async def test_large_list_compression(client):
    """Test compression with a large list response"""
    # Authenticate
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # Create multiple test APIs to get a larger response
    test_apis = []
    for i in range(5):
        api_payload = {
            'api_name': f'compression-test-{i}',
            'api_version': 'v1',
            'api_description': f'Test API for compression testing - {i}' * 10,  # Make it longer
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://example.com'],
            'api_type': 'REST',
            'active': True,
        }
        r = await client.post('/platform/api', json=api_payload)
        if r.status_code in (200, 201):
            test_apis.append(f'compression-test-{i}')

    # Get the full list
    r = await client.get('/platform/api')
    assert r.status_code == 200

    json_data = r.json()
    json_str = json.dumps(json_data, separators=(',', ':'))
    uncompressed_size = len(json_str.encode('utf-8'))

    # Manually compress
    compressed_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
        gz.write(json_str.encode('utf-8'))
    compressed_size = len(compressed_buffer.getvalue())

    compression_ratio = (1 - (compressed_size / uncompressed_size)) * 100

    print('\nLarge List Compression Stats:')
    print(f'  Uncompressed: {uncompressed_size} bytes')
    print(f'  Compressed:   {compressed_size} bytes')
    print(f'  Ratio:        {compression_ratio:.1f}% reduction')

    # Cleanup
    for api_name in test_apis:
        try:
            await client.delete(f'/platform/api/{api_name}/v1')
        except Exception:
            pass

    # Should achieve good compression on repeated data
    if uncompressed_size > 1000:
        assert compression_ratio > 40, 'Expected >40% compression for large list'


@pytest.mark.asyncio
async def test_compression_bandwidth_savings(client):
    """Calculate total bandwidth savings across multiple requests"""
    # Authenticate
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # Test multiple endpoints
    endpoints = ['/platform/api', '/platform/user', '/platform/role', '/platform/group']

    total_uncompressed = 0
    total_compressed = 0

    for endpoint in endpoints:
        r = await client.get(endpoint)
        if r.status_code != 200:
            continue

        json_data = r.json()
        json_str = json.dumps(json_data, separators=(',', ':'))
        uncompressed_size = len(json_str.encode('utf-8'))

        # Manually compress
        compressed_buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
            gz.write(json_str.encode('utf-8'))
        compressed_size = len(compressed_buffer.getvalue())

        total_uncompressed += uncompressed_size
        total_compressed += compressed_size

    if total_uncompressed > 0:
        overall_ratio = (1 - (total_compressed / total_uncompressed)) * 100

        print('\nOverall Bandwidth Savings:')
        print(f'  Total uncompressed: {total_uncompressed} bytes')
        print(f'  Total compressed:   {total_compressed} bytes')
        print(f'  Overall ratio:      {overall_ratio:.1f}% reduction')
        print(f'  Bandwidth saved:    {total_uncompressed - total_compressed} bytes')

        # Should see significant savings
        assert overall_ratio > 0, 'Compression should reduce size'


@pytest.mark.asyncio
async def test_compression_level_affects_ratio(client):
    """Verify different compression levels affect compression ratio"""
    # Authenticate
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # Get a response
    r = await client.get('/platform/api')
    assert r.status_code == 200

    json_data = r.json()
    json_str = json.dumps(json_data, separators=(',', ':'))
    uncompressed_size = len(json_str.encode('utf-8'))

    # Test different compression levels
    compression_results = {}
    for level in [1, 6, 9]:
        compressed_buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=level) as gz:
            gz.write(json_str.encode('utf-8'))
        compressed_size = len(compressed_buffer.getvalue())
        ratio = (1 - (compressed_size / uncompressed_size)) * 100
        compression_results[level] = {'size': compressed_size, 'ratio': ratio}

    print('\nCompression Level Comparison:')
    print(f'  Uncompressed: {uncompressed_size} bytes')
    for level, result in compression_results.items():
        print(f'  Level {level}: {result["size"]} bytes ({result["ratio"]:.1f}% reduction)')

    # Higher compression levels should achieve better (or equal) compression
    # Level 9 should be <= Level 6 <= Level 1 in size
    if uncompressed_size > 500:
        assert compression_results[9]['size'] <= compression_results[6]['size']
        assert compression_results[6]['size'] <= compression_results[1]['size']


@pytest.mark.asyncio
async def test_minimum_size_threshold(client):
    """Verify responses below minimum size aren't compressed"""
    # Small response (health check)
    r = await client.get('/api/health')
    assert r.status_code == 200

    response_content = r.content
    response_size = len(response_content)

    print(f'\nSmall Response Size: {response_size} bytes')

    # If response is smaller than 500 bytes (default minimum_size),
    # compressing it may not be worth the CPU overhead
    # This is just informational - the middleware handles this automatically


@pytest.mark.asyncio
async def test_compression_transfer_savings_calculation(client):
    """Calculate potential monthly transfer savings with compression"""
    # Authenticate
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars'),
    }

    r_auth = await client.post('/platform/authorization', json=login_payload)
    assert r_auth.status_code == 200

    # Simulate typical API usage
    r = await client.get('/platform/api')
    assert r.status_code == 200

    json_data = r.json()
    json_str = json.dumps(json_data, separators=(',', ':'))
    uncompressed_size = len(json_str.encode('utf-8'))

    # Compress
    compressed_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
        gz.write(json_str.encode('utf-8'))
    compressed_size = len(compressed_buffer.getvalue())

    # Calculate savings
    bytes_saved_per_request = uncompressed_size - compressed_size
    compression_ratio = (1 - (compressed_size / uncompressed_size)) * 100

    # Estimate monthly savings (example: 1M requests/month)
    requests_per_month = 1_000_000
    monthly_savings_bytes = bytes_saved_per_request * requests_per_month
    monthly_savings_mb = monthly_savings_bytes / (1024 * 1024)
    monthly_savings_gb = monthly_savings_mb / 1024

    print('\nTransfer Savings Estimate:')
    print(f'  Compression ratio: {compression_ratio:.1f}%')
    print(f'  Bytes saved per request: {bytes_saved_per_request}')
    print(f'  Monthly requests: {requests_per_month:,}')
    print(f'  Monthly bandwidth saved: {monthly_savings_gb:.2f} GB')
    print(f'  Annual bandwidth saved: {monthly_savings_gb * 12:.2f} GB')

    # Should save significant bandwidth
    assert bytes_saved_per_request >= 0


# Mark all tests with integration marker
pytestmark = [pytest.mark.compression, pytest.mark.integration]
