from __future__ import annotations

from urllib.parse import urljoin

import requests


class LiveClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/') + '/'
        self.sess = requests.Session()
        # Track resources created during tests for cleanup
        self._created_apis: set[tuple[str, str]] = set()
        self._created_endpoints: set[tuple[str, str, str, str]] = set()
        self._created_protos: set[tuple[str, str]] = set()
        self._created_subscriptions: set[tuple[str, str, str]] = set()
        self._created_rules: set[str] = set()
        self._created_groups: set[str] = set()
        self._created_roles: set[str] = set()
        self._created_users: set[str] = set()

    def _get_csrf(self) -> str | None:
        for c in self.sess.cookies:
            if c.name == 'csrf_token':
                return c.value
        return None

    def _headers_with_csrf(self, headers: dict | None) -> dict:
        out = {'Accept': 'application/json'}
        if headers:
            out.update(headers)
        csrf = self._get_csrf()
        if csrf and 'X-CSRF-Token' not in out:
            out['X-CSRF-Token'] = csrf
        return out

    def get(self, path: str, **kwargs):
        url = urljoin(self.base_url, path.lstrip('/'))
        headers = self._headers_with_csrf(kwargs.pop('headers', None))
        return self.sess.get(url, headers=headers, allow_redirects=False, **kwargs)

    def post(self, path: str, json=None, data=None, files=None, headers=None, **kwargs):
        url = urljoin(self.base_url, path.lstrip('/'))
        hdrs = self._headers_with_csrf(headers)
        # Map 'content' to 'data' for requests compat (used by SOAP tests)
        if 'content' in kwargs and data is None:
            data = kwargs.pop('content')
        resp = self.sess.post(
            url, json=json, data=data, files=files, headers=hdrs, allow_redirects=False, **kwargs
        )
        # Best-effort resource tracking
        try:
            p = path.split('?')[0]
            if p.startswith('/platform/api') and isinstance(json, dict) and 'api_name' in (json or {}):
                name = json.get('api_name')
                ver = json.get('api_version')
                if name and ver:
                    self._created_apis.add((name, ver))
            elif p.startswith('/platform/endpoint') and isinstance(json, dict):
                name = json.get('api_name')
                ver = json.get('api_version')
                method = json.get('endpoint_method')
                uri = json.get('endpoint_uri')
                if name and ver and method and uri:
                    self._created_endpoints.add((method, name, ver, uri))
            elif p.startswith('/platform/proto/') and files is not None:
                parts = [seg for seg in p.split('/') if seg]
                # /platform/proto/{name}/{ver}
                if len(parts) >= 4:
                    self._created_protos.add((parts[2], parts[3]))
            elif p.endswith('/platform/subscription/subscribe') and isinstance(json, dict):
                name = json.get('api_name')
                ver = json.get('api_version')
                user = json.get('username') or 'admin'
                if name and ver and user:
                    self._created_subscriptions.add((name, ver, user))
            elif p.startswith('/platform/rate-limits') and isinstance(json, dict) and json.get('rule_id'):
                self._created_rules.add(json['rule_id'])
            elif p.startswith('/platform/group') and isinstance(json, dict) and json.get('group_name'):
                self._created_groups.add(json['group_name'])
            elif p.startswith('/platform/role') and isinstance(json, dict) and json.get('role_name'):
                self._created_roles.add(json['role_name'])
            elif p.startswith('/platform/user') and isinstance(json, dict) and json.get('username'):
                # Skip admin user just in case
                if json['username'] != 'admin':
                    self._created_users.add(json['username'])
        except Exception:
            pass
        return resp

    def put(self, path: str, json=None, headers=None, **kwargs):
        url = urljoin(self.base_url, path.lstrip('/'))
        hdrs = self._headers_with_csrf(headers)
        return self.sess.put(url, json=json, headers=hdrs, allow_redirects=False, **kwargs)

    def delete(self, path: str, json=None, headers=None, **kwargs):
        url = urljoin(self.base_url, path.lstrip('/'))
        hdrs = self._headers_with_csrf(headers)
        return self.sess.delete(url, json=json, headers=hdrs, allow_redirects=False, **kwargs)

    def options(self, path: str, headers=None, **kwargs):
        url = urljoin(self.base_url, path.lstrip('/'))
        hdrs = self._headers_with_csrf(headers)
        return self.sess.options(url, headers=hdrs, allow_redirects=False, **kwargs)

    def login(self, email: str, password: str):
        r = self.post('/platform/authorization', json={'email': email, 'password': password})
        r.raise_for_status()
        return r.json()

    def logout(self):
        r = self.post('/platform/authorization/invalidate', json={})
        return r

    # ------------------------
    # Cleanup support
    # ------------------------

    def cleanup(self):
        """Best-effort cleanup of resources created during tests.

        Performs deletions in dependency-safe order and ignores failures.
        """
        # Unsubscribe first to release ties
        for name, ver, user in list(self._created_subscriptions):
            try:
                self.post(
                    '/platform/subscription/unsubscribe',
                    json={'api_name': name, 'api_version': ver, 'username': user},
                )
            except Exception:
                pass
        # Delete endpoints
        for method, name, ver, uri in list(self._created_endpoints):
            try:
                # Normalize uri startswith '/'
                u = uri if uri.startswith('/') else '/' + uri
                self.delete(f'/platform/endpoint/{method.upper()}/{name}/{ver}{u}')
            except Exception:
                pass
        # Delete protos
        for name, ver in list(self._created_protos):
            try:
                self.delete(f'/platform/proto/{name}/{ver}')
            except Exception:
                pass
        # Delete APIs
        for name, ver in list(self._created_apis):
            try:
                self.delete(f'/platform/api/{name}/{ver}')
            except Exception:
                pass
        # Delete rate limit rules
        for rid in list(self._created_rules):
            try:
                self.delete(f'/platform/rate-limits/{rid}')
            except Exception:
                pass
        # Delete groups
        for g in list(self._created_groups):
            try:
                self.delete(f'/platform/group/{g}')
            except Exception:
                pass
        # Delete roles
        for r in list(self._created_roles):
            try:
                self.delete(f'/platform/role/{r}')
            except Exception:
                pass
        # Delete users (except admin)
        for u in list(self._created_users):
            try:
                if u != 'admin':
                    self.delete(f'/platform/user/{u}')
            except Exception:
                pass
