import bcrypt

from utils.doorman_cache_util import doorman_cache


def test_cache_serializes_bytes_password_to_json_string():
    doc = {
        'username': 'u1',
        'password': bcrypt.hashpw(b'super-secret', bcrypt.gensalt()),  # bytes
        'role': 'user',
    }

    doorman_cache.set_cache('user_cache', 'u1', doc)
    out = doorman_cache.get_cache('user_cache', 'u1')

    assert isinstance(out, dict)
    assert isinstance(out.get('password'), str)
    assert out['password'].startswith('$2b$') or out['password'].startswith('$2a$')
