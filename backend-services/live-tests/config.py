import os


def _parse_env_value(raw: str) -> str:
    """Parse a .env value.

    Supports:
    - Quoted values: KEY="value with spaces # not a comment"
    - Unquoted values with inline comments: KEY=value   # comment
    """
    v = raw.strip()
    if not v:
        return ''
    if v[0] in {'"', "'"}:
        quote = v[0]
        out: list[str] = []
        escaped = False
        for ch in v[1:]:
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == '\\':
                escaped = True
                continue
            if ch == quote:
                break
            out.append(ch)
        return ''.join(out).strip()

    # Strip inline comments starting at the first `#` that is preceded by whitespace.
    for i, ch in enumerate(v):
        if ch != '#':
            continue
        if i == 0 or v[i - 1].isspace():
            return v[:i].rstrip()
    return v


def _load_env_file_values() -> dict[str, str]:
    values: dict[str, str] = {}
    live_tests_dir = os.path.dirname(__file__)
    env_paths = [
        os.path.abspath(os.path.join(live_tests_dir, '..', '.env')),
        os.path.abspath(os.path.join(live_tests_dir, '..', '..', '.env')),
    ]
    for env_path in env_paths:
        if not os.path.exists(env_path):
            continue
        try:
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    # Allow "export KEY=VALUE" lines.
                    if line.startswith('export '):
                        line = line[len('export ') :].lstrip()
                    key, value = line.split('=', 1)
                    key = key.strip()
                    if key and key not in values:
                        values[key] = _parse_env_value(value)
        except Exception:
            continue
    return values


_ENV_FILE_VALUES = _load_env_file_values()


def _truthy(value: str | None) -> bool:
    return str(value).strip().lower() in {'true', '1', 'yes', 'y'}


def _resolve_base_url() -> str:
    env_base = os.getenv('DOORMAN_BASE_URL') or _ENV_FILE_VALUES.get('DOORMAN_BASE_URL')
    if env_base:
        return env_base.rstrip('/')
    port = os.getenv('PORT') or _ENV_FILE_VALUES.get('PORT') or '3001'
    host = os.getenv('DOORMAN_HOST') or _ENV_FILE_VALUES.get('DOORMAN_HOST') or '127.0.0.1'
    # Only honor HTTPS_ONLY if it's explicitly set in the environment.
    https_only = os.getenv('HTTPS_ONLY')
    scheme = 'https' if _truthy(https_only) else 'http'
    return f'{scheme}://{host}:{port}'


BASE_URL = _resolve_base_url().rstrip('/')
ADMIN_EMAIL = os.getenv('DOORMAN_ADMIN_EMAIL') or _ENV_FILE_VALUES.get('DOORMAN_ADMIN_EMAIL')

# Resolve admin email/password from environment or .env files.
# Search order:
# 1) Environment variable DOORMAN_ADMIN_EMAIL / DOORMAN_ADMIN_PASSWORD
# 2) backend-services/.env
# 3) repo root .env
# 4) Defaults
ADMIN_PASSWORD = os.getenv('DOORMAN_ADMIN_PASSWORD') or _ENV_FILE_VALUES.get('DOORMAN_ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    ADMIN_PASSWORD = 'test-only-password-12chars'
if not ADMIN_EMAIL:
    ADMIN_EMAIL = 'admin@doorman.dev'

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
