from __future__ import annotations

import os

from fastapi import HTTPException, Request

from utils.audit_util import audit
from utils.security_settings_util import get_cached_settings


def _get_client_ip(request: Request, trust_xff: bool) -> str | None:
    """Determine client IP with optional proxy trust.

    When `trust_xff` is True, this prefers headers supplied by trusted proxies.
    Trusted proxies are matched against `xff_trusted_proxies` (IPs/CIDRs) in
    security settings. If that list is empty, any proxy is implicitly trusted
    to preserve backwards-compatibility.
    """
    try:
        settings = get_cached_settings()
        trusted = settings.get('xff_trusted_proxies') or []
        src_ip = request.client.host if request.client else None
        if isinstance(src_ip, str) and src_ip in ('testserver', 'localhost'):
            src_ip = '127.0.0.1'

        def _from_trusted_proxy() -> bool:
            if not trusted:
                # Empty list means trust all proxies for backwards-compatibility
                return True
            return _ip_in_list(src_ip, trusted) if src_ip else False

        if trust_xff and _from_trusted_proxy():
            for header in (
                'x-forwarded-for',
                'X-Forwarded-For',
                'x-real-ip',
                'X-Real-IP',
                'cf-connecting-ip',
                'CF-Connecting-IP',
            ):
                val = request.headers.get(header)
                if val:
                    ip = val.split(',')[0].strip()
                    if ip:
                        return ip
        return src_ip
    except Exception:
        return request.client.host if request.client else None


def _ip_in_list(ip: str, patterns: list[str]) -> bool:
    try:
        import ipaddress

        ip_obj = ipaddress.ip_address(ip)
        for pat in patterns or []:
            p = (pat or '').strip()
            if not p:
                continue
            try:
                if '/' in p:
                    net = ipaddress.ip_network(p, strict=False)
                    if ip_obj in net:
                        return True
                else:
                    if ip_obj == ipaddress.ip_address(p):
                        return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def _is_loopback(ip: str | None) -> bool:
    try:
        if not ip:
            return False
        if ip in ('testserver', 'localhost'):
            return True
        import ipaddress

        return ipaddress.ip_address(ip).is_loopback
    except Exception:
        return False


def enforce_api_ip_policy(request: Request, api: dict):
    """
    Enforce per-API IP policy.
    - api_ip_mode: 'allow_all' (default) or 'whitelist'
    - api_ip_whitelist: applied when mode=='whitelist'
    - api_ip_blacklist: always applied (deny)
    - api_trust_x_forwarded_for: override; otherwise use platform trust_x_forwarded_for
    """
    try:
        settings = get_cached_settings()
        trust_xff = (
            bool(api.get('api_trust_x_forwarded_for'))
            if api.get('api_trust_x_forwarded_for') is not None
            else bool(settings.get('trust_x_forwarded_for'))
        )
        client_ip = _get_client_ip(request, trust_xff)
        if not client_ip:
            return
        try:
            settings = get_cached_settings()
            env_flag = os.getenv('LOCAL_HOST_IP_BYPASS')
            allow_local = (
                (env_flag.lower() == 'true')
                if isinstance(env_flag, str) and env_flag.strip() != ''
                else bool(settings.get('allow_localhost_bypass'))
            )
            direct_ip = getattr(getattr(request, 'client', None), 'host', None)
            has_forward = any(
                request.headers.get(h)
                for h in (
                    'x-forwarded-for',
                    'X-Forwarded-For',
                    'x-real-ip',
                    'X-Real-IP',
                    'cf-connecting-ip',
                    'CF-Connecting-IP',
                    'forwarded',
                    'Forwarded',
                )
            )
            if allow_local and direct_ip and _is_loopback(direct_ip) and not has_forward:
                return
        except Exception:
            pass
        mode = (api.get('api_ip_mode') or 'allow_all').strip().lower()
        wl = api.get('api_ip_whitelist') or []
        bl = api.get('api_ip_blacklist') or []
        if bl and _ip_in_list(client_ip, bl):
            try:
                audit(
                    request,
                    actor=None,
                    action='ip.api_deny',
                    target=str(api.get('api_id') or api.get('api_name') or 'unknown_api'),
                    status='blocked',
                    details={'reason': 'blacklisted', 'effective_ip': client_ip},
                )
            except Exception:
                pass
            raise HTTPException(status_code=403, detail='API011')
        if mode == 'whitelist':
            if not wl or not _ip_in_list(client_ip, wl):
                try:
                    audit(
                        request,
                        actor=None,
                        action='ip.api_deny',
                        target=str(api.get('api_id') or api.get('api_name') or 'unknown_api'),
                        status='blocked',
                        details={'reason': 'not_in_whitelist', 'effective_ip': client_ip},
                    )
                except Exception:
                    pass
                raise HTTPException(status_code=403, detail='API010')
    except HTTPException:
        raise
    except Exception:
        return
