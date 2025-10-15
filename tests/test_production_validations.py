"""
Test production security validations
Tests the validation logic without running the full application
"""
import os

def test_jwt_secret_validation():
    """Test JWT secret validation logic"""
    test_cases = [
        ('please-change-me', False, 'default value'),
        ('test-secret-key', False, 'default value'),
        ('test-secret-key-please-change', False, 'default value'),
        ('', False, 'empty string'),
        ('my-super-secret-key-123456789', True, 'valid custom key'),
        ('a' * 32, True, 'valid 32-char key'),
    ]

    print("Testing JWT Secret Validation:")
    for secret, should_pass, description in test_cases:
        is_valid = secret not in ('please-change-me', 'test-secret-key', 'test-secret-key-please-change', '')
        status = '✓' if is_valid == should_pass else '✗'
        print(f"  {status} '{secret[:20]}...' ({description}): {'VALID' if is_valid else 'INVALID'}")
    print()

def test_cors_strict_validation():
    """Test CORS strict mode validation"""
    test_cases = [
        ('true', True, 'strict enabled'),
        ('True', True, 'strict enabled (caps)'),
        ('false', False, 'strict disabled'),
        ('False', False, 'strict disabled (caps)'),
        ('', False, 'empty (defaults to false)'),
    ]

    print("Testing CORS Strict Validation:")
    for value, should_pass, description in test_cases:
        is_valid = value.lower() == 'true' if value else False
        status = '✓' if is_valid == should_pass else '✗'
        print(f"  {status} CORS_STRICT={value} ({description}): {'VALID' if is_valid else 'INVALID'}")
    print()

def test_allowed_origins_validation():
    """Test allowed origins validation"""
    test_cases = [
        ('https://app.example.com', True, 'specific domain'),
        ('https://app.example.com,https://admin.example.com', True, 'multiple domains'),
        ('*', False, 'wildcard'),
        ('https://app.example.com,*', False, 'wildcard in list'),
        ('http://localhost:3000', True, 'localhost (dev only)'),
    ]

    print("Testing Allowed Origins Validation:")
    for origins, should_pass, description in test_cases:
        is_valid = '*' not in origins
        status = '✓' if is_valid == should_pass else '✗'
        print(f"  {status} ALLOWED_ORIGINS={origins} ({description}): {'VALID' if is_valid else 'INVALID'}")
    print()

def test_encryption_key_validation():
    """Test encryption key validation"""
    test_cases = [
        ('', 0, False, 'empty key'),
        ('short', 5, False, 'too short'),
        ('a' * 31, 31, False, 'just under 32 chars'),
        ('a' * 32, 32, True, 'exactly 32 chars'),
        ('a' * 64, 64, True, '64 chars'),
    ]

    print("Testing Encryption Key Validation (MEM_ENCRYPTION_KEY):")
    for key, length, should_pass, description in test_cases:
        is_valid = bool(key) and len(key) >= 32
        status = '✓' if is_valid == should_pass else '✗'
        print(f"  {status} Key length={length} ({description}): {'VALID' if is_valid else 'INVALID'}")
    print()

def test_https_validation():
    """Test HTTPS enforcement validation"""
    test_cases = [
        ('true', 'true', True, 'both enabled'),
        ('true', 'false', True, 'HTTPS_ONLY enabled'),
        ('false', 'true', True, 'HTTPS_ENABLED enabled'),
        ('false', 'false', False, 'both disabled'),
        ('', '', False, 'both unset'),
    ]

    print("Testing HTTPS Enforcement Validation:")
    for https_only, https_enabled, should_pass, description in test_cases:
        only = https_only.lower() == 'true' if https_only else False
        enabled = https_enabled.lower() == 'true' if https_enabled else False
        is_valid = only or enabled
        status = '✓' if is_valid == should_pass else '✗'
        print(f"  {status} HTTPS_ONLY={https_only}, HTTPS_ENABLED={https_enabled} ({description}): {'VALID' if is_valid else 'INVALID'}")
    print()

def test_redis_validation():
    """Test Redis configuration validation"""
    test_cases = [
        ('MEM', '', True, 'MEM mode (no Redis required)'),
        ('REDIS', 'redis.example.com', True, 'REDIS mode with host'),
        ('EXTERNAL', 'redis.example.com', True, 'EXTERNAL mode with host'),
        ('REDIS', '', False, 'REDIS mode without host'),
        ('EXTERNAL', '', False, 'EXTERNAL mode without host'),
    ]

    print("Testing Redis Configuration Validation:")
    for mode, redis_host, should_pass, description in test_cases:
        if mode == 'MEM':
            is_valid = True
        else:
            is_valid = bool(redis_host)
        status = '✓' if is_valid == should_pass else '✗'
        print(f"  {status} MEM_OR_EXTERNAL={mode}, REDIS_HOST={redis_host} ({description}): {'VALID' if is_valid else 'INVALID'}")
    print()

def main():
    print("=" * 70)
    print("Production Security Validation Tests")
    print("=" * 70)
    print()

    test_jwt_secret_validation()
    test_cors_strict_validation()
    test_allowed_origins_validation()
    test_encryption_key_validation()
    test_https_validation()
    test_redis_validation()

    print("=" * 70)
    print("All validation logic tests completed!")
    print("=" * 70)
    print()
    print("Note: These tests verify the validation logic only.")
    print("To test actual startup validation, set ENV=production and run:")
    print("  python backend-services/doorman.py run")
    print()

if __name__ == '__main__':
    main()
