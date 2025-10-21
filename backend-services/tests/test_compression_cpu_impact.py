"""
Deep dive into GZip CPU impact for production capacity planning.

Tests realistic scenarios:
1. CPU time per request at different compression levels
2. Impact on concurrent request handling
3. Throughput reduction due to compression overhead
4. Memory allocation patterns during compression
"""

import pytest
import gzip
import json
import io
import time
import os


def create_realistic_response(size_category):
    """Create realistic API responses of different sizes"""
    if size_category == 'small':
        # Typical small response (< 500 bytes, won't compress)
        return {
            'status': 'success',
            'data': {'id': 123, 'name': 'John Doe'},
            'timestamp': '2025-01-18T10:30:00Z'
        }
    elif size_category == 'medium':
        # Typical REST API response (1-10 KB)
        return {
            'status': 'success',
            'data': [
                {
                    'id': i,
                    'name': f'User {i}',
                    'email': f'user{i}@example.com',
                    'role': 'developer',
                    'created_at': '2025-01-15T10:00:00Z'
                }
                for i in range(50)
            ],
            'pagination': {'page': 1, 'total': 500}
        }
    elif size_category == 'large':
        # Large API list (10-50 KB)
        return {
            'status': 'success',
            'data': [
                {
                    'id': i,
                    'name': f'Product {i}',
                    'description': 'A detailed product description with lots of metadata and information',
                    'price': 99.99 + i,
                    'category': 'Electronics',
                    'tags': ['popular', 'featured', 'new', 'sale'],
                    'metadata': {
                        'created_at': '2025-01-15T12:00:00Z',
                        'updated_at': '2025-01-18T15:30:00Z',
                        'views': 1234,
                        'likes': 567,
                        'reviews_count': 42
                    }
                }
                for i in range(200)
            ],
            'pagination': {'page': 1, 'per_page': 200, 'total': 2000}
        }
    else:  # very_large
        # Very large response (50-100 KB)
        return {
            'status': 'success',
            'data': [
                {
                    'id': i,
                    'name': f'Item {i}',
                    'description': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. ' * 5,
                    'attributes': {f'attr_{j}': f'value_{j}' for j in range(20)}
                }
                for i in range(500)
            ]
        }


def benchmark_compression(data, level, iterations=1000):
    """Benchmark compression performance"""
    json_str = json.dumps(data, separators=(',', ':'))
    json_bytes = json_str.encode('utf-8')

    # Warm-up
    for _ in range(100):
        compressed_buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=level) as gz:
            gz.write(json_bytes)

    # Actual benchmark
    start = time.perf_counter()
    total_compressed_size = 0
    for _ in range(iterations):
        compressed_buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed_buffer, mode='wb', compresslevel=level) as gz:
            gz.write(json_bytes)
        total_compressed_size += len(compressed_buffer.getvalue())

    elapsed = time.perf_counter() - start
    avg_time_ms = (elapsed / iterations) * 1000
    avg_compressed_size = total_compressed_size // iterations
    compression_ratio = (1 - avg_compressed_size / len(json_bytes)) * 100

    return {
        'uncompressed_size': len(json_bytes),
        'compressed_size': avg_compressed_size,
        'compression_ratio': compression_ratio,
        'avg_time_ms': avg_time_ms,
        'throughput_per_core': 1000 / avg_time_ms if avg_time_ms > 0 else 0
    }


@pytest.mark.asyncio
async def test_cpu_impact_by_response_size():
    """Measure CPU impact across different response sizes"""

    print(f"\n{'='*80}")
    print(f"CPU IMPACT ANALYSIS - BY RESPONSE SIZE")
    print(f"{'='*80}\n")

    sizes = ['small', 'medium', 'large', 'very_large']
    levels = [1, 4, 6, 9]

    for size in sizes:
        data = create_realistic_response(size)
        print(f"\n{size.upper()} Response:")
        print(f"{'-'*80}")

        for level in levels:
            result = benchmark_compression(data, level, iterations=500)

            print(f"\n  Level {level}:")
            print(f"    Size:              {result['uncompressed_size']:,} → {result['compressed_size']:,} bytes")
            print(f"    Compression ratio: {result['compression_ratio']:.1f}%")
            print(f"    CPU time:          {result['avg_time_ms']:.3f} ms/request")
            print(f"    Max throughput:    {result['throughput_per_core']:.0f} req/sec (single core)")


