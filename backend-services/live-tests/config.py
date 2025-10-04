import os

BASE_URL = os.environ.get('DOORMAN_BASE_URL', 'http://localhost:5001').rstrip('/')
ADMIN_EMAIL = os.environ.get('DOORMAN_ADMIN_EMAIL', os.environ.get('STARTUP_ADMIN_EMAIL', 'admin@doorman.dev'))
ADMIN_PASSWORD = os.environ.get('DOORMAN_ADMIN_PASSWORD', os.environ.get('STARTUP_ADMIN_PASSWORD', 'password1'))

ENABLE_GRAPHQL = os.environ.get('DOORMAN_TEST_GRAPHQL', '1') in ('1', 'true', 'True')
ENABLE_GRPC = os.environ.get('DOORMAN_TEST_GRPC', '1') in ('1', 'true', 'True')
STRICT_HEALTH = os.environ.get('DOORMAN_TEST_STRICT_HEALTH', '1') in ('1', 'true', 'True')

def require_env():
    missing = []
    if not BASE_URL:
        missing.append('DOORMAN_BASE_URL')
    if not ADMIN_EMAIL:
        missing.append('DOORMAN_ADMIN_EMAIL')
    if not ADMIN_PASSWORD:
        missing.append('DOORMAN_ADMIN_PASSWORD')
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
