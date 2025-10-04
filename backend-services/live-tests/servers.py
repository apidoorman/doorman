from __future__ import annotations
import threading
import socket
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

def _find_free_port() -> int:
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

class _ThreadedHTTPServer:
    def __init__(self, handler_cls, host='127.0.0.1', port=None):
        self.host = host
        self.port = port or _find_free_port()
        self._server = HTTPServer((self.host, self.port), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self):
        self._thread.start()
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
                'query': self.path.split('?', 1)[1] if '?' in self.path else ''
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
                'json': parsed
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
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
                "<soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "  <soap:Body><EchoResponse><message>ok</message></EchoResponse></soap:Body>"
                "</soap:Envelope>"
            )
            self._xml(200, resp)

    return _ThreadedHTTPServer(Handler).start()

# Optional servers (GraphQL, gRPC) are set up inside tests conditionally to avoid hard deps here.
