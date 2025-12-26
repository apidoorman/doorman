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
        self._created_credit_defs: set[str] = set()
        self._created_user_credits: set[str] = set()
        self._created_routings: set[str] = set()
        self._created_tiers: set[str] = set()
        self._created_tier_assignments: set[str] = set()

    def _get_csrf(self) -> str | None:
        for c in self.sess.cookies:
            if c.name == 'csrf_token':
                return c.value
        return None

    def _headers_with_csrf(self, headers: dict | None) -> dict:
        out = {'Accept': 'application/json'}
        # Mark requests as test traffic so analytics can exclude them
        out['X-IS-TEST'] = 'true'
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
            elif p.startswith('/platform/credit') and isinstance(json, dict):
                if json.get('api_credit_group'):
                    self._created_credit_defs.add(json['api_credit_group'])
                parts = [seg for seg in p.split('/') if seg]
                if len(parts) >= 3 and parts[1] == 'credit':
                    username = parts[2]
                    if username and username != 'defs':
                        self._created_user_credits.add(username)
            elif p.startswith('/platform/routing') and isinstance(json, dict):
                client_key = json.get('client_key')
                if client_key:
                    self._created_routings.add(client_key)
                else:
                    try:
                        msg = (resp.json() or {}).get('message') or ''
                        if 'key:' in msg:
                            self._created_routings.add(msg.split('key:')[-1].strip())
                    except Exception:
                        pass
            elif p.startswith('/platform/tiers/assignments') and isinstance(json, dict):
                user_id = json.get('user_id')
                if user_id:
                    self._created_tier_assignments.add(user_id)
            elif p.startswith('/platform/tiers') and isinstance(json, dict):
                tier_id = json.get('tier_id')
                if tier_id:
                    self._created_tiers.add(tier_id)
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

    def _json(self, resp):
        try:
            return resp.json()
        except Exception:
            return None

    def _extract_list(self, payload, key: str):
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        if key in payload and isinstance(payload.get(key), list):
            return payload.get(key) or []
        resp = payload.get('response')
        if isinstance(resp, dict) and key in resp and isinstance(resp.get(key), list):
            return resp.get(key) or []
        if isinstance(resp, list):
            return resp
        return []

    def cleanup(self):
        """Best-effort cleanup of resources created during tests.

        Performs deletions in dependency-safe order and ignores failures.
        """
        # Ensure we have a valid session before attempting cleanup
        try:
            from config import ADMIN_EMAIL, ADMIN_PASSWORD

            self.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        except Exception:
            pass
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
        # Clear tier assignments
        for user_id in list(self._created_tier_assignments):
            try:
                self.delete(f'/platform/tiers/assignments/{user_id}')
            except Exception:
                pass
        # Delete tiers
        for tier_id in list(self._created_tiers):
            try:
                self.delete(f'/platform/tiers/{tier_id}')
            except Exception:
                pass
        # Delete routings
        for client_key in list(self._created_routings):
            try:
                self.delete(f'/platform/routing/{client_key}')
            except Exception:
                pass
        # Clear user credits
        for username in list(self._created_user_credits):
            try:
                self.post(f'/platform/credit/{username}', json={'username': username, 'users_credits': {}})
            except Exception:
                pass
        # Delete credit definitions
        for group in list(self._created_credit_defs):
            try:
                self.delete(f'/platform/credit/{group}')
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

        # Sweep cleanup for any remaining resources created by tests
        try:
            self._cleanup_all_resources()
        except Exception:
            pass

    def _cleanup_all_resources(self):
        # Users
        users_payload = self._json(self.get('/platform/user/all?page=1&page_size=1000'))
        users = self._extract_list(users_payload, 'users')
        usernames = []
        for u in users:
            if isinstance(u, dict) and u.get('username'):
                usernames.append(u['username'])
            elif isinstance(u, str):
                usernames.append(u)
        usernames = [u for u in usernames if u and u != 'admin']

        # Subscriptions
        for username in usernames + ['admin']:
            try:
                subs_payload = self._json(self.get(f'/platform/subscription/subscriptions/{username}'))
                apis = self._extract_list(subs_payload, 'apis')
                for api in apis:
                    if isinstance(api, str) and '/' in api:
                        name, ver = api.split('/', 1)
                    elif isinstance(api, dict):
                        name = api.get('api_name')
                        ver = api.get('api_version')
                    else:
                        continue
                    if name and ver:
                        self.post(
                            '/platform/subscription/unsubscribe',
                            json={'api_name': name, 'api_version': ver, 'username': username},
                        )
            except Exception:
                pass

        # APIs and endpoints
        apis_payload = self._json(self.get('/platform/api/all?page=1&page_size=1000'))
        apis = self._extract_list(apis_payload, 'apis')
        api_pairs = []
        for api in apis:
            if isinstance(api, dict):
                name = api.get('api_name')
                ver = api.get('api_version')
                if name and ver:
                    api_pairs.append((name, ver))
        for name, ver in api_pairs:
            try:
                endpoints_payload = self._json(self.get(f'/platform/endpoint/{name}/{ver}'))
                endpoints = self._extract_list(endpoints_payload, 'endpoints')
                for ep in endpoints:
                    if not isinstance(ep, dict):
                        continue
                    method = ep.get('endpoint_method') or ep.get('method')
                    uri = ep.get('endpoint_uri') or ep.get('uri')
                    if method and uri:
                        u = uri if uri.startswith('/') else '/' + uri
                        self.delete(f'/platform/endpoint/{method.upper()}/{name}/{ver}{u}')
            except Exception:
                pass
            try:
                self.delete(f'/platform/api/{name}/{ver}')
            except Exception:
                pass

        # Protos
        for name, ver in list(self._created_protos):
            try:
                self.delete(f'/platform/proto/{name}/{ver}')
            except Exception:
                pass

        # Rate limit rules
        for rid in list(self._created_rules):
            try:
                self.delete(f'/platform/rate-limits/{rid}')
            except Exception:
                pass

        # Tier assignments
        for username in usernames + ['admin']:
            try:
                self.delete(f'/platform/tiers/assignments/{username}')
            except Exception:
                pass

        # Tiers
        tiers_payload = self._json(self.get('/platform/tiers?skip=0&limit=1000'))
        tiers = self._extract_list(tiers_payload, 'tiers')
        for tier in tiers:
            if isinstance(tier, dict):
                tier_id = tier.get('tier_id')
            else:
                tier_id = None
            if tier_id:
                try:
                    self.delete(f'/platform/tiers/{tier_id}')
                except Exception:
                    pass

        # Routings
        routings_payload = self._json(self.get('/platform/routing/all?page=1&page_size=1000'))
        routings = self._extract_list(routings_payload, 'routings')
        for route in routings:
            if isinstance(route, dict):
                client_key = route.get('client_key')
            else:
                client_key = None
            if client_key:
                try:
                    self.delete(f'/platform/routing/{client_key}')
                except Exception:
                    pass

        # User credits
        credits_payload = self._json(self.get('/platform/credit/all?page=1&page_size=1000'))
        credits = self._extract_list(credits_payload, 'user_credits')
        for credit in credits:
            if isinstance(credit, dict):
                username = credit.get('username')
            else:
                username = None
            if username:
                try:
                    self.post(
                        f'/platform/credit/{username}',
                        json={'username': username, 'users_credits': {}},
                    )
                except Exception:
                    pass

        # Credit definitions
        defs_payload = self._json(self.get('/platform/credit/defs?page=1&page_size=1000'))
        defs = self._extract_list(defs_payload, 'items')
        for credit_def in defs:
            if isinstance(credit_def, dict):
                group = credit_def.get('api_credit_group')
            else:
                group = None
            if group:
                try:
                    self.delete(f'/platform/credit/{group}')
                except Exception:
                    pass

        # Delete users (except admin)
        for username in usernames:
            try:
                self.delete(f'/platform/user/{username}')
            except Exception:
                pass

        # Groups
        groups_payload = self._json(self.get('/platform/group/all?page=1&page_size=1000'))
        groups = self._extract_list(groups_payload, 'groups')
        for group in groups:
            if isinstance(group, dict):
                name = group.get('group_name')
            else:
                name = None
            if name and name not in ('ALL', 'admin'):
                try:
                    self.delete(f'/platform/group/{name}')
                except Exception:
                    pass

        # Roles
        roles_payload = self._json(self.get('/platform/role/all?page=1&page_size=1000'))
        roles = self._extract_list(roles_payload, 'roles')
        for role in roles:
            if isinstance(role, dict):
                name = role.get('role_name')
            else:
                name = None
            if name and name not in ('admin',):
                try:
                    self.delete(f'/platform/role/{name}')
                except Exception:
                    pass
