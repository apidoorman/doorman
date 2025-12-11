from __future__ import annotations

from urllib.parse import urljoin

import requests


class LiveClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/') + '/'
        self.sess = requests.Session()

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
        return self.sess.post(
            url, json=json, data=data, files=files, headers=hdrs, allow_redirects=False, **kwargs
        )

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
