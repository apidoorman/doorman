import os

# Resolve configuration from environment variables or the repo root env files.
# Search order:
# 1) Environment variables (DOORMAN_BASE_URL, DOORMAN_ADMIN_EMAIL, etc.)
# 2) Repo root .env
# 3) Repo root .env.demo (fallback for demo setups)
# 4) Hardcoded defaults

ADMIN_EMAIL = os.getenv('DOORMAN_ADMIN_EMAIL')
ADMIN_PASSWORD = os.getenv('DOORMAN_ADMIN_PASSWORD')
_env_port = None
_env_in_docker = None

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _env_val(raw_line: str) -> str:
    """Extract the value from a KEY=VALUE line, stripping inline comments."""
    val = raw_line.split('=', 1)[1]
    # Strip inline comments (unquoted # ... )
    if '#' in val:
        val = val[:val.index('#')]
    return val.strip()


def _load_env_file(path: str) -> None:
    """Parse a single .env file, filling any values not yet resolved."""
    global ADMIN_EMAIL, ADMIN_PASSWORD, _env_port, _env_in_docker
    try:
        if not os.path.exists(path):
            return
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('DOORMAN_ADMIN_EMAIL=') and not ADMIN_EMAIL:
                    ADMIN_EMAIL = _env_val(line)
                if line.startswith('DOORMAN_ADMIN_PASSWORD=') and not ADMIN_PASSWORD:
                    ADMIN_PASSWORD = _env_val(line)
                if line.startswith('PORT=') and _env_port is None:
                    _env_port = _env_val(line)
                if line.startswith('DOORMAN_IN_DOCKER=') and _env_in_docker is None:
                    _env_in_docker = _env_val(line)
    except Exception:
        pass


# Try .env first, then .env.demo as fallback
_load_env_file(os.path.join(_repo_root, '.env'))
_load_env_file(os.path.join(_repo_root, '.env.demo'))

if not ADMIN_PASSWORD:
    ADMIN_PASSWORD = 'test-only-password-12chars'
if not ADMIN_EMAIL:
    ADMIN_EMAIL = 'admin@doorman.dev'

# Build BASE_URL: honour DOORMAN_BASE_URL env var, otherwise derive from .env PORT.
# Always use http:// — HTTPS_ONLY is a server-side cookie/CSRF setting;
# the server itself listens on plain HTTP (TLS is terminated at a reverse proxy).
_default_port = _env_port or '3001'
BASE_URL = os.getenv('DOORMAN_BASE_URL', f'http://localhost:{_default_port}').rstrip('/')

# Export DOORMAN_IN_DOCKER so servers.py auto-detects the Docker bridge IP
# for mock servers. Env var takes precedence, then .env/.env.demo value.
if not os.getenv('DOORMAN_IN_DOCKER') and _env_in_docker:
    os.environ['DOORMAN_IN_DOCKER'] = _env_in_docker

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
