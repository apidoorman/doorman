from __future__ import annotations

from fastapi import Request, HTTPException
from typing import Optional, List

from utils.security_settings_util import get_cached_settings

def _get_client_ip(request: Request, trust_xff: bool) -> Optional[str]:
    if trust_xff:
        xff = request.headers.get('x-forwarded-for') or request.headers.get('X-Forwarded-For')
        if xff:
            return xff.split(',')[0].strip()
    return request.client.host if request.client else None

def _ip_in_list(ip: str, patterns: List[str]) -> bool:
    try:
        import ipaddress
        ip_obj = ipaddress.ip_address(ip)
        for pat in (patterns or []):
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
        trust_xff = bool(api.get('api_trust_x_forwarded_for')) if api.get('api_trust_x_forwarded_for') is not None else bool(settings.get('trust_x_forwarded_for'))
        client_ip = _get_client_ip(request, trust_xff)
        if not client_ip:
            return
        mode = (api.get('api_ip_mode') or 'allow_all').strip().lower()
        wl = api.get('api_ip_whitelist') or []
        bl = api.get('api_ip_blacklist') or []
        # Blacklist always applies
        if bl and _ip_in_list(client_ip, bl):
            raise HTTPException(status_code=403, detail='API011')
        if mode == 'whitelist':
            if not wl or not _ip_in_list(client_ip, wl):
                raise HTTPException(status_code=403, detail='API010')
    except HTTPException:
        raise
    except Exception:
        # Fail open on errors
        return