@pytest.mark.asyncio
async def test_cpu_overhead_on_total_request_time():
    """Calculate compression overhead as % of total request time"""

    print(f"\n{'='*80}")
    print(f"COMPRESSION OVERHEAD AS % OF TOTAL REQUEST TIME")
    print(f"{'='*80}\n")

    # Realistic request times for different operations
    base_times = {
        'health_check': 2,      # Very fast
        'auth': 50,             # JWT generation/verification
        'simple_query': 30,     # Database lookup
        'list_query': 80,       # Multiple DB queries
        'complex_query': 150,   # Joins, aggregations
        'upstream_proxy': 200,  # Proxying to upstream API
    }

    data = create_realistic_response('medium')

    print(f"Medium response size: {len(json.dumps(data, separators=(',', ':')).encode('utf-8')):,} bytes\n")

    for operation, base_time_ms in base_times.items():
        print(f"\n{operation.replace('_', ' ').title()} (base: {base_time_ms}ms):")
        print(f"{'-'*80}")

        for level in [1, 4, 6, 9]:
            result = benchmark_compression(data, level, iterations=500)
            compression_time = result['avg_time_ms']
            total_time = base_time_ms + compression_time
            overhead_pct = (compression_time / total_time) * 100
            throughput_reduction = (compression_time / base_time_ms) * 100

            print(f"  Level {level}: {compression_time:.3f}ms → "
                  f"total {total_time:.1f}ms "
                  f"({overhead_pct:.1f}% overhead, "
                  f"{throughput_reduction:.1f}% slower)")


@pytest.mark.asyncio
async def test_realistic_production_scenario():
    """Simulate production workload with compression"""

    print(f"\n{'='*80}")
    print(f"REALISTIC PRODUCTION SCENARIO")
    print(f"{'='*80}\n")

    # Realistic traffic mix
    workload = [
        ('small', 0.30, 10),      # 30% small responses (health checks, simple GETs)
        ('medium', 0.50, 40),     # 50% medium responses (typical API calls)
        ('large', 0.15, 100),     # 15% large responses (list endpoints)
        ('very_large', 0.05, 200) # 5% very large (export/reports)
    ]

    print("Traffic Mix:")
    for size, percentage, base_time in workload:
        print(f"  {size:12s}: {percentage*100:>5.1f}% (base processing: {base_time}ms)")

    print(f"\n{'='*80}")

    for level in [1, 4, 6, 9]:
        print(f"\nCompression Level {level}:")
        print(f"{'-'*80}")

        total_time_without_compression = 0
        total_time_with_compression = 0
        total_bytes_saved = 0

        for size, percentage, base_time in workload:
            data = create_realistic_response(size)
            result = benchmark_compression(data, level, iterations=200)

            # Apply minimum size threshold (500 bytes)
            if result['uncompressed_size'] < 500:
                compression_time = 0
                bytes_saved = 0
            else:
                compression_time = result['avg_time_ms']
                bytes_saved = result['uncompressed_size'] - result['compressed_size']

            weighted_base_time = base_time * percentage
            weighted_compression_time = compression_time * percentage
            weighted_bytes_saved = bytes_saved * percentage

            total_time_without_compression += weighted_base_time
            total_time_with_compression += weighted_base_time + weighted_compression_time
            total_bytes_saved += weighted_bytes_saved

        overhead_pct = ((total_time_with_compression - total_time_without_compression) /
                       total_time_without_compression) * 100

        # Calculate max RPS reduction
        rps_without = 1000 / total_time_without_compression
        rps_with = 1000 / total_time_with_compression
        rps_reduction_pct = ((rps_without - rps_with) / rps_without) * 100

        print(f"  Avg request time:  {total_time_without_compression:.1f}ms → {total_time_with_compression:.1f}ms")
        print(f"  CPU overhead:      {overhead_pct:.1f}%")
        print(f"  Max RPS (1 core):  {rps_without:.1f} → {rps_with:.1f} ({rps_reduction_pct:.1f}% reduction)")
        print(f"  Avg bytes saved:   {total_bytes_saved:.0f} bytes/request")


