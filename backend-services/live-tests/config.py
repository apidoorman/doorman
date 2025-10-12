import os

BASE_URL = os.getenv('DOORMAN_BASE_URL', 'http://localhost:5001').rstrip('/')
ADMIN_EMAIL = os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev')
# For live tests, read from env or check parent .env file; default for dev
ADMIN_PASSWORD = os.getenv('DOORMAN_ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    # Try to read from parent .env file
    env_file = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if line.startswith('DOORMAN_ADMIN_PASSWORD='):
                    ADMIN_PASSWORD = line.split('=', 1)[1].strip()
                    break
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
    # Password defaults to a dev value; warn but do not fail hard
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
