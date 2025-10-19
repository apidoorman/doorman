"""
Real-world compression benchmarks for AWS Lightsail capacity planning.

This test creates realistic API payloads and measures:
1. Actual compression ratios
2. CPU overhead of compression
3. Memory usage impact
4. Realistic throughput estimates
"""

import pytest
import gzip
import json
import io
import os
import time
import asyncio


@pytest.mark.asyncio
async def test_realistic_rest_api_response_compression(client):
    """Test compression with realistic REST API response"""
    # Authenticate
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars')
    }

    r = await client.post('/platform/authorization', json=login_payload)
    assert r.status_code == 200

    # Create a realistic API config (typical size)
    api_name = f'benchmark-{int(time.time())}'
    api_payload = {
        'api_name': api_name,
        'api_version': 'v1',
        'api_description': 'A realistic API for e-commerce product catalog with search, filtering, and recommendations',
        'api_allowed_roles': ['admin', 'user', 'guest'],
        'api_allowed_groups': ['ALL', 'DEVELOPERS', 'CUSTOMERS'],
        'api_servers': [
            'https://api-primary.example.com',
            'https://api-secondary.example.com',
            'https://api-backup.example.com'
        ],
        'api_type': 'REST',
        'api_allowed_retry_count': 3,
        'active': True,
        'api_cors_allow_origins': ['https://app.example.com', 'https://www.example.com'],
        'api_credits_enabled': False,
        'api_rate_limit_enabled': True,
        'api_rate_limit_requests': 1000,
        'api_rate_limit_window': 60
    }

    r = await client.post('/platform/api', json=api_payload)
    assert r.status_code in (200, 201)

    # Measure the response
    json_str = json.dumps(r.json(), separators=(',', ':'))
    uncompressed_size = len(json_str.encode('utf-8'))

    # Compress at different levels
    results = {}
    for level in [1, 6, 9]:
        start_time = time.perf_counter()
        compressed_buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=level) as gz:
            gz.write(json_str.encode('utf-8'))
        compression_time = (time.perf_counter() - start_time) * 1000  # ms

        compressed_size = len(compressed_buffer.getvalue())
        ratio = (1 - (compressed_size / uncompressed_size)) * 100

        results[level] = {
            'compressed_size': compressed_size,
            'ratio': ratio,
            'time_ms': compression_time
        }

    print(f"\n{'='*70}")
    print(f"REALISTIC REST API RESPONSE COMPRESSION BENCHMARK")
    print(f"{'='*70}")
    print(f"Uncompressed size: {uncompressed_size:,} bytes")
    print(f"\nCompression Results:")
    for level, result in results.items():
        print(f"  Level {level}: {result['compressed_size']:,} bytes "
              f"({result['ratio']:.1f}% reduction) "
              f"in {result['time_ms']:.3f}ms")

    # Cleanup
    await client.delete(f'/platform/api/{api_name}/v1')

    # Assertions
    assert results[6]['ratio'] > 0, "Should achieve some compression"


@pytest.mark.asyncio
async def test_typical_api_gateway_request_flow(client):
    """Simulate typical API gateway request and measure end-to-end size"""
    # Login
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars')
    }

    # Measure login response
    r = await client.post('/platform/authorization', json=login_payload)
    assert r.status_code == 200

    login_json = json.dumps(r.json(), separators=(',', ':'))
    login_uncompressed = len(login_json.encode('utf-8'))

    compressed_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
        gz.write(login_json.encode('utf-8'))
    login_compressed = len(compressed_buffer.getvalue())

    # Measure health check
    r = await client.get('/api/health')
    assert r.status_code == 200

    health_json = json.dumps(r.json(), separators=(',', ':'))
    health_uncompressed = len(health_json.encode('utf-8'))

    compressed_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
        gz.write(health_json.encode('utf-8'))
    health_compressed = len(compressed_buffer.getvalue())

    print(f"\n{'='*70}")
    print(f"TYPICAL API GATEWAY REQUEST FLOW")
    print(f"{'='*70}")
    print(f"\nLogin (POST /platform/authorization):")
    print(f"  Uncompressed: {login_uncompressed:,} bytes")
    print(f"  Compressed:   {login_compressed:,} bytes")
    print(f"  Ratio:        {(1 - login_compressed/login_uncompressed)*100:.1f}% reduction")
    print(f"\nHealth Check (GET /api/health):")
    print(f"  Uncompressed: {health_uncompressed:,} bytes")
    print(f"  Compressed:   {health_compressed:,} bytes")
    if health_uncompressed > 500:
        print(f"  Ratio:        {(1 - health_compressed/health_uncompressed)*100:.1f}% reduction")
    else:
        print(f"  Note:         Below 500 byte minimum - not compressed in production")


