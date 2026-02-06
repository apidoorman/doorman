import os

from fastapi import APIRouter, Response, Request

from utils.prometheus_metrics import CONTENT_TYPE_LATEST, PROMETHEUS_ENABLED, render_latest
from utils.ip_policy_util import (
    _get_client_ip as _policy_get_client_ip,
    _ip_in_list as _policy_ip_in_list,
    _is_loopback as _policy_is_loopback,
)


metrics_router = APIRouter()


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _parse_allowlist() -> list[str]:
    raw = os.getenv('PROMETHEUS_ALLOWLIST') or os.getenv('PROMETHEUS_IP_ALLOWLIST') or ''
    return [p.strip() for p in raw.split(',') if p.strip()]


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get('authorization') or request.headers.get('Authorization') or ''
    if auth.lower().startswith('bearer '):
        return auth.split(' ', 1)[1].strip()
    token = request.headers.get('x-prometheus-token') or request.headers.get('X-Prometheus-Token')
    return token.strip() if token else None


def _metrics_allowed(request: Request) -> bool:
    if _env_flag('PROMETHEUS_PUBLIC', False):
        return True
    token_required = os.getenv('PROMETHEUS_BEARER_TOKEN') or os.getenv('PROMETHEUS_TOKEN')
    if token_required:
        provided = _extract_token(request)
        if not provided or provided != token_required:
            return False
    allowlist = _parse_allowlist()
    trust_xff = _env_flag('PROMETHEUS_TRUST_XFF', False)
    client_ip = _policy_get_client_ip(request, trust_xff)
    if allowlist:
        return bool(client_ip) and _policy_ip_in_list(client_ip, allowlist)
    return _policy_is_loopback(client_ip)


@metrics_router.get('/metrics', include_in_schema=False)
async def metrics(request: Request):
    if not PROMETHEUS_ENABLED:
        return Response(content=b'prometheus_disabled 1\n', media_type=CONTENT_TYPE_LATEST, status_code=503)
    if not _metrics_allowed(request):
        return Response(content=b'prometheus_forbidden 1\n', media_type=CONTENT_TYPE_LATEST, status_code=403)
    data = render_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
