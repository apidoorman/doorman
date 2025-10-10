"""
Integration test for Redis-backed token revocation in HA deployments.

Simulates multi-node scenario:
- User logs in and gets token
- User logs out on "Node A" (revokes JTI in Redis)
- Token validation on "Node B" (different process) should fail
"""

import pytest
import os


@pytest.mark.asyncio
async def test_redis_token_revocation_shared_across_processes(monkeypatch, authed_client):
    """Test that token revocation via Redis is visible across simulated nodes.

    Scenario:
    1. Login and get access token
    2. Use add_revoked_jti to revoke the JTI (simulating logout on Node A)
    3. Verify is_jti_revoked returns True (simulating auth check on Node B)
    """
    # Force Redis mode for this test
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'REDIS')

    # Re-initialize Redis connection (simulates separate process)
    from utils import auth_blacklist
    auth_blacklist._redis_client = None
    auth_blacklist._redis_enabled = False
    auth_blacklist._init_redis_if_possible()

    # If Redis is not available, skip test
    if not auth_blacklist._redis_enabled or auth_blacklist._redis_client is None:
        pytest.skip('Redis not available for HA revocation test')

    # Get access token by logging in
    login_response = await authed_client.post(
        '/platform/authorization',
        json={'email': os.environ.get('DOORMAN_ADMIN_EMAIL'), 'password': os.environ.get('DOORMAN_ADMIN_PASSWORD')}
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    access_token = token_data.get('access_token')
    assert access_token is not None

    # Decode token to get JTI
    from jose import jwt
    payload = jwt.decode(
        access_token,
        os.environ.get('JWT_SECRET_KEY'),
        algorithms=['HS256']
    )
    jti = payload.get('jti')
    username = payload.get('sub')
    exp = payload.get('exp')

    assert jti is not None
    assert username is not None

    # Simulate logout on Node A: revoke the JTI in Redis
    import time
    ttl = max(1, int(exp - time.time())) if exp else 3600
    auth_blacklist.add_revoked_jti(username, jti, ttl)

    # Simulate auth check on Node B: verify JTI is revoked
    # Create a NEW instance to simulate different process
    auth_blacklist._redis_client = None
    auth_blacklist._redis_enabled = False
    auth_blacklist._init_redis_if_possible()

    is_revoked = auth_blacklist.is_jti_revoked(username, jti)
    assert is_revoked is True, 'Token should be revoked in Redis (visible across nodes)'

    # Cleanup: remove the revocation
    if auth_blacklist._redis_client:
        auth_blacklist._redis_client.delete(auth_blacklist._revoked_jti_key(username, jti))


@pytest.mark.asyncio
async def test_redis_revoke_all_for_user_shared_across_processes(monkeypatch):
    """Test that user-level revocation via Redis is visible across nodes."""
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'REDIS')

    from utils import auth_blacklist
    auth_blacklist._redis_client = None
    auth_blacklist._redis_enabled = False
    auth_blacklist._init_redis_if_possible()

    if not auth_blacklist._redis_enabled:
        pytest.skip('Redis not available for HA revocation test')

    test_username = 'test_user_revoke_all'

    # Node A: Revoke all tokens for user
    auth_blacklist.revoke_all_for_user(test_username)

    # Node B: Check revocation (simulate different process)
    auth_blacklist._redis_client = None
    auth_blacklist._redis_enabled = False
    auth_blacklist._init_redis_if_possible()

    is_revoked = auth_blacklist.is_user_revoked(test_username)
    assert is_revoked is True, 'User revocation should be visible across nodes'

    # Cleanup
    auth_blacklist.unrevoke_all_for_user(test_username)
    is_revoked_after_cleanup = auth_blacklist.is_user_revoked(test_username)
    assert is_revoked_after_cleanup is False


@pytest.mark.asyncio
async def test_redis_token_revocation_ttl_expiry(monkeypatch):
    """Test that revoked tokens auto-expire in Redis based on TTL."""
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'REDIS')

    from utils import auth_blacklist
    import time

    auth_blacklist._redis_client = None
    auth_blacklist._redis_enabled = False
    auth_blacklist._init_redis_if_possible()

    if not auth_blacklist._redis_enabled:
        pytest.skip('Redis not available for TTL test')

    test_username = 'test_user_ttl'
    test_jti = 'test_jti_expires_soon'

    # Add revocation with 2 second TTL
    auth_blacklist.add_revoked_jti(test_username, test_jti, ttl_seconds=2)

    # Should be revoked immediately
    assert auth_blacklist.is_jti_revoked(test_username, test_jti) is True

    # Wait for TTL to expire
    time.sleep(3)

    # Should no longer be revoked (TTL expired)
    assert auth_blacklist.is_jti_revoked(test_username, test_jti) is False


@pytest.mark.asyncio
async def test_memory_fallback_when_redis_unavailable(monkeypatch):
    """Test that system falls back to in-memory revocation when Redis is unavailable."""
    # Force memory mode
    monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')

    from utils import auth_blacklist

    # Reset to force re-initialization
    auth_blacklist._redis_client = None
    auth_blacklist._redis_enabled = False
    auth_blacklist._init_redis_if_possible()

    # Verify Redis is disabled
    assert auth_blacklist._redis_enabled is False
    assert auth_blacklist._redis_client is None

    # Test in-memory revocation still works
    test_username = 'test_memory_user'
    test_jti = 'test_memory_jti'

    auth_blacklist.add_revoked_jti(test_username, test_jti, ttl_seconds=60)
    assert auth_blacklist.is_jti_revoked(test_username, test_jti) is True

    # Note: In memory mode, this revocation is NOT shared across processes
    # This is the known limitation for HA deployments
