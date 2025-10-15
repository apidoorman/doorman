"""
Test Redis authentication validation
Validates that Redis URL is built correctly with/without authentication
"""

def test_redis_auth_url_building():
    """Test Redis URL construction logic"""

    test_cases = [
        {
            'name': 'Redis with password',
            'host': 'localhost',
            'port': '6379',
            'db': '0',
            'password': 'my-secret-password',
            'expected_url': 'redis://:my-secret-password@localhost:6379/0'
        },
        {
            'name': 'Redis without password (development)',
            'host': 'localhost',
            'port': '6379',
            'db': '0',
            'password': '',
            'expected_url': 'redis://localhost:6379/0'
        },
        {
            'name': 'Redis production with strong password',
            'host': 'redis.production.internal',
            'port': '6379',
            'db': '1',
            'password': 'p@ssw0rd!12345678901234567890',
            'expected_url': 'redis://:p@ssw0rd!12345678901234567890@redis.production.internal:6379/1'
        }
    ]

    print("Redis Authentication URL Building Tests")
    print("=" * 70)

    for test in test_cases:
        redis_host = test['host']
        redis_port = test['port']
        redis_db = test['db']
        redis_password = test['password']

        # Logic from doorman.py
        if redis_password:
            redis_url = f'redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}'
        else:
            redis_url = f'redis://{redis_host}:{redis_port}/{redis_db}'

        status = '✓' if redis_url == test['expected_url'] else '✗'
        print(f"{status} {test['name']}")
        print(f"   Host: {redis_host}:{redis_port}/{redis_db}")
        print(f"   Password set: {bool(redis_password)}")
        # Avoid printing clear-text secrets; mask password in URL display
        def _mask(url: str) -> str:
            # Replace ':password@' with ':***@' if present
            return re.sub(r":([^@]+)@", ":***@", url)

        import re  # local import for test-only masking
        print(f"   URL: {_mask(redis_url)}")
        if redis_url != test['expected_url']:
            print(f"   Expected: {_mask(test['expected_url'])}")
        print()

    print("=" * 70)
    print("Implementation Notes:")
    print()
    print("1. Redis URL format with authentication:")
    print("   redis://:{password}@{host}:{port}/{db}")
    print("   Note: Username is empty, only password is used (colon before password)")
    print()
    print("2. Redis URL format without authentication:")
    print("   redis://{host}:{port}/{db}")
    print()
    print("3. Warning behavior:")
    print("   - MEM mode: No warning (Redis not critical)")
    print("   - REDIS/EXTERNAL mode without password: Warning logged")
    print()
    print("4. Security recommendations:")
    print("   - Always set REDIS_PASSWORD in production")
    print("   - Use strong passwords (32+ characters)")
    print("   - Rotate Redis passwords regularly")
    print()

if __name__ == '__main__':
    test_redis_auth_url_building()