@pytest.mark.asyncio
async def test_two_vcpu_capacity_analysis():
    """Calculate realistic capacity for 2 vCPU instance"""

    print(f"\n{'='*80}")
    print(f"2 vCPU AWS LIGHTSAIL CAPACITY ANALYSIS")
    print(f"{'='*80}\n")

    # Workload parameters
    workload = [
        ('small', 0.30, 10, False),    # Not compressed
        ('medium', 0.50, 40, True),    # Compressed
        ('large', 0.15, 100, True),    # Compressed
        ('very_large', 0.05, 200, True)  # Compressed
    ]

    print("AWS Lightsail 1GB RAM, 2 vCPUs")
    print("Single worker mode (MEM_OR_EXTERNAL=MEM)")
    print(f"\n{'='*80}\n")

    for level in [1, 4, 6, 9]:
        print(f"Compression Level {level}:")
        print(f"{'-'*80}")

        total_cpu_time = 0
        total_bytes_uncompressed = 0
        total_bytes_compressed = 0

        for size, percentage, base_time, should_compress in workload:
            data = create_realistic_response(size)
            json_str = json.dumps(data, separators=(',', ':'))
            uncompressed_size = len(json_str.encode('utf-8'))

            if should_compress and uncompressed_size >= 500:
                result = benchmark_compression(data, level, iterations=200)
                compression_time = result['avg_time_ms']
                compressed_size = result['compressed_size']
            else:
                compression_time = 0
                compressed_size = uncompressed_size

            weighted_cpu_time = (base_time + compression_time) * percentage
            weighted_uncompressed = uncompressed_size * percentage
            weighted_compressed = compressed_size * percentage

            total_cpu_time += weighted_cpu_time
            total_bytes_uncompressed += weighted_uncompressed
            total_bytes_compressed += weighted_compressed

        # Calculate capacity
        max_rps_single_core = 1000 / total_cpu_time
        max_rps_two_cores = max_rps_single_core * 1.8  # Not perfect 2x due to GIL and overhead

        # Account for async I/O wait time (requests waiting for upstream)
        # In practice, async allows ~1.5-2x more throughput than pure CPU calculation
        realistic_rps = max_rps_two_cores * 1.3  # Async bonus

        # Transfer limits
        avg_transfer_per_request = (total_bytes_uncompressed + total_bytes_compressed) / 2  # In + Out
        monthly_requests_at_1tb = (1000 * 1024 * 1024 * 1024) / avg_transfer_per_request
        monthly_rps_limit = monthly_requests_at_1tb / (30 * 24 * 60 * 60)

        compression_ratio = (1 - total_bytes_compressed / total_bytes_uncompressed) * 100

        print(f"  CPU time per request:       {total_cpu_time:.1f} ms")
        print(f"  Max RPS (CPU-limited):      {realistic_rps:.1f} RPS")
        print(f"  Avg response size:          {total_bytes_uncompressed:.0f} → {total_bytes_compressed:.0f} bytes")
        print(f"  Compression ratio:          {compression_ratio:.1f}%")
        print(f"  Transfer per request:       {avg_transfer_per_request:.0f} bytes (req+resp)")
        print(f"  Max RPS (transfer-limited): {monthly_rps_limit:.1f} RPS")
        print(f"  Monthly capacity (1TB):   {monthly_requests_at_1tb/1_000_000:.1f}M requests")

        if monthly_rps_limit < realistic_rps:
            print(f"  ⚠️  BOTTLENECK: Transfer (CPU can handle {realistic_rps:.1f} RPS)")
        else:
            print(f"  ⚠️  BOTTLENECK: CPU (transfer allows {monthly_rps_limit:.1f} RPS)")
        print()


@pytest.mark.asyncio
async def test_recommended_production_level():
    """Determine optimal compression level for production"""

    print(f"\n{'='*80}")
    print(f"PRODUCTION COMPRESSION LEVEL RECOMMENDATION")
    print(f"{'='*80}\n")

    data = create_realistic_response('medium')

    print("Criteria:")
    print("  1. Maximize bandwidth savings")
    print("  2. Minimize CPU overhead")
    print("  3. Balance throughput vs. transfer")
    print(f"\n{'='*80}\n")

    recommendations = []

    for level in [1, 4, 6, 9]:
        result = benchmark_compression(data, level, iterations=500)

        # Calculate efficiency score
        # Higher compression ratio is good, lower CPU time is good
        efficiency = result['compression_ratio'] / result['avg_time_ms']

        recommendations.append({
            'level': level,
            'ratio': result['compression_ratio'],
            'time': result['avg_time_ms'],
            'efficiency': efficiency
        })

        print(f"Level {level}:")
        print(f"  Compression ratio: {result['compression_ratio']:.1f}%")
        print(f"  CPU time:          {result['avg_time_ms']:.3f} ms")
        print(f"  Efficiency score:  {efficiency:.1f}")
        print()

    # Find best efficiency
    best = max(recommendations, key=lambda x: x['efficiency'])
    print(f"{'='*80}")
    print(f"RECOMMENDATION: Level {best['level']}")
    print(f"  Best efficiency score: {best['efficiency']:.1f}")
    print(f"  Compression: {best['ratio']:.1f}%")
    print(f"  CPU cost: {best['time']:.3f} ms")


pytestmark = [pytest.mark.benchmark, pytest.mark.cpu]
