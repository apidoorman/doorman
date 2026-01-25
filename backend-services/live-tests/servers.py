from __future__ import annotations

import json
import os
import platform
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def _find_free_port() -> int:
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _get_host_from_container():
    """Hostname to use from container to reach host-run test servers.

    Precedence:
    - DOORMAN_TEST_HOSTNAME (explicit override)
    - If running tests for a Dockerized gateway (DOORMAN_IN_DOCKER=1):
      - macOS/Windows: host.docker.internal (Docker Desktop)
      - Linux: 172.17.0.1 (default docker0 bridge)
    - Otherwise: 127.0.0.1 (tests and gateway share the host)
    """
    override = (os.getenv('DOORMAN_TEST_HOSTNAME') or '').strip()
    if override:
        return override
    docker_env = os.getenv('DOORMAN_IN_DOCKER', '').lower()
    if docker_env in ('1', 'true', 'yes'):
        system = platform.system()
        if system in ('Darwin', 'Windows'):
            return 'host.docker.internal'
        return '172.17.0.1'
    return '127.0.0.1'


class _ThreadedHTTPServer:
    def __init__(self, handler_cls, host='0.0.0.0', port=None):
        # Bind to all interfaces so Dockerized gateway can reach the server
        self.bind_host = host
        self.port = port or _find_free_port()
        self._server = HTTPServer((self.bind_host, self.port), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        # Advertise a host reachable by containers or local host
        self.host = _get_host_from_container()

    def start(self):
        self._thread.start()
        # Wait for readiness: ensure the socket accepts connections
        try:
            for _ in range(100):
                ok = False
                for target in (('127.0.0.1', self.port), (self.host, self.port)):
                    s = socket.socket()
                    try:
                        s.settimeout(0.05)
                        s.connect(target)
                        ok = True
                        break
                    except Exception:
                        pass
                    finally:
                        try:
                            s.close()
                        except Exception:
                            pass
                if ok:
                    break
                import time as _t
                _t.sleep(0.01)
        except Exception:
            pass
        return self

    def stop(self):
        try:
            self._server.shutdown()
        finally:
            self._server.server_close()

    @property
    def url(self):
        return f'http://{self.host}:{self.port}'


def start_rest_echo_server():
    class Handler(BaseHTTPRequestHandler):
        def _json(self, status=200, payload=None):
            body = json.dumps(payload or {}).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            payload = {
                'method': 'GET',
                'path': self.path,
                'headers': {k: v for k, v in self.headers.items()},
                'query': self.path.split('?', 1)[1] if '?' in self.path else '',
            }
            self._json(200, payload)

        def do_POST(self):
            content_length = int(self.headers.get('Content-Length', '0') or '0')
            body = self.rfile.read(content_length) if content_length else b''
            try:
                parsed = json.loads(body.decode('utf-8') or '{}')
            except Exception:
                parsed = {'raw': body.decode('utf-8', errors='ignore')}
            payload = {
                'method': 'POST',
                'path': self.path,
                'headers': {k: v for k, v in self.headers.items()},
                'json': parsed,
            }
            self._json(200, payload)

        def do_PUT(self):
            content_length = int(self.headers.get('Content-Length', '0') or '0')
            body = self.rfile.read(content_length) if content_length else b''
            try:
                parsed = json.loads(body.decode('utf-8') or '{}')
            except Exception:
                parsed = {'raw': body.decode('utf-8', errors='ignore')}
            payload = {
                'method': 'PUT',
                'path': self.path,
                'headers': {k: v for k, v in self.headers.items()},
                'json': parsed,
            }
            self._json(200, payload)

        def do_DELETE(self):
            payload = {
                'method': 'DELETE',
                'path': self.path,
                'headers': {k: v for k, v in self.headers.items()},
            }
            self._json(200, payload)

    return _ThreadedHTTPServer(Handler).start()


def start_soap_echo_server():
    class Handler(BaseHTTPRequestHandler):
        def _xml(self, status=200, content=''):
            body = content.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/xml; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            content_length = int(self.headers.get('Content-Length', '0') or '0')
            _ = self.rfile.read(content_length) if content_length else b''
            resp = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
                '  <soap:Body><EchoResponse><message>ok</message></EchoResponse></soap:Body>'
                '</soap:Envelope>'
            )
            self._xml(200, resp)

    return _ThreadedHTTPServer(Handler).start()


def start_rest_headers_server(response_headers: dict[str, str]):
    """Start a REST server that returns fixed response headers on GET /p."""

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status=200, payload=None):
            body = json.dumps(payload or {}).encode('utf-8')
            self.send_response(status)
            # Set provided response headers
            for k, v in (response_headers or {}).items():
                self.send_header(k, v)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            payload = {'ok': True, 'path': self.path}
            self._json(200, payload)

    return _ThreadedHTTPServer(Handler).start()


def start_rest_sequence_server(status_codes: list[int]):
    """Start a simple REST server that serves GET /r with scripted statuses.

    Each GET /r consumes the next status code from the list; when exhausted,
    subsequent calls return 200 with a basic JSON body.
    """
    seq = list(status_codes)

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status=200, payload=None):
            body = json.dumps(payload or {}).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith('/r'):
                status = seq.pop(0) if seq else 200
                self._json(status, {'ok': status == 200, 'path': self.path})
            else:
                self._json(200, {'ok': True, 'path': self.path})

    return _ThreadedHTTPServer(Handler).start()


def start_soap_sequence_server(status_codes: list[int]):
    """Start a SOAP-like server that responds on POST /s with scripted statuses."""
    seq = list(status_codes)

    class Handler(BaseHTTPRequestHandler):
        def _xml(self, status=200, content=''):
            body = content.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/xml; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            _ = int(self.headers.get('Content-Length', '0') or '0')
            status = seq.pop(0) if seq else 200
            resp = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
                '  <soap:Body><EchoResponse><message>ok</message></EchoResponse></soap:Body>'
                '</soap:Envelope>'
            )
            self._xml(status, resp)

    return _ThreadedHTTPServer(Handler).start()


def start_graphql_json_server(payload: dict):
    """Start a minimal JSON server for GraphQL POSTs that returns the given payload."""

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status=200, data=None):
            body = json.dumps(data or {}).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self._json(200, payload)

    return _ThreadedHTTPServer(Handler).start()