@pytest.mark.asyncio
async def test_large_list_response_compression(client):
    """Test compression on large list responses (multiple APIs)"""
    login_payload = {
        'email': os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.getenv('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars')
    }

    r = await client.post('/platform/authorization', json=login_payload)
    assert r.status_code == 200

    # Create multiple APIs to get a larger list response
    api_names = []
    for i in range(10):
        api_name = f'benchmark-large-{i}-{int(time.time())}'
        api_payload = {
            'api_name': api_name,
            'api_version': 'v1',
            'api_description': f'Test API number {i} for compression benchmarking with realistic metadata and configuration settings',
            'api_allowed_roles': ['admin', 'developer', 'user'],
            'api_allowed_groups': ['ALL', 'TEAM_A', 'TEAM_B'],
            'api_servers': [
                f'https://api-{i}-primary.example.com',
                f'https://api-{i}-secondary.example.com'
            ],
            'api_type': 'REST',
            'api_allowed_retry_count': 3,
            'active': True
        }
        r = await client.post('/platform/api', json=api_payload)
        if r.status_code in (200, 201):
            api_names.append(api_name)

    # Small delay to ensure all APIs are created
    await asyncio.sleep(0.1)

    # Now measure - but we can't list all APIs, so let's measure the create response
    # which is representative of a typical API response
    if api_names:
        # Get the last created API details as a proxy for list size
        api_payload = {
            'api_name': f'final-benchmark-{int(time.time())}',
            'api_version': 'v1',
            'api_description': 'Final benchmark API with extensive metadata for realistic compression testing',
            'api_allowed_roles': ['admin', 'developer', 'user', 'guest', 'moderator'],
            'api_allowed_groups': ['ALL', 'PREMIUM', 'ENTERPRISE', 'FREE_TIER'],
            'api_servers': [
                'https://api-prod-1.example.com',
                'https://api-prod-2.example.com',
                'https://api-prod-3.example.com',
                'https://api-dr.example.com'
            ],
            'api_type': 'REST',
            'active': True
        }
        r = await client.post('/platform/api', json=api_payload)

        if r.status_code in (200, 201):
            json_str = json.dumps(r.json(), separators=(',', ':'))
            uncompressed = len(json_str.encode('utf-8'))

            compressed_buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
                gz.write(json_str.encode('utf-8'))
            compressed = len(compressed_buffer.getvalue())

            ratio = (1 - compressed/uncompressed) * 100

            print(f"\n{'='*70}")
            print(f"LARGE API CONFIGURATION RESPONSE")
            print(f"{'='*70}")
            print(f"Uncompressed: {uncompressed:,} bytes")
            print(f"Compressed:   {compressed:,} bytes")
            print(f"Ratio:        {ratio:.1f}% reduction")

            api_names.append(api_payload['api_name'])

    # Cleanup
    for api_name in api_names:
        try:
            await client.delete(f'/platform/api/{api_name}/v1')
        except Exception:
            pass


@pytest.mark.asyncio
async def test_worst_case_already_compressed_data(client):
    """Test compression on data that doesn't compress well"""
    # Random binary-like data doesn't compress well
    # But in API responses, this is rare - most are text-based JSON

    # Simulate a JWT token (random-looking base64)
    import base64
    random_bytes = os.urandom(256)
    token_like = base64.b64encode(random_bytes).decode('utf-8')

    response_data = {
        'status': 'success',
        'token': token_like,
        'expires_in': 3600
    }

    json_str = json.dumps(response_data, separators=(',', ':'))
    uncompressed = len(json_str.encode('utf-8'))

    compressed_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=6) as gz:
        gz.write(json_str.encode('utf-8'))
    compressed = len(compressed_buffer.getvalue())

    ratio = (1 - compressed/uncompressed) * 100

    print(f"\n{'='*70}")
    print(f"WORST CASE: RANDOM DATA (JWT-like tokens)")
    print(f"{'='*70}")
    print(f"Uncompressed: {uncompressed:,} bytes")
    print(f"Compressed:   {compressed:,} bytes")
    print(f"Ratio:        {ratio:.1f}% reduction")
    print(f"\nNote: Even random data achieves some compression due to JSON structure")


@pytest.mark.asyncio
async def test_compression_cpu_overhead_estimate(client):
    """Estimate CPU overhead of compression at different levels"""
    # Create a realistic 10KB JSON response
    large_response = {
        'status': 'success',
        'data': [
            {
                'id': i,
                'name': f'Product {i}',
                'description': 'A detailed product description with lots of text to make this realistic',
                'price': 99.99 + i,
                'category': 'Electronics',
                'tags': ['popular', 'featured', 'new', 'sale'],
                'metadata': {
                    'created_at': '2025-01-15T12:00:00Z',
                    'updated_at': '2025-01-18T15:30:00Z',
                    'views': 1234,
                    'likes': 567
                }
            }
            for i in range(50)  # 50 products
        ],
        'pagination': {
            'page': 1,
            'per_page': 50,
            'total': 500,
            'total_pages': 10
        }
    }

    json_str = json.dumps(large_response, separators=(',', ':'))
    data = json_str.encode('utf-8')

    print(f"\n{'='*70}")
    print(f"COMPRESSION CPU OVERHEAD BENCHMARK")
    print(f"{'='*70}")
    print(f"Test payload: {len(data):,} bytes")
    print(f"\nCompression performance:")

    for level in [1, 4, 6, 9]:
        # Warm-up
        for _ in range(5):
            compressed_buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=level) as gz:
                gz.write(data)

        # Actual measurement (100 compressions)
        iterations = 100
        start = time.perf_counter()
        total_compressed = 0
        for _ in range(iterations):
            compressed_buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=level) as gz:
                gz.write(data)
            total_compressed += len(compressed_buffer.getvalue())

        elapsed = time.perf_counter() - start
        avg_time_ms = (elapsed / iterations) * 1000
        avg_size = total_compressed // iterations
        ratio = (1 - avg_size/len(data)) * 100

        # Estimate RPS capacity (assuming 50ms total request time)
        # Compression adds overhead, reducing available CPU time
        base_request_time = 50  # ms
        with_compression_time = base_request_time + avg_time_ms
        rps_impact = (avg_time_ms / with_compression_time) * 100

        print(f"\n  Level {level}:")
        print(f"    Time:            {avg_time_ms:.3f} ms/request")
        print(f"    Compressed size: {avg_size:,} bytes ({ratio:.1f}% reduction)")
        print(f"    CPU overhead:    {rps_impact:.1f}% of total request time")
        print(f"    Throughput:      ~{1000/avg_time_ms:.0f} compressions/sec (single core)")


pytestmark = [pytest.mark.benchmark]
