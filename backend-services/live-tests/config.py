import os

BASE_URL = os.getenv('DOORMAN_BASE_URL', 'http://localhost:3001').rstrip('/')
ADMIN_EMAIL = os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev')

# Resolve admin password from environment or the repo root .env.
# Search order:
# 1) Environment variable DOORMAN_ADMIN_PASSWORD
# 2) Repo root .env (two levels up from live-tests)
# 3) Default test password
ADMIN_PASSWORD = os.getenv('DOORMAN_ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
    try:
        if os.path.exists(env_path):
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    if line.startswith('DOORMAN_ADMIN_PASSWORD='):
                        ADMIN_PASSWORD = line.split('=', 1)[1].strip()
                        break
    except Exception:
        pass
    if not ADMIN_PASSWORD:
        ADMIN_PASSWORD = 'test-only-password-12chars'

ENABLE_GRAPHQL = True
ENABLE_GRPC = True
STRICT_HEALTH = True


def require_env():
    missing = []
    if not BASE_URL:
        missing.append('DOORMAN_BASE_URL')
    if not ADMIN_EMAIL:
        missing.append('DOORMAN_ADMIN_EMAIL')
    if missing:
        raise RuntimeError(f'Missing required env vars: {", ".join(missing)}')
